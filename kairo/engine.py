"""Deterministic command routing with local typed decisions for ambiguous text."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

from .config import model_paths, read_config
from .audit import record
from .pairing import configured_peer
from .providers import INTENTS, JevCloud, LayaLocal, ProviderUnavailable, QwenLocal
from .routines import remember
from .secrets import get_secret
from .tools import LocalTools, ToolError


@dataclass
class Answer:
    text: str
    route: str
    location: str


class Engine:
    def __init__(self, *, remote: bool = False, local_tools: LocalTools | None = None):
        self.remote = remote
        self.tools = local_tools or LocalTools()
        cfg = read_config()
        laya_dir, qwen_file = model_paths(cfg)
        self.laya = LayaLocal(laya_dir)
        self.qwen = QwenLocal(qwen_file, binary=cfg.get("llama_server", "llama-server"),
                               port=cfg.get("qwen_port", 18080))

    def _tool(self, action: str, args: dict | None = None, *, confirmed: bool = False) -> dict:
        arguments = args or {}
        started = time.monotonic()
        try:
            if self.remote:
                result = configured_peer().request("/v1/action", {"tool": action, "arguments": arguments,
                                                                    "confirmed": confirmed})
            else:
                result = self.tools.execute(action, arguments, confirmed=confirmed)
        except Exception as exc:
            record("remote_tool" if self.remote else "tool", action, False,
                   int((time.monotonic() - started) * 1000), exc)
            raise
        record("remote_tool" if self.remote else "tool", action, True,
               int((time.monotonic() - started) * 1000))
        if result.get("status") not in {"ok", "launched"}:
            raise ToolError("Action did not complete")
        remember(action, arguments, self.remote)
        return result

    def tool(self, action: str, args: dict, *, confirmed: bool = False) -> Answer:
        result = self._tool(action, args, confirmed=confirmed)
        return Answer(str(result), "tool", "paired desktop" if self.remote else "this computer")

    def ask(self, text: str, *, file: str | None = None, allow_jev: bool = False,
            chat: bool = False) -> Answer:
        prompt = re.sub(r"^\s*kairo[,:]?\s*", "", text.strip(), flags=re.I)
        if not prompt:
            raise ValueError("Enter a request")
        if chat:
            return Answer(self.qwen.chat(prompt), "Qwen", "LOCAL")
        normalized = prompt.lower().strip(" .!?")
        browser_url = re.fullmatch(r"(?:open|visit|go to)\s+(https?://\S+)", prompt.strip(), flags=re.I)
        if browser_url:
            result = self._tool("browser_navigate", {"url": browser_url.group(1)})
            return Answer(f"Opened {result['url']}", "rule", "paired desktop" if self.remote else "this computer")
        if normalized in {"read this page", "read the page", "summarize this page"}:
            result = self._tool("browser_read")
            if normalized.startswith("summarize"):
                return Answer(self.qwen.chat("Summarize this web page.", result["text"]), "rule → Qwen",
                              "LOCAL on Kairo Node" if self.remote else "LOCAL on this computer")
            return Answer(result["text"], "rule", "paired desktop" if self.remote else "this computer")
        if re.fullmatch(r"(open|show)( my| the)? downloads( folder| directory)?", normalized):
            intent, route = "open_downloads", "rule"
        elif re.fullmatch(r"(list|show)( the| my)? (files in )?downloads( folder| directory)?", normalized):
            intent, route = "list_files", "rule"
        elif file and re.match(r"^(summarize|explain|describe|what is in)\b", normalized):
            intent, route = "summarize_file", "rule"
        else:
            try:
                intent, confidence = self.laya.choose(prompt, INTENTS)
                route = "Laya LOCAL"
            except ProviderUnavailable:
                key = get_secret("jev") if allow_jev else None
                if not key:
                    raise ProviderUnavailable("No local Laya checkpoint; install it, or use explicit --chat for local Qwen")
                intent, confidence = JevCloud(key).choose(prompt, INTENTS)
                route = "Jev CLOUD"
            if confidence < 0.75:
                raise ValueError(f"Intent confidence too low ({confidence:.2f}); give a more specific command")
        if intent == "open_downloads":
            self._tool("open_downloads")
            return Answer("Opened Downloads.", route, "paired desktop" if self.remote else "this computer")
        if intent == "list_files":
            result = self._tool("list_files")
            return Answer("\n".join(f["name"] for f in result["files"]) or "Downloads is empty.", route,
                          "paired desktop" if self.remote else "this computer")
        if intent == "summarize_file":
            if not file:
                raise ValueError("Select a text file with --file")
            result = self._tool("read_text", {"path": file})
            return Answer(self.qwen.chat("Summarize this file in a few sentences.", result["text"]),
                          f"{route} → Qwen", "LOCAL on Kairo Node" if self.remote else "LOCAL on this computer")
        if intent == "chat":
            return Answer(self.qwen.chat(prompt), f"{route} → Qwen", "LOCAL")
        raise ValueError("That command is outside the tools currently implemented")

    def close(self) -> None:
        self.qwen.close()
        self.tools.close()
