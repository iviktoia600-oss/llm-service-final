from http.server import ThreadingHTTPServer

from api.routes import routes
from config.events import configure
from config.settings import ROOT, load
from services.summary import SummaryService


if __name__ == "__main__":
    configure(ROOT / "service.jsonl")
    settings = load()
    port = settings.port
    handler = routes(SummaryService(settings))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"POST http://127.0.0.1:{port}/chat", flush=True)
        server.serve_forever()
