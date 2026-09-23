"""Public configuration and file layout; secrets never go in config.json."""
from __future__ import annotations

import json
import os
from pathlib import Path


def data_dir() -> Path:
    return Path(os.environ.get("KAIRO_DATA_DIR", Path.home() / ".kairo")).expanduser()


def read_config() -> dict:
    path = data_dir() / "config.json"
    if not path.exists():
        return {}
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("config.json must contain an object")
    return result


def write_config(config: dict) -> None:
    path = data_dir() / "config.json"
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        temp.chmod(0o600)
    temp.replace(path)


def model_paths(config: dict) -> tuple[Path, Path]:
    laya = Path(os.environ.get("KAIRO_LAYA_MODEL", config.get("laya_model", data_dir() / "models" / "laya")))
    qwen = Path(os.environ.get("KAIRO_QWEN_MODEL", config.get("qwen_model", data_dir() / "models" / "qwen.gguf")))
    return laya.expanduser(), qwen.expanduser()


def voice_model_path(config: dict) -> Path:
    return Path(os.environ.get("KAIRO_VOSK_MODEL", config.get("voice_model", data_dir() / "models" / "vosk-model-small-en-us-0.15"))).expanduser()
