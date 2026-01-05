"""
Cortex MCP Server - FastMCP integration.

This server exposes Cortex memory functions to LLM agents via MCP protocol.

Usage:
    # Run directly
    python -m cortex.mcp.server
    
    # Or via entry point
    cortex-mcp

Configuration (claude_desktop_config.json):
    {
        "mcpServers": {
            "cortex": {
                "command": "cortex-mcp",
                "env": {
                    "CORTEX_DATA_DIR": "/path/to/data"
                }
            }
        }
    }
"""

import os
import sys
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from cortex.services.memory_service import (
    MemoryService,
    StoreRequest,
    RecallRequest,
    ParticipantInput,
    RelationInput,
)


def get_data_dir() -> Path:
    """Get the Cortex data directory from environment or default."""
    data_dir = os.environ.get("CORTEX_DATA_DIR")
    if data_dir:
        path = Path(data_dir)
        print(f"[cortex-mcp] Data dir from env: {path}", file=sys.stderr)
        return path
    default_path = Path.home() / ".cortex"
    print(f"[cortex-mcp] Using default data dir: {default_path}", file=sys.stderr)
    return default_path


# Initialize MCP server
mcp = FastMCP(
    "cortex-memory",
    instructions="""
    Cortex Memory System - MANDATORY WORKFLOW
    
    You MUST follow this workflow for EVERY user interaction:
    
    1. BEFORE responding: Call cortex_recall with the user's message
       - This retrieves relevant context from past interactions
       - Use the returned context to inform your response
    
    2. AFTER responding: Call cortex_store to save the interaction
       - action: what you did (analyzed, explained, resolved, etc.)
       - outcome: the result or conclusion
       - participants: entities mentioned (people, files, concepts)
       - relations: causal connections discovered
    
    NEVER skip these steps. Memory enables continuity across sessions.
    """,
)

# Initialize service (lazy loading)
_service: MemoryService | None = None


def get_service() -> MemoryService:
    """Get or create the memory service instance."""
    global _service
    if _service is None:
        data_dir = get_data_dir()
        print(f"[cortex-mcp] Creating MemoryService with path: {data_dir}", file=sys.stderr)
        _service = MemoryService(storage_path=data_dir)
        print(f"[cortex-mcp] Service created, graph has {len(_service.graph._entities)} entities", file=sys.stderr)
    return _service


# ==================== MCP TOOLS ====================


