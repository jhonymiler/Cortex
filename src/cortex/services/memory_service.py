"""
MemoryService - Main orchestrator for memory operations.

This service is the single source of truth for memory operations.
Both MCP and REST API use this service to ensure consistent behavior.

Supports namespace isolation for multi-tenant scenarios:
- Each namespace has its own isolated memory graph
- No data leakage between namespaces
- User defines namespace format (e.g., "agent:user", "bot:client")

W5H Memory Model:
- WHO: Participants involved
- WHAT: Action/fact
- WHY: Cause/reason
- WHEN: Timestamp + temporal context
- WHERE: Namespace + spatial context
- HOW: Outcome/result
"""

from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from cortex.core import Entity, Episode, MemoryGraph, Relation
from cortex.core.primitives import Memory
from cortex.core.graph import RecallResult
from cortex.core.learning import DecayManager, create_default_decay_manager
from cortex.core.primitives import NamespacedMemoryManager
from cortex.core.processing.embedding import get_embedding_service, cosine_similarity
from cortex.core.storage import (
    SharedMemoryManager,
    SharedMemoryContext,
    MemoryVisibility,
    NamespaceConfig,
)

# Logging
from cortex.utils.logging import get_audit_logger, get_performance_logger, get_logger


# ==================== REQUEST/RESPONSE MODELS ====================


class ParticipantInput(BaseModel):
    """Input for a participant entity."""
    
    type: str = Field(..., description="Entity type: person, file, concept, etc.")
    name: str = Field(..., description="Entity name")
    identifiers: list[str] = Field(default_factory=list, description="Ways to identify this entity")


class RelationInput(BaseModel):
    """Input for a relation between entities."""
    
    from_name: str = Field(..., alias="from", description="Source entity name")
    relation_type: str = Field(..., alias="type", description="Relation type: caused_by, resolved_by, etc.")
    to_name: str = Field(..., alias="to", description="Target entity name")


class StoreRequest(BaseModel):
    """Request to store a memory."""
    
    action: str = Field(..., description="What was done (verb): analyzed, resolved, discussed...")
    outcome: str = Field(..., description="The result or conclusion")
    participants: list[ParticipantInput] = Field(default_factory=list, description="Entities involved")
    context: str = Field(default="", description="The situation or scenario")
    relations: list[RelationInput] = Field(default_factory=list, description="Connections discovered")
    
    # Context tracking
    conversation_id: str | None = Field(default=None, description="ID of the active conversation")
    session_id: str | None = Field(default=None, description="ID of the current session")
    namespace: str = Field(default="default", description="Namespace for isolation")


class StoreResponse(BaseModel):
    """Response from storing a memory."""
    
    success: bool
    episode_id: str
    entities_created: int
    entities_updated: int
    relations_created: int
    consolidated: bool
    consolidation_count: int


class RecallRequest(BaseModel):
    """Request to recall memories."""
    
    query: str = Field(..., description="The topic or message to search for")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    limit: int = Field(default=5, description="Maximum results per category")
    
    # Context tracking
    conversation_id: str | None = Field(default=None, description="ID of the active conversation")
    session_id: str | None = Field(default=None, description="ID of the current session")
    namespace: str = Field(default="default", description="Namespace to search in")


class EntitySummary(BaseModel):
    """Summary of an entity for responses."""
    
    id: str
    type: str
    name: str
    access_count: int


class EpisodeSummary(BaseModel):
    """Summary of an episode for responses."""
    
    id: str
    action: str
    outcome: str
    occurrence_count: int
    is_pattern: bool


class RecallResponse(BaseModel):
    """Response from recalling memories."""
    
    entities_found: int
    episodes_found: int
    relations_found: int
    context_summary: str
    prompt_context: str
    entities: list[EntitySummary]
    episodes: list[EpisodeSummary]


class StatsResponse(BaseModel):
    """Statistics about the memory graph."""
    
    total_entities: int
    total_episodes: int
    total_relations: int
    entities_by_type: dict[str, int]
    consolidated_episodes: int
    storage_path: Optional[str] = None


# ==================== W5H REQUEST/RESPONSE MODELS ====================


