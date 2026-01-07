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
from cortex.core.memory import Memory
from cortex.core.decay import DecayManager, create_default_decay_manager
from cortex.core.namespace import NamespacedMemoryManager
from cortex.core.shared_memory import (
    SharedMemoryManager, 
    SharedMemoryContext, 
    MemoryVisibility,
    NamespaceConfig,
)


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
    
    # Context tracking
    conversation_id: str | None = Field(default=None, description="ID of the active conversation")
    session_id: str | None = Field(default=None, description="ID of the current session")


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
    
    def store(self, request: StoreRequest) -> StoreResponse:
        """
        Store a new memory (episode + entities + relations).
        
        This is called AFTER responding to the user to record what happened.
        """
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
        
        return StoreResponse(
            success=True,
            episode_id=episode.id,
            entities_created=entities_created,
            entities_updated=entities_updated,
            relations_created=relations_created,
            consolidated=consolidated,
            consolidation_count=consolidation_count,
        )
    
    def recall(self, request: RecallRequest) -> RecallResponse:
        """
        Recall relevant memories for a query.
        
        This is called BEFORE responding to the user to get context.
        Memories that are recalled get reinforced (use = strength).
        
        Supports hierarchical namespace inheritance:
        - First searches in current namespace (PERSONAL memories)
        - Then searches in parent namespace for SHARED/LEARNED memories
        
        Example: namespace "support:customer_support:user_123"
        - Searches in "support:customer_support:user_123" (personal)
        - Then in "support:customer_support" (domain shared/learned)
        - Then in "support" (global shared/learned)
        """
        # Enriquece context com conversation_id, session_id e namespace
        enriched_context = {
            **request.context,
            "conversation_id": request.conversation_id,
            "session_id": request.session_id,
            "namespace": request.namespace,
        }
        
        # 1. Busca memórias do namespace atual (PERSONAL)
        result = self.graph.recall(
            query=request.query,
            context=enriched_context,
            limit=request.limit,
        )
        
        # 2. Busca memórias do namespace pai (SHARED/LEARNED)
        parent_episodes = self._recall_from_parent_namespaces(
            query=request.query,
            namespace=request.namespace,
            limit=max(3, request.limit // 2),  # Menos memórias do pai
        )
        
        # 3. Combina resultados (pai tem prioridade menor)
        if parent_episodes:
            # Adiciona episódios do pai que não estão duplicados
            existing_ids = {ep.id for ep in result.episodes}
            for ep in parent_episodes:
                if ep.id not in existing_ids:
                    result.episodes.append(ep)
                    existing_ids.add(ep.id)
        
        # Reforça memórias que foram lembradas (uso real = fortalecimento)
        if result.entities or result.episodes:
            self.graph.reinforce_on_recall(
                entity_ids=[e.id for e in result.entities],
                episode_ids=[ep.id for ep in result.episodes],
            )
        
        return RecallResponse(
            entities_found=len(result.entities),
            episodes_found=len(result.episodes),
            relations_found=len(result.relations),
            context_summary=result.context_summary,
            prompt_context=result.to_prompt_context(),
            entities=[
                EntitySummary(
                    id=e.id,
                    type=e.type,
                    name=e.name,
                    access_count=e.access_count,
                )
                for e in result.entities
            ],
            episodes=[
                EpisodeSummary(
                    id=ep.id,
                    action=ep.action,
                    outcome=ep.outcome,
                    occurrence_count=ep.occurrence_count,
                    is_pattern=ep.is_consolidated,
                )
                for ep in result.episodes
            ],
        )
    
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
        parent_namespaces = []
        for i in range(len(parts) - 1, 0, -1):
            parent_ns = ":".join(parts[:i])
            parent_namespaces.append(parent_ns)
        
        # Busca em cada namespace pai
        for parent_ns in parent_namespaces:
            # Busca episódios no namespace pai que são SHARED ou LEARNED
            episodes = self.graph.find_episodes(
                query=query,
                limit=limit,
                context={
                    "namespace": parent_ns,
                    # Só busca memórias que foram marcadas como compartilháveis
                    "include_shared": True,
                },
                min_score=0.2,  # Threshold mais baixo para memórias compartilhadas
            )
            
            # Filtra apenas memórias que são SHARED/LEARNED ou consolidadas (is_summary=True)
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
            
            if len(parent_episodes) >= limit:
                break
        
        return parent_episodes[:limit]
    
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
        
        # 4. Add with consolidation check
        consolidated, consolidation_count = self.graph.add_episode_with_consolidation(episode)
        
        # 5. Register in SharedMemoryManager for visibility tracking
        visibility_enum = MemoryVisibility(request.visibility)
        self.shared_manager.register_memory(
            memory_id=episode.id,
            visibility=visibility_enum,
            owner_id=episode.metadata["owner_id"],
            namespace=request.where,
            memory_type="episode",
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
            service = MemoryService.__new__(MemoryService)
            service.graph = graph
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
