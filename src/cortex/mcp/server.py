"""
Cortex MCP Server - FastMCP integration with namespace isolation.

This server exposes Cortex memory functions to LLM agents via MCP protocol.
Supports multi-tenant scenarios via CORTEX_NAMESPACE environment variable.

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
                    "CORTEX_DATA_DIR": "/path/to/data",
                    "CORTEX_NAMESPACE": "agent_001:user_123"
                }
            }
        }
    }

Namespace is set via environment at server startup and used for ALL operations.
This matches the pattern in agent_with_mcp.py where mcp_env is passed to StdioServerParameters.
"""

import os
import sys
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from cortex.services.memory_service import (
    NamespacedMemoryService,
    MemoryService,
    RecallRequest,
    # W5H models
    RememberRequest,
    ForgetRequest,
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


def get_namespace() -> str:
    """
    Get namespace from environment variable.
    
    Set CORTEX_NAMESPACE in the env passed to StdioServerParameters:
    
        mcp_env = os.environ.copy()
        mcp_env["CORTEX_NAMESPACE"] = "agent_001:user_123"
        
        server_params = StdioServerParameters(
            command="python",
            args=["-m", "cortex.mcp.server"],
            env=mcp_env
        )
    
    Returns "default" if not set.
    """
    namespace = os.environ.get("CORTEX_NAMESPACE", "default")
    print(f"[cortex-mcp] Using namespace: {namespace}", file=sys.stderr)
    return namespace


# Initialize MCP server
mcp = FastMCP(
    "cortex-memory",
    instructions="""
    Cortex Memory System - W5H Model
    
    Cortex uses the W5H memory model for storing interactions:
    - WHO: Participants involved
    - WHAT: What happened
    - WHY: Why it happened
    - WHEN: (automatic timestamp)
    - WHERE: Namespace/context
    - HOW: Outcome/result
    
    ## MANDATORY WORKFLOW
    
    1. BEFORE responding: Call cortex_recall
       - Retrieves relevant context from past interactions
       - Use returned context to inform your response
    
    2. AFTER responding: Call cortex_remember
       - who: participants involved (names, emails, systems)
       - what: what you did (analyzed, explained, resolved)
       - why: cause or reason (if applicable)
       - how: outcome or result
    
    3. If user asks to forget: Call cortex_forget
       - Marks memory as forgotten (excluded from recalls)
    
    NEVER skip recall/remember. Memory enables continuity.
    
    ## Available Tools
    
    - cortex_recall: Search past memories (BEFORE responding)
    - cortex_remember: Store W5H memory (AFTER responding)
    - cortex_forget: Mark memory as forgotten
    - cortex_stats: Memory statistics
    - cortex_health: Memory health metrics
    - cortex_decay: Manual decay (testing only)
    """,
)

# Initialize service (lazy loading)
_namespaced_service: NamespacedMemoryService | None = None
_namespace: str | None = None


def get_service() -> MemoryService:
    """
    Get the memory service for the configured namespace.
    
    Namespace is determined at startup from CORTEX_NAMESPACE env var.
    """
    global _namespaced_service, _namespace
    
    if _namespaced_service is None:
        data_dir = get_data_dir()
        _namespace = get_namespace()
        print(f"[cortex-mcp] Creating NamespacedMemoryService", file=sys.stderr)
        print(f"[cortex-mcp] Path: {data_dir}, Namespace: {_namespace}", file=sys.stderr)
        _namespaced_service = NamespacedMemoryService(base_path=data_dir)
    
    return _namespaced_service.get_service(_namespace)


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


# ==================== W5H TOOLS ====================


@mcp.tool()
def cortex_remember(
    who: list[str],
    what: str,
    why: str = "",
    how: str = "",
    where: str = "default",
    importance: float = 0.5,
) -> dict[str, Any]:
    """
    Store a W5H memory after interacting with the user.
    
    Uses the W5H model:
    - WHO: Participants involved
    - WHAT: What happened (action/fact)
    - WHY: Why it happened (cause/reason)
    - WHERE: Namespace/context
    - HOW: How it was resolved (outcome)
    
    Args:
        who: List of participant names (people, systems, concepts)
        what: What happened - the main action or fact
        why: Why it happened - the cause or reason (optional)
        how: How it was resolved - the outcome (optional)
        where: Namespace for organization (default: "default")
        importance: How important 0.0-1.0 (default: 0.5)
    
    Returns:
        Dictionary with:
        - success: Whether storage succeeded
        - memory_id: ID of the created memory
        - who_resolved: Entity IDs for participants
        - consolidated: Whether this merged with similar memories
        - retrievability: How easily this memory can be recalled
    
    Example:
        cortex_remember(
            who=["maria@email.com", "payment_system"],
            what="reported payment error",
            why="expired card",
            how="guided to update card details",
            importance=0.7
        )
    """
    service = get_service()
    request = RememberRequest(
        who=who,
        what=what,
        why=why,
        how=how,
        where=where,
        importance=importance,
    )
    print(f"[cortex-mcp] Remember: what={what[:50]}, who={who}", file=sys.stderr)
    response = service.remember(request)
    print(f"[cortex-mcp] Remember result: id={response.memory_id[:8]}", file=sys.stderr)
    return response.model_dump()


@mcp.tool()
def cortex_forget(
    memory_id: str,
    reason: str = "",
) -> dict[str, Any]:
    """
    Forget a specific memory.
    
    Forgotten memories are not deleted but excluded from recalls.
    Use this when:
    - User asks to forget something
    - Information is outdated/incorrect
    - Memory should be superseded
    
    Args:
        memory_id: ID of the memory to forget
        reason: Why it's being forgotten (for audit)
    
    Returns:
        Dictionary with:
        - success: Whether operation succeeded
        - memory_id: The memory ID
        - was_forgotten: True if already forgotten
        - message: Human-readable status
    """
    service = get_service()
    request = ForgetRequest(
        memory_id=memory_id,
        reason=reason,
    )
    print(f"[cortex-mcp] Forget: id={memory_id[:8]}, reason={reason}", file=sys.stderr)
    response = service.forget(request)
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


@mcp.tool()
def cortex_namespace_info() -> dict[str, Any]:
    """
    Get information about the current namespace.
    
    Returns:
        Dictionary with:
        - namespace: Current namespace name
        - data_dir: Base data directory
        - storage_path: Full path to namespace storage
    """
    global _namespace
    service = get_service()  # Ensures initialization
    stats = service.stats()
    
    return {
        "namespace": _namespace,
        "data_dir": str(get_data_dir()),
        "storage_path": stats.storage_path,
        "stats": {
            "entities": stats.total_entities,
            "episodes": stats.total_episodes,
            "relations": stats.total_relations,
        }
    }


# ==================== MCP RESOURCES ====================


@mcp.resource("cortex://stats")
def get_stats_resource() -> str:
    """Current memory statistics."""
    service = get_service()
    stats = service.stats()
    return f"""
Cortex Memory Statistics
========================
Namespace: {_namespace}
Entities: {stats.total_entities}
Episodes: {stats.total_episodes}
Relations: {stats.total_relations}
Consolidated Patterns: {stats.consolidated_episodes}
Storage: {stats.storage_path or 'In-memory only'}
"""


@mcp.resource("cortex://namespace")
def get_namespace_resource() -> str:
    """Current namespace information."""
    global _namespace
    get_service()  # Ensures initialization
    return f"""
Cortex Namespace
================
Current: {_namespace}
Data Dir: {get_data_dir()}

Set CORTEX_NAMESPACE env var to change namespace.
"""


# ==================== ENTRY POINT ====================


def main() -> None:
    """Run the MCP server."""
    print(f"[cortex-mcp] Starting Cortex MCP Server", file=sys.stderr)
    print(f"[cortex-mcp] Namespace: {get_namespace()}", file=sys.stderr)
    print(f"[cortex-mcp] Data dir: {get_data_dir()}", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
