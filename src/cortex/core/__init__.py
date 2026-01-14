"""Core components of Cortex memory system."""

# Primitives (basic memory types)
from cortex.core.primitives import Entity, Episode, Relation, Memory, NamespacedMemoryManager
from cortex.core.primitives.namespace import get_memory_manager, reset_memory_manager

# Graph (memory graph and recall)
from cortex.core.graph import MemoryGraph, RecallResult

# Learning (decay, forgetting, attention, contradiction)
from cortex.core.learning.decay import (
    DecayManager,
    DecayConfig,
    create_decay_manager,
    create_default_decay_manager,
    create_aggressive_decay_manager,
    create_gentle_decay_manager,
)
from cortex.core.learning.contradiction import (
    ContradictionDetector,
    Contradiction,
    ResolutionStrategy,
    ResolutionResult,
    create_default_detector,
    create_conservative_detector,
    create_strict_detector,
)

# Storage (shared memory, collective memory, identity)
from cortex.core.storage.shared_memory import (
    SharedMemoryManager,
    MemoryVisibility,
    SharedMemoryContext,
    MemoryWithVisibility,
    NamespaceConfig,
    create_shared_memory_manager,
)
from cortex.core.storage.identity import (
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

__all__ = [
    "Entity",
    "Episode",
    "Relation",
    "Memory",  # W5H memory model
    "MemoryGraph",
    "RecallResult",
    "NamespacedMemoryManager",
    "get_memory_manager",
    "reset_memory_manager",
    # Decay / Forgetting
    "DecayManager",
    "DecayConfig",
    "create_decay_manager",
    "create_default_decay_manager",
    "create_aggressive_decay_manager",
    "create_gentle_decay_manager",
    # Shared Memory
    "SharedMemoryManager",
    "MemoryVisibility",
    "SharedMemoryContext",
    "MemoryWithVisibility",
    "NamespaceConfig",
    "create_shared_memory_manager",
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
