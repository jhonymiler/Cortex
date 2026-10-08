"""
Background abstraction: raw turns → durable facts, by the user's own model.

Chosen by measurement (bench/jev/timing.py, docs/experiments/): extracting
from windows of 4 turns and then consolidating with the LLM captured 100% of
the planted facts, kept no superseded value and produced the most compact
memory, with 4x fewer model calls than per-turn extraction. Consolidating with
a decision-only judge (no generation) lost information (46% captured).

    turn ──▶ stored raw at once (recallable immediately) ──▶ session buffer
    every 4 turns / session end / idle ──▶ job `extract`  (window → facts)
    facts ──▶ job `consolidate` (facts + related stored memories → final set)
    raw turns ──▶ archived, linked to the facts they produced (or as noise)

Jobs go through JobQueue; whoever runs the model (the Claude Code mod with
$.model.complete, or the daemon's CORTEXT_LLM backend) only turns a prompt
into text. Building prompts and applying answers happens here.
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any, Optional

from cortext.core.text import tokenize
from cortext.llm import DEFAULT_SYSTEM, parse_json_object

if TYPE_CHECKING:
    from cortext.server.engine import MemoryEngine

WINDOW = 4
RULES = (
    "Durable facts: decisions, conventions, constraints, ownership, preferences, causes of problems and their fixes, "
    "facts about customers/students/employees, things the agent discovered that will matter later. "
    "Not durable: one-off commands, acknowledgements, generic questions, transient output. "
    "Write each fact as one self-contained sentence in the language the user wrote in, naming who/what it is "
    "about, and give the same fact in English too."
)
NOISE = "abstracted:noise"
SUPERSEDED = "superseded"


def _turns_text(mems) -> str:
    return "\n".join(f"USER: {m.what}\nAGENT: {m.how}" for m in mems)


class Abstractor:
    def __init__(self, engine: "MemoryEngine", window: int = WINDOW, idle_flush_s: float = 300.0) -> None:
        self.engine = engine
        self.window = window
        self.idle_flush_s = idle_flush_s
        self._buffers: dict[tuple[str, str], list[str]] = {}
        self._last: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()

    # --- buffering -------------------------------------------------------------------

    def on_turn(self, ns: str, session: str, memory_id: str) -> Optional[int]:
        key = (ns, session or "-")
        with self._lock:
            buf = self._buffers.setdefault(key, [])
            buf.append(memory_id)
            self._last[key] = time.time()
            if len(buf) < self.window:
                return None
            ids, self._buffers[key] = buf[:], []
        return self._enqueue_extract(ns, session, ids)

    def flush(self, ns: str, session: Optional[str] = None) -> list[int]:
        """Enqueue whatever is buffered (session end, shutdown, idle)."""
        with self._lock:
            keys = [k for k in self._buffers if k[0] == ns and (session is None or k[1] == (session or "-"))]
            batches = [(k, self._buffers.pop(k)) for k in keys if self._buffers.get(k)]
        return [self._enqueue_extract(k[0], k[1], ids) for k, ids in batches]

    def flush_idle(self) -> list[int]:
        cutoff = time.time() - self.idle_flush_s
        with self._lock:
            idle = [k for k, t in self._last.items() if t < cutoff and self._buffers.get(k)]
            batches = [(k, self._buffers.pop(k)) for k in idle]
        return [self._enqueue_extract(k[0], k[1], ids) for k, ids in batches]

    def _enqueue_extract(self, ns: str, session: str, ids: list[str]) -> int:
        return self.engine.queue.enqueue(ns, "extract", {"turn_ids": ids, "session": session})

    # --- prompts ------------------------------------------------------------------------

    def prompt_for(self, job: dict[str, Any]) -> Optional[str]:
        c = self.engine.cortex(job["ns"])
        p = job["payload"]
        if job["kind"] == "extract":
            turns = [m for m in (c.get(i) for i in p["turn_ids"]) if m is not None]
            if not turns:
                return None
            return (f"Part of an agent session:\n{_turns_text(turns)}\n\n{RULES}\n"
                    "If a later turn changes something said earlier, keep only the final value.\n"
                    'Return 0 to 5: {"facts": [{"fact": "...", "en": "..."}]}')
        if job["kind"] == "consolidate":
            related = self.related(job["ns"], p["facts"])
            existing = "\n".join(f"[{m.id[:8]}] {m.what}" for m in related) or "(none)"
            facts = "\n".join(f"{i + 1}. {f['fact']}" for i, f in enumerate(p["facts"]))
            return (
                f"Memories already stored about these subjects (may be outdated):\n{existing}\n\n"
                f"New facts, in order (later = newer):\n{facts}\n\n"
                "Produce the final memory for these subjects: merge duplicates and facts that complete each other "
                "into one, keep every detail, and when two conflict keep only the newer value. Invent nothing. "
                "For each final memory give the id of the stored memory it updates, or null if it is new. "
                "List in retire the stored ids that are no longer true and not updated. Write each memory in the "
                "language of the new facts, and in English as en.\n"
                '{"memories": [{"id": "abc12345 or null", "what": "...", "en": "..."}], "retire": ["abc12345"]}'
            )
        return None

    def related(self, ns: str, facts: list[str], per_fact: int = 3, cap: int = 12):
        """Stored facts that share the most terms with each new fact (index-backed)."""
        c = self.engine.cortex(ns)
        g = c.graph
        picked: dict[str, Any] = {}
        for f in facts:
            toks = tokenize(f["fact"] + " " + f.get("en", ""))
            hits: dict[str, int] = {}
            for t in toks:
                for mid in g.ids_for_token(t):
                    hits[mid] = hits.get(mid, 0) + 1
            ranked = sorted(hits.items(), key=lambda kv: -kv[1])
            n = 0
            for mid, h in ranked:
                m = g.get_memory(mid)
                if m is None or m.consolidated_into or m.metadata.get("kind") == "turn" or h < 2:
                    continue
                picked.setdefault(m.id, m)
                n += 1
                if n >= per_fact:
                    break
        return list(picked.values())[:cap]

    # --- applying answers -----------------------------------------------------------------

    def apply(self, job: dict[str, Any], text: str) -> dict[str, Any]:
        out = parse_json_object(text)
        ns, p = job["ns"], job["payload"]
        c = self.engine.cortex(ns)
        if job["kind"] == "extract":
            facts = []
            for f in out.get("facts", []):
                if isinstance(f, str) and f.strip():
                    facts.append({"fact": f.strip(), "en": ""})
                elif isinstance(f, dict) and str(f.get("fact", "")).strip():
                    facts.append({"fact": str(f["fact"]).strip(), "en": str(f.get("en") or "").strip()})
            if not facts:
                self._archive_turns(c, p["turn_ids"], NOISE)
                self.engine._emit("abstract", ns, 0.0, f"{len(p['turn_ids'])} turns → no durable fact")
                return {"facts": 0}
            jid = self.engine.queue.enqueue(ns, "consolidate", {**p, "facts": facts})
            return {"facts": len(facts), "consolidate_job": jid}

        if job["kind"] == "consolidate":
            related = {m.id[:8]: m for m in self.related(ns, p["facts"])}
            added, updated, retired = [], [], []
            with c._lock:
                for item in out.get("memories", []):
                    if not isinstance(item, dict) or not str(item.get("what", "")).strip():
                        continue
                    what = str(item["what"]).strip()
                    en = str(item.get("en") or "").strip()
                    en = "" if en == what else en
                    target = related.get(str(item.get("id") or "")[:8])
                    if target is not None:
                        if target.what != what or target.alt != en:
                            target.metadata.setdefault("history", []).append(target.what)
                            target.what, target.alt = what, en
                            target.touch()
                            c.graph.reindex(target)
                        updated.append(target.id)
                        continue
                    m, _ = c.remember(what=what, importance=0.7, validate=False, metadata={
                        "kind": "fact", "session": p.get("session", ""), "from_turns": p["turn_ids"]})
                    if en and m.alt != en:
                        m.alt = en
                        c.graph.reindex(m)
                    added.append(m.id)
                for rid in out.get("retire", []) or []:
                    m = related.get(str(rid)[:8])
                    if m is not None and m.id not in updated:
                        m.consolidated_into = SUPERSEDED
                        m.metadata["retired_at"] = time.time()
                        c.graph.mark_dirty(m)
                        retired.append(m.id)
                anchor = (added or updated or [NOISE])[0]
                self._archive_turns(c, p["turn_ids"], anchor)
                c.flush()
            self.engine._emit("abstract", ns, 0.0,
                              f"+{len(added)} facts, {len(updated)} updated, {len(retired)} retired")
            return {"added": added, "updated": updated, "retired": retired}
        return {}

    @staticmethod
    def _archive_turns(c, turn_ids: list[str], into: str) -> None:
        with c._lock:
            for tid in turn_ids:
                m = c.get(tid)
                if m is not None and not m.consolidated_into:
                    m.consolidated_into = into
                    c.graph.mark_dirty(m)
            c.flush()

    # --- worker (daemon side) -------------------------------------------------------------

    def work_once(self, backend, worker: str = "daemon") -> Optional[dict[str, Any]]:
        job = self.engine.queue.lease(worker, kinds=["extract", "consolidate"])
        if job is None:
            return None
        try:
            prompt = self.prompt_for(job)
            if prompt is None:
                self.engine.queue.complete(job["id"], {"skipped": "nothing to do"})
                return {"job": job["id"], "skipped": True}
            result = self.apply(job, backend.complete(prompt, DEFAULT_SYSTEM))
            self.engine.queue.complete(job["id"], result)
            return {"job": job["id"], **result}
        except Exception as e:
            state = self.engine.queue.fail(job["id"], f"{type(e).__name__}: {e}")
            return {"job": job["id"], "error": str(e), "state": state}

    def drain(self, backend, worker: str = "daemon", max_jobs: int = 1000) -> int:
        done = 0
        while done < max_jobs and self.work_once(backend, worker) is not None:
            done += 1
        return done
