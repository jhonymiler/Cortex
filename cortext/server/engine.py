"""
MemoryEngine — the long-lived service behind the daemon.

Holds one CortexV5 per namespace over a single SQLite store, so every agent
(Claude Code, Cursor, Copilot, MCP clients) shares one warm, indexed graph per
project. Adds what a service needs on top of the library: turn capture for
agent transcripts, a session-start digest, an activity feed for the
dashboard, and a background DreamAgent loop.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Optional

from cortext.cortex import CortexV5
from cortext.core.validation import ValidationPolicy
from cortext.store import SQLiteStore
from cortext.workers import DreamAgent

logger = logging.getLogger("cortext.engine")

# Prompts that carry no memory-worthy content.
_TRIVIAL = re.compile(
    r"^\s*(ok(ay)?|sim|s|n[aã]o|yes|no|y|n|continue|continua(r)?|segue|go( on)?|thanks?|"
    r"obrigad[oa]|valeu|beleza|perfeito|done|pronto|next|pr[oó]ximo)\s*[.!]*\s*$",
    re.IGNORECASE,
)
# A block this system injected earlier must never be stored back as a memory.
_INJECTED = re.compile(r"<cortext-memory>.*?</cortext-memory>", re.DOTALL)
_WS = re.compile(r"\s+")

CONTEXT_HEADER = "Cortext memory — facts recalled from earlier sessions (may be stale; verify before relying on them):"


def _one_line(text: str, limit: int) -> str:
    text = _WS.sub(" ", _INJECTED.sub("", text or "")).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def format_context(lines: str) -> str:
    """Wrap packed recall lines in the block agents receive."""
    if not lines.strip():
        return ""
    body = "\n".join(f"- {line}" for line in lines.splitlines() if line.strip())
    return f"<cortext-memory>\n{CONTEXT_HEADER}\n{body}\n</cortext-memory>"


class MemoryEngine:
    """Multi-namespace memory service over one SQLite file."""

    def __init__(
        self,
        db_path: Any,
        validation_policy: ValidationPolicy = ValidationPolicy.WARN,
        dream_interval_seconds: int = 1800,
        enable_embeddings: bool = True,
        llm: Any = "env",
    ) -> None:
        from cortext.llm import from_env
        from cortext.server.abstraction import Abstractor
        from cortext.server.queue import JobQueue

        self.store = SQLiteStore(db_path)
        # Background abstraction: jobs persist in the same SQLite file. The
        # daemon runs them itself only with an LLM backend (CORTEXT_LLM); the
        # Claude Code mod can lease and run them with the user's own model.
        self.queue = JobQueue(self.store._conn, self.store._lock)
        self.abstractor = Abstractor(self)
        self.llm = from_env() if llm == "env" else llm
        self._worker_thread: Optional[threading.Thread] = None
        self.validation_policy = validation_policy
        self.enable_embeddings = enable_embeddings
        self._cortex: dict[str, CortexV5] = {}
        self._lock = threading.RLock()
        self._events: deque[dict[str, Any]] = deque(maxlen=500)
        self._seq = 0
        self._cond = threading.Condition()
        self.started_at = time.time()
        self._dream = DreamAgent()
        self._dream_interval = dream_interval_seconds
        self._stop = threading.Event()
        self._dream_thread: Optional[threading.Thread] = None
        self._flush_thread: Optional[threading.Thread] = None
        self.last_dream: dict[str, Any] = {}

    # === Namespaces ===

    def cortex(self, namespace: str) -> CortexV5:
        ns = namespace or "default"
        with self._lock:
            c = self._cortex.get(ns)
            if c is None:
                t0 = time.perf_counter()
                c = CortexV5(
                    namespace=ns,
                    validation_policy=self.validation_policy,
                    enable_embedding_recall=self.enable_embeddings,
                    store=self.store,
                )
                self._cortex[ns] = c
                self._emit("load", ns, (time.perf_counter() - t0) * 1000, f"{len(c.graph)} memories")
            return c

    def namespaces(self) -> list[dict[str, Any]]:
        with self._lock:
            names = set(self.store.namespaces()) | set(self._cortex)
            out = []
            for ns in sorted(names):
                c = self.cortex(ns)
                out.append({"name": ns, "memories": len(c.graph), "levels": c.levels()})
            return out

    # === Activity feed ===

    def _emit(self, op: str, ns: str, ms: float, detail: str = "", **extra: Any) -> None:
        with self._cond:
            self._seq += 1
            self._events.append({
                "seq": self._seq, "ts": time.time(), "op": op, "ns": ns,
                "ms": round(ms, 3), "detail": detail[:160], **extra,
            })
            self._cond.notify_all()

    def events_since(self, seq: int, wait: float = 0.0) -> list[dict[str, Any]]:
        """Events with seq > ``seq``; blocks up to ``wait`` seconds for one."""
        with self._cond:
            if wait and (not self._events or self._events[-1]["seq"] <= seq):
                self._cond.wait(timeout=wait)
            return [e for e in self._events if e["seq"] > seq]

    # === Write ===

    def remember(self, namespace: str, text: str = "", **fields: Any) -> dict[str, Any]:
        c = self.cortex(namespace)
        t0 = time.perf_counter()
        fields = {k: v for k, v in fields.items() if v not in (None, "")}
        # Who is writing (an agent, or a person in team mode) travels as metadata.
        source = {k: fields.pop(k) for k in ("agent", "author") if k in fields}
        if source:
            fields["metadata"] = {**(fields.get("metadata") or {}), **source}
        if text and not fields.get("what"):
            memory, result = c.remember_text(
                text,
                who=fields.get("who"),
                where=fields.get("where"),
                how=fields.get("how", ""),
                importance=float(fields.get("importance", 0.6)),
                metadata=fields.get("metadata"),
            )
        else:
            fields.setdefault("importance", 0.6)
            fields["importance"] = float(fields["importance"])
            memory, result = c.remember(**{k: v for k, v in fields.items() if k in _REMEMBER_FIELDS})
        ms = (time.perf_counter() - t0) * 1000
        status = result.status.value if result is not None else "OK"
        stored = status != "BLOCKED"
        self._emit("remember", namespace, ms, memory.what, status=status, id=memory.id if stored else None)
        return {
            "stored": stored,
            "id": memory.id if stored else None,
            "status": status,
            "reason": result.reason if result is not None else "",
            "ms": round(ms, 3),
        }

    def capture_turn(
        self,
        namespace: str,
        user: str,
        assistant: str = "",
        agent: str = "",
        session: str = "",
    ) -> dict[str, Any]:
        """Store one agent exchange as a memory, unless it carries nothing.

        The user's request becomes ``what`` (one line, capped); the start of
        the assistant's answer becomes ``how``. Slash commands, one-word
        acknowledgements and blocks this system injected are skipped.
        """
        prompt = _one_line(user, 400)
        if len(prompt) < 12 or prompt.startswith("/") or _TRIVIAL.match(prompt):
            return {"stored": False, "skipped": "trivial"}
        from cortext.core.recall.text_extractor import extract_via_heuristic

        data = extract_via_heuristic(prompt)
        out = self.remember(
            namespace,
            what=prompt,
            who=data.get("who") or [],
            where=data.get("where") or "default",
            how=_one_line(assistant, 400),
            importance=0.5,
            metadata={k: v for k, v in {"agent": agent, "session": session, "kind": "turn"}.items() if v},
        )
        if out.get("stored") and out.get("id"):
            job = self.abstractor.on_turn(namespace, session, out["id"])
            if job is not None:
                out["abstract_job"] = job
        return out

    def end_session(self, namespace: str, session: str = "") -> list[int]:
        """Queue abstraction of whatever the session left buffered."""
        return self.abstractor.flush(namespace, session or None)

    # === Queue (workers: the daemon's LLM backend, or the Claude Code mod) ===

    def lease_job(self, worker: str) -> Optional[dict[str, Any]]:
        """Hand a worker the next job as a ready prompt (None when idle)."""
        from cortext.llm import DEFAULT_SYSTEM

        while True:
            job = self.queue.lease(worker, kinds=["extract", "consolidate"])
            if job is None:
                return None
            prompt = self.abstractor.prompt_for(job)
            if prompt is not None:
                return {"id": job["id"], "kind": job["kind"], "ns": job["ns"], "prompt": prompt,
                        "system": DEFAULT_SYSTEM, "model": "haiku"}
            self.queue.complete(job["id"], {"skipped": "nothing to do"})

    def complete_job(self, job_id: int, text: str) -> dict[str, Any]:
        job = self.queue.get(job_id)
        if job is None or job["state"] != "leased":
            return {"ok": False, "error": "unknown or not leased"}
        full = {**job, "payload": self._job_payload(job_id)}
        try:
            result = self.abstractor.apply(full, text)
        except Exception as e:
            return {"ok": False, "state": self.queue.fail(job_id, f"{type(e).__name__}: {e}")}
        self.queue.complete(job_id, result)
        return {"ok": True, **result}

    def _job_payload(self, job_id: int) -> dict[str, Any]:
        with self.store._lock:
            row = self.store._conn.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()
        return json.loads(row[0]) if row else {}

    def forget(self, namespace: str, memory_id: str) -> bool:
        t0 = time.perf_counter()
        ok = self.cortex(namespace).forget(memory_id)
        self._emit("forget", namespace, (time.perf_counter() - t0) * 1000, memory_id)
        return ok

    # === Read ===

    def recall(
        self,
        namespace: str,
        query: str,
        max_results: int = 5,
        max_tokens: int = 300,
        touch: bool = True,
    ) -> dict[str, Any]:
        c = self.cortex(namespace)
        t0 = time.perf_counter()
        packed, result = c.recall(query, max_results=max_results, max_tokens=max_tokens, touch=touch)
        ms = (time.perf_counter() - t0) * 1000
        now = datetime.now()
        records = [c._memory_to_record(m, now=now) for m in result.memories]
        self._emit("recall", namespace, ms, query, hits=len(records))
        return {
            "context": format_context(packed),
            "packed": packed,
            "memories": records,
            "ms": round(ms, 3),
        }

    def session_digest(self, namespace: str, max_items: int = 8) -> dict[str, Any]:
        """The most established memories of a namespace, for a session's start.

        Agents whose hooks can only inject context once (Cursor, Copilot at
        sessionStart) get the long-term layer up front: summaries and
        reinforced or important memories, most relied-upon first.
        """
        c = self.cortex(namespace)
        t0 = time.perf_counter()
        with c._lock:
            tiers = c._tiers()
            pool = [m for m in c.graph.iter_memories() if tiers.get(m.id) == "semantic"]
            if len(pool) < max_items:
                pool += [m for m in c.graph.iter_memories() if tiers.get(m.id) in ("episodic", "working")]
            pool.sort(key=lambda m: (m.is_summary, m.importance, m.access_count, m.created_at), reverse=True)
            from cortext.core.recall.pack import pack_for_context

            packed = pack_for_context(pool[:max_items], None, max_tokens=400)
        ms = (time.perf_counter() - t0) * 1000
        self._emit("digest", namespace, ms, f"{min(len(pool), max_items)} memories")
        return {"context": format_context(packed), "count": min(len(pool), max_items), "ms": round(ms, 3)}

    # === Maintenance ===

    def dream(self, namespace: str) -> dict[str, Any]:
        c = self.cortex(namespace)
        t0 = time.perf_counter()
        with c._lock:
            r = self._dream.run_cycle(c.graph)
            c.flush()
        ms = (time.perf_counter() - t0) * 1000
        out = {
            "namespace": namespace, "replayed": r.n_replayed, "consolidated": r.n_consolidated,
            "cleaned": r.n_cleaned, "ms": round(ms, 3), "at": time.time(),
        }
        self.last_dream[namespace] = out
        self._emit("dream", namespace, ms, f"+{r.n_consolidated} merged, -{r.n_cleaned} pruned")
        return out

    def flush_pending(self) -> int:
        """Persist write-behind changes (access counts) of every namespace."""
        written = 0
        with self._lock:
            cortexes = list(self._cortex.values())
        for c in cortexes:
            if c.graph._dirty or c.graph._deleted or c.graph._other_changes:
                written += c.flush()
        return written

    def start_background(self) -> None:
        if self.llm is not None and self._worker_thread is None:
            def worker() -> None:
                last_idle_check = 0.0
                while not self._stop.is_set():
                    try:
                        if time.time() - last_idle_check > 30:
                            self.abstractor.flush_idle()
                            last_idle_check = time.time()
                        if self.abstractor.work_once(self.llm, worker=f"daemon:{self.llm.name}") is None:
                            self._stop.wait(2.0)
                    except Exception as e:  # keep the worker alive
                        logger.warning("abstraction worker: %s", e)
                        self._stop.wait(5.0)

            self._worker_thread = threading.Thread(target=worker, name="cortext-abstract", daemon=True)
            self._worker_thread.start()
        if self._flush_thread is None:
            def flusher() -> None:
                while not self._stop.wait(2.0):
                    try:
                        self.flush_pending()
                    except Exception as e:
                        logger.warning("background flush failed: %s", e)

            self._flush_thread = threading.Thread(target=flusher, name="cortext-flush", daemon=True)
            self._flush_thread.start()
        if self._dream_interval <= 0 or self._dream_thread is not None:
            return

        def loop() -> None:
            while not self._stop.wait(self._dream_interval):
                for ns in list(self._cortex):
                    try:
                        self.dream(ns)
                    except Exception as e:  # keep the loop alive
                        logger.warning("dream cycle failed for %s: %s", ns, e)

        self._dream_thread = threading.Thread(target=loop, name="cortext-dream", daemon=True)
        self._dream_thread.start()

    def overview(self) -> dict[str, Any]:
        """Everything the dashboard header needs in one call."""
        nss = self.namespaces()
        totals: dict[str, int] = {}
        for n in nss:
            for tier, count in n["levels"].items():
                totals[tier] = totals.get(tier, 0) + count
        lat: dict[str, list[float]] = {"remember": [], "recall": []}
        for c in self._cortex.values():
            for op in lat:
                lat[op].extend(c._latency[op])
        from cortext.cortex import _percentile

        return {
            "namespaces": nss,
            "total_memories": sum(n["memories"] for n in nss),
            "levels": totals,
            "latency": {
                op: {"p50_ms": round(_percentile(v, 0.5), 3), "p95_ms": round(_percentile(v, 0.95), 3), "count": len(v)}
                for op, v in lat.items()
            },
            "uptime_s": round(time.time() - self.started_at, 1),
            "queue": self.queue.stats(),
            "llm": self.llm.name if self.llm is not None else None,
            "last_dream": self.last_dream,
            "db": str(self.store.path),
        }

    def close(self) -> None:
        self._stop.set()
        for ns in list(self._cortex):
            self.abstractor.flush(ns)  # buffered turns become jobs; they persist for the next run
        with self._lock:
            for c in self._cortex.values():
                try:
                    c.flush()
                except Exception as e:
                    logger.warning("flush failed for %s: %s", c.namespace, e)
            self.store.close()


_REMEMBER_FIELDS = {"who", "what", "why", "when", "where", "how", "importance", "lang", "validate", "metadata"}
