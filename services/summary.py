from cache.results import Cache, key_for
from config.events import event, stage
from llm.client import extract, fetch
from llm.prompt import build


class SummaryService:
    def __init__(self, settings, provider=fetch):
        self.settings = settings
        self.provider = provider
        self.cache = Cache(settings.ttl)

    def summarize(self, text, rid):
        with stage(rid, "prompt"):
            payload = build(text, self.settings)
            event(rid, "prompt", payload=payload)
        with stage(rid, "cache_lookup"):
            key = key_for(self.settings.url, payload)
            cached = self.cache.get(key)
            event(rid, "cache_hit" if cached is not None else "cache_miss")
        if cached is not None:
            return {"answer": cached, "cached": True}
        with stage(rid, "llm"):
            raw = self.provider(self.settings, payload, rid)
            event(rid, "model_response", body=raw.decode("utf-8", errors="replace"))
        with stage(rid, "postprocess"):
            answer = extract(raw)
        with stage(rid, "cache_write"):
            self.cache.put(key, answer)
        return {"answer": answer, "cached": False}
