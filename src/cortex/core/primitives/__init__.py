"""
Cortex Primitives - Basic memory types.

Contains fundamental building blocks:
- Entity: Things and concepts
- Episode: Experiences and events
- Memory: Memory wrapper (alias for Episode)
- Relation: Connections between entities/episodes
- Namespace: Multi-tenant isolation
"""

from cortex.core.primitives.entity import Entity
from cortex.core.primitives.episode import Episode
from cortex.core.primitives.memory import Memory
from cortex.core.primitives.relation import Relation
from cortex.core.primitives.namespace import NamespacedMemoryManager

__all__ = [
    "Entity",
    "Episode",
    "Memory",
    "Relation",
    "NamespacedMemoryManager",
]
