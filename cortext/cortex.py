"""
CortexV5 — main entry point for the library.

A thin, thread-safe facade over:
  - MemoryGraph (indexed storage)
  - a Store (optional persistence: SQLite incremental, or JSON snapshot)
  - CanonicalValidator (NORMA at write time)
  - StructuralQueryParser (index-backed recall)
  - DreamAgent (opt-in background consolidation)

Usage:
    from cortext import CortexV5

    cortex = CortexV5(namespace="myapp", path="~/.cortext/memory.db")

    cortex.remember(who=["Maria"], what="pediu reembolso", where="suporte")
    context, result = cortex.recall("O que Maria pediu?")
"""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Optional

from cortext.core.decay import TIERS, memory_tier, retrievability
from cortext.core.graph import MemoryGraph
from cortext.core.memory import Memory
from cortext.core.recall import StructuralQueryParser
from cortext.core.recall.embedding import EmbeddingRecall
from cortext.core.recall.pack import pack_for_context
from cortext.core.text import fold
from cortext.core.validation import CanonicalValidator, ValidationPolicy, ValidationStatus
from cortext.workers import DreamAgent


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


class CortexV5:
    """
    Main entry point for the Cortext memory system.

    Every public method takes the instance lock, so one CortexV5 can serve
    many threads (a daemon, a background DreamAgent). With a ``path`` (or a
    ``store``) each write is persisted incrementally before the call returns.

    Detector compliance (target 5/5):
      E1. Discrete alphabet: Entity, Memory, Relation types
      E2. Syntax: W5H enforced via __post_init__ in Memory
      E3. Separable mapping + external referent: who points to real entities
      E4. Independent interpreter: StructuralQueryParser (not LLM)
      E5. Functional semantics: ForgetGate + DreamAgent + access_count
    """

    def __init__(
        self,
        namespace: str = "default",
        validation_policy: ValidationPolicy = ValidationPolicy.WARN,
        enable_embedding_recall: bool = True,
        enable_dream_agent: bool = False,
        path: Any = None,
        store: Any = None,
        autosave: bool = True,
    ) -> None:
        """
        Args:
            namespace: isolation namespace
            validation_policy: WARN (default) or BLOCK
            enable_embedding_recall: use embeddings for cross-language recall
                                     when sentence-transformers is installed
            enable_dream_agent: instantiate a DreamAgent (run_dream_cycle)
            path: persist to this file (.db/.sqlite -> SQLite, .json -> JSON)
            store: an already-open store (overrides ``path``)
            autosave: flush to the store after every mutating call (SQLite);
                      a JSON store is only written on flush()/close()
        """
        if store is None and path is not None:
            from cortext.store import open_store

            store = open_store(path)
        self.store = store
        self.graph = store.load(namespace) if store is not None else MemoryGraph(namespace=namespace)
        self.validator = CanonicalValidator(policy=validation_policy)
        self.parser = StructuralQueryParser(
            embedding_recall=EmbeddingRecall() if enable_embedding_recall else None,
            enable_embedding_recall=enable_embedding_recall,
        )
        self.dream_agent = DreamAgent() if enable_dream_agent else None
        self.namespace = namespace
        self.autosave = autosave
        self._lock = threading.RLock()
        self._stats = {
            "writes_total": 0,
            "writes_blocked": 0,
            "writes_warned": 0,
            "recalls_total": 0,
        }
        self._latency: dict[str, deque] = {
            "remember": deque(maxlen=512),
            "recall": deque(maxlen=512),
        }
        self._tier_cache: tuple[Any, dict[str, str]] = (None, {})

    # === Persistence ===

    def _autoflush(self) -> None:
        if self.store is not None and self.autosave and type(self.store).__name__ != "JsonStore":
            self.store.flush(self.graph)

    def flush(self) -> int:
        """Write pending changes to the store. Returns rows written (0 without a store)."""
        with self._lock:
            return self.store.flush(self.graph) if self.store is not None else 0

    def close(self) -> None:
        with self._lock:
            if self.store is not None:
                self.store.flush(self.graph)
                self.store.close()
                self.store = None

    def __enter__(self) -> "CortexV5":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # === Write API ===

    def remember(
        self,
        who: Optional[list[str]] = None,
        what: str = "",
        why: str = "",
        when: Any = None,
        where: str = "default",
        how: str = "",
        importance: float = 0.5,
        lang: Optional[str] = None,
        similar_to: Optional[Memory] = None,
        validate: bool = True,
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[Memory, Any]:
        """
        Store a memory. Optionally validates against the existing graph.

        Returns:
            (Memory, ValidationResult) — ValidationResult is None when
            validate=False. A BLOCKED memory is returned but not stored.
        """
        t0 = time.perf_counter()
        if similar_to is not None:
            if where == "default":
                where = similar_to.where
            if lang is None:
                lang = similar_to.lang
            if importance == 0.5:
                importance = similar_to.importance * 0.8
            if not who:
                who = list(similar_to.who)

        kwargs: dict[str, Any] = dict(
            who=who or [],
            what=what,
            why=why,
            where=where,
            how=how,
            importance=importance,
            lang=lang,
            metadata=dict(metadata or {}),
        )
        if when is not None:
            kwargs["when"] = when
        memory = Memory(**kwargs)

        with self._lock:
            result = None
            if validate:
                result = self.validator.validate_write(memory, self.graph)
                self._stats["writes_total"] += 1
                if result.status == ValidationStatus.BLOCKED:
                    self._stats["writes_blocked"] += 1
                    return memory, result
                if result.status == ValidationStatus.WARN:
                    self._stats["writes_warned"] += 1

            self.graph.add_memory(memory)
            self._autoflush()
            self._latency["remember"].append((time.perf_counter() - t0) * 1000)
        return memory, result

    def remember_text(
        self,
        text: str,
        who: Optional[list[str]] = None,
        where: Optional[str] = None,
        how: str = "",
        importance: float = 0.5,
        validate: bool = True,
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[Memory, Any]:
        """Store free text: who/when/where are extracted heuristically."""
        from cortext.core.recall.text_extractor import extract_via_heuristic

        data = extract_via_heuristic(text)
        return self.remember(
            who=who if who is not None else data.get("who", []),
            what=text,
            where=where or data.get("where", "default"),
            how=how,
            importance=importance,
            validate=validate,
            metadata=metadata,
        )

    def forget(self, memory_id: str) -> bool:
        """Delete a memory (and the duplicates consolidated into it)."""
        with self._lock:
            memory = self.graph.remove_memory(memory_id)
            if memory is None:
                return False
            for m in [m for m in self.graph.iter_memories() if m.consolidated_into == memory_id]:
                self.graph.remove_memory(m.id)
            self._autoflush()
            return True

    # === Read API ===

    def recall(
        self,
        query: str,
        lang: str = "auto",
        max_results: int = 5,
        max_tokens: int = 200,
        touch: bool = True,
    ) -> tuple[str, Any]:
        """
        Recall memories matching the query. Returns (packed_context, RecallResult).

        touch=True (default) records the access on each returned memory — the
        usage signal behind decay and consolidation. Audit reads pass False.
        """
        t0 = time.perf_counter()
        with self._lock:
            result = self.parser.recall(query, self.graph, lang=lang, max_results=max_results)
            if touch and result.memories:
                for memory in result.memories:
                    memory.touch()
                # Access counts are written behind: a read never waits on the
                # disk. They reach the store with the next write, flush() or
                # close() (the daemon also flushes them every few seconds).
                self.graph.mark_dirty(result.memories)
            packed = pack_for_context(result.memories, result.intent, max_tokens=max_tokens)
            self._stats["recalls_total"] += 1
            self._latency["recall"].append((time.perf_counter() - t0) * 1000)
        return packed, result

    def get(self, memory_id: str) -> Optional[Memory]:
        with self._lock:
            return self.graph.get_memory(memory_id)

    # === Convenience API ===

    def remember_and_recall(
        self,
        what: str,
        who: Optional[list[str]] = None,
        where: str = "default",
        importance: float = 0.5,
        lang: Optional[str] = None,
    ) -> tuple[Memory, str]:
        """One-shot: store a memory, then recall what it was stored alongside."""
        memory, result = self.remember(who=who, what=what, where=where, importance=importance, lang=lang)
        if result is not None and result.is_blocking:
            return memory, ""
        context, _ = self.recall(what, max_results=3)
        return memory, context

    # === Inspection / audit API ===

    def _memory_to_record(self, memory: Memory, query: Optional[str] = None, now: Optional[datetime] = None) -> dict[str, Any]:
        """Serialize a memory to an audit record (W5H + metadata + level)."""
        now = now or datetime.now()
        when = memory.when
        record = {
            "id": memory.id,
            "who": list(memory.who or []),
            "what": memory.what,
            "why": memory.why,
            "when": when.isoformat() if hasattr(when, "isoformat") else when,
            "where": memory.where,
            "how": memory.how,
            "importance": round(memory.importance, 3),
            "access_count": memory.access_count,
            "lang": memory.lang,
            "created_at": memory.created_at.isoformat(),
            "last_accessed": memory.last_accessed.isoformat() if memory.last_accessed else None,
            "tier": memory_tier(memory, now),
            "retrievability": round(retrievability(memory, now), 3),
            "consolidated_into": memory.consolidated_into,
            "is_summary": memory.is_summary,
        }
        if query is not None:
            record["match_score"] = round(memory.matches_text(query), 3)
        return record

    def inspect(self, query: str, lang: str = "auto", max_results: int = 5) -> dict[str, Any]:
        """Structured recall for auditing (does not count as an access)."""
        _, result = self.recall(query, lang=lang, max_results=max_results, touch=False)
        metrics = {
            k: v for k, v in (result.metrics or {}).items()
            if isinstance(v, (str, int, float, bool, type(None)))
        }
        with self._lock:
            return {
                "query": query,
                "namespace": self.namespace,
                "count": len(result.memories),
                "memories": [self._memory_to_record(m, query) for m in result.memories],
                "metrics": metrics,
            }

    def about(self, entity: str, max_results: int = 20) -> dict[str, Any]:
        """All memories about an entity (who-match), by importance then recency."""
        with self._lock:
            mems = [m for m in self.graph.find_memories(who=entity) if not m.consolidated_into]
            mems.sort(key=lambda m: (m.importance, m.created_at), reverse=True)
            mems = mems[:max_results]
            return {
                "entity": entity,
                "namespace": self.namespace,
                "count": len(mems),
                "memories": [self._memory_to_record(m) for m in mems],
            }

    def _tiers(self) -> dict[str, str]:
        """memory id -> tier, cached per graph version and 30-second window."""
        key = (id(self.graph), self.graph.version, int(time.time() // 30))
        if self._tier_cache[0] != key:
            now = datetime.now()
            self._tier_cache = (key, {m.id: memory_tier(m, now) for m in self.graph.iter_memories()})
        return self._tier_cache[1]

    def levels(self) -> dict[str, int]:
        """How many memories sit in each level (working ... archived)."""
        with self._lock:
            counts = dict.fromkeys(TIERS, 0)
            for tier in self._tiers().values():
                counts[tier] += 1
            return counts

    def list_memories(
        self,
        tier: Optional[str] = None,
        query: Optional[str] = None,
        who: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort: str = "recent",
    ) -> dict[str, Any]:
        """Page through memories, filtered by level, text and participant."""
        with self._lock:
            tiers = self._tiers()
            if query:
                from cortext.core.text import tokenize

                ids = self.graph.ids_for_tokens(tokenize(query), prefix=True)
                if ids:
                    pool = [self.graph.get_memory(i) for i in ids]
                else:  # no content token (short/stopword query): substring scan
                    needle = fold(query)
                    pool = [m for m in self.graph.iter_memories() if needle in fold(m.what)]
            elif who:
                pool = self.graph.find_memories(who=who)
            else:
                pool = self.graph.all_memories()
            pool = [m for m in pool if m is not None and (tier is None or tiers.get(m.id) == tier)]
            keys = {
                "recent": lambda m: m.created_at,
                "importance": lambda m: (m.importance, m.created_at),
                "access": lambda m: (m.access_count, m.created_at),
            }
            pool.sort(key=keys.get(sort, keys["recent"]), reverse=True)
            now = datetime.now()
            return {
                "namespace": self.namespace,
                "total": len(pool),
                "offset": offset,
                "memories": [self._memory_to_record(m, now=now) for m in pool[offset: offset + limit]],
            }

    def graph_snapshot(self, limit: int = 400) -> dict[str, Any]:
        """Nodes and links for visualization: memories, their participants and places.

        The ``limit`` most relevant memories are kept (active first, by
        importance, access and recency); entities are derived from ``who``.
        """
        with self._lock:
            tiers = self._tiers()
            now = datetime.now()
            mems = sorted(
                self.graph.iter_memories(),
                key=lambda m: (m.consolidated_into is None, m.importance + 0.05 * min(m.access_count, 10), m.created_at),
                reverse=True,
            )[:limit]
            nodes: list[dict[str, Any]] = []
            links: list[dict[str, Any]] = []
            people: dict[str, dict[str, Any]] = {}
            kept = {m.id for m in mems}
            for m in mems:
                nodes.append({
                    "id": m.id, "kind": "memory", "label": m.what[:80], "tier": tiers.get(m.id, "episodic"),
                    "importance": round(m.importance, 3), "access": m.access_count,
                    "r": round(retrievability(m, now), 3), "where": m.where,
                    "who": list(m.who or []), "created_at": m.created_at.isoformat(),
                })
                for w in m.who or ():
                    key = "e:" + fold(w)
                    person = people.get(key)
                    if person is None:
                        person = people[key] = {"id": key, "kind": "entity", "label": w, "degree": 0}
                    person["degree"] += 1
                    links.append({"source": m.id, "target": key, "kind": "who"})
                if m.consolidated_into and m.consolidated_into in kept:
                    links.append({"source": m.id, "target": m.consolidated_into, "kind": "merged"})
            nodes.extend(people.values())
            return {"namespace": self.namespace, "nodes": nodes, "links": links, "total_memories": len(self.graph)}

    # === Background ===

    def run_dream_cycle(self) -> Any:
        """Run one Dream Agent consolidation cycle (if enabled)."""
        if not self.dream_agent:
            raise RuntimeError("DreamAgent not enabled. Pass enable_dream_agent=True to CortexV5().")
        with self._lock:
            result = self.dream_agent.run_cycle(self.graph)
            self._autoflush()
            return result

    # === Stats ===

    def latency(self) -> dict[str, dict[str, float]]:
        """p50/p95/max of recent remember/recall calls, in milliseconds."""
        out = {}
        for op, samples in self._latency.items():
            vals = list(samples)
            out[op] = {
                "count": len(vals),
                "p50_ms": round(_percentile(vals, 0.50), 3),
                "p95_ms": round(_percentile(vals, 0.95), 3),
                "max_ms": round(max(vals), 3) if vals else 0.0,
            }
        return out

    def stats(self) -> dict[str, Any]:
        """Combined stats: graph + writes + recalls + levels + latency."""
        with self._lock:
            return {
                "namespace": self.namespace,
                "graph": self.graph.stats(),
                "writes": dict(self._stats),
                "validator_policy": self.validator.policy.value,
                "levels": self.levels(),
                "latency": self.latency(),
                "store": repr(self.store) if self.store is not None else None,
            }

    def __repr__(self) -> str:
        return f"CortexV5(ns={self.namespace!r}, M={len(self.graph)}, validator={self.validator.policy.value})"


# Brand-consistent aliases (docs and the CLI use these names).
CortextV5 = CortexV5
Cortex = CortexV5
