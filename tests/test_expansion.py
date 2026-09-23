import difflib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from kairo import repair
from kairo.browser import BrowserController, validate_browser_action
from kairo.engine import Answer
from kairo.tools import LocalTools, ToolError
from kairo.voice import WakeRouter, VoiceService


class VoiceTests(unittest.TestCase):
    def test_wake_follow_up_timeout_and_same_utterance(self):
        router = WakeRouter(timeout=8)
        self.assertIsNone(router.accept("open downloads", now=100))
        self.assertEqual(router.accept("Kairo", now=100).kind, "wake")
        self.assertEqual(router.accept("list Downloads", now=106).text, "list Downloads")
        self.assertIsNone(router.accept("list Downloads", now=107))
        self.assertEqual(router.accept("Cairo, open Downloads", now=108).text, "open Downloads")
        router.accept("Kairo", now=200)
        self.assertIsNone(router.accept("list Downloads", now=209))
        self.assertEqual(router.accept("stop", now=210).kind, "stop")

    def test_voice_dispatches_one_command_after_wake(self):
        observed = []
        class FakeEngine:
            qwen = type("Q", (), {"close": lambda _: None})()
            def ask(self, text):
                observed.append(text)
                return Answer("Done.", "rule", "local")
            def close(self):
                pass
        voice = VoiceService(engine=FakeEngine(), muted=True, on_output=observed.append)
        try:
            voice.accept_text("Kairo", now=2)
            voice.accept_text("list Downloads", now=3)
            voice.active.result(timeout=2)
            self.assertIn("list Downloads", observed)
            self.assertTrue(any("Done." in message for message in observed))
        finally:
            voice.close()


class BrowserTests(unittest.TestCase):
    def test_browser_needs_structured_targets_and_confirmation(self):
        class FakeBrowser:
            def execute(self, action, arguments):
                validate_browser_action(action, arguments)
                return {"status": "ok", "action": action}

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            tools = LocalTools(Path(tmp), browser=FakeBrowser())
            self.assertEqual(tools.execute("browser_navigate", {"url": "https://example.org"})["status"], "ok")
            with self.assertRaises(ToolError):
                tools.execute("browser_navigate", {"url": "file:///etc/passwd"})
            with self.assertRaises(ToolError):
                tools.execute("browser_click", {"role": "button", "name": "Buy now"})
            self.assertEqual(tools.execute("browser_click", {"role": "button", "name": "Buy now"},
                                           confirmed=True)["status"], "ok")
            with self.assertRaises(ToolError):
                tools.execute("browser_click", {"role": "script", "name": "foo"}, confirmed=True)

    def test_browser_driver_retains_page_across_actions(self):
        class Page:
            url = "about:blank"
            async def goto(self, url, **kwargs):
                self.url = url
            async def title(self):
                return "Example"
            def locator(self, name):
                return self
            async def inner_text(self):
                return "Readable page"
            def get_by_role(self, *args, **kwargs):
                return self
            def get_by_label(self, *args, **kwargs):
                return self
            async def click(self):
                pass
            async def fill(self, text):
                self.filled = text
        page = Page()
        class Context:
            pages = [page]
            def set_default_timeout(self, ms):
                pass
            async def close(self):
                pass
        class Chromium:
            async def launch_persistent_context(self, *args, **kwargs):
                return Context()
        class Driver:
            chromium = Chromium()
            async def stop(self):
                pass
        class Launcher:
            async def start(self):
                return Driver()
        module = types.ModuleType("playwright.async_api")
        module.async_playwright = Launcher
        package = types.ModuleType("playwright")
        package.__path__ = []
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {"playwright": package,
                                                                          "playwright.async_api": module}):
            browser = BrowserController(Path(tmp) / "profile")
            try:
                self.assertEqual(browser.execute("browser_navigate", {"url": "https://example.org"})["title"], "Example")
                self.assertEqual(browser.execute("browser_read", {})["text"], "Readable page")
                browser.execute("browser_fill", {"label": "Search", "text": "Kairo"})
                self.assertEqual(page.filled, "Kairo")
            finally:
                browser.close()


class RepairTests(unittest.TestCase):
    def test_stage_approve_and_rollback_on_disposable_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            (root / "kairo").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / "kairo" / "voice.py").write_text("VALUE = 1\n")
            (root / "tests" / "test_dummy.py").write_text(
                "import unittest\nclass Dummy(unittest.TestCase):\n    def test_truth(self): self.assertTrue(True)\n")
            first = "VALUE = 1\n"
            second = "VALUE = 2\n"
            diff = "".join(difflib.unified_diff(first.splitlines(True), second.splitlines(True),
                                                fromfile="a/kairo/voice.py", tofile="b/kairo/voice.py"))
            with patch.dict(os.environ, {"KAIRO_DATA_DIR": str(Path(tmp) / "data")}), \
                 patch.object(repair, "ROOT", root):
                candidate = repair.stage(diff)
                self.assertEqual((root / "kairo" / "voice.py").read_text(), first)
                with patch.object(repair, "_test_command", return_value=None):
                    self.assertEqual(repair.verify(candidate["id"])["status"], "sandbox unavailable")
                    with self.assertRaises(repair.RepairError):
                        repair.apply(candidate["id"], approve=True)
                self.assertEqual(repair.verify(candidate["id"], trusted_run=True)["status"], "passed")
                with self.assertRaises(repair.RepairError):
                    repair.apply(candidate["id"])
                self.assertEqual(repair.apply(candidate["id"], approve=True)["status"], "applied")
                self.assertEqual((root / "kairo" / "voice.py").read_text(), second)
                self.assertEqual(repair.rollback()["status"], "rolled back")
                self.assertEqual((root / "kairo" / "voice.py").read_text(), first)
                with self.assertRaises(repair.RepairError):
                    repair.stage(diff.replace("voice.py", "secrets.py"))


if __name__ == "__main__":
    unittest.main()
