"""Offline checks for the runtime and both tool sets. Run from the repo root."""

import copy
import json
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx2 as httpx
from openai import APIStatusError, OpenAI

from apps import assistant, coding_agent
from cli import _print_event
from core import logger, retry
from core.agent import Agent, ModelResponseError, ToolError, tool


def response(text=None, calls=(), *, reason=None):
    message = SimpleNamespace(content=text, tool_calls=calls)
    finish_reason = reason if reason is not None else ("tool_calls" if calls else "stop")
    return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish_reason)])


def call(call_id, name, arguments):
    return SimpleNamespace(
        id=call_id,
        type="function",
        function=SimpleNamespace(name=name, arguments=arguments),
    )


class ScriptedModel:
    """Return prepared answers and save a snapshot of each request."""

    def __init__(self, *answers):
        self.answers = iter(answers)
        self.requests = []

    def complete(self, **request):
        self.requests.append(copy.deepcopy(request))
        answer = next(self.answers)
        if isinstance(answer, BaseException):
            raise answer
        return answer


class AgentTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(directory)
        self.enterContext(patch.object(logger, "LOG_DIR", self.root))

    def test_two_tools_and_followup_use_message_history(self):
        model = ScriptedModel(
            response(calls=[call("a", "calculate", '{"expression":"2+3"}'), call("b", "get_time", "{}")]),
            response("结果是 5。"),
            response("刚才的结果是 5。"),
        )
        agent = Agent(assistant.TOOLS, "助手", complete=model.complete, model="fake")
        self.assertEqual(agent.run("先算，再查时间"), "结果是 5。")

        messages = model.requests[1]["messages"]
        self.assertEqual([item["role"] for item in messages], ["system", "user", "assistant", "tool", "tool"])
        self.assertEqual([item["tool_call_id"] for item in messages[-2:]], ["a", "b"])
        self.assertEqual(messages[-2]["content"], "5")
        json.dumps(messages, ensure_ascii=False)

        self.assertEqual(agent.run("刚才的结果是多少？"), "刚才的结果是 5。")
        self.assertEqual(model.requests[2]["messages"][-2], {"role": "assistant", "content": "结果是 5。"})

    def test_cli_progress_reports_requests_and_tool_results_in_order(self):
        model = ScriptedModel(response(calls=[
            call("bad", "calculate", '{"expression":"1/0"}'),
            call("ok", "calculate", '{"expression":"13*17"}'),
        ]), response("完成"))
        agent = Agent(assistant.TOOLS, "助手", complete=model.complete, model="fake", on_event=_print_event)
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(agent.run("private question"), "完成")
        self.assertEqual(output.getvalue().splitlines(), [
            "  [第 1 轮] 请求模型",
            "  [第 1 轮] 模型请求工具 calculate",
            "  [第 1 轮] calculate → 失败或拒绝",
            "  [第 1 轮] 模型请求工具 calculate",
            "  [第 1 轮] calculate → 成功",
            "  [第 2 轮] 请求模型",
        ])

    def test_failed_tools_return_matched_results_without_stopping_batch(self):
        @tool
        def broken():
            raise RuntimeError("internal secret")

        errors = [
            ("calculate", "{", "有效的 JSON"),
            ("unknown", "{}", "未知工具"),
            ("calculate", "[]", "JSON 对象"),
            ("calculate", '{"expression":true}', "应为 string"),
            ("calculate", '{"expression":"1+1","expression":"2+2"}', "重复"),
            ("calculate", "{}", "缺少必填"),
            ("get_time", '{"extra":"private value"}', "未知参数"),
            ("calculate", '{"expression":"1/0"}', "除数不能为零"),
            ("broken", "{}", "RuntimeError"),
        ]
        calls = [call(str(index), name, args) for index, (name, args, _) in enumerate(errors)]
        calls.append(call("ok", "calculate", '{"expression":"4*5"}'))
        model = ScriptedModel(response(calls=calls), response("完成"))
        agent = Agent([*assistant.TOOLS, broken], "system", complete=model.complete, model="fake")
        agent.run("private question")

        results = model.requests[1]["messages"][3:]
        self.assertEqual([item["tool_call_id"] for item in results], [item.id for item in calls])
        for result, (_, _, expected) in zip(results, errors):
            self.assertIn(expected, result["content"])
            self.assertNotIn("internal secret", result["content"])
        self.assertEqual(results[-1]["content"], "20")

        log_text = next(self.root.glob("*.jsonl")).read_text(encoding="utf-8")
        events = [json.loads(line) for line in log_text.splitlines()]
        self.assertEqual(len({event["turn_id"] for event in events}), 1)
        self.assertIn("final_answer", [event["event"] for event in events])
        self.assertEqual({event["status"] for event in events if event["event"] == "tool_result"},
                         {"ok", "rejected", "error"})
        for secret in ("private question", "private value", "internal secret", "4*5"):
            self.assertNotIn(secret, log_text)

    def test_round_limit_keeps_completed_tool_results(self):
        model = ScriptedModel(response(calls=[call("a", "calculate", '{"expression":"2+3"}')]))
        agent = Agent(assistant.TOOLS, "助手", max_turns=1, complete=model.complete, model="fake")
        self.assertIn("上限", agent.run("计算"))
        self.assertEqual(agent.messages[-1]["content"], "5")
        self.assertEqual(len(model.requests), 1)

    def test_bad_first_response_leaves_no_unanswered_user_message(self):
        for bad_response in (
            None,
            SimpleNamespace(choices=[]),
            SimpleNamespace(choices={"0": object()}),
            response(),
            response("   "),
            response(calls=[call("a", "get_time", "{}"), call("a", "get_time", "{}")]),
            response(calls=[call("a", "get_time", {})]),
            response(calls=[SimpleNamespace(id="a", type="function")]),
            response(calls=[call("a", "get_time", "{}")], reason="stop"),
            response("unexpected text", reason="tool_calls"),
        ):
            with self.subTest(response=bad_response):
                model = ScriptedModel(bad_response)
                agent = Agent(assistant.TOOLS, "助手", complete=model.complete, model="fake")
                with self.assertRaises(ModelResponseError):
                    agent.run("计算")
                self.assertEqual([item["role"] for item in agent.messages], ["system"])

    def test_incomplete_model_reply_never_executes_tools(self):
        effect = Mock()

        @tool
        def change():
            effect()

        for reason in ("length", "content_filter", "insufficient_system_resource", "aborted"):
            with self.subTest(reason=reason):
                model = ScriptedModel(response("partial", [call("a", "change", "{}")], reason=reason))
                agent = Agent([change], "助手", complete=model.complete, model="fake")
                with self.assertRaises(ModelResponseError):
                    agent.run("修改")
                self.assertEqual([item["role"] for item in agent.messages], ["system"])
        effect.assert_not_called()

    def test_interrupted_tool_batch_keeps_protocol_and_does_not_replay(self):
        effect = Mock()

        @tool
        def change(value: str):
            effect(value)
            if value == "stop":
                raise KeyboardInterrupt
            return "saved"

        model = ScriptedModel(
            response(calls=[call(value, "change", json.dumps({"value": value}))
                            for value in ("first", "stop", "skip")]),
            response("继续"),
        )
        agent = Agent([change], "助手", complete=model.complete, model="fake")
        with self.assertRaises(KeyboardInterrupt):
            agent.run("修改")
        self.assertEqual([item.args[0] for item in effect.call_args_list], ["first", "stop"])
        results = agent.messages[-3:]
        self.assertEqual([item["tool_call_id"] for item in results], ["first", "stop", "skip"])
        self.assertEqual(results[0]["content"], "saved")
        self.assertIn("状态未知", results[1]["content"])
        self.assertIn("未执行", results[2]["content"])
        self.assertEqual(agent.run("接着聊"), "继续")
        self.assertEqual(model.requests[1]["messages"][-4:-1], results)

    def test_interrupted_first_request_discards_unanswered_input(self):
        model = ScriptedModel(KeyboardInterrupt(), response("继续"))
        agent = Agent([], "助手", complete=model.complete, model="fake")
        with self.assertRaises(KeyboardInterrupt):
            agent.run("取消的问题")
        self.assertEqual(agent.run("新的问题"), "继续")
        self.assertEqual([item["content"] for item in model.requests[1]["messages"]],
                         ["助手", "新的问题"])

    def test_later_request_failure_keeps_tool_call_and_result(self):
        model = ScriptedModel(
            response(calls=[call("a", "calculate", '{"expression":"2+3"}')]),
            ValueError("request failed"),
        )
        agent = Agent(assistant.TOOLS, "助手", complete=model.complete, model="fake")
        with self.assertRaises(ValueError):
            agent.run("计算")
        self.assertEqual([item["role"] for item in agent.messages], ["system", "user", "assistant", "tool"])

    def test_constructor_and_schema(self):
        @tool
        def flags(count: int, ratio: float = 0.5, overwrite: bool = False):
            return f"{count} / {ratio} / {overwrite}"

        model = ScriptedModel(
            response(calls=[
                call("a", "flags", '{"count":true}'),
                call("b", "flags", '{"count":1,"ratio":NaN}'),
                call("c", "flags", '{"count":1}'),
            ]),
            response("完成"),
        )
        agent = Agent([flags], "助手", complete=model.complete, model="fake")
        other = Agent([flags], "独立助手", complete=model.complete, model="fake")
        self.assertEqual(agent.schemas[0]["function"]["parameters"]["required"], ["count"])
        agent.run("验证参数")
        self.assertIn("应为 integer", agent.messages[-4]["content"])
        self.assertIn("应为 number", agent.messages[-3]["content"])
        self.assertEqual(agent.messages[-2]["content"], "1 / 0.5 / False")
        self.assertEqual(other.messages, [{"role": "system", "content": "独立助手"}])
        with self.assertRaises(ValueError):
            Agent([flags, flags], "助手", complete=model.complete, model="fake")
        with self.assertRaises(ValueError):
            Agent([], "助手", max_turns=0, complete=model.complete, model="fake")

    def test_sdk_roundtrip_without_network(self):
        requests = []

        def handler(request):
            body = json.loads(request.content)
            requests.append(body)
            message = {"role": "assistant", "content": "读到了 hello。"}
            if len(requests) == 1:
                message = {"role": "assistant", "content": None, "tool_calls": [{
                    "id": "write",
                    "type": "function",
                    "function": {"name": "write_file", "arguments": '{"path":"hello.txt","content":"hello"}'},
                }, {
                    "id": "read",
                    "type": "function",
                    "function": {"name": "read_file", "arguments": '{"path":"hello.txt"}'},
                }]}
            return httpx.Response(200, json={
                "id": "mock", "created": 0, "model": "fake", "object": "chat.completion",
                "choices": [{
                    "index": 0,
                    "finish_reason": "tool_calls" if "tool_calls" in message else "stop",
                    "message": message,
                }],
            })

        with OpenAI(
            api_key="offline", base_url="https://offline.invalid", max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        ) as client:
            agent = Agent(coding_agent.build_tools(self.root), "编程助手",
                          complete=client.chat.completions.create, model="fake")
            self.assertEqual(agent.run("创建后读文件"), "读到了 hello。")

        self.assertEqual((self.root / "hello.txt").read_text(encoding="utf-8"), "hello")
        self.assertEqual(requests[1]["messages"][-1],
                         {"role": "tool", "tool_call_id": "read", "content": "hello"})


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        base = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.root = base / "workspace"
        self.root.mkdir()
        self.outside = base / "outside.txt"
        self.outside.write_text("outside", encoding="utf-8")
        self.tools = {func.__name__: func for func in coding_agent.build_tools(self.root)}

    def test_write_requires_explicit_overwrite_and_user_confirmation(self):
        write = self.tools["write_file"]
        read = self.tools["read_file"]
        approve = Mock(return_value=False)
        confirmed_write = coding_agent.build_tools(self.root, approve_overwrite=approve)[2]
        write("sub/note.txt", "第一版")
        with self.assertRaises(ToolError):
            confirmed_write("sub/note.txt", "意外覆盖")
        approve.assert_not_called()
        with self.assertRaises(ToolError):
            write("sub/note.txt", "未接入确认", overwrite=True)
        with self.assertRaisesRegex(ToolError, "用户拒绝"):
            confirmed_write("sub/note.txt", "用户拒绝", overwrite=True)
        self.assertEqual(read("sub/note.txt"), "第一版")
        approve.return_value = True
        confirmed_write("sub/note.txt", "第二版", overwrite=True)
        self.assertEqual(read("sub/note.txt"), "第二版")
        self.assertEqual(self.tools["list_files"]("sub"), "note.txt")

    def test_approved_overwrite_rejects_changed_file(self):
        target = self.root / "note.txt"
        target.write_text("first", encoding="utf-8")

        def approve(path):
            path.write_text("newer content", encoding="utf-8")
            return True

        write = coding_agent.build_tools(self.root, approve_overwrite=approve)[2]
        with self.assertRaisesRegex(ToolError, "已变动"):
            write("note.txt", "overwritten", overwrite=True)
        self.assertEqual(target.read_text(encoding="utf-8"), "newer content")
        self.assertEqual(list(self.root.iterdir()), [target])

    def test_failed_creation_cleans_up_partial_file(self):
        original_open = Path.open

        @contextmanager
        def open_with_failed_write(path, mode):
            with original_open(path, mode) as file:
                broken = Mock(wraps=file)

                def fail(data):
                    file.write(data[:1])
                    raise OSError("disk write failed")

                broken.write.side_effect = fail
                yield broken

        with patch.object(Path, "open", new=open_with_failed_write):
            with self.assertRaisesRegex(ToolError, "无法写入"):
                self.tools["write_file"]("partial.txt", "hello")
        self.assertFalse((self.root / "partial.txt").exists())

    def test_file_limits_count_bytes_and_keep_valid_unicode(self):
        limit = coding_agent.MAX_FILE_BYTES
        (self.root / "long.txt").write_bytes(b"a" * (limit - 1) + "中".encode("utf-8"))
        result = self.tools["read_file"]("long.txt")
        self.assertTrue(result.startswith("a" * (limit - 1) + "\n"))
        self.assertIn("截断", result)
        with self.assertRaises(ToolError):
            self.tools["write_file"]("too-large.txt", "中" * limit)
        self.assertFalse((self.root / "too-large.txt").exists())

    def test_relative_paths_cannot_escape(self):
        for path in ("../outside.txt", r"..\outside.txt", str(self.outside), r"C:secret.txt",
                     "NUL", "file:stream", "name. ", ".. /outside.txt", "file\x1b.txt"):
            with self.subTest(path=path), self.assertRaises(ToolError):
                self.tools["read_file"](path)
        with self.assertRaises(ToolError):
            self.tools["write_file"]("../outside.txt", "changed", overwrite=True)
        with patch.object(coding_agent, "_write_text") as write:
            with self.assertRaises(ToolError):
                self.tools["write_file"](".", "changed", overwrite=True)
            write.assert_not_called()
        self.assertEqual(self.outside.read_text(encoding="utf-8"), "outside")

    def test_symlink_pointing_outside_is_rejected(self):
        link = self.root / "link.txt"
        try:
            link.symlink_to(self.outside)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Symlink unavailable: {type(exc).__name__}")
        with self.assertRaisesRegex(ToolError, "工作区外"):
            self.tools["read_file"]("link.txt")

    def test_python_is_opt_in_and_denial_does_not_start_a_process(self):
        self.assertNotIn("run_python", self.tools)
        (self.root / "demo.py").write_text("print('hello')\n", encoding="utf-8")
        run = coding_agent.build_tools(self.root, approve_python=lambda _: False)[-1]
        with patch.object(coding_agent, "_run_python") as launch:
            with self.assertRaisesRegex(ToolError, "拒绝"):
                run("demo.py")
            launch.assert_not_called()

    def test_approved_script_runs_and_does_not_inherit_api_key(self):
        (self.root / "demo.py").write_text(
            "import os\nfrom pathlib import Path\n"
            "print(Path.cwd().name, 'DEEPSEEK_API_KEY' in os.environ)\n"
            "print('x' * 5000)\n",
            encoding="utf-8",
        )
        run = coding_agent.build_tools(self.root, approve_python=lambda _: True)[-1]
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-only"}):
            result = run("demo.py")
        self.assertTrue(result.startswith("workspace False"))
        self.assertIn("截断", result)
        self.assertLess(len(result), coding_agent.MAX_OUTPUT_BYTES + 100)

    def test_approved_script_is_not_launched_if_changed_during_prompt(self):
        (self.root / "demo.py").write_text("print('hello')\n", encoding="utf-8")

        def approve(path):
            path.write_text("print('changed script')\n", encoding="utf-8")
            return True

        run = coding_agent.build_tools(self.root, approve_python=approve)[-1]
        with patch.object(coding_agent, "_run_python") as launch:
            with self.assertRaisesRegex(ToolError, "已变动"):
                run("demo.py")
            launch.assert_not_called()

    def test_script_errors_and_timeouts_are_reported(self):
        (self.root / "error.py").write_text("raise SystemExit(3)\n", encoding="utf-8")
        (self.root / "slow.py").write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
        run = coding_agent.build_tools(self.root, approve_python=lambda _: True)[-1]
        with self.assertRaisesRegex(ToolError, "退出码 3"):
            run("error.py")
        with patch.object(coding_agent, "TIMEOUT_SECONDS", 0.3):
            with self.assertRaisesRegex(ToolError, "运行上限"):
                run("slow.py")


