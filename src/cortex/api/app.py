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

Endpoints (W5H Model):
    POST /memory/remember - Store a W5H memory after interaction
    POST /memory/recall   - Recall memories before responding  
    POST /memory/forget   - Forget a memory
    GET  /memory/stats    - Get memory statistics
    GET  /memory/health   - Get memory health metrics
    DELETE /memory/clear  - Clear all memories in namespace
    GET  /namespaces      - List all namespaces
    GET  /health          - Health check

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
    RecallRequest,
    RecallResponse,
    StatsResponse,
    # W5H models
    RememberRequest,
    RememberResponse,
    ForgetRequest,
    ForgetResponse,
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
    
    ## W5H Memory Model
    
    Cortex uses the W5H model for semantic memory:
    - **WHO**: Participants involved (people, systems, concepts)
    - **WHAT**: What happened (action/fact)
    - **WHY**: Why it happened (cause/reason)
    - **WHEN**: Timestamp (automatic)
    - **WHERE**: Namespace/context
    - **HOW**: How it was resolved (outcome)
    
    ## Multi-Tenant Support
    
    Use the `X-Cortex-Namespace` header to isolate memories:
    
    ```
    X-Cortex-Namespace: agent_001:user_123
    ```
    
    ## Workflow
    
    1. **Before responding**: Call `/memory/recall` to get relevant context
    2. **After responding**: Call `/memory/remember` to save the interaction
    3. **To forget**: Call `/memory/forget` when user requests or memory is wrong
    
    ## Example
    
    ```python
    # Remember (W5H)
    POST /memory/remember
    {
        "who": ["maria@email.com", "payment_system"],
        "what": "reported payment error",
        "why": "expired credit card",
        "how": "guided to update card details",
        "importance": 0.7
    }
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


# ==================== W5H ENDPOINTS ====================


@app.post("/memory/remember", response_model=RememberResponse)
async def remember_w5h(
    request: RememberRequest,
    namespace: str = Depends(get_namespace),
    service: MemoryService = Depends(get_service),
) -> RememberResponse:
    """
    Store a W5H memory after interaction.
    
    Call this AFTER responding to the user to record what happened.
    Uses the W5H model (Who, What, Why, When, Where, How).
    
    Headers:
        X-Cortex-Namespace: Namespace for isolation (optional, default: "default")
    
    Body:
        - who: List of participants (names, emails, systems)
        - what: What happened (action/fact)
        - why: Why it happened (cause/reason) - optional
        - how: Outcome/result - optional
        - where: Namespace (default: "default")
        - importance: 0.0-1.0 (default: 0.5)
    
    Returns:
        - success: Whether storage succeeded
        - memory_id: ID of created memory
        - who_resolved: Entity IDs for participants
        - consolidated: Whether merged with similar memories
        - retrievability: Current retrievability score
    
    Example:
        ```json
        {
            "who": ["maria@email.com", "payment_system"],
            "what": "reported payment error",
            "why": "expired credit card",
            "how": "guided user to update card details",
            "importance": 0.7
        }
        ```
    """
    try:
        return service.remember(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/forget", response_model=ForgetResponse)
async def forget_memory(
    request: ForgetRequest,
    namespace: str = Depends(get_namespace),
    service: MemoryService = Depends(get_service),
) -> ForgetResponse:
    """
    Forget a memory (mark as forgotten, excluded from recalls).
    
    Call this when a user requests to forget something or when
    a memory is found to be incorrect.
    
    Headers:
        X-Cortex-Namespace: Namespace for isolation (optional, default: "default")
    
    Body:
        - memory_id: ID of memory to forget
        - reason: Why it's being forgotten (optional)
    
    Returns:
        - success: Whether operation succeeded
        - memory_id: ID of forgotten memory
        - was_forgotten: True if already forgotten before
        - message: Status message
    """
    try:
        return service.forget(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# ==================== INTERACT ENDPOINT (AUTO W5H) ====================


from pydantic import BaseModel, Field


class InteractRequest(BaseModel):
    """Request para armazenar interação com extração automática W5H."""
    user_message: str = Field(..., description="Mensagem do usuário")
    assistant_response: str = Field(..., description="Resposta do assistente")
    user_name: str = Field(default="user", description="Nome do usuário (opcional)")


class InteractResponse(BaseModel):
    """Response do endpoint interact."""
    success: bool
    memory_id: str | None = None
    extracted: dict = Field(default_factory=dict)
    message: str = ""


@app.post("/memory/interact")
async def store_interaction(
    request: InteractRequest,
    namespace: str = Depends(get_namespace),
    service: MemoryService = Depends(get_service),
) -> InteractResponse:
    """
    Armazena interação com extração automática de W5H.
    
    Use este endpoint para automatizar o armazenamento de memória
    SEM que o cliente precise extrair W5H.
    
    O Cortex internamente:
    1. Analisa a interação
    2. Extrai W5H (who, what, why, how)
    3. Armazena a memória
    
    Headers:
        X-Cortex-Namespace: Namespace (opcional, default: "default")
    
    Body:
        user_message: A mensagem que o usuário enviou
        assistant_response: A resposta que o assistente deu
        user_name: Nome do usuário (opcional, default: "user")
    
    Returns:
        success: Se foi armazenado
        memory_id: ID da memória criada
        extracted: O W5H extraído
        message: Mensagem de status
    """
    try:
        # Extração simples de W5H (sem LLM - determinístico básico)
        # TODO: Pode ser melhorado com LLM assíncrono no futuro
        extracted = _extract_w5h_simple(
            request.user_message, 
            request.assistant_response,
            request.user_name,
        )
        
        # Armazena
        remember_request = RememberRequest(
            who=extracted["who"],
            what=extracted["what"],
            why=extracted["why"],
            how=extracted["how"],
            where=namespace,
            importance=0.5,
        )
        
        result = service.remember(remember_request)
        
        return InteractResponse(
            success=True,
            memory_id=result.memory_id,
            extracted=extracted,
            message="Interação armazenada com sucesso",
        )
    except Exception as e:
        return InteractResponse(
            success=False,
            message=f"Erro ao armazenar: {str(e)}",
        )


def _extract_w5h_simple(user_msg: str, assistant_resp: str, user_name: str) -> dict:
    """
    Extração simples de W5H sem LLM.
    
    Usa heurísticas básicas para extrair informações.
    Não é tão bom quanto LLM, mas é rápido e não onera o cliente.
    """
    # WHO: usuário + primeiras palavras capitalizadas (possíveis nomes)
    who = [user_name]
    words = user_msg.split()
    for word in words[:10]:
        clean = word.strip(".,!?")
        if clean and clean[0].isupper() and len(clean) > 2 and clean.lower() not in ["olá", "oi", "bom", "boa"]:
            if clean not in who:
                who.append(clean)
    
    # WHAT: ação principal (primeira frase do assistente, resumida)
    first_sentence = assistant_resp.split(".")[0][:100] if assistant_resp else "responded"
    what = first_sentence.lower().replace(" ", "_")[:50] if first_sentence else "interaction"
    
    # WHY: contexto do usuário (primeiras palavras da mensagem)
    why = user_msg[:80] if user_msg else ""
    
    # HOW: resumo da resposta
    how = assistant_resp[:100] if assistant_resp else ""
    
    return {
        "who": who[:5],  # Limita a 5 participantes
        "what": what,
        "why": why,
        "how": how,
    }


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
