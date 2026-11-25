import os
from http.server import ThreadingHTTPServer

from api.routes import routes
from config.events import configure
from config.settings import ROOT, load
from services.summary import SummaryService


if __name__ == "__main__":
    configure(ROOT / "service.jsonl")
    port = int(os.getenv("PORT", "8000"))
    handler = routes(SummaryService(load()))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"POST http://127.0.0.1:{port}/chat", flush=True)
        server.serve_forever()
