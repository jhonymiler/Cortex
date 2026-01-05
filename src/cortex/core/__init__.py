"""Core components of Cortex memory system."""

from cortex.core.entity import Entity
from cortex.core.episode import Episode
from cortex.core.relation import Relation
from cortex.core.memory_graph import MemoryGraph, RecallResult
from cortex.core.namespace import NamespacedMemoryManager, get_memory_manager, reset_memory_manager
from cortex.core.identity import (
    IdentityKernel,
    JailbreakPattern,
    EvaluationResult,
    Threat,
    Action,
    Severity,
    Boundary,
    Value,
    Directive,
    create_default_kernel,
    create_strict_kernel,
)
from cortex.core.contradiction import (
    ContradictionDetector,
    Contradiction,
    ResolutionStrategy,
    ResolutionResult,
    create_default_detector,
    create_conservative_detector,
    create_strict_detector,
)

__all__ = [
    "Entity",
    "Episode",
    "Relation",
    "MemoryGraph",
    "RecallResult",
    "NamespacedMemoryManager",
    "get_memory_manager",
    "reset_memory_manager",
    # Identity / Anti-jailbreak
    "IdentityKernel",
    "JailbreakPattern",
    "EvaluationResult",
    "Threat",
    "Action",
    "Severity",
    "Boundary",
    "Value",
    "Directive",
    "create_default_kernel",
    "create_strict_kernel",
    # Contradiction Detection
    "ContradictionDetector",
    "Contradiction",
    "ResolutionStrategy",
    "ResolutionResult",
    "create_default_detector",
    "create_conservative_detector",
    "create_strict_detector",
]
