"""
Cortex REST API - FastAPI application with namespace isolation.

This API exposes Cortex memory functions via HTTP endpoints.
Supports multi-tenant scenarios via X-Cortex-Namespace header.

Usage:
    # Run directly
    python -m cortex.api.app
    
    # Or via entry point
    cortex-api
    
    # Or with uvicorn
    uvicorn cortex.api.app:app --reload

Endpoints:
    POST /memory/store   - Store a memory after interaction
    POST /memory/recall  - Recall memories before responding
    GET  /memory/stats   - Get memory statistics
    GET  /memory/health  - Get memory health metrics
    DELETE /memory/clear - Clear all memories in namespace
    GET  /namespaces     - List all namespaces
    GET  /health         - Health check

Headers:
    X-Cortex-Namespace: Optional namespace for isolation (default: "default")
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

from cortex.services.memory_service import (
    MemoryService,
    NamespacedMemoryService,
    StoreRequest,
    StoreResponse,
    RecallRequest,
    RecallResponse,
    StatsResponse,
)


def get_data_dir() -> Path:
    """Get the Cortex data directory from environment or default."""
    data_dir = os.environ.get("CORTEX_DATA_DIR")
    if data_dir:
        return Path(data_dir)
    return Path.home() / ".cortex"


# Global namespaced service
_namespaced_service: NamespacedMemoryService | None = None


def get_namespaced_service() -> NamespacedMemoryService:
    """Get the global namespaced service."""
    global _namespaced_service
    if _namespaced_service is None:
        _namespaced_service = NamespacedMemoryService(base_path=get_data_dir())
    return _namespaced_service


def get_namespace(
    x_cortex_namespace: str | None = Header(None, alias="X-Cortex-Namespace"),
) -> str:
    """
    Extract namespace from header.
    
    Defaults to "default" if not provided.
    
    Examples:
        X-Cortex-Namespace: agent_001:user_123
        X-Cortex-Namespace: support_bot:cliente_acme
        X-Cortex-Namespace: dev_assistant:projeto_alpha
    """
    return x_cortex_namespace or "default"


def get_service(
    namespace: str = Depends(get_namespace),
    namespaced_service: NamespacedMemoryService = Depends(get_namespaced_service),
) -> MemoryService:
    """Get service for the current namespace."""
    return namespaced_service.get_service(namespace)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    global _namespaced_service
    _namespaced_service = NamespacedMemoryService(base_path=get_data_dir())
    yield
    _namespaced_service = None


# Create FastAPI app
app = FastAPI(
    title="Cortex Memory API",
    description="""
    Cognitive memory system for LLM agents with namespace isolation.
    
    ## Multi-Tenant Support
    
    Use the `X-Cortex-Namespace` header to isolate memories:
    
    ```
    X-Cortex-Namespace: agent_001:user_123
    ```
    
    Each namespace has completely isolated memories. Perfect for:
    - Multiple agents sharing same Cortex instance
    - Single agent serving multiple users
    - Different projects/contexts
    
    ## Workflow
    
    1. **Before responding**: Call `/memory/recall` to get relevant context
    2. **After responding**: Call `/memory/store` to save the interaction
    
    ## Concepts
    
    - **Entity**: Any "thing" (person, file, concept, character, product)
    - **Episode**: Any "event" (action + participants + outcome)
    - **Relation**: Any "connection" (caused_by, resolved_by, related_to)
    
    ## Context Format
    
    The `prompt_context` field returns YAML format for minimal tokens:
    
    ```yaml
    # MEMÓRIA DO USUÁRIO
    conhecidos:
      - João (customer): vip=True
    histórico:
      - [4x] login_issue: VPN blocking access
    resumo: User has recurring VPN problems
    ```
    """,
    version="3.0.0",
    lifespan=lifespan,
)

# CORS middleware for browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== ENDPOINTS ====================


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "cortex-memory"}


@app.post("/memory/store", response_model=StoreResponse)
async def store_memory(
    request: StoreRequest,
    namespace: str = Depends(get_namespace),
    service: MemoryService = Depends(get_service),
) -> StoreResponse:
    """
    Store a memory after interaction.
    
    Call this AFTER responding to the user to record what happened.
    
    Headers:
        X-Cortex-Namespace: Namespace for isolation (optional, default: "default")
    
    The system automatically:
    - Resolves existing entities (won't create duplicates)
    - Consolidates repeated patterns (5+ similar = 1 rich memory)
    - Creates searchable connections
    """
    try:
        return service.store(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/recall", response_model=RecallResponse)
async def recall_memories(
    request: RecallRequest,
    namespace: str = Depends(get_namespace),
    service: MemoryService = Depends(get_service),
) -> RecallResponse:
    """
    Recall relevant memories before responding.
    
    Call this BEFORE responding to the user to get context.
    
    Headers:
        X-Cortex-Namespace: Namespace for isolation (optional, default: "default")
    
    Returns:
    - Known entities related to the query
    - Past episodes/experiences
    - Causal connections
    - A YAML context summary for your prompt (minimal tokens)
    """
    try:
        return service.recall(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/stats", response_model=StatsResponse)
async def get_stats(
    namespace: str = Depends(get_namespace),
    service: MemoryService = Depends(get_service),
) -> StatsResponse:
    """
    Get statistics about the memory graph.
    
    Headers:
        X-Cortex-Namespace: Namespace for isolation (optional, default: "default")
    """
    return service.stats()


@app.get("/memory/health")
async def get_memory_health(
    namespace: str = Depends(get_namespace),
    service: MemoryService = Depends(get_service),
) -> dict[str, Any]:
    """
    Get memory health metrics.
    
    Returns info about orphan entities, lonely episodes,
    weak relations, and overall health score.
    
    Headers:
        X-Cortex-Namespace: Namespace for isolation (optional, default: "default")
    """
    return service.get_health()


@app.delete("/memory/clear")
async def clear_memories(
    namespace: str = Depends(get_namespace),
    service: MemoryService = Depends(get_service),
) -> dict[str, Any]:
    """
    Clear all memories in the namespace.
    
    ⚠️ Use with caution! This is irreversible.
    
    Headers:
        X-Cortex-Namespace: Namespace to clear (optional, default: "default")
    """
    return service.clear()


@app.get("/namespaces")
async def list_namespaces(
    namespaced_service: NamespacedMemoryService = Depends(get_namespaced_service),
) -> dict[str, Any]:
    """
    List all namespaces.
    
    Returns both active (in-memory) and persisted namespaces.
    """
    return {
        "active": namespaced_service.list_namespaces(),
        "persisted": namespaced_service.list_persisted_namespaces(),
        "stats": namespaced_service.global_stats(),
    }


@app.delete("/namespaces/{namespace}")
async def delete_namespace(
    namespace: str,
    namespaced_service: NamespacedMemoryService = Depends(get_namespaced_service),
) -> dict[str, Any]:
    """
    Delete a namespace and all its data.
    
    ⚠️ Use with caution! This is irreversible.
    """
    deleted = namespaced_service.delete_namespace(namespace)
    return {
        "success": deleted,
        "namespace": namespace,
        "message": f"Namespace '{namespace}' deleted" if deleted else "Namespace not found",
    }


# ==================== ENTRY POINT ====================


def main() -> None:
    """Run the API server."""
    import uvicorn
    
    host = os.environ.get("CORTEX_HOST", "0.0.0.0")
    port = int(os.environ.get("CORTEX_PORT", "8000"))
    
    uvicorn.run(
        "cortex.api.app:app",
        host=host,
        port=port,
        reload=os.environ.get("CORTEX_RELOAD", "false").lower() == "true",
    )


if __name__ == "__main__":
    main()
