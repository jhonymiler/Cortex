"""Cortext — Memory system for AI agents.

5-element detector compliant, internationalized, efficient.
"""

from cortext.cortex import CortexV5
from cortext.core.memory import Memory
from cortext.core.entity import Entity
from cortext.core.relation import Relation, RelationType
from cortext.core.graph import MemoryGraph, RecallResult
from cortext.core.validation import (
    CanonicalValidator,
    ValidationResult,
    ValidationStatus,
    ValidationPolicy,
    create_default_validator,
    create_strict_validator,
)
from cortext.core.recall import (
    StructuralQueryParser,
    QueryIntent,
    pack_for_context,
    RegexExtractor,
    LLMExtractor,
    HybridExtractor,
)
from cortext.core.decay import (
    DecayConfig,
    retrievability,
    effective_stability,
    decay_status,
    ForgetGate,
    ForgetGateConfig,
)
from cortext.workers import DreamAgent

__version__ = "0.3.1"

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
