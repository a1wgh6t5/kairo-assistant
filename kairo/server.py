"""Desktop listener: authenticated, pinned TLS and explicit schema checks."""
from __future__ import annotations

import json
import ssl
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys

from .audit import record
from .config import data_dir
from .pairing import authorize
from .tools import REGISTRY, LocalTools, ToolError


class DesktopHandler(BaseHTTPRequestHandler):
    server_version = "KairoDesktop/0.1"

    def log_message(self, fmt: str, *args) -> None:
        # Intentionally do not log requests, headers, paths or document contents.
        pass

    @property
    def tools(self) -> LocalTools:
        return self.server.tools

    def _respond(self, status: int, result: dict) -> None:
        content = json.dumps(result).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def _authorized(self) -> bool:
        value = self.headers.get("Authorization", "")
        if not value.startswith("Bearer "):
            return False
        return authorize(value[7:])

    def do_GET(self) -> None:
        if not self._authorized():
            return self._respond(401, {"error": "Unauthorized"})
        if self.path == "/health":
            return self._respond(200, {"status": "ok", "device": "desktop"})
        self._respond(404, {"error": "Unknown endpoint"})

    def do_POST(self) -> None:
        if not self._authorized():
            return self._respond(401, {"error": "Unauthorized"})
        if self.path != "/v1/action":
            return self._respond(404, {"error": "Unknown endpoint"})
        started = time.monotonic()
        action = "invalid"
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                raise ToolError("Invalid request size")
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict) or set(request) != {"tool", "arguments", "confirmed"}:
                raise ToolError("Invalid action request")
            if type(request["confirmed"]) is not bool:
                raise ToolError("Confirmation must be a boolean")
            action = request["tool"] if isinstance(request["tool"], str) and request["tool"] in REGISTRY else "invalid"
            result = self.tools.execute(request["tool"], request["arguments"], confirmed=request["confirmed"])
        except (ToolError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            record("desktop_remote", action, False, int((time.monotonic() - started) * 1000), exc)
            return self._respond(400, {"error": str(exc)})
        record("desktop_remote", action, True, int((time.monotonic() - started) * 1000))
        self._respond(200, result)


class DesktopHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        # Clients reject a wrong certificate pin and close before HTTP begins.
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError, ssl.SSLEOFError)):
            return
        super().handle_error(request, client_address)


def serve_desktop(host: str = "0.0.0.0", port: int = 18443, tools: LocalTools | None = None) -> None:
    base = data_dir()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(base / "desktop-cert.pem"), str(base / "desktop-key.pem"))
    with DesktopHTTPServer((host, port), DesktopHandler) as server:
        server.tools = tools or LocalTools()
        server.socket = context.wrap_socket(server.socket, server_side=True)
        print(f"Kairo desktop listening on {host}:{port}; press Ctrl+C to stop", flush=True)
        try:
            server.serve_forever(poll_interval=0.2)
        finally:
            server.tools.close()
