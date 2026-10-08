"""
Ebbinghaus decay — R = e^(-t/S).

The classic forgetting curve, applied to memory retrieval. Simple,
universal, and validated empirically (Ebbinghaus, 1885).

Formula: R = e^(-t/S)
  - R: retrievability (0.0-1.0)
  - t: time since last access (days)
  - S: stability (days) — base × modifiers

Stability modifiers (extensible):
  - access_count: more accesses = more stable (log scale)
  - importance: high importance = more stable
  - consolidation: consolidated memories = more stable
  - (custom) user-defined via metadata
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cortext.core.memory import Memory


@dataclass
class DecayConfig:
    """Tunables for the decay function."""

    # Base stability (days for 63% decay without reinforcement)
    base_stability_days: float = 7.0

    # Stability modifiers
    access_log_multiplier: float = 1.0      # log(access_count + 1) factor
    importance_bonus: float = 1.3            # bonus for high importance (>0.7)
    consolidation_bonus: float = 2.0        # bonus for consolidated memories

    # Min/max stability (prevent degenerate values)
    min_stability: float = 0.1
    max_stability: float = 365.0

    # Thresholds for status
    active_threshold: float = 0.7
    fading_threshold: float = 0.3
    forgotten_threshold: float = 0.1


def retrievability(
    memory: "Memory",
    now: datetime | None = None,
    config: DecayConfig | None = None,
) -> float:
    """
    Compute retrievability of a memory using the Ebbinghaus curve.

    R = e^(-t/S), where S = base_stability × modifiers.

    Returns:
        float between 0.0 (forgotten) and 1.0 (fresh)
    """
    if config is None:
        config = DecayConfig()
    now = now or datetime.now()

    # Reference time = last access, fallback to when the memory was *stored*.
    # Not `when`: that is the event's time, and a memory about a past event
    # ("born in 1990") is not forgotten the moment it is written.
    reference_time = memory.last_accessed or memory.created_at
    days_since = max(0.0, (now - reference_time).total_seconds() / 86400)

    # Compute effective stability
    s = effective_stability(memory, config)

    # Ebbinghaus formula
    return math.exp(-days_since / s)


def effective_stability(
    memory: "Memory",
    config: DecayConfig | None = None,
) -> float:
    """
    Compute the effective stability S for a memory.

    S = base × access_modifier × importance_modifier × consolidation_modifier
    """
    if config is None:
        config = DecayConfig()

    s = config.base_stability_days

    # Access count modifier (logarithmic)
    access_factor = 1.0 + config.access_log_multiplier * math.log(memory.access_count + 1)
    s *= access_factor

    # Importance bonus
    if memory.importance > 0.7:
        s *= config.importance_bonus

    # Consolidation bonus
    if memory.is_consolidated:
        s *= config.consolidation_bonus

    return max(config.min_stability, min(config.max_stability, s))


def decay_status(
    memory: "Memory",
    now: datetime | None = None,
    config: DecayConfig | None = None,
) -> str:
    """
    Get a categorical status: "active" | "fading" | "weak" | "forgotten".
    """
    if config is None:
        config = DecayConfig()
    r = retrievability(memory, now, config)
    if r >= config.active_threshold:
        return "active"
    elif r >= config.fading_threshold:
        return "fading"
    elif r >= config.forgotten_threshold:
        return "weak"
    return "forgotten"


# === Memory levels ===

#: The levels a memory moves through, in display order.
#:   working   — just stored, still "in mind" (younger than working_window)
#:   episodic  — short-term: an event, retrievable, not yet reinforced
#:   semantic  — long-term: reinforced by use, highly important, or a summary
#:   fading    — retrievability dropping; a candidate for the forget gate
#:   archived  — merged into another memory by consolidation (kept for audit)
TIERS = ("working", "episodic", "semantic", "fading", "archived")


@dataclass
class TierConfig:
    working_window_minutes: float = 60.0
    semantic_min_access: int = 3
    semantic_min_importance: float = 0.8
    fading_below: float = 0.3


def memory_tier(
    memory: "Memory",
    now: datetime | None = None,
    config: TierConfig | None = None,
    decay: DecayConfig | None = None,
) -> str:
    """Classify a memory into one of ``TIERS``."""
    if memory.consolidated_into:
        return "archived"
    config = config or TierConfig()
    now = now or datetime.now()
    age_min = (now - memory.created_at).total_seconds() / 60
    if age_min <= config.working_window_minutes and memory.access_count < config.semantic_min_access:
        return "working"
    if retrievability(memory, now, decay) < config.fading_below:
        return "fading"
    if (
        memory.is_consolidated
        or memory.access_count >= config.semantic_min_access
        or memory.importance >= config.semantic_min_importance
    ):
        return "semantic"
    return "episodic"
