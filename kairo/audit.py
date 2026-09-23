"""Metadata-only action journal: no prompts, document contents or credentials."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .config import data_dir


def record(component: str, action: str, success: bool, duration_ms: int,
           error: BaseException | None = None) -> None:
    entry = {"time": int(time.time()), "component": component, "action": action,
             "success": success, "duration_ms": duration_ms,
             "error_type": type(error).__name__ if error else None}
    path = data_dir() / "audit.jsonl"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(descriptor, (json.dumps(entry, separators=(",", ":")) + "\n").encode())
    finally:
        os.close(descriptor)


def recent(limit: int = 20) -> list[dict]:
    path = data_dir() / "audit.jsonl"
    if not path.is_file():
        return []
    # Read at most the final 64 KB. Corrupt or partial lines are ignored.
    with path.open("rb") as file:
        file.seek(0, os.SEEK_END)
        file.seek(max(0, file.tell() - 65_536))
        lines = file.read().decode("utf-8", errors="replace").splitlines()[-limit:]
    result = []
    for line in lines:
        try:
            result.append(json.loads(line))
        except ValueError:
            continue
    return result
