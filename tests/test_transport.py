import socket
import time
import unittest
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler
from threading import Thread
from unittest.mock import patch
from urllib.request import ProxyHandler, build_opener

from config.settings import Settings
from llm.client import ProviderError, extract, fetch
from llm.prompt import build
from tests.provider import Fixture


class SlowProvider(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        time.sleep(0.12)


class Transport(unittest.TestCase):
    def exchange(self, fixture, text):
        settings = Settings(key="demo", url="http://fixture/v1/chat/completions", timeout=0.05)
        threads = []

        def connect(conn):
            conn.sock, peer = socket.socketpair()
            conn.sock.settimeout(conn.timeout)

            def serve():
                with peer:
                    fixture(peer, ("local", 0), None)

            thread = Thread(target=serve)
            thread.start()
            threads.append(thread)

        try:
            with patch.object(HTTPConnection, "connect", connect):
                opener = build_opener(ProxyHandler({})).open
                return fetch(settings, build(text, settings), "transport-test",
                             opener=opener, sleep=lambda seconds: None)
        finally:
            for thread in threads:
                thread.join()

    def test_provider_http_success(self):
        self.assertEqual(extract(self.exchange(Fixture, "пример")), "Команда добавила кеш и проверила сервис.")

    def test_actual_read_timeout(self):
        with self.assertRaisesRegex(ProviderError, "TimeoutError"):
            self.exchange(SlowProvider, "таймаут")
