"""
Cortex Graph Module - Modular Memory Graph Components

This module provides organized access to MemoryGraph and related types.

Backward Compatibility:
    from cortex.core.memory_graph import MemoryGraph, RecallResult  # Still works!

New Modular Imports:
    from cortex.core.graph import MemoryGraph, RecallResult
    from cortex.core.graph.types import RecallResult
"""

# Import from original location for now (backward compatibility)
from cortex.core.memory_graph import MemoryGraph, RECALL_MIN_THRESHOLD, RECALL_MAX_CANDIDATES, RECALL_MAX_RESULTS

# Import types
from cortex.core.graph.types import RecallResult as RecallResultNew

# Export all
__all__ = [
    "MemoryGraph",
    "RecallResult",  # From original
    "RecallResultNew",  # From modular structure
    "RECALL_MIN_THRESHOLD",
    "RECALL_MAX_CANDIDATES",
    "RECALL_MAX_RESULTS",
]
