import copy
import io
import json
import logging
import socket
import unittest
from http.client import HTTPConnection
from threading import Thread
from urllib.error import HTTPError, URLError
from unittest.mock import Mock

from api.routes import routes, validate
from cache.results import Cache, key_for
from config.events import logger
from config.settings import Settings
from llm.client import fetch
from llm.prompt import build
from services.summary import SummaryService

MESSAGE = "Команда добавила кеш. Затем команда проверила сервис."
MODEL_REPLY = {"choices": [{"message": {"content": "  Команда добавила кеш и проверила сервис.  "}}]}


def post(handler, payload):
    # Реальный HTTP/1.1 по локальной паре сокетов без привязки к порту.
    client, server = socket.socketpair()
    with client, server:
        thread = Thread(target=handler, args=(server, ("local", 0), None))
        thread.start()
        conn = HTTPConnection("localhost", timeout=2)
        client.settimeout(conn.timeout)
        conn.sock = client
        try:
            data = json.dumps(payload, ensure_ascii=False).encode()
            conn.request("POST", "/chat", body=data, headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            return response.status, json.loads(response.read()), response.getheader("X-Request-ID")
        finally:
            conn.close()
            thread.join(timeout=2)


def success():
    return io.BytesIO(json.dumps(MODEL_REPLY).encode())


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.opener = Mock(side_effect=lambda *a, **kw: success())
        self.sleep = Mock()
        settings = Settings(key="test-key")

        def provider(cfg, payload, rid):
            return fetch(cfg, payload, rid, self.opener, self.sleep)

        self.handler = routes(SummaryService(settings, provider))
        self.logs = io.StringIO()
        self.sink = logging.StreamHandler(self.logs)
        logger.setLevel(logging.INFO)
        logger.addHandler(self.sink)
        self.addCleanup(logger.removeHandler, self.sink)

    def events(self):
        return [json.loads(line) for line in self.logs.getvalue().splitlines()]

    def call(self, payload):
        return post(self.handler, payload)

    def test_success_and_cache(self):
        status, body, rid = self.call({"message": MESSAGE})
        self.assertEqual((status, body), (200, {"answer": "Команда добавила кеш и проверила сервис.", "cached": False}))
        self.assertEqual(self.call({"message": MESSAGE})[1], dict(body, cached=True))
        self.assertEqual(self.opener.call_count, 1)
        events = self.events()
        self.assertEqual([e["event"] for e in events if e["event"] in ("cache_hit","cache_miss")],
                         ["cache_miss", "cache_hit"])
        self.assertTrue(any(e["request_id"] == rid and "elapsed_ms" in e for e in events))
        req = self.opener.call_args.args[0]
        self.assertEqual(json.loads(req.data)["messages"][1]["content"], MESSAGE)
        self.assertEqual(self.opener.call_args.kwargs["timeout"], Settings.timeout)

    def test_validation(self):
        for payload in ({}, {"message": " "}, {"message": 2}, {"message": "а"*1001}, []):
            with self.subTest(payload=str(payload)[:25]):
                self.assertEqual(self.call(payload)[0], 400)
        self.opener.assert_not_called()
        self.assertEqual(len(validate(json.dumps({"message": "а"*1000}).encode())), 1000)

    def test_connection_failure_and_recovery(self):
        self.opener.side_effect = URLError(ConnectionRefusedError())
        self.assertEqual(self.call({"message": MESSAGE})[0], 503)
        self.assertEqual(self.opener.call_count, 3)
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [0.25, 0.5])
        self.opener.side_effect = lambda *a, **kw: success()
        self.assertFalse(self.call({"message": MESSAGE})[1]["cached"])

    def test_timeout(self):
        self.opener.side_effect = TimeoutError()
        self.assertEqual(self.call({"message": MESSAGE})[0], 503)
        self.assertEqual(self.opener.call_count, 3)

    def test_transient_http(self):
        self.opener.side_effect = [HTTPError("url", 503, "", {}, io.BytesIO()), success()]
        self.assertEqual(self.call({"message": MESSAGE})[0], 200)
        self.assertEqual(self.opener.call_count, 2)

    def test_permanent_http(self):
        self.opener.side_effect = HTTPError("url", 401, "", {}, io.BytesIO())
        self.assertEqual(self.call({"message": MESSAGE})[0], 503)
        self.assertEqual(self.opener.call_count, 1)

    def test_invalid_provider_reply(self):
        for raw in (b"broken", b"{}", b'{"choices":[{"message":{"content":" "}}]}'):
            self.opener.reset_mock()
            self.opener.side_effect = [io.BytesIO(raw)]
            self.assertEqual(self.call({"message": MESSAGE})[0], 503)
            self.assertEqual(self.opener.call_count, 1)

    def test_ttl(self):
        now = [1]
        cache = Cache(600, clock=lambda: now[0])
        cache.put("a", "b")
        now[0] += 599
        self.assertEqual(cache.get("a"), "b")
        now[0] += 1
        self.assertIsNone(cache.get("a"))

    def test_cache_key(self):
        payload = build(MESSAGE, Settings())
        keys = {key_for("url", payload)}
        for field, val in (("model", "another"), ("temperature", 0.8)):
            keys.add(key_for("url", dict(payload, **{field: val})))
        for idx in (0, 1):
            other = copy.deepcopy(payload)
            other["messages"][idx]["content"] += "!"
            keys.add(key_for("url", other))
        self.assertEqual(len(keys), 5)