class RememberRequest(BaseModel):
    """
    W5H Request to store a memory.
    
    Fields follow the W5H model:
    - WHO: who (participants)
    - WHAT: what (action/fact)
    - WHY: why (cause/reason)
    - WHEN: (automatic timestamp)
    - WHERE: where (namespace)
    - HOW: how (outcome/result)
    
    Visibility levels:
    - personal: Only visible to this user/namespace (default)
    - shared: Visible to all in the parent namespace (team knowledge)
    - learned: Visible to all, anonymous (extracted patterns, high-value)
    """
    
    who: list[str] = Field(default_factory=list, description="Participants: names or identifiers")
    what: str = Field(..., description="What happened (action/fact)")
    why: str = Field(default="", description="Why it happened (cause/reason)")
    how: str = Field(default="", description="How it was resolved (outcome/result)")
    where: str = Field(default="default", description="Namespace/context")
    importance: float = Field(default=0.5, ge=0.0, le=1.0, description="Importance 0.0-1.0")
    visibility: str = Field(
        default="personal", 
        description="Visibility: personal, shared, or learned"
    )
    owner_id: str = Field(default="", description="Owner ID for personal memories")


class RememberResponse(BaseModel):
    """Response from storing a W5H memory."""
    
    success: bool
    memory_id: str
    who_resolved: list[str]  # Entity IDs created/found
    consolidated: bool
    consolidation_count: int
    retrievability: float


class ForgetRequest(BaseModel):
    """Request to forget a memory."""
    
    memory_id: str = Field(..., description="ID of memory to forget")
    reason: str = Field(default="", description="Why it's being forgotten")


class ForgetResponse(BaseModel):
    """Response from forgetting a memory."""
    
    success: bool
    memory_id: str
    was_forgotten: bool  # True if already forgotten
    message: str


class RecallW5HRequest(BaseModel):
    """W5H-aware recall request with filters."""
    
    query: str = Field(..., description="The topic to search for")
    who: Optional[list[str]] = Field(default=None, description="Filter by participants")
    where: Optional[str] = Field(default=None, description="Filter by namespace")
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum importance")
    include_forgotten: bool = Field(default=False, description="Include forgotten memories")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")


# ==================== SERVICE ====================


