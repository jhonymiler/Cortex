"""
HermesCortexBridge — connect Cortex v5 memory to the Hermes agent.

This is the integration point. When Hermes chats:
  - pre_chat(query)  → returns context string to inject into LLM prompt
  - post_chat(query, response) → stores the turn as memory

Used inside Hermes as a memory layer. No HTTP, no MCP — pure library.
"""

from __future__ import annotations

from typing import Optional

from cortex_v5 import CortexV5
from cortex_v5.core.recall.text_extractor import (
    default_extractor,
    heuristic_only_extractor,
)
from cortex_v5.core.validation import ValidationPolicy


class HermesCortexBridge:
    """
    Bridge between Cortex v5 memory and Hermes agent.

    Usage:
        bridge = HermesCortexBridge(namespace="hermes-session-1")

        # Before each LLM call:
        context = bridge.pre_chat("What did we discuss about Maria?")
        # Inject `context` into the system prompt or as a prefix

        # After each turn:
        bridge.post_chat(
            user_message="Maria ligou hoje",
            assistant_message="Oi Maria! Como posso ajudar?",
        )
    """

    def __init__(
        self,
        namespace: str = "hermes",
        validation_policy: ValidationPolicy = ValidationPolicy.WARN,
        use_llm_extractor: bool = False,
        max_context_tokens: int = 300,
    ) -> None:
        """
        Args:
            namespace: memory namespace (use per-session for isolation)
            validation_policy: WARN (default) or BLOCK for strict
            use_llm_extractor: if True, use LLM for extraction (slower, better quality)
            max_context_tokens: max tokens for injected context
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

    def pre_chat(self, query: str, lang: str = "auto") -> str:
        """
        Retrieve context relevant to query. Returns compact string.

        Use the returned string as a prefix to the LLM prompt:
            system = bridge.pre_chat(user_input) + "\\n\\n" + base_system_prompt
        """
        context, _ = self.cortex.recall(query, lang=lang, max_tokens=self.max_context_tokens)
        return context or ""

    def post_chat(
        self,
        user_message: str,
        assistant_message: str,
        who: Optional[list[str]] = None,
        lang: Optional[str] = None,
        validate: bool = True,
    ) -> tuple:
        """
        Store the turn as a memory.

        The user message is parsed for W5H structure. The assistant message
        is stored as 'how' (response/method).

        Returns:
            (memory, validation_result) tuple from cortex.remember()
        """
        # Parse user message for W5H
        user_data = self.text_extractor.extract(user_message)
        # The when field from text extraction is a string ("hoje", "ontem")
        # Memory expects datetime or None — only pass if parseable
        when_value = user_data.get("when")
        if when_value and not isinstance(when_value, type(None)):
            # Only pass when if it's None or a datetime; otherwise drop it
            # (string "hoje" isn't a datetime — Memory will use default)
            when_value = None
        # The assistente's response is stored as `how`
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

    def recall_for_injection(self, query: str, lang: str = "auto") -> str:
        """Alias for pre_chat — clear method name for prompt injection."""
        return self.pre_chat(query, lang)

    # === Inspection / audit API (for an opt-in agent tool) ===

    def inspect(self, query: str, lang: str = "auto", max_results: int = 5) -> dict:
        """Structured recall with full W5H metadata + match scores.

        For an opt-in agent tool that lets the model audit *why* a memory
        surfaced — distinct from pre_chat(), which returns a packed string.
        """
        return self.cortex.inspect(query, lang=lang, max_results=max_results)

    def about(self, entity: str, max_results: int = 20) -> dict:
        """All memories about a given entity (who-match)."""
        return self.cortex.about(entity, max_results=max_results)

    def stats(self) -> dict:
        """Return bridge statistics."""
        return self.cortex.stats()

    def __repr__(self) -> str:
        return f"HermesCortexBridge(ns={self.namespace!r}, {self.cortex})"
