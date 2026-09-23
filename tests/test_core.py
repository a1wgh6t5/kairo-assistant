import os
import json
import ssl
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from kairo.engine import Engine
from kairo.pairing import PairingError, PeerClient, init_desktop
from kairo.providers import LayaLocal, QwenLocal
from kairo.routines import get, save
from kairo.server import DesktopHTTPServer, DesktopHandler
from kairo.tools import LocalTools, ToolError


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        (self.home / "Downloads").mkdir(parents=True)
        (self.home / "Documents").mkdir()
        self.tools = LocalTools(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def test_move_requires_confirmation_and_verifies(self):
        source = self.home / "Downloads" / "paper.md"
        destination = self.home / "Documents" / "paper.md"
        source.write_text("test")
        arguments = {"source": str(source), "destination": str(destination)}
        with self.assertRaises(ToolError):
            self.tools.execute("move_file", arguments)
        self.assertTrue(source.exists())
        self.assertEqual(self.tools.execute("move_file", arguments, confirmed=True)["status"], "ok")
        self.assertFalse(source.exists())
        self.assertEqual(destination.read_text(), "test")

    def test_paths_cannot_escape_home_even_through_symlink(self):
        outside = Path(self.tmp.name) / "private.md"
        outside.write_text("secret")
        (self.home / "Downloads" / "link.md").symlink_to(outside)
        with self.assertRaises(ToolError):
            self.tools.execute("read_text", {"path": str(outside)})
        with self.assertRaises(ToolError):
            self.tools.execute("read_text", {"path": str(self.home / "Downloads" / "link.md")})

    def test_known_rules_never_load_models(self):
        with patch.dict(os.environ, {"KAIRO_DATA_DIR": str(self.home)}):
            engine = Engine(local_tools=self.tools)
            with patch.object(engine.laya, "choose", side_effect=AssertionError("Laya called")), \
                 patch.object(engine.qwen, "chat", side_effect=AssertionError("Qwen called")):
                answer = engine.ask("Kairo, list my Downloads")
                self.assertEqual(answer.route, "rule")

    def test_routine_is_saved_only_after_success(self):
        with patch.dict(os.environ, {"KAIRO_DATA_DIR": str(self.home)}):
            engine = Engine(local_tools=self.tools)
            engine.ask("list Downloads")
            save("my_downloads")
            self.assertEqual(get("my_downloads")["action"], "list_files")


class PairClientTests(unittest.TestCase):
    def test_fingerprint_validation(self):
        with self.assertRaises(PairingError):
            PeerClient("http://example.com", "0" * 64, "token")
        with self.assertRaises(PairingError):
            PeerClient("https://example.com", "bad", "token")

    def test_tls_round_trip_and_wrong_pin(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"KAIRO_DATA_DIR": tmp}):
            home = Path(tmp) / "home"
            (home / "Downloads").mkdir(parents=True)
            (home / "Downloads" / "paper.md").write_text("local")
            token, pin = init_desktop()
            tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tls.load_cert_chain(str(Path(tmp) / "desktop-cert.pem"), str(Path(tmp) / "desktop-key.pem"))
            server = DesktopHTTPServer(("127.0.0.1", 0), DesktopHandler)
            server.tools = LocalTools(home)
            server.socket = tls.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"https://127.0.0.1:{server.server_port}"
                peer = PeerClient(url, pin, token)
                self.assertEqual(peer.request("/health")["status"], "ok")
                action = {"tool": "list_files", "arguments": {}, "confirmed": False}
                self.assertEqual(peer.request("/v1/action", action)["files"][0]["name"], "paper.md")
                with self.assertRaisesRegex(PairingError, "Unauthorized"):
                    PeerClient(url, pin, "wrong-token").request("/health")
                with self.assertRaisesRegex(PairingError, "fingerprint mismatch"):
                    PeerClient(url, "0" * 64, token).request("/health")
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_laya_uses_local_directory_and_offline_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_agent = type("FakeAgent", (), {"predict": lambda _, state, question: {
                "answers": {"intent": {"choice": "chat", "confidence": .96}}}})()
            fake_laya = type("FakeLaya", (), {"load": lambda _, location: fake_agent})()
            with patch.dict("sys.modules", {"laya": fake_laya}):
                provider = LayaLocal(Path(tmp))
                self.assertEqual(provider.choose("hello", {"chat": "Talk"})[0], "chat")
                self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")


class LocalModelAdapterTests(unittest.TestCase):
    def test_qwen_requests_loopback_chat_endpoint(self):
        observed = []
        class FakeModelHandler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                body = (json.dumps({"model_path": str(model)}) if self.path == "/props" else
                        '{"status":"ok"}').encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                observed.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                body = b'{"choices":[{"message":{"content":"Local reply"}}]}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeModelHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                model = Path(tmp) / "qwen.gguf"
                model.write_bytes(b"pretend gguf")
                provider = QwenLocal(model, port=server.server_port)
                provider.process = type("FakeProcess", (), {"poll": lambda _: None})()
                self.assertEqual(provider.chat("Summarize", "some document"), "Local reply")
                self.assertEqual(observed[0][0], "/v1/chat/completions")
                self.assertEqual(observed[0][1]["model"], "kairo-qwen")
                self.assertIn("some document", observed[0][1]["messages"][1]["content"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_two_clients_share_one_warm_qwen_server(self):
        class Process:
            stopped = False
            def poll(self):
                return 0 if self.stopped else None
            def terminate(self):
                self.stopped = True
            def wait(self, timeout):
                return 0
        with tempfile.TemporaryDirectory() as tmp:
            model = Path(tmp) / "qwen.gguf"
            model.write_bytes(b"model")
            owner = QwenLocal(model, port=18441)
            peer = QwenLocal(model, port=18441)
            process = Process()
            key = (str(model.resolve()), 18441)
            with patch.object(QwenLocal, "healthy", return_value=True), \
                 patch.object(QwenLocal, "_matching_model", return_value=True):
                owner.process = process
                owner._registered = True
                QwenLocal._shared[key] = {"process": process, "refs": 1}
                peer.prewarm()
                self.assertEqual(QwenLocal._shared[key]["refs"], 2)
                peer.close()
                self.assertFalse(process.stopped)
                owner.close()
                self.assertTrue(process.stopped)


if __name__ == "__main__":
    unittest.main()