class UtilityTests(unittest.TestCase):
    def test_calculator_evaluates_only_arithmetic(self):
        self.assertEqual(assistant.calculate("-(2 + 3) * 4"), "-20")
        for expression in ("__import__('os')", "2 ** 10", "1/0", "1e100", "True", "1" * 129):
            with self.subTest(expression=expression), self.assertRaises(ToolError):
                assistant.calculate(expression)

    def test_transient_error_retries_with_backoff(self):
        attempts = iter([TimeoutError(), ConnectionError(), "ok"])

        def flaky():
            value = next(attempts)
            if isinstance(value, Exception):
                raise value
            return value

        with patch.object(retry.time, "sleep") as sleep:
            self.assertEqual(retry.call_with_retry(flaky), "ok")
            self.assertEqual([item.args[0] for item in sleep.call_args_list], [1, 2])

    def test_http_retry_policy(self):
        request = httpx.Request("POST", "https://offline.invalid")
        for status, expected in ((401, False), (400, False), (429, True), (503, True)):
            with self.subTest(status=status):
                response = httpx.Response(status, request=request)
                error = APIStatusError("test", response=response, body=None)
                self.assertEqual(retry.is_retryable(error), expected)
        with patch.object(retry.time, "sleep") as sleep:
            with self.assertRaises(ValueError):
                retry.call_with_retry(lambda: int("invalid"))
            sleep.assert_not_called()

    def test_log_failure_is_nonfatal(self):
        with patch.object(logger.Path, "mkdir", side_effect=OSError):
            logger.log_event("test")


if __name__ == "__main__":
    unittest.main(verbosity=2)
