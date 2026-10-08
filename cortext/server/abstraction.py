"""
Background abstraction: the user's own model separates durable facts from noise.

    turn ──▶ stored raw at once (recallable immediately) ──▶ session buffer
    every 4 turns / session end / idle ──▶ job `extract`  (window → facts)
    mode "gate" (default): no fact → turns archived as noise (unless related to
        a kept memory); facts → raw turns stay, facts indexed on them
    mode "facts": facts ──▶ job `consolidate` ──▶ raw turns replaced by facts

Chosen by measurement (docs/EVIDENCE.md): agents answered 29/30 with gate vs
25/30 with facts. Rewriting loses detail and the order of corrections, while
the model is reliable as a noise classifier. Windows of 4 turns cost a quarter
of per-turn calls (docs/experiments/).

Jobs go through JobQueue; whoever runs the model (the Claude Code mod with
$.model.complete, or the daemon's CORTEXT_LLM backend) only turns a prompt
into text. Building prompts and applying answers happens here.
"""

from __future__ import annotations

import re
import threading
import time
from typing import TYPE_CHECKING, Any, Optional

from cortext.core.recall.text_extractor import extract_who
from cortext.core.text import fold, tokenize
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
SHAPE = '{"fact": "...", "en": "..."}'
NOISE = "abstracted:noise"
SUPERSEDED = "superseded"


_KEY = re.compile(r"\b\d[\w.:/%-]*|\b\w+[_/.]\w[\w/._-]*")


def key_terms(text: str) -> set[str]:
    """What a summary must not lose: numbers, identifiers (snake_case, paths,
    dotted names) and proper names."""
    keys = {fold(m.group(0)).strip(".,;:") for m in _KEY.finditer(text or "")}
    return keys | {fold(n) for n in extract_who(text or "")}


def _strs(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(x).strip() for x in value if isinstance(x, (str, int, float)) and str(x).strip()]


def _turns_text(mems) -> str:
    return "\n".join(f"USER: {m.what}\nAGENT: {m.how}" for m in mems)


MODES = ("gate", "facts")


