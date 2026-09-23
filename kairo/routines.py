"""Versioned deterministic single-step routines from verified operations."""
from __future__ import annotations

import json
import re

from .config import data_dir
from .tools import REGISTRY


class RoutineError(RuntimeError):
    pass


def _read(name: str, default: dict) -> dict:
    path = data_dir() / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _write(name: str, value: dict) -> None:
    path = data_dir() / name
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(path)


def remember(action: str, args: dict, remote: bool) -> None:
    # Never record form contents or replay a click that could submit or purchase.
    if action in REGISTRY and action not in {"browser_fill", "browser_click", "browser_read", "browser_close"}:
        _write("last.json", {"version": 1, "action": action, "args": args, "remote": remote})


def save(name: str) -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,49}", name):
        raise RoutineError("Routine names use lowercase letters, digits, and underscores")
    last = _read("last.json", {})
    if last.get("action") not in REGISTRY:
        raise RoutineError("No verified action is available to save")
    routines = _read("routines.json", {"version": 1, "items": {}})
    if name in routines["items"]:
        raise RoutineError("A routine with that name already exists")
    routines["items"][name] = last
    _write("routines.json", routines)
    return last


def get(name: str) -> dict:
    value = _read("routines.json", {"version": 1, "items": {}})["items"].get(name)
    if not value or value.get("action") not in REGISTRY or not isinstance(value.get("args"), dict):
        raise RoutineError("Unknown or invalid routine")
    return value


def names() -> list[str]:
    return sorted(_read("routines.json", {"version": 1, "items": {}})["items"])
