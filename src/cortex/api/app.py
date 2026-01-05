"""
Cortex REST API - FastAPI application.

This API exposes Cortex memory functions via HTTP endpoints.

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
    GET  /health         - Health check
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from cortex.services.memory_service import (
    MemoryService,
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


# Global service instance
_service: MemoryService | None = None


def get_service() -> MemoryService:
    """Dependency injection for MemoryService."""
    global _service
    if _service is None:
        _service = MemoryService(storage_path=get_data_dir())
    return _service


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager."""
    # Startup
    global _service
    _service = MemoryService(storage_path=get_data_dir())
    yield
    # Shutdown
    _service = None


# Create FastAPI app
app = FastAPI(
    title="Cortex Memory API",
    description="""
    Cognitive memory system for LLM agents.
    
    ## Workflow
    
    1. **Before responding**: Call `/memory/recall` to get relevant context
    2. **After responding**: Call `/memory/store` to save the interaction
    
    ## Concepts
    
    - **Entity**: Any "thing" (person, file, concept, character, product)
    - **Episode**: Any "event" (action + participants + outcome)
    - **Relation**: Any "connection" (caused_by, resolved_by, related_to)
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
    service: MemoryService = Depends(get_service),
) -> StoreResponse:
    """
    Store a memory after interaction.
    
    Call this AFTER responding to the user to record what happened.
    
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
    service: MemoryService = Depends(get_service),
) -> RecallResponse:
    """
    Recall relevant memories before responding.
    
    Call this BEFORE responding to the user to get context.
    
    Returns:
    - Known entities related to the query
    - Past episodes/experiences
    - Causal connections
    - A context summary for your prompt
    """
    try:
        return service.recall(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/stats", response_model=StatsResponse)
async def get_stats(
    service: MemoryService = Depends(get_service),
) -> StatsResponse:
    """Get statistics about the memory graph."""
    return service.stats()


@app.delete("/memory/clear")
async def clear_memories(
    service: MemoryService = Depends(get_service),
) -> dict[str, Any]:
    """
    Clear all memories.
    
    ⚠️ Use with caution! This is irreversible.
    """
    return service.clear()


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
