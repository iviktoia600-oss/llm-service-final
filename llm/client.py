import http.client
import json
import errno
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from config.events import event, stage


class ProviderError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(settings, payload, rid, opener=None, sleep=time.sleep):
    if not settings.key:
        raise ProviderError("missing_key")
    send = opener or build_opener(NoRedirect()).open
    request = Request(settings.url, data=json.dumps(payload).encode(),
                      headers={"Authorization": "Bearer " + settings.key,
                               "Content-Type": "application/json"})
    for attempt in range(1, 4):
        try:
            with stage(rid, "provider_attempt"):
                with send(request, timeout=settings.timeout) as response:
                    raw = response.read(256 * 1024 + 1)
                    if len(raw) > 256 * 1024:
                        raise ProviderError("response_too_large")
                    return raw
        except HTTPError as exc:
            code = exc.code
            exc.close()
            reason = f"http_{code}"
            temporary = code in (408, 429) or 500 <= code < 600
        except URLError as exc:
            cause = exc.reason
            reason = "TimeoutError" if isinstance(cause, socket.timeout) else type(cause).__name__
            temporary = isinstance(cause, (socket.timeout, TimeoutError, ConnectionError)) or (
                isinstance(cause, OSError) and cause.errno in (
                    socket.EAI_AGAIN, errno.ENETUNREACH, errno.EHOSTUNREACH, errno.ETIMEDOUT))
        except (socket.timeout, TimeoutError, ConnectionError, http.client.IncompleteRead) as exc:
            reason = "TimeoutError" if isinstance(exc, socket.timeout) else type(exc).__name__
            temporary = True
        except (OSError, http.client.HTTPException) as exc:
            raise ProviderError(type(exc).__name__) from exc
        event(rid, "provider_error", attempt=attempt, reason=reason)
        if not temporary or attempt == 3:
            raise ProviderError(reason)
        delay = 0.25 * 2 ** (attempt - 1)
        event(rid, "retry", delay_s=delay)
        sleep(delay)


def extract(raw):
    try:
        value = json.loads(raw)["choices"][0]["message"]["content"]
        if not isinstance(value, str) or not value.strip():
            raise ValueError("empty or non-text content")
        return value.strip()
    except (ValueError, KeyError, IndexError, TypeError, RecursionError) as exc:
        raise ProviderError("invalid_response") from exc
