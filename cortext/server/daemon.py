"""
Cortext daemon — a local HTTP service holding the memory graph warm.

Agent hooks start a fresh process per event; loading and indexing a graph on
each would cost a second. Instead they talk to this daemon, which keeps every
namespace loaded and answers in about a millisecond. It also serves the
dashboard at ``/``.

Run:  cortext-memory serve            (foreground)
      cortext-memory daemon start     (background)

Bound to 127.0.0.1. Requests must name a local Host (DNS-rebinding guard),
writes must be JSON (a cross-site form can't send that), a browser Origin must
be local, and when CORTEXT_TOKEN is set every /api call must carry it.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import parse_qs, urlparse

from cortext.server import config
from cortext.server.engine import MemoryEngine

logger = logging.getLogger("cortext.daemon")

_STATIC = Path(__file__).resolve().parent / "static"
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}


class _Handler(BaseHTTPRequestHandler):
    server_version = "cortext"
    protocol_version = "HTTP/1.1"
    engine: MemoryEngine  # set on the subclass by make_server

    # --- plumbing -----------------------------------------------------------

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet by default
        logger.debug("%s - " + fmt, self.address_string(), *args)

    def _send(self, status: int, body: bytes, ctype: str = "application/json; charset=utf-8", extra: Optional[dict] = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data: Any, status: int = 200) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"))

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status)

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > 2_000_000:
            raise ValueError("body too large")
        data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("body must be a JSON object")
        return data

    def _guard(self, write: bool) -> Optional[str]:
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip().lower()
        if host not in _LOCAL_HOSTS:
            return "forbidden host"
        origin = self.headers.get("Origin")
        if origin:
            o = urlparse(origin).hostname or ""
            if o.lower() not in _LOCAL_HOSTS:
                return "forbidden origin"
        if write and "application/json" not in (self.headers.get("Content-Type") or ""):
            return "writes must be application/json"
        secret = config.token()
        if secret and self.path.startswith("/api/") and self.headers.get("X-Cortext-Token") != secret:
            return "missing or wrong X-Cortext-Token"
        return None

    # --- routing ------------------------------------------------------------

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        problem = self._guard(write=method in ("POST", "DELETE") and self.path.startswith("/api/"))
        if problem:
            return self._error(HTTPStatus.FORBIDDEN, problem)
        url = urlparse(self.path)
        q = {k: v[-1] for k, v in parse_qs(url.query).items()}
        route = _ROUTES.get((method, url.path))
        try:
            if route is not None:
                return route(self, q)
            if method == "DELETE" and url.path.startswith("/api/memory/"):
                mid = url.path.rsplit("/", 1)[-1]
                return self._json({"deleted": self.engine.forget(q.get("ns", "default"), mid)})
            if method == "GET" and url.path.startswith("/api/memory/"):
                mid = url.path.rsplit("/", 1)[-1]
                c = self.engine.cortex(q.get("ns", "default"))
                m = c.get(mid)
                if m is None:
                    return self._error(HTTPStatus.NOT_FOUND, "no such memory")
                record = c._memory_to_record(m)
                record["neighbors"] = [c._memory_to_record(n) for n in c.graph.neighbors(m, limit=12)]
                return self._json(record)
            return self._error(HTTPStatus.NOT_FOUND, "not found")
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            return self._error(HTTPStatus.BAD_REQUEST, str(e))
        except BrokenPipeError:
            return None
        except Exception as e:  # never kill the server thread
            logger.exception("request failed: %s %s", method, self.path)
            return self._error(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(e).__name__}: {e}")

    # --- endpoints ----------------------------------------------------------

    def get_index(self, q: dict) -> None:
        page = _STATIC / "dashboard.html"
        csp = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; connect-src 'self'; img-src 'self' data:"
        )
        self._send(200, page.read_bytes(), "text/html; charset=utf-8", {"Content-Security-Policy": csp})

    def get_health(self, q: dict) -> None:
        from cortext import __version__

        self._json({"ok": True, "version": __version__, "pid": os.getpid(), "uptime_s": round(time.time() - self.engine.started_at, 1)})

    def get_ns(self, q: dict) -> None:
        """The namespace for a working directory (same rule the hooks use)."""
        self._json({"ns": config.namespace_for(q.get("cwd") or None)})

    def get_overview(self, q: dict) -> None:
        self._json(self.engine.overview())

    def get_namespaces(self, q: dict) -> None:
        self._json(self.engine.namespaces())

    def get_stats(self, q: dict) -> None:
        self._json(self.engine.cortex(q.get("ns", "default")).stats())

    def get_levels(self, q: dict) -> None:
        self._json(self.engine.cortex(q.get("ns", "default")).levels())

    def get_memories(self, q: dict) -> None:
        c = self.engine.cortex(q.get("ns", "default"))
        self._json(c.list_memories(
            tier=q.get("tier") or None, query=q.get("q") or None, who=q.get("who") or None,
            limit=min(500, int(q.get("limit", 50))), offset=int(q.get("offset", 0)), sort=q.get("sort", "recent"),
        ))

    def get_graph(self, q: dict) -> None:
        self._json(self.engine.cortex(q.get("ns", "default")).graph_snapshot(limit=min(2000, int(q.get("limit", 400)))))

    def get_digest(self, q: dict) -> None:
        self._json(self.engine.session_digest(q.get("ns", "default"), max_items=int(q.get("max", 8))))

    def get_activity(self, q: dict) -> None:
        self._json(self.engine.events_since(int(q.get("since", 0))))

    def get_events(self, q: dict) -> None:
        """Server-sent events: the activity feed, live."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        seq = int(q.get("since", 0))
        try:
            while not self.server.stopping:  # type: ignore[attr-defined]
                events = self.engine.events_since(seq, wait=15)
                if events:
                    for e in events:
                        self.wfile.write(f"id: {e['seq']}\ndata: {json.dumps(e, ensure_ascii=False)}\n\n".encode())
                        seq = e["seq"]
                else:
                    self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def post_remember(self, q: dict) -> None:
        b = self._body()
        ns = b.pop("ns", None) or q.get("ns", "default")
        text = b.pop("text", "")
        if not text and not b.get("what"):
            raise ValueError("'what' or 'text' is required")
        if isinstance(b.get("who"), str):
            b["who"] = [w.strip() for w in b["who"].split(",") if w.strip()]
        self._json(self.engine.remember(ns, text=text, **b))

    def post_recall(self, q: dict) -> None:
        b = self._body()
        query = b.get("query") or ""
        if not query.strip():
            raise ValueError("'query' is required")
        self._json(self.engine.recall(
            b.get("ns") or q.get("ns", "default"), query,
            max_results=int(b.get("max_results", 5)), max_tokens=int(b.get("max_tokens", 300)),
            touch=bool(b.get("touch", True)),
        ))

    def post_turn(self, q: dict) -> None:
        b = self._body()
        self._json(self.engine.capture_turn(
            b.get("ns") or q.get("ns", "default"), b.get("user", ""), b.get("assistant", ""),
            agent=b.get("agent", ""), session=b.get("session", ""),
        ))

    def post_dream(self, q: dict) -> None:
        b = self._body()
        self._json(self.engine.dream(b.get("ns") or q.get("ns", "default")))

    def post_shutdown(self, q: dict) -> None:
        self._json({"ok": True})
        threading.Thread(target=self.server.shutdown, daemon=True).start()


