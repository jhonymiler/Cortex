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

    Operations:
      1. Replay: touch high-utility memories (boost importance)
      2. Consolidate: cluster similar memories, mark one as canonical
      3. Cleanup: remove memories with very low retrievability

    v5 simplifications vs v3:
      - No LLM reflection
      - No auto-sleep cycles (external cron)
      - No spaced-repetition scheduling
    """

    def __init__(
        self,
        consolidation_threshold: float = 0.85,
        cleanup_threshold: float = 0.05,
        replay_count: int = 5,
    ) -> None:
        """
        Args:
            consolidation_threshold: similarity above which 2 memories are merged
            cleanup_threshold: retrievability below which a memory is deleted
            replay_count: number of top memories to "replay" (touch + boost)
        """
        self.consolidation_threshold = consolidation_threshold
        self.cleanup_threshold = cleanup_threshold
        self.replay_count = replay_count

    def run_cycle(self, graph: "MemoryGraph") -> DreamCycleResult:
        """
        Run one consolidation cycle. Returns stats.
        """
        import time
        start = time.perf_counter()

        result = DreamCycleResult()

        # 1. Replay top memories (boost importance + touch)
        result.n_replayed = self._replay_top(graph)

        # 2. Consolidate similar memories
        result.n_consolidated = self._consolidate_similar(graph)

        # 3. Cleanup forgotten
        result.n_cleaned = self._cleanup_forgotten(graph)

        result.duration_ms = (time.perf_counter() - start) * 1000
        return result

    def _replay_top(self, graph: "MemoryGraph") -> int:
        """Touch top-N most important memories to boost their access_count."""
        if not hasattr(graph, "iter_memories"):
            return 0
        memories = list(graph.iter_memories())
        # Sort by importance desc
        memories.sort(key=lambda m: m.importance, reverse=True)
        # Touch top N
        for mem in memories[:self.replay_count]:
            mem.touch()  # increments access_count
        return min(self.replay_count, len(memories))

    def _consolidate_similar(self, graph: "MemoryGraph") -> int:
        """Merge similar memories (token Jaccard above threshold)."""
        if not hasattr(graph, "iter_memories"):
            return 0
        memories = list(graph.iter_memories())
        merged = 0
        # Naive O(n^2) — fine for v5 scale
        skip_ids = set()
        for i, m1 in enumerate(memories):
            if m1.id in skip_ids:
                continue
            for m2 in memories[i + 1:]:
                if m2.id in skip_ids:
                    continue
                # Skip if different who/where
                if (m1.who or []) and (m2.who or []) and not set(m1.who) & set(m2.who):
                    continue
                if (m1.where or "default") != (m2.where or "default"):
                    continue
                # Compute Jaccard
                a = set((m1.what or "").lower().split())
                b = set((m2.what or "").lower().split())
                if not a or not b:
                    continue
                sim = len(a & b) / len(a | b)
                if sim >= self.consolidation_threshold:
                    # Merge: keep m1, mark m2 as consolidated_into m1
                    m2.consolidated_into = m1.id
                    # Boost m1 importance
                    m1.importance = min(1.0, m1.importance + 0.05)
                    merged += 1
                    skip_ids.add(m2.id)
        return merged

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
