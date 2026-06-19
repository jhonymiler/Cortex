"""
Dream Agent — background consolidator.

Inspired by human sleep consolidation: replay high-utility memories,
cluster similar ones, and clean up forgotten ones. Opt-in (default off).

This is a SIMPLIFIED version of the v3 dream_agent. No LLM-based
reflection, no auto-sleep cycles (use external cron for that).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cortex_v5.core.memory import Memory
    from cortex_v5.core.graph import MemoryGraph


@dataclass
class DreamCycleResult:
    """Statistics from a single dream cycle run."""

    cycle_at: datetime = field(default_factory=datetime.now)
    n_consolidated: int = 0
    n_replayed: int = 0
    n_cleaned: int = 0
    duration_ms: float = 0.0


class DreamAgent:
    """
    Background consolidator. Opt-in — call run_cycle() when desired.

    Operations (run_cycle order: cleanup → consolidate → replay):
      1. Cleanup: remove memories with very low retrievability
      2. Consolidate: cluster near-duplicate memories into a canonical one
      3. Replay: touch high-utility memories (boost importance)

    Consolidation is hybrid:
      - Candidate generation is always heuristic (bucket by who/where + token
        Jaccard). This is cheap and scales — it is what makes "many memories"
        tractable: the LLM never sees the whole graph, only small candidate
        clusters.
      - The merge step is pluggable. Without an llm_fn, the most-informative
        memory in a cluster becomes canonical and the rest are marked
        consolidated_into it (no info-preserving summary). With an llm_fn, the
        cluster is sent to the LLM, which writes a single merged memory that
        preserves the union of facts.

    v5 simplifications vs v3:
      - No auto-sleep cycles (external cron or background thread)
      - No spaced-repetition scheduling
    """

    def __init__(
        self,
        consolidation_threshold: float = 0.85,
        cleanup_threshold: float = 0.05,
        replay_count: int = 5,
        llm_fn=None,
        llm_candidate_threshold: float = 0.45,
        max_llm_merges: int = 5,
    ) -> None:
        """
        Args:
            consolidation_threshold: heuristic similarity above which 2 memories
                are merged (used when llm_fn is None)
            cleanup_threshold: retrievability below which a memory is deleted
            replay_count: number of top memories to "replay" (touch + boost)
            llm_fn: optional callable(prompt)->str. When set, the merge step
                uses the LLM to write info-preserving summaries.
            llm_candidate_threshold: lower similarity used to form candidate
                clusters in LLM mode (catches paraphrases the LLM can judge)
            max_llm_merges: cap on LLM merge calls per cycle (cost budget)
        """
        self.consolidation_threshold = consolidation_threshold
        self.cleanup_threshold = cleanup_threshold
        self.replay_count = replay_count
        self.llm_fn = llm_fn
        self.llm_candidate_threshold = llm_candidate_threshold
        self.max_llm_merges = max_llm_merges

    def run_cycle(self, graph: "MemoryGraph") -> DreamCycleResult:
        """
        Run one consolidation cycle. Returns stats.
        """
        import time
        start = time.perf_counter()

        result = DreamCycleResult()

        # Order matters:
        #   1. Cleanup FIRST — remove forgotten memories before anything touches
        #      them. (Replaying before cleanup would reset last_accessed and
        #      resurrect memories that should have been pruned.)
        #   2. Consolidate survivors — merge near-duplicates.
        #   3. Replay LAST — boost the important survivors.
        result.n_cleaned = self._cleanup_forgotten(graph)
        result.n_consolidated = self._consolidate_similar(graph)
        result.n_replayed = self._replay_top(graph)

        result.duration_ms = (time.perf_counter() - start) * 1000
        return result

    def _replay_top(self, graph: "MemoryGraph") -> int:
        """Touch top-N most important memories to boost their access_count."""
        if not hasattr(graph, "iter_memories"):
            return 0
        # Don't replay memories that were merged away.
        memories = [m for m in graph.iter_memories() if not m.consolidated_into]
        # Sort by importance desc
        memories.sort(key=lambda m: m.importance, reverse=True)
        # Touch top N
        for mem in memories[:self.replay_count]:
            mem.touch()  # increments access_count
        return min(self.replay_count, len(memories))

    def _consolidate_similar(self, graph: "MemoryGraph") -> int:
        """Merge near-duplicate memories (token Jaccard above threshold).

        Bucketed by ``where`` then primary ``who`` so the O(n^2) comparison
        only runs *within* groups that could ever match (consolidation already
        requires same who/where). On a corpus of unrelated memories this is
        effectively linear; the quadratic term is bounded by the largest
        same-who/where cluster, not the whole graph.

        Already-consolidated memories (``consolidated_into`` set) are skipped.
        """
        if not hasattr(graph, "iter_memories"):
            return 0

        # Bucket key: (where, frozenset(who)). Memories with no who go in their
        # own per-where bucket (they can only merge with other who-less ones).
        buckets: dict[tuple, list] = {}
        for m in graph.iter_memories():
            if m.consolidated_into:
                continue
            key = ((m.where or "default"), frozenset(m.who or ()))
            buckets.setdefault(key, []).append(m)

        # In LLM mode, group at a lower threshold (catch paraphrases the LLM
        # can judge); otherwise require high similarity for a safe heuristic merge.
        threshold = (
            self.llm_candidate_threshold if self.llm_fn else self.consolidation_threshold
        )

        merged = 0
        llm_budget = self.max_llm_merges
        for group in buckets.values():
            if len(group) < 2:
                continue
            tokens = {m.id: set((m.what or "").lower().split()) for m in group}
            skip_ids = set()
            for i, m1 in enumerate(group):
                if m1.id in skip_ids:
                    continue
                a = tokens[m1.id]
                if not a:
                    continue
                cluster = [m1]
                for m2 in group[i + 1:]:
                    if m2.id in skip_ids:
                        continue
                    b = tokens[m2.id]
                    if not b:
                        continue
                    sim = len(a & b) / len(a | b)
                    if sim >= threshold:
                        cluster.append(m2)
                        skip_ids.add(m2.id)
                if len(cluster) < 2:
                    continue
                if self.llm_fn and llm_budget > 0:
                    if self._llm_merge(graph, cluster):
                        merged += len(cluster) - 1
                        llm_budget -= 1
                        continue
                # Heuristic merge: most-informative memory is canonical.
                merged += self._heuristic_merge(cluster)
        return merged

    @staticmethod
    def _heuristic_merge(cluster: list) -> int:
        """Keep the most-informative memory as canonical; mark the rest merged.

        'Most informative' = longest `what` (proxy for richest content), so we
        don't drop 'urgente'/'hoje' qualifiers by arbitrarily keeping the first.
        """
        canonical = max(cluster, key=lambda m: len((m.what or "")))
        n = 0
        for m in cluster:
            if m.id == canonical.id:
                continue
            m.consolidated_into = canonical.id
            n += 1
        if n:
            canonical.importance = min(1.0, canonical.importance + 0.05)
        return n

    def _llm_merge(self, graph: "MemoryGraph", cluster: list) -> bool:
        """Use the LLM to write one info-preserving merged memory for a cluster.

        Returns True if a merge happened. On any failure, returns False so the
        caller falls back to the heuristic merge.
        """
        import json

        from cortex_v5.core.memory import Memory

        lines = []
        for idx, m in enumerate(cluster, 1):
            parts = [m.what or ""]
            if m.why:
                parts.append(f"(porque: {m.why})")
            if m.how:
                parts.append(f"(como: {m.how})")
            lines.append(f"{idx}. {' '.join(parts)}")
        listing = "\n".join(lines)
        prompt = (
            "Você consolida memórias duplicadas/relacionadas de um agente em UMA "
            "única memória, preservando todos os fatos (não invente, não omita). "
            "Se forem o mesmo assunto, una; mantenha a informação mais específica "
            "e a mais recente em caso de conflito.\n\n"
            f"Memórias:\n{listing}\n\n"
            "Responda APENAS com JSON: "
            '{"what": "fato consolidado", "why": "", "how": ""}'
        )
        try:
            raw = self.llm_fn(prompt)
            if not raw:
                return False
            data = self._parse_json(raw)
            what = (data.get("what") or "").strip()
            if not what:
                return False
        except Exception:
            return False

        # Build the consolidated memory: union of who, same where, max importance.
        who: list = []
        for m in cluster:
            for w in (m.who or []):
                if w not in who:
                    who.append(w)
        summary = Memory(
            who=who,
            what=what,
            why=(data.get("why") or "").strip(),
            how=(data.get("how") or "").strip(),
            where=cluster[0].where,
            importance=min(1.0, max(m.importance for m in cluster) + 0.05),
            lang=cluster[0].lang,
            is_summary=True,
            consolidated_from=[m.id for m in cluster],
        )
        graph.add_memory(summary)
        for m in cluster:
            m.consolidated_into = summary.id
        return True

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """Extract the first JSON object from an LLM response."""
        import json

        raw = raw.strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end < start:
            return {}
        return json.loads(raw[start : end + 1])

    def _cleanup_forgotten(self, graph: "MemoryGraph") -> int:
        """Delete memories with very low retrievability."""
        if not hasattr(graph, "iter_memories"):
            return 0
        from cortex_v5.core.decay.ebbinghaus import retrievability

        to_delete = []
        for mem in graph.iter_memories():
            try:
                r = retrievability(mem)
                if r < self.cleanup_threshold:
                    to_delete.append(mem)
            except Exception:
                pass

        # Delete (direct dict removal)
        for mem in to_delete:
            if hasattr(graph, "_memories"):
                graph._memories.pop(mem.id, None)
        return len(to_delete)
