import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone

logger = logging.getLogger("llm-service")


def configure(path):
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    for handler in (logging.StreamHandler(), logging.FileHandler(path, encoding="utf-8")):
        logger.addHandler(handler)
    logger.propagate = False


def event(request_id, name, **fields):
    record = dict(time=datetime.now(timezone.utc).isoformat(),
                  request_id=request_id, event=name, **fields)
    logger.info(json.dumps(record, ensure_ascii=False))


@contextmanager
def stage(rid, name):
    start = time.monotonic()
    event(rid, "stage_start", stage=name)
    outcome = "ok"
    try:
        yield
    except Exception:
        outcome = "error"
        raise
    finally:
        event(rid, "stage_end", stage=name, outcome=outcome,
              elapsed_ms=round((time.monotonic() - start) * 1000, 3))
