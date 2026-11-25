"""Локальный тестовый двойник Chat Completions для ручной проверки."""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Fixture(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        text = payload["messages"][-1]["content"]
        status = 200
        if text == "сбой":
            status, raw = 503, b"{}"
        elif text == "невалидный JSON":
            raw = b"broken"
        else:
            if text == "таймаут":
                time.sleep(10)
            raw = json.dumps({"choices": [{"message": {
                "content": "  Команда добавила кеш и проверила сервис.  "}}]}).encode()
        self.send_response(status)
        self.end_headers()
        try:
            self.wfile.write(raw)
        except ConnectionError:
            pass


if __name__ == "__main__":
    with ThreadingHTTPServer(("127.0.0.1", 8091), Fixture) as server:
        server.serve_forever()