class MemoryService:
    """
    Main service for memory operations.
    
    This is the single entry point for all memory operations.
    Both MCP and REST API use this service.
    
    Supports hierarchical namespaces for shared memory:
    - PERSONAL: User-specific memories (isolated)
    - SHARED: Team/namespace knowledge (visible to all in namespace)
    - LEARNED: Patterns extracted from consolidation (anonymous, high-value)
    
    Namespace hierarchy example:
    - "support" (parent) -> SHARED/LEARNED memories
    - "support:user_123" (child) -> PERSONAL memories + inherits from parent
    """
    
    def __init__(
        self,
        storage_path: Path | str | None = None,
        shared_memory_manager: SharedMemoryManager | None = None,
    ):
        """
        Initialize the memory service.

        Args:
            storage_path: Path for data persistence. None = in-memory only.
            shared_memory_manager: Optional SharedMemoryManager for visibility control.
                                   If None, a new one is created.
        """
        self.graph = MemoryGraph(storage_path=storage_path)
        self.shared_manager = shared_memory_manager or SharedMemoryManager()
        self.decay_manager = create_default_decay_manager()

        # Logging
        self._logger = get_logger("memory_service")
        self._audit = get_audit_logger("memory_service")
        self._perf = get_performance_logger("memory_service")

        # Cache de recall por sessão (evita recálculos)
        # Chave: (session_id, namespace, owner_id, query_hash) -> RecallResponse
        # CORREÇÃO: Inclui namespace e owner_id para evitar vazamento entre usuários
        self._recall_cache: dict[tuple[str, str, str, int], "RecallResponse"] = {}
        self._cache_max_size = 100  # Limita tamanho do cache

        self._logger.info(
            f"MemoryService initialized: storage_path={storage_path}"
        )
    
    def store(self, request: StoreRequest) -> StoreResponse:
        """
        Store a new memory (episode + entities + relations).

        This is called AFTER responding to the user to record what happened.
        """
        import time
        start_time = time.time()

        # Audit log: Store request
        self._audit.log_create(
            "memory_store",
            action=request.action,
            namespace=request.namespace,
            conversation_id=request.conversation_id,
            session_id=request.session_id,
            participants_count=len(request.participants),
            relations_count=len(request.relations)
        )

        entities_created = 0
        entities_updated = 0
        participant_ids: list[str] = []
        
        # 1. Resolve/create entities for participants
        for participant in request.participants:
            entity = self.graph.resolve_entity(
                name=participant.name,
                identifiers=participant.identifiers,
            )
            
            if entity:
                # Entity exists, update it
                entity.touch()
                entities_updated += 1
            else:
                # Create new entity
                entity = Entity(
                    type=participant.type,
                    name=participant.name,
                    identifiers=participant.identifiers,
                )
                self.graph.add_entity(entity)
                entities_created += 1
            
            participant_ids.append(entity.id)
        
        # 2. Create episode
        episode = Episode(
            action=request.action,
            participants=participant_ids,
            context=request.context,
            outcome=request.outcome,
            conversation_id=request.conversation_id,
            session_id=request.session_id,
        )
        
        # Store namespace in metadata
        if request.namespace and request.namespace != "default":
            episode.metadata["namespace"] = request.namespace
        
        # 2.5 Gera embedding para busca semântica (não-bloqueante)
        self._generate_episode_embedding(episode)
        
        # 3. Check for consolidation (similar episodes)
        consolidated, consolidation_count = self.graph.add_episode_with_consolidation(episode)
        
        # 4. Create relations
        relations_created = 0
        for rel_input in request.relations:
            # Find entities by name
            from_entity = self.graph.find_entity_by_name(rel_input.from_name)
            to_entity = self.graph.find_entity_by_name(rel_input.to_name)
            
            if from_entity and to_entity:
                relation = Relation(
                    from_id=from_entity.id,
                    relation_type=rel_input.relation_type,
                    to_id=to_entity.id,
                )
                _, _ = self.graph.add_relation(relation)
                relations_created += 1

        # Performance log
        duration_ms = (time.time() - start_time) * 1000
        self._perf.log_metric(
            "store",
            duration_ms=duration_ms,
            entities_created=entities_created,
            entities_updated=entities_updated,
            relations_created=relations_created,
            consolidated=consolidated,
            consolidation_count=consolidation_count
        )

        self._logger.info(
            f"Memory stored: action='{request.action}', episode={episode.id}, "
            f"entities={entities_created}+{entities_updated}, relations={relations_created}, "
            f"consolidated={consolidated} ({duration_ms:.1f}ms)"
        )

        return StoreResponse(
            success=True,
            episode_id=episode.id,
            entities_created=entities_created,
            entities_updated=entities_updated,
            relations_created=relations_created,
            consolidated=consolidated,
            consolidation_count=consolidation_count,
        )
    
    def _generate_episode_embedding(self, episode: Episode) -> None:
        """
        Gera embedding para um episódio (para busca semântica).

        Usa o EmbeddingService singleton. Loga warning se falhar
        para ajudar no diagnóstico de problemas de configuração.
        """
        try:
            embedding_service = get_embedding_service()
            text = episode.get_text_for_embedding()
            if text:
                result = embedding_service.embed(text)
                if result:
                    episode.embedding = result.vector
                else:
                    # Log warning para ajudar diagnóstico
                    self._logger.warning(
                        f"Embedding não gerado para episódio {episode.id[:8]}. "
                        f"Verifique se OLLAMA_URL está configurado e Ollama está rodando."
                    )
        except Exception as e:
            # Log error para diagnóstico
            self._logger.error(f"Erro ao gerar embedding para episódio {episode.id[:8]}: {e}")
    
    def _recall_by_embedding(
        self,
        query: str,
        limit: int = 5,
        exclude_ids: set[str] | None = None,
        min_similarity: float = 0.6,
        namespace: str | None = None,
        owner_id: str | None = None,
    ) -> list[Episode]:
        """
        Busca episódios por similaridade de embedding COM ISOLAMENTO.
        
        IMPORTANTE: Filtra por namespace e owner_id para evitar vazamento
        de memórias entre usuários/contextos diferentes.
        
        ESTRATÉGIA DE THRESHOLD ADAPTATIVO:
        - Threshold base: 0.65 (alto para evitar falsos positivos)
        - Se há um candidato claramente melhor (gap > 0.15), aceita
        - Se todos os scores são similares (std < 0.05), rejeita todos
        
        Args:
            query: Query de busca
            limit: Máximo de episódios a retornar
            exclude_ids: IDs de episódios para excluir
            min_similarity: Similaridade mínima (0.0 a 1.0)
            namespace: Namespace para filtrar
            owner_id: Owner/user_id para filtrar
            
        Returns:
            Lista de episódios ordenados por similaridade
        """
        exclude_ids = exclude_ids or set()
        
        try:
            embedding_service = get_embedding_service()
            
            # Gera embedding da query
            query_result = embedding_service.embed(query)
            if not query_result:
                return []
            
            # Coleta TODOS os candidatos com seus scores (sem filtro inicial)
            all_candidates: list[tuple[Episode, float]] = []
            
            for ep_id, ep in self.graph._episodes.items():
                if ep_id in exclude_ids:
                    continue
                
                if not ep.embedding:
                    continue
                
                # FILTRO 1: Namespace
                if namespace:
                    ep_namespace = ep.metadata.get("namespace") or ep.metadata.get("where")
                    if ep_namespace and ep_namespace != namespace:
                        continue
                
                # FILTRO 2: Owner/User
                if owner_id:
                    ep_owner = ep.metadata.get("owner_id", "")
                    ep_who = ep.metadata.get("w5h", {}).get("who", [])
                    owner_match = (
                        owner_id in ep.participants or
                        owner_id == ep_owner or
                        owner_id in str(ep_who)
                    )
                    if not owner_match:
                        continue
                
                # Calcula similaridade
                sim = cosine_similarity(query_result.vector, ep.embedding)
                
                # Calcula centralidade do episódio (hub detection)
                centrality = self.decay_manager.calculate_episode_centrality(ep.id, self.graph)
                
                # Score combinado com boost para hubs
                # Hubs com centralidade > 0.3 recebem boost proporcional
                # Isso garante que memórias muito referenciadas apareçam
                hub_boost = 0.0
                if centrality > 0.3:
                    # Boost proporcional à centralidade (max 0.15)
                    hub_boost = min(0.15, (centrality - 0.3) * 0.5)
                
                # 70% similaridade + 15% centralidade + 15% hub_boost
                combined_score = (sim * 0.7) + (centrality * 0.15) + (hub_boost * 0.15) + hub_boost
                
                all_candidates.append((ep, sim, combined_score))
            
            if not all_candidates:
                return []
            
            # Ordena por score COMBINADO (maior primeiro)
            all_candidates.sort(key=lambda x: x[2], reverse=True)
            
            # ESTRATÉGIA ADAPTATIVA:
            # 1. Se melhor score é alto (> 0.75), aceita independente de outros
            # 2. Gap analysis: se melhor candidato é significativamente melhor, aceita
            # 3. Uniformity check: se TODOS são muito similares E baixos, rejeita
            
            # Usa similaridade original para threshold (não o combined_score)
            scores = [sim for _, sim, _ in all_candidates]
            best_score = scores[0]
            
            # THRESHOLD ADAPTATIVO v4:
            # Melhor equilíbrio entre precisão e recall
            # 
            # Regras:
            # 1. Score muito baixo (< 0.35): Rejeita tudo
            # 2. Score alto (>= 0.65): Aceita sem verificar gap (boa confiança)
            # 3. Score médio-alto (0.50-0.65): Aceita se gap >= 0.03
            # 4. Score médio (0.35-0.50): Aceita se gap >= 0.08
            # 5. Se gap insuficiente: Não retorna (ambiguidade)
            
            # Se melhor score é muito baixo, rejeita tudo
            if best_score < 0.35:
                return []
            
            # Se melhor score é alto, aceita sem verificar gap
            # Score >= 0.65 indica boa confiança semântica
            if best_score >= 0.65:
                return [all_candidates[0][0]]
            
            # Calcula gap entre melhor e segundo melhor
            if len(scores) > 1:
                second_best = scores[1]
                gap = best_score - second_best
            else:
                # Apenas um candidato: aceita se score >= 0.45
                if best_score >= 0.45:
                    return [all_candidates[0][0]]
                else:
                    return []
            
            # Define gap mínimo baseado no score
            if best_score >= 0.50:
                min_gap = 0.03  # Score médio-alto, gap pequeno OK
            else:
                min_gap = 0.08  # Score médio, exige gap moderado
            
            # Se gap insuficiente, há ambiguidade - não retorna
            if gap < min_gap:
                return []
            
            # Gap OK - retorna o melhor
            return [all_candidates[0][0]]
            
        except Exception as e:
            # Log error para diagnóstico
            import logging
            logger = logging.getLogger("cortex.memory")
            logger.error(f"Erro em _recall_by_embedding: {e}")
            return []
    
    def recall(self, request: RecallRequest) -> RecallResponse:
        """
        Recall relevant memories for a query.
        
        This is called BEFORE responding to the user to get context.
        Memories that are recalled get reinforced (use = strength).
        
        IMPORTANTE: Só retorna contexto se for RELEVANTE para a query.
        - Não força memória quando não há nada útil
        - Avalia relevância do match antes de incluir no contexto
        - Threshold adaptativo baseado na qualidade
        
        OTIMIZAÇÃO v3: Cache por sessão para evitar recálculos.
        
        Supports hierarchical namespace inheritance:
        - First searches in current namespace (PERSONAL memories)
        - Then searches in parent namespace for SHARED/LEARNED memories
        """
        # Cache check: evita recálculo para mesma query na mesma sessão
        # CORREÇÃO: Inclui namespace e owner_id na chave do cache para evitar
        # retornar resultados de outro usuário
        session_id = request.session_id or "default"
        who_filter = request.context.get("who", [])
        owner_for_cache = who_filter[0] if who_filter else request.context.get("user_id", "")
        cache_key = (session_id, request.namespace, owner_for_cache, hash(request.query.lower().strip()))
        
        if cache_key in self._recall_cache:
            return self._recall_cache[cache_key]
        
        # Enriquece context com conversation_id, session_id e namespace
        enriched_context = {
            **request.context,
            "conversation_id": request.conversation_id,
            "session_id": request.session_id,
            "namespace": request.namespace,
        }
        
        # Extrai owner_id do context (pode vir como who[0] ou user_id)
        who_filter = request.context.get("who", [])
        owner_id = who_filter[0] if who_filter else request.context.get("user_id")
        
        # 1. BUSCA POR EMBEDDING (principal - alta acurácia)
        # Usa embeddings para busca semântica com threshold adaptativo
        # CORREÇÃO: Passa namespace e owner_id para filtrar corretamente
        # NOTA: min_similarity=0.30 é o piso - o threshold adaptativo interno
        # ajusta para cima baseado na qualidade dos candidatos
        episodes = self._recall_by_embedding(
            query=request.query,
            limit=request.limit,
            min_similarity=0.30,  # Threshold base baixo (adaptativo ajusta)
            namespace=request.namespace,
            owner_id=owner_id,
        )
        
        # 2. Busca entidades por nome (para context "Você lembra de mim?")
        result = self.graph.recall(
            query=request.query,
            context=enriched_context,
            limit=request.limit,
        )
        
        # Usa entidades do recall por tokens, mas episódios do embedding
        result.episodes = episodes
        
        # 2. Busca memórias do namespace pai (SHARED/LEARNED)
        parent_episodes = self._recall_from_parent_namespaces(
            query=request.query,
            namespace=request.namespace,
            limit=max(3, request.limit // 2),
        )
        
        # 3. Combina resultados (pai tem prioridade menor)
        if parent_episodes:
            existing_ids = {ep.id for ep in result.episodes}
            for ep in parent_episodes:
                if ep.id not in existing_ids:
                    result.episodes.append(ep)
                    existing_ids.add(ep.id)
        
        # 4. NOVA LÓGICA: Avalia relevância antes de retornar contexto
        relevance_info = self._evaluate_recall_relevance(
            query=request.query,
            result=result,
        )
        
        # Se relevância for muito baixa, retorna contexto vazio
        # mas ainda retorna os metadados para debug
        should_return_context = relevance_info["should_include"]
        
        # Reforça APENAS se for relevante (não reforça ruído)
        if should_return_context and (result.entities or result.episodes):
            self.graph.reinforce_on_recall(
                entity_ids=[e.id for e in result.entities],
                episode_ids=[ep.id for ep in result.episodes],
            )
        
        # Gera prompt_context apenas se relevante
        prompt_context = ""
        if should_return_context:
            prompt_context = result.to_prompt_context()
        
        response = RecallResponse(
            entities_found=len(result.entities),
            episodes_found=len(result.episodes),
            relations_found=len(result.relations),
            context_summary=result.context_summary if should_return_context else "",
            prompt_context=prompt_context,
            entities=[
                EntitySummary(
                    id=e.id,
                    type=e.type,
                    name=e.name,
                    access_count=e.access_count,
                )
                for e in result.entities
            ] if should_return_context else [],
            episodes=[
                EpisodeSummary(
                    id=ep.id,
                    action=ep.action,
                    outcome=ep.outcome,
                    occurrence_count=ep.occurrence_count,
                    is_pattern=ep.is_consolidated,
                )
                for ep in result.episodes
            ] if should_return_context else [],
        )
        
        # Cache: salva resultado para reutilização na mesma sessão
        if len(self._recall_cache) >= self._cache_max_size:
            # Remove entradas antigas (FIFO simples)
            oldest_key = next(iter(self._recall_cache))
            del self._recall_cache[oldest_key]
        self._recall_cache[cache_key] = response
        
        return response
    
    def _evaluate_recall_relevance(
        self,
        query: str,
        result: "RecallResult",
        min_relevance: float = 0.15,  # Threshold baixo para evitar falsos negativos
    ) -> dict:
        """
        Avalia se o resultado do recall é relevante o suficiente para retornar.
        
        IMPORTANTE: Esta função NÃO re-avalia episódios encontrados por embedding.
        Episódios que chegaram via embedding já passaram pelo threshold de 
        similaridade (0.35) e são considerados semanticamente relevantes.
        
        A avaliação por tokens só é usada para:
        1. Casos onde não há episódios (apenas entidades)
        2. Queries conversacionais ("Você lembra de mim?")
        
        Args:
            query: Query original
            result: Resultado do recall
            min_relevance: Threshold mínimo para entidades-only
            
        Returns:
            Dict com should_include (bool) e score (float)
        """
        # Caso trivial: sem resultados
        if not result.episodes and not result.entities:
            return {"should_include": False, "score": 0.0, "reason": "no_results"}
        
        # REGRA 1: Se há episódios, eles vieram de embedding e já são relevantes
        # O embedding com threshold 0.35 já filtrou por similaridade semântica
        if result.episodes:
            # Confiamos no resultado do embedding
            return {
                "should_include": True, 
                "score": 1.0, 
                "reason": "embedding_match",
                "episode_count": len(result.episodes),
            }
        
        # REGRA 2: Se só há entidades (sem episódios), avalia relevância por tokens
        # Isso cobre casos conversacionais como "Você lembra do João?"
        from cortex.core.processing.language import tokenize_to_set
        
        query_tokens = tokenize_to_set(query.lower())
        if not query_tokens:
            # Query vazia ou só stopwords → retorna entidades conhecidas
            return {"should_include": True, "score": 0.5, "reason": "empty_query"}
        
        scores = []
        
        # Avalia relevância das entidades (participantes)
        has_known_entities = False
        for entity in result.entities:
            entity_text = f"{entity.name} {entity.type}".lower()
            entity_tokens = tokenize_to_set(entity_text)
            
            if entity_tokens:
                overlap = len(query_tokens & entity_tokens) / len(query_tokens)
                scores.append(min(overlap * 0.8, 0.8))
            
            # Entidades com access_count > 0 indicam contexto relevante
            if hasattr(entity, 'access_count') and entity.access_count > 0:
                has_known_entities = True
        
        # Se há entidades conhecidas, garantir retorno para contexto conversacional
        if has_known_entities:
            scores.append(0.3)
        
        if not scores:
            return {"should_include": False, "score": 0.0, "reason": "no_scorable_items"}
        
        final_score = max(scores)
        should_include = final_score >= min_relevance
        
        return {
            "should_include": should_include,
            "score": round(final_score, 3),
            "entity_count": len(result.entities),
            "has_known_entities": has_known_entities,
            "threshold": min_relevance,
            "reason": "entity_relevance" if should_include else "below_threshold",
        }
    
    def _recall_from_parent_namespaces(
        self,
        query: str,
        namespace: str,
        limit: int = 3,
    ) -> list[Episode]:
        """
        Busca memórias SHARED/LEARNED dos namespaces pai.
        
        Percorre a hierarquia de namespaces buscando memórias de alto valor
        que podem ser úteis para o usuário atual.
        
        Args:
            query: Query de busca
            namespace: Namespace atual (ex: "support:customer_support:user_123")
            limit: Máximo de memórias do pai
            
        Returns:
            Lista de episódios SHARED/LEARNED dos namespaces pai
        """
        parent_episodes: list[Episode] = []
        
        # Extrai namespaces pai da hierarquia
        # "support:customer_support:user_123" -> ["support:customer_support", "support"]
        parts = namespace.split(":")
        if len(parts) <= 1:
            return parent_episodes  # Já está no nível raiz
        
        parent_namespaces = []
        for i in range(len(parts) - 1, 0, -1):
            parent_ns = ":".join(parts[:i])
            parent_namespaces.append(parent_ns)
        
        # Método 1: Usa namespaced_service se disponível (mais eficiente)
        if hasattr(self, 'namespaced_service') and self.namespaced_service:
            for parent_ns in parent_namespaces:
                try:
                    parent_service = self.namespaced_service.get_service(parent_ns)
                    
                    # Usa busca por embedding no namespace pai
                    episodes = parent_service._recall_by_embedding(
                        query=query,
                        limit=limit,
                        min_similarity=0.35,  # Threshold para coletivas
                    )
                    
                    self._filter_and_add_parent_episodes(
                        episodes, parent_ns, parent_episodes, limit
                    )
                    
                    if len(parent_episodes) >= limit:
                        break
                except Exception:
                    continue
        
        # Método 2: Fallback para busca por storage_path usando embedding
        elif self.graph.storage_path:
            base_dir = self.graph.storage_path.parent
            
            for parent_ns in parent_namespaces:
                parent_path = base_dir / parent_ns.replace(":", "__")
                
                if not parent_path.exists():
                    continue
                
                try:
                    parent_graph = MemoryGraph(storage_path=parent_path)
                    
                    # Cria serviço temporário para usar embedding
                    temp_service = MemoryService.__new__(MemoryService)
                    temp_service.graph = parent_graph
                    temp_service.decay_manager = create_default_decay_manager()  # ESSENCIAL: Hub Detection
                    temp_service._recall_cache = {}
                    
                    episodes = temp_service._recall_by_embedding(
                        query=query,
                        limit=limit,
                        min_similarity=0.35,
                    )
                    
                    self._filter_and_add_parent_episodes(
                        episodes, parent_ns, parent_episodes, limit
                    )
                    
                    if len(parent_episodes) >= limit:
                        break
                except Exception:
                    continue
        
        return parent_episodes[:limit]
    
    def _filter_and_add_parent_episodes(
        self,
        episodes: list[Episode],
        parent_ns: str,
        parent_episodes: list[Episode],
        limit: int,
    ) -> None:
        """Filtra e adiciona episódios SHARED/LEARNED do namespace pai."""
        for ep in episodes:
            visibility = ep.metadata.get("visibility", "personal")
            is_summary = ep.metadata.get("is_summary", False) or ep.is_consolidated
            
            # Inclui se é SHARED, LEARNED ou um resumo de consolidação
            if visibility in ["shared", "learned"] or is_summary:
                # Marca como memória herdada para formatação diferenciada
                ep.metadata["inherited_from"] = parent_ns
                parent_episodes.append(ep)
                
                if len(parent_episodes) >= limit:
                    break
    
    def stats(self) -> StatsResponse:
        """Get statistics about the memory graph."""
        raw_stats = self.graph.stats()
        
        return StatsResponse(
            total_entities=raw_stats.get("total_entities", 0),
            total_episodes=raw_stats.get("total_episodes", 0),
            total_relations=raw_stats.get("total_relations", 0),
            entities_by_type=raw_stats.get("entities_by_type", {}),
            consolidated_episodes=raw_stats.get("consolidated_episodes", 0),
            storage_path=str(self.graph.storage_path) if self.graph.storage_path else None,
        )
    
    def apply_manual_decay(self, decay_factor: float = 0.95) -> dict[str, Any]:
        """
        Apply manual decay to all non-accessed memories.
        
        Use this for testing or manual cleanup. In normal operation,
        decay happens automatically during recall().
        
        Args:
            decay_factor: How much to decay (0.95 = 5% loss)
        """
        # Decay everything (no IDs = nothing was accessed)
        return self.graph.apply_access_decay([], [], decay_factor)
    
    def get_health(self) -> dict[str, Any]:
        """
        Get memory health metrics.
        
        Returns info about orphan entities, lonely episodes,
        weak relations, and overall health score.
        """
        return self.graph.get_memory_health()
    
    def clear(self) -> dict[str, Any]:
        """Clear all memories. Use with caution!"""
        self.graph.clear()
        return {"success": True, "message": "All memories cleared"}
    
    # ==================== W5H METHODS ====================
    
    def remember(self, request: RememberRequest) -> RememberResponse:
        """
        Store a W5H memory.
        
        Uses the new Memory model with WHO, WHAT, WHY, WHEN, WHERE, HOW.
        
        Args:
            request: RememberRequest with W5H fields
        
        Returns:
            RememberResponse with memory_id and status
        """
        # 1. Resolve entities from WHO
        who_resolved: list[str] = []
        for participant_name in request.who:
            entity = self.graph.resolve_entity(name=participant_name)
            if entity:
                entity.touch()
            else:
                entity = Entity(
                    type="participant",  # Generic type
                    name=participant_name,
                )
                self.graph.add_entity(entity)
            who_resolved.append(entity.id)
        
        # 2. Create Memory object
        memory = Memory(
            who=request.who,  # Store names for readability
            what=request.what,
            why=request.why,
            how=request.how,
            where=request.where,
            importance=request.importance,
        )
        
        # 3. Store as Episode (compatibility layer)
        # Map W5H to Episode fields
        episode = Episode(
            id=memory.id,
            action=memory.what,
            outcome=memory.how,
            context=memory.why,  # WHY stored in context
            participants=who_resolved,
            importance=memory.importance,
        )
        
        # Store in metadata for full W5H access
        episode.metadata["w5h"] = memory.to_w5h_dict()
        episode.metadata["where"] = memory.where
        episode.metadata["namespace"] = memory.where
        
        # Store visibility and owner for shared memory management
        episode.metadata["visibility"] = request.visibility
        episode.metadata["owner_id"] = request.owner_id or (
            request.who[0] if request.who else "anonymous"
        )
        
        # 3.5 Gera embedding para busca semântica
        self._generate_episode_embedding(episode)
        
        # 4. Add with consolidation check
        consolidated, consolidation_count = self.graph.add_episode_with_consolidation(episode)
        
        # 5. Register in SharedMemoryManager for visibility tracking
        visibility_enum = MemoryVisibility(request.visibility)
        self.shared_manager.register_memory(
            memory_id=episode.id,
            memory_type="episode",
            content=episode.to_dict(),  # Conteúdo serializado do episódio
            owner_id=episode.metadata["owner_id"],
            namespace=request.where,
            visibility=visibility_enum,
        )
        
        return RememberResponse(
            success=True,
            memory_id=memory.id,
            who_resolved=who_resolved,
            consolidated=consolidated,
            consolidation_count=consolidation_count,
            retrievability=memory.retrievability,
        )
    
    def forget(self, request: ForgetRequest) -> ForgetResponse:
        """
        Forget a memory (mark as forgotten).
        
        Forgotten memories are not deleted but excluded from recalls.
        
        Args:
            request: ForgetRequest with memory_id
        
        Returns:
            ForgetResponse with status
        """
        # Try to find as episode
        episode = self.graph.get_episode(request.memory_id)
        
        if not episode:
            return ForgetResponse(
                success=False,
                memory_id=request.memory_id,
                was_forgotten=False,
                message=f"Memory not found: {request.memory_id}",
            )
        
        # Check if already forgotten
        was_forgotten = episode.metadata.get("forgotten", False)
        
        # Mark as forgotten
        episode.metadata["forgotten"] = True
        episode.metadata["forget_reason"] = request.reason
        episode.importance = 0.0
        
        return ForgetResponse(
            success=True,
            memory_id=request.memory_id,
            was_forgotten=was_forgotten,
            message="Memory forgotten" if not was_forgotten else "Memory was already forgotten",
        )


class NamespacedMemoryService:
    """
    Memory service with namespace isolation.
    
    Each namespace has its own isolated memory graph.
    Perfect for multi-tenant scenarios:
    - Multiple agents sharing same Cortex instance
    - Single agent serving multiple users
    - Different projects/contexts
    
    Usage:
        service = NamespacedMemoryService(base_path="./data")
        
        # Store for user A
        service.store("agent:user_a", StoreRequest(...))
        
        # Store for user B (completely isolated)
        service.store("agent:user_b", StoreRequest(...))
        
        # Recall only sees user A's memories
        service.recall("agent:user_a", RecallRequest(...))
    """
    
    def __init__(self, base_path: Path | str | None = None):
        """
        Initialize the namespaced service.
        
        Args:
            base_path: Base directory for all namespace data.
                       Each namespace creates a subdirectory.
        """
        self.manager = NamespacedMemoryManager(base_path=base_path)
        self.base_path = Path(base_path) if base_path else None
        self._services: dict[str, MemoryService] = {}
    
    def get_service(self, namespace: str) -> MemoryService:
        """
        Get or create a MemoryService for a namespace.
        
        Args:
            namespace: Unique identifier (e.g., "agent:user", "bot:client")
        
        Returns:
            Isolated MemoryService for this namespace
        """
        if namespace not in self._services:
            graph = self.manager.get_graph(namespace)
            # Usa __new__ para evitar duplicação de grafo, mas inicializa corretamente
            service = MemoryService.__new__(MemoryService)
            service.graph = graph
            service.shared_manager = SharedMemoryManager()
            service.decay_manager = create_default_decay_manager()  # ESSENCIAL: Hub Detection
            service.namespaced_service = self  # Referência para buscar grafos pai
            service._current_namespace = namespace  # Namespace atual
            service._recall_cache = {}  # Cache de recall por sessão
            service._cache_max_size = 100  # Limite do cache
            
            # Logging (necessário porque __new__ não chama __init__)
            service._logger = get_logger("memory_service")
            service._audit = get_audit_logger("memory_service")
            service._perf = get_performance_logger("memory_service")
            
            self._services[namespace] = service
        
        return self._services[namespace]
    
    def store(self, namespace: str, request: StoreRequest) -> StoreResponse:
        """Store memory in a specific namespace."""
        return self.get_service(namespace).store(request)
    
    def recall(self, namespace: str, request: RecallRequest) -> RecallResponse:
        """Recall memories from a specific namespace."""
        return self.get_service(namespace).recall(request)
    
    def stats(self, namespace: str) -> StatsResponse:
        """Get stats for a specific namespace."""
        return self.get_service(namespace).stats()
    
    def get_health(self, namespace: str) -> dict[str, Any]:
        """Get health metrics for a specific namespace."""
        return self.get_service(namespace).get_health()
    
    def clear(self, namespace: str) -> dict[str, Any]:
        """Clear all memories in a specific namespace."""
        return self.get_service(namespace).clear()
    
    def list_namespaces(self) -> list[str]:
        """List all active namespaces."""
        return self.manager.list_namespaces()
    
    def list_persisted_namespaces(self) -> list[str]:
        """List all namespaces with persisted data."""
        return self.manager.list_persisted_namespaces()
    
    def delete_namespace(self, namespace: str) -> bool:
        """Delete a namespace and all its data."""
        if namespace in self._services:
            del self._services[namespace]
        return self.manager.delete_namespace(namespace)
    
    def global_stats(self) -> dict[str, Any]:
        """Get aggregated stats across all namespaces."""
        return self.manager.get_stats()
