"""The two command-line apps share setup and the input loop."""

import argparse
import os
import sys
from functools import partial
from pathlib import Path

from dotenv import load_dotenv
from openai import APIError, APIStatusError, OpenAI

from apps import assistant, coding_agent
from core.agent import Agent, ModelResponseError

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_WORKSPACE = PROJECT_DIR / "workspace"
_TOOL_STATUS = {"ok": "成功", "rejected": "失败或拒绝", "error": "执行异常"}


def _print_event(event, **fields):
    prefix = f"  [第 {fields['round']} 轮]"
    if event == "model_request":
        print(f"{prefix} 请求模型", flush=True)
    elif event in ("tool_call", "tool_result"):
        name = fields["tool"][:64]
        label = name if name.isidentifier() else repr(name)
        detail = f"模型请求工具 {label}" if event == "tool_call" else f"{label} → {_TOOL_STATUS[fields['status']]}"
        print(f"{prefix} {detail}", flush=True)
    elif event == "turn_interrupted":
        print(f"{prefix} 工具批次已中断，请检查已执行的操作。", flush=True)


def _approve_overwrite(path):
    print(f"即将覆盖已有文件：{str(path)!r}")
    return input("输入 yes 确认覆盖：").strip().lower() == "yes"


def _approve_python(path):
    print(f"脚本将以当前用户权限运行：{str(path)!r}")
    return input("仅运行你已检查且信任的脚本。输入 yes 确认：").strip().lower() == "yes"


def main(*, coding=False):
    parser = argparse.ArgumentParser(description="MiniAgent 编程助手" if coding else "MiniAgent 演示助手")
    if coding:
        parser.add_argument("--workspace", type=Path, help="已有工作区目录，默认使用 MiniAgent/workspace")
        parser.add_argument("--enable-python", action="store_true", help="注册 Python 执行工具，每次运行前确认")
    args = parser.parse_args()

    load_dotenv(PROJECT_DIR.parent / ".env", encoding="utf-8-sig")
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        parser.error("请复制 .env.example 为 .env，并填写 DEEPSEEK_API_KEY。")
    model = os.getenv("MINIAGENT_MODEL", "deepseek-flash").strip() or "deepseek-flash"

    if coding:
        try:
            workspace = (args.workspace or DEFAULT_WORKSPACE).resolve()
            if args.workspace is None:
                workspace.mkdir(exist_ok=True)
            if not workspace.is_dir():
                parser.error("工作区必须是一个已有的目录。")
        except (OSError, RuntimeError) as exc:
            parser.error(f"无法打开工作区（{type(exc).__name__}）。")
        tools = coding_agent.build_tools(
            workspace,
            approve_overwrite=_approve_overwrite,
            approve_python=_approve_python if args.enable_python else None,
        )
        system_prompt = coding_agent.SYSTEM_PROMPT
        print(f"工作区：{workspace}")
    else:
        tools, system_prompt = assistant.TOOLS, assistant.SYSTEM_PROMPT

    with OpenAI(
        api_key=api_key, base_url="https://api.deepseek.com", max_retries=0, timeout=20,
    ) as client:
        complete = partial(
            client.chat.completions.create, extra_body={"thinking": {"type": "disabled"}},
        )
        agent = Agent(tools, system_prompt, complete=complete, model=model, on_event=_print_event)
        print("MiniAgent 已启动，输入 q 退出。")
        while True:
            try:
                question = input("你: ").strip()
                if question == "q":
                    break
                if question:
                    print(f"Agent: {agent.run(question)}")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            except APIStatusError as exc:
                print(f"模型请求失败（HTTP {exc.status_code}）。", file=sys.stderr)
            except APIError as exc:
                print(f"模型请求失败（{type(exc).__name__}）。", file=sys.stderr)
            except ModelResponseError as exc:
                print(exc, file=sys.stderr)
    return 0
