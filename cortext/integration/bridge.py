"""
AgentMemoryBridge — a framework-agnostic memory layer over Cortext.

This is convenience sugar for the common chat-agent pattern, usable by *any*
framework (LangChain, LangGraph, CrewAI, a plain loop, …). It does not import or
depend on any agent framework:

  - recall_context(query) → compact context string to inject into the prompt
  - store_turn(user, assistant) → persist the exchange as a structured memory

For full control, use :class:`cortext.CortexV5` directly (``remember`` /
``recall`` / ``inspect``) — that is the universal entry point and this bridge is
a thin wrapper around it.
"""

from __future__ import annotations

from typing import Optional

from cortext import CortexV5
from cortext.core.recall.text_extractor import (
    default_extractor,
    heuristic_only_extractor,
)
from cortext.core.validation import ValidationPolicy


class AgentMemoryBridge:
    """
    Framework-agnostic chat-memory bridge over Cortext.

    Usage (works with any LLM framework)::

        bridge = AgentMemoryBridge(namespace="session-1")

        # Before each LLM call:
        context = bridge.recall_context("What did we discuss about Maria?")
        system = (context + "\\n\\n" + base_system_prompt) if context else base_system_prompt

        # After each turn:
        bridge.store_turn(
            user_message="Maria called today",
            assistant_message="Hi Maria! How can I help?",
        )
    """

    def __init__(
        self,
        namespace: str = "default",
        validation_policy: ValidationPolicy = ValidationPolicy.WARN,
        use_llm_extractor: bool = False,
        max_context_tokens: int = 300,
    ) -> None:
        """
        Args:
            namespace: memory namespace (use per-session/user for isolation)
            validation_policy: WARN (default) or BLOCK for strict
            use_llm_extractor: if True, use an LLM for extraction (slower, better)
            max_context_tokens: max tokens for the injected context
        """
        self.cortex = CortexV5(
            namespace=namespace,
            validation_policy=validation_policy,
        )
        self.text_extractor = (
            default_extractor() if use_llm_extractor else heuristic_only_extractor()
        )
        self.max_context_tokens = max_context_tokens
        self.namespace = namespace

    def recall_context(self, query: str, lang: str = "auto") -> str:
        """Retrieve context relevant to ``query`` as a compact string (or "")."""
        context, _ = self.cortex.recall(
            query, lang=lang, max_tokens=self.max_context_tokens
        )
        return context or ""

    # Backward-compatible / alternate name.
    pre_chat = recall_context

    def store_turn(
        self,
        user_message: str,
        assistant_message: str,
        who: Optional[list[str]] = None,
        lang: Optional[str] = None,
        validate: bool = True,
    ) -> tuple:
        """
        Store an exchange as a structured memory.

        The user message is parsed for W5H structure; the assistant message is
        stored as ``how`` (the response/method).

        Returns:
            (memory, validation_result) from ``cortex.remember()``.
        """
        user_data = self.text_extractor.extract(user_message)
        # `when` from text extraction is a string ("today"); Memory expects a
        # datetime or None, so drop non-datetime values.
        when_value = user_data.get("when")
        if when_value is not None:
            when_value = None
        memory, result = self.cortex.remember(
            who=who or user_data.get("who", []),
            what=user_data.get("what", user_message),
            why=user_data.get("why", ""),
            when=when_value,
            where=user_data.get("where", "default"),
            how=assistant_message,
            importance=0.6,
            lang=lang or user_data.get("lang"),
            validate=validate,
        )
        return memory, result

    # Backward-compatible / alternate name.
    post_chat = store_turn

    def recall_for_injection(self, query: str, lang: str = "auto") -> str:
        """Alias for :meth:`recall_context`."""
        return self.recall_context(query, lang)

    # === Inspection / audit API (for an opt-in agent tool) ===

    def inspect(self, query: str, lang: str = "auto", max_results: int = 5) -> dict:
        """Structured recall with full W5H metadata + match scores."""
        return self.cortex.inspect(query, lang=lang, max_results=max_results)

    def about(self, entity: str, max_results: int = 20) -> dict:
        """All memories about a given entity (who-match)."""
        return self.cortex.about(entity, max_results=max_results)

    def stats(self) -> dict:
        """Return bridge statistics."""
        return self.cortex.stats()

    def __repr__(self) -> str:
        return f"AgentMemoryBridge(ns={self.namespace!r}, {self.cortex})"
