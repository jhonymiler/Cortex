"""
Forget Gate — active forgetting based on 3 signals.

Inspired by LSTM forget gates and active forgetting in human cognition.
3 signals combine into a forget score (0-1, higher = more forgettable):

  1. Noise (0.4 weight): how likely the memory is noise vs signal
     - Low importance, no participants, empty/short content
  2. Redundancy (0.35): is this memory redundant with others?
  3. Obsolescence (0.25): is this memory outdated?

Usage: gate = ForgetGate()
       score = gate.compute_forget_signal(memory, graph)
       if score >= threshold: accelerate_decay(memory)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cortext.core.memory import Memory
    from cortext.core.graph import MemoryGraph


@dataclass
class ForgetGateConfig:
    noise_weight: float = 0.4
    redundancy_weight: float = 0.35
    obsolescence_weight: float = 0.25
    forget_threshold: float = 0.3  # lowered from 0.6 — typical "noisy" memories cross this


class ForgetGate:
    """
    Active forgetting: score memories for deletion.

    Combines 3 signals into a single forget score.
    """

    def __init__(self, config: ForgetGateConfig | None = None) -> None:
        self.config = config or ForgetGateConfig()

    def compute_forget_signal(
        self, memory: "Memory", graph: "MemoryGraph"
    ) -> float:
        """Compute forget signal (0-1, higher = more forgettable)."""
        noise = self._noise_score(memory)
        redundancy = self._redundancy_score(memory, graph)
        obsolescence = self._obsolescence_score(memory)

        return min(1.0, max(0.0, (
            self.config.noise_weight * noise +
            self.config.redundancy_weight * redundancy +
            self.config.obsolescence_weight * obsolescence
        )))

    def filter_forgettable(
        self, memories: list["Memory"], graph: "MemoryGraph"
    ) -> tuple[list["Memory"], list["Memory"]]:
        """
        Split memories into (keep, forget) based on forget signal.

        Returns:
            (memories_to_keep, memories_to_forget)
        """
        keep: list["Memory"] = []
        forget: list["Memory"] = []
        for mem in memories:
            signal = self.compute_forget_signal(mem, graph)
            if signal >= self.config.forget_threshold:
                forget.append(mem)
            else:
                keep.append(mem)
        return keep, forget

    def accelerate_decay(
        self, memory: "Memory", multiplier: float = 0.5
    ) -> float:
        """Reduce importance to accelerate decay. Returns new importance."""
        memory.importance = max(0.0, memory.importance * multiplier)
        return memory.importance

    def _noise_score(self, memory: "Memory") -> float:
        """Estimate if memory is noise vs signal."""
        score = 0.0

        # Low importance
        if memory.importance < 0.3:
            score += 0.3
        elif memory.importance < 0.5:
            score += 0.1

        # No participants
        if not memory.who:
            score += 0.2

        # Empty/short content
        content_len = len(memory.what or "")
        if content_len < 10:
            score += 0.2
        elif content_len < 30:
            score += 0.1

        # Generic values
        generic_terms = {"undefined", "none", "null", "unknown", "n/a", ""}
        if (memory.what or "").lower().strip() in generic_terms:
            score += 0.2

        # Not consolidated
        if not memory.is_consolidated:
            score += 0.1

        return min(1.0, score)

    def _redundancy_score(
        self, memory: "Memory", graph: "MemoryGraph"
    ) -> float:
        """Estimate redundancy with other memories."""
        score = 0.0
        similar_count = 0
        if hasattr(graph, "iter_memories"):
            for other in graph.iter_memories():
                if other.id == memory.id:
                    continue
                # Simple overlap check on what-field
                a = set((memory.what or "").lower().split())
                b = set((other.what or "").lower().split())
                if a and b:
                    overlap = len(a & b) / len(a | b)
                    if overlap > 0.7:
                        similar_count += 1

        if similar_count >= 3:
            score += 0.5
        elif similar_count >= 1:
            score += 0.2

        return min(1.0, score)

    def _obsolescence_score(self, memory: "Memory") -> float:
        """Estimate if memory is obsolete."""
        score = 0.0
        now = datetime.now()

        # Old with no recent access
        if memory.when:
            days_old = (now - memory.when).days
            last_access = memory.last_accessed or memory.when
            days_since_access = (now - last_access).days
            if days_old > 90 and days_since_access > 60:
                score += 0.4
            elif days_old > 30 and days_since_access > 30:
                score += 0.2

        # Low retrievability (uses ebbinghaus)
        try:
            from cortext.core.decay.ebbinghaus import retrievability
            r = retrievability(memory)
            if r < 0.2:
                score += 0.4
            elif r < 0.4:
                score += 0.2
        except Exception:
            pass

        return min(1.0, score)
