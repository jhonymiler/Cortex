"""
Cortex Storage - Multi-tenant, collective memory, and storage adapters.

Components:
- StorageAdapter: Interface abstrata para backends de persistência
- JSONStorageAdapter: Backend padrão, persistência em arquivo JSON
- Neo4jStorageAdapter: Backend para produção, grafo nativo Neo4j
- CollectiveMemory: Shared learning across users
- SharedMemory: Team/namespace memory sharing
- Identity: Memory firewall and input validation

Uso dos adaptadores:
    from cortex.core.storage import create_storage_adapter
    
    # Auto-detecta baseado em CORTEX_STORAGE_BACKEND
    adapter = create_storage_adapter()
    
    # Ou especifica explicitamente
    adapter = create_storage_adapter(backend="neo4j", uri="bolt://localhost:7687")
    
    # Ou importa diretamente (Neo4j requer pip install neo4j)
    from cortex.core.storage.neo4j_adapter import Neo4jStorageAdapter
"""

from cortex.core.storage.adapters import (
    StorageAdapter,
    StorageStats,
    JSONStorageAdapter,
    create_storage_adapter,
)
from cortex.core.storage.collective_memory import CollectiveMemoryCollector
from cortex.core.storage.shared_memory import SharedMemoryManager, MemoryVisibility, SharedMemoryContext, MemoryWithVisibility, NamespaceConfig, create_shared_memory_manager
from cortex.core.storage.identity import IdentityKernel, EvaluationResult, Action, Severity, Threat, create_default_kernel, create_strict_kernel


def get_neo4j_adapter():
    """
    Lazy import do Neo4jStorageAdapter.
    
    Evita erro de import se neo4j não estiver instalado.
    
    Returns:
        Neo4jStorageAdapter class
        
    Raises:
        ImportError: Se neo4j não estiver instalado
    """
    from cortex.core.storage.neo4j_adapter import Neo4jStorageAdapter
    return Neo4jStorageAdapter


__all__ = [
    # Storage Adapters
    "StorageAdapter",
    "StorageStats",
    "JSONStorageAdapter",
    "create_storage_adapter",
    "get_neo4j_adapter",
    # Collective Memory
    "CollectiveMemoryCollector",
    # Shared Memory
    "SharedMemoryManager",
    "MemoryVisibility",
    "SharedMemoryContext",
    "MemoryWithVisibility",
    "NamespaceConfig",
    "create_shared_memory_manager",
    # Identity Kernel
    "IdentityKernel",
    "EvaluationResult",
    "Action",
    "Severity",
    "Threat",
    "create_default_kernel",
    "create_strict_kernel",
]
