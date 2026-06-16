"""
Pack — ultra-compact context string for prompt injection.

Given a list of Memory matches and a query intent, returns a minimal
string that captures the relevant W5H fields. Designed to minimize
token usage while preserving semantic information.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cortex_v5.core.memory import Memory
    from cortex_v5.core.recall.extractor import QueryIntent


def rough_token_count(text: str) -> int:
    """Approximate token count: 1 token ≈ 4 characters (PT/EN average)."""
    return len(text) // 4


def pack_for_context(
    matches: list["Memory"],
    intent: "QueryIntent | None" = None,
    max_tokens: int = 200,
) -> str:
    """
    Pack matched memories into a compact context string.

    Only includes the W5H fields that match the intent, plus a minimal
    'what' for context. Stops when token budget is exhausted.

    Args:
        matches: list of Memory objects (ordered by relevance)
        intent: optional QueryIntent (for projection)
        max_tokens: rough token budget

    Returns:
        compact string suitable for prompt injection
    """
    if not matches:
        return ""

    parts: list[str] = []
    budget_chars = max_tokens * 4
    used_chars = 0

    for mem in matches:
        mem_who = mem.who or []
        mem_what = mem.what or ""
        mem_where = mem.where or "default"
        mem_why = mem.why or ""

        # Build a compact line based on what's relevant
        line_parts: list[str] = []
        if mem_who:
            line_parts.append(",".join(mem_who[:2]))
        if mem_what:
            line_parts.append(mem_what)
        if intent and intent.query_type == "location" and mem_where != "default":
            line_parts.append(f"@{mem_where}")
        if intent and intent.query_type == "causal" and mem_why:
            line_parts.append(f"({mem_why})")

        if not line_parts:
            continue

        line = " | ".join(line_parts)
        line_with_break = line + "\n"

        if used_chars + len(line_with_break) > budget_chars:
            remaining = budget_chars - used_chars
            if remaining > 20:
                parts.append(line[:remaining - 1] + "…")
            break

        parts.append(line)
        used_chars += len(line_with_break)

    return "".join(parts).rstrip()
