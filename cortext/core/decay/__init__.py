"""
Decay subsystem: Ebbinghaus R = e^(-t/S) + Forget Gate.
"""

from cortext.core.decay.ebbinghaus import (
    DecayConfig,
    retrievability,
    effective_stability,
    decay_status,
    memory_tier,
    TierConfig,
    TIERS,
)
from cortext.core.decay.forget_gate import (
    ForgetGate,
    ForgetGateConfig,
)

__all__ = [
    "DecayConfig",
    "retrievability",
    "effective_stability",
    "decay_status",
    "memory_tier",
    "TierConfig",
    "TIERS",
    "ForgetGate",
    "ForgetGateConfig",
]
