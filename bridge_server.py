"""Local HTTP bridge used by the browser extension.

The macOS app starts this server on 127.0.0.1. Browser extensions can send a
POST request to /chat, and the server uses the API key saved by the desktop app
to call OpenAI.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional

from openai_client import ChatMessage, OpenAIChatClient, user_friendly_error


class LocalChatBridge:
    """A small localhost JSON API for extension-to-app chat requests."""

    def __init__(
        self,
        api_key_provider: Callable[[], str],
        model_provider: Callable[[], str],
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        self.api_key_provider = api_key_provider
        self.model_provider = model_provider
        self.host = host
        self.port = port
        self._history: list[ChatMessage] = []
        self._lock = threading.Lock()
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> None:
        if self._server is not None:
            return

        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib method name
                self._send_json({"ok": True})

            def do_GET(self) -> None:  # noqa: N802 - stdlib method name
                if self.path == "/health":
                    self._send_json({"ok": True, "service": "OpenAI Chat Bridge"})
                    return
                self._send_json({"error": "Not found"}, status=404)

            def do_POST(self) -> None:  # noqa: N802 - stdlib method name
                if self.path != "/chat":
                    self._send_json({"error": "Not found"}, status=404)
                    return

                try:
                    payload = self._read_json()
                    message = str(payload.get("message", "")).strip()
                    if not message:
                        self._send_json({"error": "Missing message"}, status=400)
                        return

                    reply = bridge.chat(message, reset=bool(payload.get("reset", False)))
                    self._send_json({"reply": reply})
                except Exception as exc:
                    self._send_json({"error": user_friendly_error(exc)}, status=502)

            def log_message(self, format: str, *args) -> None:  # noqa: A002
                return

            def _read_json(self) -> dict:
                length = int(self.headers.get("Content-Length", "0"))
                raw_body = self.rfile.read(length).decode("utf-8") if length else "{}"
                return json.loads(raw_body or "{}")

            def _send_json(self, payload: dict, status: int = 200) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        self._server = None
        self._thread = None

    def chat(self, message: str, reset: bool = False) -> str:
        api_key = self.api_key_provider().strip()
        if not api_key:
            raise ValueError("Missing OpenAI API key. Open the desktop app and save your key first.")

        with self._lock:
            if reset:
                self._history.clear()

            self._history.append(ChatMessage(role="user", content=message))
            client = OpenAIChatClient(api_key, self.model_provider())
            reply = client.send_message(self._history)
            self._history.append(ChatMessage(role="assistant", content=reply))
            return reply

    def clear_history(self) -> None:
        with self._lock:
            self._history.clear()
