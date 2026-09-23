"""Run reproducible on-device checks. Does not make external web requests."""
from __future__ import annotations

import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

from .config import data_dir, model_paths, read_config, voice_model_path
from .pairing import configured_peer
from .providers import LayaLocal, QwenLocal
from .voice import WakeRouter


def _pi_model() -> str:
    path = Path("/proc/device-tree/model")
    return path.read_bytes().decode(errors="replace").rstrip("\x00") if path.is_file() else "unknown"


def _temperature() -> float | None:
    path = Path("/sys/class/thermal/thermal_zone0/temp")
    try:
        return int(path.read_text().strip()) / 1000
    except (OSError, ValueError):
        return None


def _memory_free_mb() -> int | None:
    path = Path("/proc/meminfo")
    if not path.is_file():
        return None
    for line in path.read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    return None


def _microphone_probe(seconds: int, model_path: Path) -> dict:
    if not seconds:
        return {"status": "not requested"}
    import sounddevice as sd
    from vosk import KaldiRecognizer, Model, SetLogLevel
    SetLogLevel(-1)
    recognizer = KaldiRecognizer(Model(str(model_path)), 16000)
    print(f"Say 'Kairo' into the microphone within {seconds} seconds.", flush=True)
    audio = sd.rec(seconds * 16000, samplerate=16000, channels=1, dtype="int16")
    sd.wait()
    transcripts = []
    data = audio.tobytes()
    for index in range(0, len(data), 8000):
        if recognizer.AcceptWaveform(data[index:index + 8000]):
            transcripts.append(json.loads(recognizer.Result()).get("text", ""))
    transcripts.append(json.loads(recognizer.FinalResult()).get("text", ""))
    router = WakeRouter()
    events = [router.accept(text) for text in transcripts]
    heard = any(event and event.kind in {"wake", "request"} for event in events)
    return {"status": "pass" if heard else "fail", "transcripts": transcripts}


def check_pi(*, microphone_seconds: int = 0) -> dict:
    if not 0 <= microphone_seconds <= 15:
        raise ValueError("Microphone probe must be between 0 and 15 seconds")
    config = read_config()
    laya_path, qwen_path = model_paths(config)
    voice_path = voice_model_path(config)
    hardware = _pi_model()
    result = {"time": datetime.now(timezone.utc).isoformat(),
              "hardware": hardware, "architecture": platform.machine(),
              "temperature_c_before": _temperature(), "available_ram_mb_before": _memory_free_mb(),
              "checks": {}}
    is_pi = "Raspberry Pi" in hardware and platform.machine().lower() in {"aarch64", "arm64"}
    result["checks"]["arm64_pi"] = {"status": "pass" if is_pi else "fail"}
    if not is_pi:
        return result
    laya = LayaLocal(laya_path)
    started = time.monotonic()
    try:
        choice, confidence = laya.choose("Open my Downloads folder on the computer", {
            "open_downloads": "Open the Downloads folder", "chat": "Answer with text only"})
        result["checks"]["laya_local"] = {"status": "pass", "choice": choice,
                                              "confidence": confidence, "elapsed_ms": int((time.monotonic() - started) * 1000)}
    except Exception as exc:
        result["checks"]["laya_local"] = {"status": "fail", "error": str(exc)}
    qwen = QwenLocal(qwen_path, binary=config.get("llama_server", "llama-server"),
                     port=config.get("qwen_port", 18080))
    started = time.monotonic()
    try:
        response = qwen.chat("Reply with the word READY.")
        result["checks"]["qwen_local"] = {"status": "pass" if response else "fail",
                                              "response": response[:120], "elapsed_ms": int((time.monotonic() - started) * 1000)}
    except Exception as exc:
        result["checks"]["qwen_local"] = {"status": "fail", "error": str(exc)}
    finally:
        qwen.close()
    try:
        result["checks"]["paired_desktop"] = {"status": "pass" if configured_peer().request("/health")["status"] == "ok" else "fail"}
    except Exception as exc:
        result["checks"]["paired_desktop"] = {"status": "fail", "error": str(exc)}
    try:
        result["checks"]["microphone"] = _microphone_probe(microphone_seconds, voice_path)
    except Exception as exc:
        result["checks"]["microphone"] = {"status": "fail", "error": str(exc)}
    result["temperature_c_after"] = _temperature()
    result["available_ram_mb_after"] = _memory_free_mb()
    result["all_requested_passed"] = all(item["status"] in {"pass", "not requested"}
                                           for item in result["checks"].values())
    path = data_dir() / "acceptance"
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    output = path / f"pi-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    result["report"] = str(output)
    return result
