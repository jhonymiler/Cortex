"""
Cortex Storage - Multi-tenant and collective memory.

Components:
- CollectiveMemory: Shared learning across users
- SharedMemory: Team/namespace memory sharing
- Identity: Memory firewall and input validation
"""

from cortex.core.storage.collective_memory import CollectiveMemoryCollector
from cortex.core.storage.shared_memory import SharedMemoryManager, MemoryVisibility, SharedMemoryContext, MemoryWithVisibility, NamespaceConfig, create_shared_memory_manager
from cortex.core.storage.identity import IdentityKernel

__all__ = [
    "CollectiveMemoryCollector",
    "SharedMemoryManager",
    "MemoryVisibility",
    "SharedMemoryContext",
    "MemoryWithVisibility",
    "NamespaceConfig",
    "create_shared_memory_manager",
    "IdentityKernel",
]
