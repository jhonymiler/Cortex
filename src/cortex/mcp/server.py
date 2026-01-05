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
        return Path(data_dir)
    return Path.home() / ".cortex"


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
        _service = MemoryService(storage_path=get_data_dir())
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
    response = service.store(request)
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
