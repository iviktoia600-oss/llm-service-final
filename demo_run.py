"""Показывает настоящие ответы обработчика с тестовым транспортом провайдера."""
import io
import json
import logging
from urllib.error import URLError

from api.routes import routes
from config.events import logger
from config.settings import Settings
from llm.client import fetch
from services.summary import SummaryService
from tests.test_pipeline import MESSAGE, post, success


def main():
    logs = io.StringIO()
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler(logs))

    def send(request, timeout):
        text = json.loads(request.data)["messages"][1]["content"]
        if text == "сбой сети":
            raise URLError(ConnectionRefusedError())
        if text == "таймаут":
            raise TimeoutError()
        return success()

    def provider(settings, payload, rid):
        return fetch(settings, payload, rid, opener=send)

    handler = routes(SummaryService(Settings(key="fixture"), provider))
    for payload in ({"message": MESSAGE}, {"message": MESSAGE}, {},
                    {"message": "сбой сети"}, {"message": "таймаут"}):
        print("POST /chat", json.dumps(payload, ensure_ascii=False), flush=True)
        status, body, rid = post(handler, payload)
        print("HTTP", status, json.dumps(body, ensure_ascii=False))
        for line in logs.getvalue().splitlines():
            row = json.loads(line)
            if row["request_id"] == rid and row["event"] in (
                    "cache_miss", "cache_hit", "provider_error", "retry", "fallback"):
                print(" ", row["event"], row.get("reason", row.get("delay_s", "")))
        print(flush=True)


if __name__ == "__main__":
    main()
