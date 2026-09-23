"""A dedicated Playwright browser profile with structured, bounded actions.

The Playwright driver lives on one event-loop thread. Desktop HTTP handler
threads submit work to it, so a browser session survives multiple requests.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from urllib.parse import urlsplit

from .config import data_dir


class BrowserError(RuntimeError):
    pass


ROLES = {"button", "link", "checkbox", "radio", "tab", "menuitem"}


def validate_browser_action(name: str, arguments: dict) -> None:
    if name == "browser_navigate":
        try:
            parts = urlsplit(arguments["url"])
        except ValueError as exc:
            raise BrowserError("Invalid URL") from exc
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            raise BrowserError("Enter a normal http or https URL without embedded credentials")
        if len(arguments["url"]) > 2048:
            raise BrowserError("URL is too long")
    elif name == "browser_click":
        if arguments["role"] not in ROLES or not 0 < len(arguments["name"]) <= 160:
            raise BrowserError("Select a named link, button, tab, or other supported role")
    elif name == "browser_fill":
        if not 0 < len(arguments["label"]) <= 160 or len(arguments["text"]) > 4000:
            raise BrowserError("Select a field label and text of at most 4000 characters")


class BrowserController:
    def __init__(self, profile: Path | None = None):
        self.profile = profile or data_dir() / "browser-profile"
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self.driver = None
        self.context = None
        self.page = None
        self._lock = threading.Lock()

    def _ensure_thread(self) -> None:
        if self.loop is not None:
            return
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True, name="Kairo Browser")
        self.thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _open(self) -> None:
        if self.context is not None:
            return
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise BrowserError("Install browser support: pip install '.[browser]' and playwright install chromium") from exc
        self.profile.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.driver = await async_playwright().start()
        try:
            self.context = await self.driver.chromium.launch_persistent_context(
                str(self.profile), headless=False, accept_downloads=False
            )
            self.context.set_default_timeout(10_000)
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        except Exception as exc:
            await self.driver.stop()
            self.driver = None
            raise BrowserError("Cannot start Chromium; run 'playwright install chromium' on the desktop") from exc

    async def _perform(self, name: str, args: dict) -> dict:
        if name == "browser_close":
            if self.context is not None:
                await self.context.close()
                await self.driver.stop()
                self.context = self.driver = self.page = None
            return {"status": "ok"}
        await self._open()
        try:
            if name == "browser_navigate":
                await self.page.goto(args["url"], wait_until="domcontentloaded", timeout=20_000)
                return {"status": "ok", "url": self.page.url, "title": await self.page.title()}
            if name == "browser_read":
                return {"status": "ok", "url": self.page.url, "title": await self.page.title(),
                        "text": (await self.page.locator("body").inner_text())[:16_000]}
            if name == "browser_click":
                await self.page.get_by_role(args["role"], name=args["name"], exact=True).click()
                return {"status": "ok", "url": self.page.url}
            if name == "browser_fill":
                await self.page.get_by_label(args["label"], exact=True).fill(args["text"])
                return {"status": "ok", "url": self.page.url}
        except Exception as exc:
            raise BrowserError(f"Browser action failed: {type(exc).__name__}") from exc
        raise BrowserError("Unknown browser action")

    def execute(self, name: str, args: dict) -> dict:
        validate_browser_action(name, args)
        with self._lock:
            self._ensure_thread()
            future = asyncio.run_coroutine_threadsafe(self._perform(name, args), self.loop)
            try:
                return future.result(timeout=28)
            except TimeoutError as exc:
                future.cancel()
                raise BrowserError("Browser action timed out") from exc

    def close(self) -> None:
        with self._lock:
            if self.loop is None:
                return
            future = asyncio.run_coroutine_threadsafe(self._perform("browser_close", {}), self.loop)
            try:
                future.result(timeout=8)
            except Exception:
                pass
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=3)
            if not self.thread.is_alive():
                self.loop.close()
            self.loop = self.thread = None