class Abstractor:
    """mode "gate" (default): a window with no durable fact is archived as noise;
    otherwise its raw turns stay active, with the extracted facts (user language +
    English) indexed on them. mode "facts": raw turns are replaced by
    consolidated facts. See docs/EVIDENCE.md for why gate is the default."""

    def __init__(self, engine: "MemoryEngine", window: int = WINDOW, idle_flush_s: float = 300.0,
                 mode: str = "gate") -> None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        self.mode = mode
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
                    f'Return 0 to 5: {{"facts": [{SHAPE}]}}')
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
                    facts.append({"fact": str(f["fact"]).strip(), "en": str(f.get("en") or "").strip(),
                                  "about": _strs(f.get("about")), "terms": _strs(f.get("terms"))})
            if not facts:
                if self.mode == "gate":
                    kept = self._archive_noise_unless_related(c, p["turn_ids"])
                    self.engine._emit("abstract", ns, 0.0,
                                      f"{len(p['turn_ids']) - kept} turns → noise, {kept} kept (related to kept memory)")
                    return {"facts": 0, "kept_turns": kept}
                self._archive_turns(c, p["turn_ids"], NOISE)
                self.engine._emit("abstract", ns, 0.0, f"{len(p['turn_ids'])} turns → no durable fact")
                return {"facts": 0}
            if self.mode == "gate":
                kept = self._annotate_turns(c, p["turn_ids"], facts)
                self.engine._emit("abstract", ns, 0.0, f"{len(facts)} facts kept on {kept} raw turns")
                return {"facts": len(facts), "kept_turns": kept}
            jid = self.engine.queue.enqueue(ns, "consolidate", {**p, "facts": facts})
            return {"facts": len(facts), "consolidate_job": jid}

        if job["kind"] == "consolidate":
            related = {m.id[:8]: m for m in self.related(ns, p["facts"])}
            out["memories"] = self.guard(p["facts"], out.get("memories", []))
            added, updated, retired = [], [], []
            with c._lock:
                for item in out.get("memories", []):
                    if not isinstance(item, dict) or not str(item.get("what", "")).strip():
                        continue
                    what = str(item["what"]).strip()
                    en = str(item.get("en") or "").strip()
                    # alt = English rendering + the words of the turns this fact came from
                    # (deterministic document expansion: the user's own vocabulary), indexed, never shown
                    alt = " ".join(x for x in [en if en != what else "", self._source_words(c, p["turn_ids"], what, en)] if x)
                    about = _strs(item.get("about"))[:6] or self._names_from_sources(c, p["turn_ids"], what)
                    target = related.get(str(item.get("id") or "")[:8])
                    if target is not None:
                        if target.what != what or target.alt != alt or (about and target.who != about):
                            target.metadata.setdefault("history", []).append(target.what)
                            target.what, target.alt = what, alt
                            if about:
                                target.who = about
                            target.touch()
                            c.graph.reindex(target)
                        updated.append(target.id)
                        continue
                    m, _ = c.remember(who=about, what=what, importance=0.7, validate=False, metadata={
                        "kind": "fact", "session": p.get("session", ""), "from_turns": p["turn_ids"]})
                    if alt and m.alt != alt:
                        m.alt = alt
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
    def guard(facts: list[dict], memories: list) -> list[dict]:
        """Deterministic preservation check on the model's consolidation.

        For each source fact, the consolidated memory closest to it must still
        carry the fact's key terms (numbers, identifiers, names). If it lost
        any, that lossy memory is replaced by the source fact itself, so a
        summary can drop words but never "5433", "Luis" or "services/reconciliation".
        """
        out = [dict(m) for m in memories if isinstance(m, dict) and str(m.get("what", "")).strip()]
        for f in facts:
            keys = key_terms(f["fact"]) | key_terms(f.get("en", ""))
            if not keys:
                continue
            f_tokens = tokenize(f["fact"] + " " + f.get("en", ""))
            best, best_overlap = None, 0
            for m in out:
                overlap = len(f_tokens & tokenize(m["what"] + " " + str(m.get("en") or "")))
                if overlap > best_overlap:
                    best, best_overlap = m, overlap
            text = fold((best or {}).get("what", "") + " " + str((best or {}).get("en") or ""))
            if best is None or any(k not in text for k in keys):
                lossless = {"id": (best or {}).get("id"), "what": f["fact"], "en": f.get("en", ""), "guarded": True}
                if best is None:
                    out.append(lossless)
                else:
                    out[out.index(best)] = lossless
        return out

    @staticmethod
    def _names_from_sources(c, turn_ids: list[str], what: str) -> list[str]:
        """Names in the fact that the user also wrote in the source turns, always
        capitalized ("Luis" yes; "Deploy" no, since the turns say "fazer deploy")."""
        source = " ".join((c.get(t).what + " " + c.get(t).how) for t in turn_ids if c.get(t) is not None)
        names = []
        for n in extract_who(what):
            if re.search(rf"\b{re.escape(n)}\b", source) and not re.search(rf"\b{re.escape(n.lower())}\b", source):
                names.append(n)
        return names[:6]

    @staticmethod
    def _source_words(c, turn_ids: list[str], what: str, en: str, limit: int = 40) -> str:
        """Words of the source turns that share a term with the fact, so it can be
        found with the vocabulary the user actually used ("conciliação", "llamar")."""
        fact_terms = tokenize(what + " " + en)
        words: list[str] = []
        for tid in turn_ids:
            m = c.get(tid)
            if m is None:
                continue
            turn_terms = tokenize(m.what + " " + m.how)
            if fact_terms.isdisjoint(turn_terms):
                continue
            words += [t for t in sorted(turn_terms - fact_terms) if t not in words]
        return " ".join(words[:limit])

    @staticmethod
    def _annotate_turns(c, turn_ids: list[str], facts: list[dict]) -> int:
        """Gate mode: keep the raw turns (the agent reads corrections in order at
        answer time) and index the extracted facts on the turns they came from,
        so a query in either language, or in the fact's words, finds them.
        A turn sharing no term with any fact is noise inside a useful window."""
        kept = 0
        with c._lock:
            for tid in turn_ids:
                m = c.get(tid)
                if m is None or m.consolidated_into:
                    continue
                turn_terms = tokenize(m.what + " " + m.how)
                mine = [f for f in facts if not turn_terms.isdisjoint(tokenize(f["fact"] + " " + f.get("en", ""))) ]
                if not mine:
                    if not Abstractor._related_to_kept(c, m):
                        m.consolidated_into = NOISE
                        c.graph.mark_dirty(m)
                    continue
                m.alt = " ".join(x for x in [m.alt, *(f["fact"] + " " + f.get("en", "") for f in mine)] if x)
                m.metadata["abstracted"] = True
                c.graph.reindex(m)
                kept += 1
            c.flush()
        return kept

    @staticmethod
    def _related_to_kept(c, m, max_df: int = 3) -> bool:
        """Does this turn share a rare term with a memory already judged useful?

        A window is judged in isolation, so "actually make the canary 10%"
        surrounded by chatter looks like noise; it is the correction of a kept
        memory, recognisable by the rare term they share ("canary").
        """
        g = c.graph
        for t in tokenize(m.what + " " + m.how):
            useful = [i for i in g.ids_for_token(t) if i != m.id]
            useful = [i for i in useful if (x := g.get_memory(i)) is not None and not x.consolidated_into
                      and (x.metadata.get("abstracted") or x.metadata.get("kind") == "fact")]
            if 0 < len(useful) <= max_df:
                return True
        return False

    def _archive_noise_unless_related(self, c, turn_ids: list[str]) -> int:
        kept = 0
        with c._lock:
            for tid in turn_ids:
                m = c.get(tid)
                if m is None or m.consolidated_into:
                    continue
                if self._related_to_kept(c, m):
                    m.metadata["abstracted"] = True
                    kept += 1
                else:
                    m.consolidated_into = NOISE
                c.graph.mark_dirty(m)
            c.flush()
        return kept

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
