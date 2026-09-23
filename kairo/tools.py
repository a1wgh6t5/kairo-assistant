"""Small, explicit desktop tool allowlist. No model text reaches a shell."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


class ToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    risk: str
    description: str
    confirmed: bool = False


REGISTRY = {
    "open_downloads": ToolSpec("low", "Open Downloads in the system file manager"),
    "list_files": ToolSpec("low", "List the newest files in Downloads"),
    "read_text": ToolSpec("low", "Read a selected text file under the user's home"),
    "move_file": ToolSpec("medium", "Move a file within the user's home", True),
    "browser_navigate": ToolSpec("low", "Open a web URL in Kairo's browser"),
    "browser_read": ToolSpec("low", "Read visible text on the current web page"),
    "browser_click": ToolSpec("high", "Click an exact named browser element", True),
    "browser_fill": ToolSpec("high", "Fill a labeled browser field", True),
    "browser_close": ToolSpec("low", "Close Kairo's browser"),
}


class LocalTools:
    def __init__(self, home: Path | None = None, browser=None):
        self.home = (home or Path.home()).expanduser().resolve()
        self._browser = browser

    def _within_home(self, raw: str) -> Path:
        if not raw or "\x00" in raw:
            raise ToolError("Invalid path")
        path = Path(raw).expanduser().resolve()
        if not path.is_relative_to(self.home):
            raise ToolError("Path is outside the home directory")
        return path

    def execute(self, name: str, args: dict | None = None, *, confirmed: bool = False) -> dict:
        if name not in REGISTRY:
            raise ToolError("Unknown tool")
        if not isinstance(args, dict):
            raise ToolError("Tool arguments must be an object")
        expected = {"open_downloads": set(), "list_files": set(), "read_text": {"path"},
                    "move_file": {"source", "destination"}, "browser_navigate": {"url"},
                    "browser_read": set(), "browser_click": {"role", "name"},
                    "browser_fill": {"label", "text"}, "browser_close": set()}[name]
        if set(args) != expected or any(not isinstance(value, str) for value in args.values()):
            raise ToolError("Invalid tool arguments")
        if REGISTRY[name].confirmed and not confirmed:
            raise ToolError("This action requires an explicit confirmation")
        if name.startswith("browser_"):
            from .browser import BrowserController, BrowserError
            if self._browser is None:
                self._browser = BrowserController()
            try:
                return self._browser.execute(name, args)
            except BrowserError as exc:
                raise ToolError(str(exc)) from exc
        downloads = self.home / "Downloads"
        if name == "open_downloads":
            if not downloads.is_dir():
                raise ToolError("Downloads folder does not exist")
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(downloads)])
            elif os.name == "nt":
                os.startfile(str(downloads))
            else:
                subprocess.Popen(["xdg-open", str(downloads)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"status": "launched", "path": str(downloads)}
        if name == "list_files":
            if not downloads.is_dir():
                raise ToolError("Downloads folder does not exist")
            files = sorted((p for p in downloads.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime, reverse=True)[:20]
            return {"status": "ok", "files": [{"name": p.name, "path": str(p)} for p in files]}
        if name == "read_text":
            path = self._within_home(args["path"])
            if path.suffix.lower() not in {".txt", ".md", ".csv", ".json"} or not path.is_file():
                raise ToolError("Only existing text, Markdown, CSV, and JSON files can be read")
            if path.stat().st_size > 16_000:
                raise ToolError("File exceeds the 16 KB first-release limit")
            return {"status": "ok", "path": str(path), "text": path.read_text(encoding="utf-8")}
        source = self._within_home(args["source"])
        target = self._within_home(args["destination"])
        if not source.is_file() or not target.parent.is_dir() or target.exists() or source == target:
            raise ToolError("Source must be a file; destination directory must exist and destination must be unused")
        shutil.move(str(source), str(target))
        if not target.is_file() or source.exists():
            raise ToolError("Move could not be verified")
        return {"status": "ok", "source": str(source), "destination": str(target)}

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
