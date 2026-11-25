import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    key: str = ""
    url: str = "https://api.openai.com/v1/chat/completions"
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    timeout: float = 8.0
    ttl: int = 600
    port: int = 8000


def load():
    values = {}
    path = ROOT / ".env"
    if os.getenv("APP_ENV", "dev") == "dev" and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    values.update(os.environ)
    settings = Settings(timeout=float(values.get("LLM_TIMEOUT", Settings.timeout)),
                        ttl=int(values.get("CACHE_TTL", Settings.ttl)),
                        port=int(values.get("PORT", Settings.port)),
                        key=values.get("OPENAI_API_KEY", ""),
                    model=values.get("LLM_MODEL", Settings.model),
                    url=values.get("LLM_URL", Settings.url))
    if not (0 < settings.timeout < float("inf") and settings.ttl > 0 and 1 <= settings.port <= 65535):
        raise ValueError("Проверьте LLM_TIMEOUT, CACHE_TTL и PORT.")
    return settings
