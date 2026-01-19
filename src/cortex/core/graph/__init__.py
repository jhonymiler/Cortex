"""
Cortex Graph Module - Modular Memory Graph Components

This module provides organized access to MemoryGraph and related types.

Backward Compatibility:
    from cortex.core.memory_graph import MemoryGraph, RecallResult  # Still works!

New Modular Imports:
    from cortex.core.graph import MemoryGraph, RecallResult
    from cortex.core.graph.types import RecallResult

V2.1 Graph Algorithms:
    from cortex.core.graph import GraphAnalyzer
    from cortex.core.graph.graph_algorithms import BFSGraphTraversal, LouvainCommunityDetection
"""

# Import from new location
from cortex.core.graph.memory_graph import MemoryGraph, RECALL_MIN_THRESHOLD, RECALL_MAX_CANDIDATES, RECALL_MAX_RESULTS

# Import types
from cortex.core.graph.types import RecallResult

# V2.1: Graph algorithms
from cortex.core.graph.graph_algorithms import (
    GraphAnalyzer,
    BFSGraphTraversal,
    LouvainCommunityDetection,
    HubDetector,
    Community,
    TraversalResult,
)

# Export all
__all__ = [
    "MemoryGraph",
    "RecallResult",
    "RECALL_MIN_THRESHOLD",
    "RECALL_MAX_CANDIDATES",
    "RECALL_MAX_RESULTS",
    # V2.1 Graph Algorithms
    "GraphAnalyzer",
    "BFSGraphTraversal",
    "LouvainCommunityDetection",
    "HubDetector",
    "Community",
    "TraversalResult",
]
