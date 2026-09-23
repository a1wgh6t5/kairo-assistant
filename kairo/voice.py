"""Offline streaming speech input with a phrase-based 'Kairo' wake trigger."""
from __future__ import annotations

import json
import queue
import re
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .config import read_config, voice_model_path
from .engine import Engine


class VoiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class VoiceEvent:
    kind: str
    text: str = ""


class WakeRouter:
    def __init__(self, timeout: float = 8.0):
        self.armed_until = 0.0
        self.timeout = timeout

    def accept(self, transcript: str, now: float | None = None) -> VoiceEvent | None:
        current = time.monotonic() if now is None else now
        text = transcript.strip(" .,!?")
        if not text:
            return None
        if re.fullmatch(r"(?:kairo |cairo )?(stop|cancel)", text, re.I):
            self.armed_until = 0.0
            return VoiceEvent("stop")
        wake = re.search(r"\b(?:kairo|cairo)\b", text, flags=re.I)
        if wake:
            tail = text[wake.end():].strip(" ,.!?")
            if tail:
                self.armed_until = 0.0
                return VoiceEvent("request", tail)
            self.armed_until = current + self.timeout
            return VoiceEvent("wake")
        if current <= self.armed_until:
            self.armed_until = 0.0
            return VoiceEvent("request", text)
        return None


class VoiceService:
    def __init__(self, *, remote: bool = False, muted: bool = False, model: Path | None = None,
                 engine: Engine | None = None, on_output: Callable[[str], None] | None = None):
        self.model = model or voice_model_path(read_config())
        self.engine = engine or Engine(remote=remote)
        self.muted = muted
        self.on_output = on_output
        self.router = WakeRouter()
        self.frames: queue.Queue[bytes] = queue.Queue(maxsize=32)
        self.stop_event = threading.Event()
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="Kairo Voice")
        self.active: Future | None = None
        self.generation = 0

    def _notify(self, message: str) -> None:
        print(message, flush=True)
        if self.on_output is not None:
            self.on_output(message)

    def _speak(self, text: str) -> None:
        if self.muted:
            return
        try:
            import pyttsx3
            speaker = pyttsx3.init()
            speaker.say(text[:300])
            speaker.runAndWait()
            speaker.stop()
        except Exception:
            # Text output remains usable when a platform TTS driver is missing.
            pass

    def accept_text(self, transcript: str, now: float | None = None) -> VoiceEvent | None:
        event = self.router.accept(transcript, now)
        if event is None:
            return None
        if event.kind == "wake":
            self._notify("Listening…")
        elif event.kind == "stop":
            self.generation += 1
            if self.active:
                self.active.cancel()
            self.engine.qwen.close()  # Best effort: abort a running local generation.
            self._notify("Stop requested.")
        elif event.kind == "request":
            if self.active is not None and not self.active.done():
                self._notify("Still working; say 'Kairo, stop' to cancel.")
            else:
                self.active = self.worker.submit(self._perform, event.text, self.generation)
        return event

    def _perform(self, text: str, generation: int) -> None:
        try:
            result = self.engine.ask(text)
            if generation != self.generation:
                return
            self._notify(f"{result.text}\n[{result.route}; {result.location}]")
            self._speak(result.text if len(result.text) < 200 else "Done.")
        except Exception as exc:
            if generation != self.generation:
                return
            self._notify(f"Kairo: {exc}")
            self._speak("I could not complete that.")

    def listen(self) -> None:
        if not self.model.is_dir():
            raise VoiceError(f"Offline Vosk model missing: {self.model}")
        try:
            import sounddevice as sd
            from vosk import KaldiRecognizer, Model, SetLogLevel
        except ImportError as exc:
            raise VoiceError("Install voice support: pip install '.[voice]'") from exc
        SetLogLevel(-1)
        recognizer = KaldiRecognizer(Model(str(self.model)), 16000)

        def capture(indata, frames, timing, status) -> None:
            try:
                self.frames.put_nowait(bytes(indata))
            except queue.Full:
                pass  # Bound memory when the CPU cannot keep up with the mic.

        self._notify("Offline voice listening. Say 'Kairo' followed by a command. Ctrl+C stops.")
        try:
            with sd.RawInputStream(samplerate=16000, blocksize=4000, channels=1,
                                   dtype="int16", callback=capture):
                while not self.stop_event.is_set():
                    try:
                        audio = self.frames.get(timeout=0.25)
                    except queue.Empty:
                        continue
                    if recognizer.AcceptWaveform(audio):
                        transcript = json.loads(recognizer.Result()).get("text", "")
                        if transcript:
                            self.accept_text(transcript)
        except KeyboardInterrupt:
            pass
        finally:
            self.close()

    def close(self) -> None:
        self.stop_event.set()
        self.worker.shutdown(wait=False, cancel_futures=True)
        self.engine.close()