@mcp.tool()
def cortex_recall(
    query: str,
    context: dict[str, Any] | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """
    MANDATORY: Call BEFORE answering the user.
    
    Retrieves relevant memories from past interactions.
    
    Args:
        query: The user's message or topic to search for
        context: Additional context (entity_names, entity_types, etc.)
        limit: Maximum results per category (default: 5)
    
    Returns:
        Dictionary with:
        - entities_found: Number of known entities
        - episodes_found: Number of relevant past experiences
        - context_summary: Human-readable summary
        - prompt_context: Text to include in your reasoning
        - entities: List of entity details
        - episodes: List of episode details
    
    Use the prompt_context to inform your response. If you've seen
    this topic before, reference it naturally in your answer.
    """
    service = get_service()
    request = RecallRequest(
        query=query,
        context=context or {},
        limit=limit,
    )
    response = service.recall(request)
    return response.model_dump()


@mcp.tool()
def cortex_store(
    action: str,
    outcome: str,
    participants: list[dict[str, Any]] | None = None,
    context: str = "",
    relations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    MANDATORY: Call AFTER answering the user.
    
    Stores the interaction as a memory (episode + entities + relations).
    
    Args:
        action: What was done (verb): analyzed, resolved, discussed, explained, debugged...
        outcome: The result or conclusion of the interaction
        participants: Entities involved. Each has:
            - type: person, file, concept, character, product, etc.
            - name: Entity name
            - identifiers: Optional list of IDs (email, path, etc.)
        context: The situation or scenario (optional)
        relations: Causal connections discovered. Each has:
            - from: Source entity name
            - type: caused_by, resolved_by, related_to, requires, etc.
            - to: Target entity name
    
    Returns:
        Dictionary with:
        - success: Whether storage succeeded
        - episode_id: ID of the created episode
        - entities_created: New entities added
        - entities_updated: Existing entities updated
        - relations_created: New connections added
        - consolidated: Whether this merged with similar episodes
        - consolidation_count: How many times this pattern occurred
    
    The system automatically:
    - Resolves existing entities (won't create duplicates)
    - Consolidates repeated patterns (5+ similar = 1 rich memory)
    - Creates searchable connections
    """
    service = get_service()
    
    # Parse participants
    parsed_participants = []
    for p in (participants or []):
        parsed_participants.append(ParticipantInput(
            type=p.get("type", "unknown"),
            name=p.get("name", "unknown"),
            identifiers=p.get("identifiers", []),
        ))
    
    # Parse relations
    parsed_relations = []
    for r in (relations or []):
        parsed_relations.append(RelationInput(
            **{"from": r.get("from", ""), "type": r.get("type", "related_to"), "to": r.get("to", "")}
        ))
    
    request = StoreRequest(
        action=action,
        outcome=outcome,
        participants=parsed_participants,
        context=context,
        relations=parsed_relations,
    )
    print(f"[cortex-mcp] Storing: action={action[:50]}, participants={len(parsed_participants)}", file=sys.stderr)
    response = service.store(request)
    print(f"[cortex-mcp] Store result: success={response.success}, episode={response.episode_id[:8]}", file=sys.stderr)
    return response.model_dump()


@mcp.tool()
def cortex_stats() -> dict[str, Any]:
    """
    Get statistics about the memory graph.
    
    Returns:
        Dictionary with:
        - total_entities: Number of known entities
        - total_episodes: Number of stored experiences
        - total_relations: Number of connections
        - entities_by_type: Breakdown by entity type
        - consolidated_episodes: Episodes that are patterns
        - storage_path: Where data is stored
    """
    service = get_service()
    response = service.stats()
    return response.model_dump()


@mcp.tool()
def cortex_health() -> dict[str, Any]:
    """
    Get memory health metrics.
    
    Returns info about the quality of the memory graph:
    - orphan_entities: Entities with no connections
    - lonely_episodes: Episodes with no participants
    - weak_relations: Relations with low strength
    - avg_episode_importance: Average importance of memories
    - avg_relation_strength: Average strength of connections
    - health_score: Overall health 0-100
    
    Use this to understand if memories are well-connected.
    """
    service = get_service()
    return service.get_health()


@mcp.tool()
def cortex_decay(decay_factor: float = 0.95) -> dict[str, Any]:
    """
    Apply manual decay to all memories.
    
    NOTE: In normal operation, decay happens AUTOMATICALLY during recall().
    Memories that are accessed strengthen, others weaken.
    
    Use this tool only for manual cleanup or testing.
    
    Args:
        decay_factor: How much to decay (0.95 = 5% loss, 0.90 = 10% loss)
    
    Returns:
        Statistics about what was decayed/forgotten:
        - episodes_decayed: Episodes that weakened
        - relations_decayed: Relations that weakened
        - episodes_forgotten: Episodes removed (too weak)
        - relations_forgotten: Relations removed (too weak)
    
    The system naturally forgets unimportant memories over many accesses.
    """
    service = get_service()
    print(f"[cortex-mcp] Applying manual decay with factor {decay_factor}", file=sys.stderr)
    result = service.apply_manual_decay(decay_factor)
    print(f"[cortex-mcp] Decay result: {result}", file=sys.stderr)
    return result


# ==================== MCP RESOURCES ====================


@mcp.resource("cortex://stats")
def get_stats_resource() -> str:
    """Current memory statistics."""
    service = get_service()
    stats = service.stats()
    return f"""
Cortex Memory Statistics
========================
Entities: {stats.total_entities}
Episodes: {stats.total_episodes}
Relations: {stats.total_relations}
Consolidated Patterns: {stats.consolidated_episodes}
Storage: {stats.storage_path or 'In-memory only'}
"""


# ==================== ENTRY POINT ====================


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
