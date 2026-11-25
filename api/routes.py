import json
import uuid
from http.server import BaseHTTPRequestHandler

from config.events import event, stage
from llm.client import ProviderError


class Invalid(Exception):
    pass


def validate(raw):
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError) as exc:
        raise Invalid("Требуется корректный JSON в UTF-8.") from exc
    message = data.get("message") if isinstance(data, dict) else None
    if not isinstance(message, str) or not message.strip():
        raise Invalid("Поле message должно быть непустой строкой.")
    if len(message) > 1000:
        raise Invalid("Максимальная длина message — 1000 символов.")
    try:
        message.encode("utf-8")
    except UnicodeError as exc:
        raise Invalid("Некорректный символ Unicode.") from exc
    return message.strip()


def routes(service):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # События запроса записываются в JSON ниже.

        def do_POST(self):
            rid = uuid.uuid4().hex
            with stage(rid, "request"):
                event(rid, "incoming", method="POST", path=self.path[:200])
                try:
                    if self.path != "/chat":
                        status, body = 404, {"error": "Маршрут не найден."}
                    else:
                        with stage(rid, "validation"):
                            try:
                                length = int(self.headers.get("Content-Length", ""))
                            except ValueError as exc:
                                raise Invalid("Требуется Content-Length.") from exc
                            if not 0 < length <= 16384:
                                raise Invalid("Тело запроса должно занимать от 1 до 16384 байт.")
                            raw = self.rfile.read(length)
                            message = validate(raw)
                            event(rid, "input", message=message)
                        with stage(rid, "summarization"):
                            body = service.summarize(message, rid)
                        status = 200
                except Invalid as exc:
                    event(rid, "validation_error", reason=str(exc))
                    status, body = 400, {"error": str(exc)}
                except ProviderError as exc:
                    event(rid, "fallback", reason=str(exc))
                    status, body = 503, {"error": "Сервис временно недоступен, попробуйте позже."}
                with stage(rid, "response"):
                    data = json.dumps(body, ensure_ascii=False).encode()
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("X-Request-ID", rid)
                    self.end_headers()
                    self.wfile.write(data)
                    event(rid, "response_sent", status=status)
    return Handler