_ROUTES: dict[tuple[str, str], Callable[[_Handler, dict], None]] = {
    ("GET", "/"): _Handler.get_index,
    ("GET", "/index.html"): _Handler.get_index,
    ("GET", "/api/health"): _Handler.get_health,
    ("GET", "/api/overview"): _Handler.get_overview,
    ("GET", "/api/ns"): _Handler.get_ns,
    ("GET", "/api/namespaces"): _Handler.get_namespaces,
    ("GET", "/api/stats"): _Handler.get_stats,
    ("GET", "/api/levels"): _Handler.get_levels,
    ("GET", "/api/memories"): _Handler.get_memories,
    ("GET", "/api/graph"): _Handler.get_graph,
    ("GET", "/api/digest"): _Handler.get_digest,
    ("GET", "/api/activity"): _Handler.get_activity,
    ("GET", "/api/events"): _Handler.get_events,
    ("POST", "/api/remember"): _Handler.post_remember,
    ("POST", "/api/recall"): _Handler.post_recall,
    ("POST", "/api/turn"): _Handler.post_turn,
    ("POST", "/api/dream"): _Handler.post_dream,
    ("POST", "/api/shutdown"): _Handler.post_shutdown,
}


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    stopping = False


def make_server(engine: MemoryEngine, host: str, port: int) -> _Server:
    handler = type("CortextHandler", (_Handler,), {"engine": engine})
    return _Server((host, port), handler)


def serve(
    host: Optional[str] = None,
    port: Optional[int] = None,
    db: Optional[str] = None,
    dream_interval: int = 1800,
    quiet: bool = False,
) -> int:
    """Run the daemon in the foreground until SIGINT/SIGTERM."""
    host = host or config.host()
    port = port or config.port()
    db_path = Path(db).expanduser() if db else config.db_path()
    config.home().mkdir(parents=True, exist_ok=True)
    engine = MemoryEngine(db_path, dream_interval_seconds=dream_interval)
    try:
        server = make_server(engine, host, port)
    except OSError as e:
        engine.close()
        print(f"cortext: cannot bind {host}:{port} ({e}) — is a daemon already running?", file=sys.stderr)
        return 1
    engine.start_background()
    config.pid_file().write_text(str(os.getpid()))

    def _stop(*_: Any) -> None:
        server.stopping = True
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _stop)
    if not quiet:
        print(f"cortext daemon on http://{host}:{port}  (db: {db_path})", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.stopping = True
        server.server_close()
        engine.close()
        try:
            if config.pid_file().read_text().strip() == str(os.getpid()):
                config.pid_file().unlink()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(serve())
