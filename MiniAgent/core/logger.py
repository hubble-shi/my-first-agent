"""
日志落盘：把每次对话的关键事件追加到 logs/YYYY-MM-DD.jsonl

为什么用 JSONL：每行一个独立的 JSON，人和程序都能读。
以后做评测时可以直接把历史日志读回来当测试集。
"""
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")

# 单个字段最长多少字符（防止一个 dir 命令把日志写爆）
MAX_FIELD_CHARS = 500


def _truncate(value):
    """过长的字符串截断，非字符串原样返回"""
    if isinstance(value, str) and len(value) > MAX_FIELD_CHARS:
        return value[:MAX_FIELD_CHARS] + "...(截断)"
    return value


def log_event(event: str, **fields):
    """
    追加一条事件到当天的日志文件。

    用法：
        log_event("user_input", content="杭州天气怎么样")
        log_event("tool_call", tool="get_weather", args={"city": "杭州"})

    ⚠️ 写日志失败不会抛异常 —— 日志是旁路，不能影响主流程。
    """
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        now = datetime.now()
        path = os.path.join(LOG_DIR, now.strftime("%Y-%m-%d") + ".jsonl")

        record = {"ts": now.strftime("%Y-%m-%dT%H:%M:%S"), "event": event}
        for k, v in fields.items():
            record[k] = _truncate(v)

        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass
