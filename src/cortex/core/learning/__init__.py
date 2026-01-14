"""
Cortex Learning System - Adaptive memory dynamics.

V2.0 Components:
- DecayManager: Ebbinghaus forgetting curve with SM-2 adaptive
- ForgetGate: LSTM-inspired active forgetting (30% noise reduction)
- MemoryAttention: Transformer-style attention for memory ranking
- ContradictionDetector: Detects and resolves contradictions
"""

from cortex.core.learning.decay import (
    DecayManager,
    ForgetGate,
)
from cortex.core.learning.memory_attention import (
    MemoryAttention,
    AttentionConfig,
)
from cortex.core.learning.contradiction import (
    ContradictionDetector,
    Contradiction,
    ResolutionStrategy,
    ResolutionResult,
    create_default_detector,
)

__all__ = [
    "DecayManager",
    "ForgetGate",
    "MemoryAttention",
    "AttentionConfig",
    "ContradictionDetector",
    "Contradiction",
    "ResolutionStrategy",
    "ResolutionResult",
    "create_default_detector",
]
