"""Handwritten model/tool loop. Importing this module does not create a client."""

import inspect
import json
import math
from typing import get_type_hints
from uuid import uuid4

from .logger import log_event
from .retry import call_with_retry

_TYPE_MAP = {str: "string", int: "integer", float: "number", bool: "boolean"}


class ToolError(Exception):
    """An expected tool failure whose message is safe to return to the model."""


class ModelResponseError(Exception):
    """The model did not return a usable assistant message."""


def tool(func):
    """Describe an ordinary function with a small, checked JSON Schema."""
    signature = inspect.signature(func)
    hints = get_type_hints(func)
    properties = {}
    required = []

    for name, parameter in signature.parameters.items():
        if parameter.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            raise TypeError(f"{func.__name__}.{name} must accept a keyword argument")
        annotation = hints.get(name)
        if annotation not in _TYPE_MAP:
            raise TypeError(f"{func.__name__}.{name} must be str, int, float or bool")
        properties[name] = {"type": _TYPE_MAP[annotation]}
        if parameter.default is inspect.Parameter.empty:
            required.append(name)

    func._schema = {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": inspect.getdoc(func) or "",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }
    return func


def _matches_type(value, kind):
    if kind == "number":
        return type(value) is int or (type(value) is float and math.isfinite(value))
    return type(value) is {"string": str, "integer": int, "boolean": bool}[kind]


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ToolError("工具参数包含重复的 JSON 键。")
        result[key] = value
    return result


def _assistant_message(response):
    choices = getattr(response, "choices", None)
    if not isinstance(choices, (list, tuple)) or not choices:
        raise ModelResponseError("模型返回了空响应或无法识别的候选列表。")
    choice = choices[0]
    reason = getattr(choice, "finish_reason", None)
    if reason == "length":
        raise ModelResponseError("本轮模型输出被截断，请缩小任务后重试。")
    if reason not in ("stop", "tool_calls"):
        raise ModelResponseError("模型未正常完成本轮响应，请重试。")

    message = getattr(choice, "message", None)
    if message is None:
        raise ModelResponseError("模型返回了空响应。")
    content = getattr(message, "content", None)
    raw_calls = getattr(message, "tool_calls", None)
    if content is not None and not isinstance(content, str):
        raise ModelResponseError("模型返回了不支持的消息正文。")
    if raw_calls is not None and not isinstance(raw_calls, (list, tuple)):
        raise ModelResponseError("模型返回了不支持的工具调用格式。")
    if bool(raw_calls) != (reason == "tool_calls"):
        raise ModelResponseError("模型结束状态与工具调用不一致。")

    assistant = {"role": "assistant", "content": content}
    calls = []
    call_ids = set()
    for call in raw_calls or ():
        call_id = getattr(call, "id", None)
        if (
            getattr(call, "type", None) != "function" or not isinstance(call_id, str)
            or not call_id or call_id in call_ids
        ):
            raise ModelResponseError("模型返回了无法配对的工具调用。")
        function = getattr(call, "function", None)
        name = getattr(function, "name", None)
        arguments = getattr(function, "arguments", None)
        if not isinstance(name, str) or not name or not isinstance(arguments, str):
            raise ModelResponseError("模型返回了不支持的工具调用格式。")
        call_ids.add(call_id)
        calls.append({
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": arguments},
        })
    if calls:
        assistant["tool_calls"] = calls
    elif not content or not content.strip():
        raise ModelResponseError("模型没有给出文本回答或工具调用。")
    return assistant


class Agent:
    def __init__(self, tools, system_prompt, max_turns=5, *, complete, model, on_event=None):
        if type(max_turns) is not int or max_turns < 1:
            raise ValueError("max_turns must be a positive integer")
        self.complete = complete
        self.model = model
        self.on_event = on_event
        self.max_turns = max_turns
        self.tools = {}
        self.schemas = []
        self.messages = [{"role": "system", "content": system_prompt}]

        for func in tools:
            if not hasattr(func, "_schema"):
                raise TypeError(f"{func.__name__} must be registered with @tool")
            if func.__name__ in self.tools:
                raise ValueError(f"Duplicate tool: {func.__name__}")
            self.tools[func.__name__] = func
            self.schemas.append(func._schema)

    def _report_event(self, event, **fields):
        log_event(event, **fields)
        if self.on_event is not None:
            try:
                self.on_event(event, **fields)
            except Exception as exc:
                log_event("event_report_failed", turn_id=fields["turn_id"], error_type=type(exc).__name__)

    def execute_tool(self, call, *, turn_id, round_number):
        """Validate, execute and return one result with the original call ID."""
        name = call["function"]["name"]
        call_id = call["id"]
        self._report_event("tool_call", turn_id=turn_id, round=round_number, tool=name, tool_call_id=call_id)
        status = "ok"

        try:
            func = self.tools.get(name)
            if func is None:
                raise ToolError("未知工具。请从已注册的工具中选择。")

            try:
                args = json.loads(call["function"]["arguments"], object_pairs_hook=_unique_json_object)
            except (ValueError, RecursionError) as exc:
                raise ToolError("工具参数不是有效的 JSON。") from exc
            if not isinstance(args, dict):
                raise ToolError("工具参数必须是 JSON 对象。")

            parameters = func._schema["function"]["parameters"]
            for key, value in args.items():
                if key not in parameters["properties"]:
                    raise ToolError("包含未知参数。请核对工具参数说明。")
                kind = parameters["properties"][key]["type"]
                if not _matches_type(value, kind):
                    raise ToolError(f"参数 {key} 应为 {kind}。")
            if any(key not in args for key in parameters["required"]):
                raise ToolError("缺少必填参数。请核对工具参数说明。")

            result = str(func(**args))
        except ToolError as exc:
            status = "rejected"
            result = f"工具失败：{exc}"
        except Exception as exc:
            status = "error"
            result = f"工具执行失败（{type(exc).__name__}）。"

        self._report_event(
            "tool_result", turn_id=turn_id, round=round_number, tool=name,
            tool_call_id=call_id, status=status,
        )
        return {"role": "tool", "tool_call_id": call_id, "content": result}

    def _append_tool_batch(self, assistant, *, turn_id, round_number):
        calls = assistant["tool_calls"]
        first_result = len(self.messages) + 1
        try:
            self.messages.append(assistant)
            for call in calls:
                self.messages.append(
                    self.execute_tool(call, turn_id=turn_id, round_number=round_number)
                )
        except KeyboardInterrupt:
            # Keep completed results. Never run or replay a tool to repair history.
            if len(self.messages) < first_result:
                raise
            remaining = calls[len(self.messages) - first_result:]
            for index, call in enumerate(remaining):
                content = "工具未执行：用户中断了本轮。"
                if index == 0:
                    content = "工具被中断，完成状态未知，请检查实际结果。"
                self.messages.append({
                    "role": "tool", "tool_call_id": call["id"], "content": content,
                })
            self._report_event("turn_interrupted", turn_id=turn_id, round=round_number)
            raise

    def run(self, user_input):
        """Run one user turn. Tool requests and their results remain adjacent."""
        turn_id = uuid4().hex
        self.messages.append({"role": "user", "content": user_input})
        log_event("user_input", turn_id=turn_id)

        for round_number in range(1, self.max_turns + 1):
            request = {"model": self.model, "messages": self.messages}
            if self.schemas:
                request["tools"] = self.schemas
            try:
                self._report_event("model_request", turn_id=turn_id, round=round_number)
                response = call_with_retry(lambda: self.complete(**request))
                assistant = _assistant_message(response)
            except (Exception, KeyboardInterrupt) as exc:
                if round_number == 1:
                    self.messages.pop()
                log_event(
                    "request_failed", turn_id=turn_id, round=round_number,
                    error_type=type(exc).__name__,
                )
                raise

            if "tool_calls" in assistant:
                self._append_tool_batch(assistant, turn_id=turn_id, round_number=round_number)
                continue

            self.messages.append(assistant)
            log_event("final_answer", turn_id=turn_id, round=round_number)
            return assistant["content"]

        log_event("max_turns_exceeded", turn_id=turn_id)
        return f"已达到 {self.max_turns} 轮模型请求上限。请检查已经完成的工具操作。"
