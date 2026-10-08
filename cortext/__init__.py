"""Cortext — Memory system for AI agents.

5-element detector compliant, internationalized, efficient.

Exports resolve lazily (PEP 562): ``from cortext import CortexV5`` works as
always, but importing a light submodule (the hook client, the CLI) does not
pay for loading the whole engine — agent hooks start a process per event.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

__version__ = "0.5.0"

_EXPORTS: dict[str, str] = {
    # Main entry point
    "CortexV5": "cortext.cortex",
    "CortextV5": "cortext.cortex",
    "Cortex": "cortext.cortex",
    # Core data structures
    "Memory": "cortext.core.memory",
    "Entity": "cortext.core.entity",
    "Relation": "cortext.core.relation",
    "RelationType": "cortext.core.relation",
    "MemoryGraph": "cortext.core.graph",
    "RecallResult": "cortext.core.graph",
    # Validation
    "CanonicalValidator": "cortext.core.validation",
    "ValidationResult": "cortext.core.validation",
    "ValidationStatus": "cortext.core.validation",
    "ValidationPolicy": "cortext.core.validation",
    "create_default_validator": "cortext.core.validation",
    "create_strict_validator": "cortext.core.validation",
    # Recall
    "StructuralQueryParser": "cortext.core.recall",
    "QueryIntent": "cortext.core.recall",
    "pack_for_context": "cortext.core.recall",
    "RegexExtractor": "cortext.core.recall",
    "LLMExtractor": "cortext.core.recall",
    "HybridExtractor": "cortext.core.recall",
    # Decay and levels
    "DecayConfig": "cortext.core.decay",
    "retrievability": "cortext.core.decay",
    "effective_stability": "cortext.core.decay",
    "decay_status": "cortext.core.decay",
    "memory_tier": "cortext.core.decay",
    "TIERS": "cortext.core.decay",
    "ForgetGate": "cortext.core.decay",
    "ForgetGateConfig": "cortext.core.decay",
    # Workers
    "DreamAgent": "cortext.workers",
    # Persistence
    "SQLiteStore": "cortext.store",
    "JsonStore": "cortext.store",
    "open_store": "cortext.store",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module 'cortext' has no attribute {name!r}")
    value = getattr(importlib.import_module(module), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals()) + __all__)


if TYPE_CHECKING:  # pragma: no cover - static analyzers see real imports
    from cortext.cortex import CortexV5, CortextV5, Cortex
    from cortext.core.memory import Memory
    from cortext.core.entity import Entity
    from cortext.core.relation import Relation, RelationType
    from cortext.core.graph import MemoryGraph, RecallResult
    from cortext.core.validation import (
        CanonicalValidator, ValidationResult, ValidationStatus, ValidationPolicy,
        create_default_validator, create_strict_validator,
    )
    from cortext.core.recall import (
        StructuralQueryParser, QueryIntent, pack_for_context,
        RegexExtractor, LLMExtractor, HybridExtractor,
    )
    from cortext.core.decay import (
        DecayConfig, retrievability, effective_stability, decay_status,
        memory_tier, TIERS, ForgetGate, ForgetGateConfig,
    )
    from cortext.workers import DreamAgent
    from cortext.store import SQLiteStore, JsonStore, open_store
