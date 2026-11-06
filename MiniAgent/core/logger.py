"""One local JSONL record per event."""

import json
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
MAX_FIELD_CHARS = 500


def log_event(event, **fields):
    """Record bounded metadata. A log failure must not interrupt the agent."""
    now = datetime.now().astimezone()
    record = {
        key: value[:MAX_FIELD_CHARS] if isinstance(value, str) else value
        for key, value in fields.items()
    }
    record.update(ts=now.isoformat(timespec="seconds"), event=event)

    try:
        directory = Path(LOG_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / f"{now:%Y-%m-%d}.jsonl").open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    except (OSError, TypeError, ValueError):
        pass
