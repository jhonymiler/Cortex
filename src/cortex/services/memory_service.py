"""
MemoryService - Main orchestrator for memory operations.

This service is the single source of truth for memory operations.
Both MCP and REST API use this service to ensure consistent behavior.
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from cortex.core import Entity, Episode, MemoryGraph, Relation


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
    storage_path: str | None


# ==================== SERVICE ====================


class MemoryService:
    """
    Main service for memory operations.
    
    This is the single entry point for all memory operations.
    Both MCP and REST API use this service.
    """
    
    def __init__(self, storage_path: Path | str | None = None):
        """
        Initialize the memory service.
        
        Args:
            storage_path: Path for data persistence. None = in-memory only.
        """
        self.graph = MemoryGraph(storage_path=storage_path)
    
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
        )
        
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
                self.graph.add_relation(relation)
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
        """
        result = self.graph.recall(
            query=request.query,
            context=request.context,
            limit=request.limit,
        )
        
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
