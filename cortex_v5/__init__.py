"""Cortex v5 — Memory system for AI agents.

5-element detector compliant, internationalized, efficient.
"""

from cortex_v5.cortex import CortexV5
from cortex_v5.core.memory import Memory
from cortex_v5.core.entity import Entity
from cortex_v5.core.relation import Relation, RelationType
from cortex_v5.core.graph import MemoryGraph, RecallResult
from cortex_v5.core.validation import (
    CanonicalValidator,
    ValidationResult,
    ValidationStatus,
    ValidationPolicy,
    create_default_validator,
    create_strict_validator,
)
from cortex_v5.core.recall import (
    StructuralQueryParser,
    QueryIntent,
    pack_for_context,
    RegexExtractor,
    LLMExtractor,
    HybridExtractor,
)
from cortex_v5.core.decay import (
    DecayConfig,
    retrievability,
    effective_stability,
    decay_status,
    ForgetGate,
    ForgetGateConfig,
)
from cortex_v5.workers import DreamAgent

__version__ = "5.0.0"

__all__ = [
    # Main entry point
    "CortexV5",
    # Core data structures
    "Memory",
    "Entity",
    "Relation",
    "RelationType",
    "MemoryGraph",
    "RecallResult",
    # Validation
    "CanonicalValidator",
    "ValidationResult",
    "ValidationStatus",
    "ValidationPolicy",
    "create_default_validator",
    "create_strict_validator",
    # Recall
    "StructuralQueryParser",
    "QueryIntent",
    "pack_for_context",
    "RegexExtractor",
    "LLMExtractor",
    "HybridExtractor",
    # Decay
    "DecayConfig",
    "retrievability",
    "effective_stability",
    "decay_status",
    "ForgetGate",
    "ForgetGateConfig",
    # Workers
    "DreamAgent",
]
