"""
CortexV5 — main entry point for the library.

This is the public API that users import. It's a thin facade over:
  - MemoryGraph (storage)
  - CanonicalValidator (NORMA at write time)
  - StructuralQueryParser (recall with embeddings跨城)
  - DreamAgent (opt-in background consolidation)

Usage:
    from cortext import CortexV5

    cortex = CortexV5(namespace="myapp")

    # Write (with optional validation)
    cortex.remember(
        who=["Maria"],
        what="pediu reembolso",
        where="suporte",
    )

    # Read (structural + token + embedding)
    context = cortex.recall("O que Maria pediu?")
    print(context)  # compact W5H string for LLM injection

    # Full pipeline: store + retrieve in one call
    response = cortex.chat("Maria ligou reclamando do mesmo problema")
"""

from __future__ import annotations

from typing import Optional, Any

from cortext.core.memory import Memory
from cortext.core.graph import MemoryGraph
from cortext.core.validation import CanonicalValidator
from cortext.core.validation import ValidationPolicy
from cortext.core.recall import StructuralQueryParser
from cortext.core.recall.pack import pack_for_context
from cortext.core.recall.embedding import EmbeddingRecall
from cortext.workers import DreamAgent


class CortexV5:
    """
    Main entry point for the Cortext memory system.

    A thin facade over the core components. The public API is minimal
    on purpose — anything more complex can be done by accessing the
    underlying components directly.

    Detector compliance (target 5/5):
      E1. Discrete alphabet: Entity, Memory, Relation types
      E2. Syntax: W5H enforced via __post_init__ in Memory
      E3. Separable mapping + external referent: who points to real entities
      E4. Independent interpreter: StructuralQueryParser (not LLM)
      E5. Functional semantics: ForgetGate + DreamAgent + access_count
    """

    def __init__(
        self,
        namespace: str = "default",
        validation_policy: ValidationPolicy = ValidationPolicy.WARN,
        enable_embedding_recall: bool = True,
        enable_dream_agent: bool = False,
    ) -> None:
        """
        Args:
            namespace: isolation namespace
            validation_policy: WARN (default) or BLOCK
            enable_embedding_recall: if True and sentence-transformers installed,
                                    use embeddings for cross-language recall
            enable_dream_agent: if True, instantiate DreamAgent for opt-in
                                background consolidation
        """
        self.graph = MemoryGraph(namespace=namespace)
        self.validator = CanonicalValidator(policy=validation_policy)
        self.parser = StructuralQueryParser(
            embedding_recall=EmbeddingRecall() if enable_embedding_recall else None,
            enable_embedding_recall=enable_embedding_recall,
        )
        self.dream_agent = DreamAgent() if enable_dream_agent else None
        self.namespace = namespace
        self._stats = {
            "writes_total": 0,
            "writes_blocked": 0,
            "writes_warned": 0,
            "recalls_total": 0,
        }

    # === Write API ===

    def remember(
        self,
        who: Optional[list[str]] = None,
        what: str = "",
        why: str = "",
        when: Any = None,
        where: str = "default",
        how: str = "",
        importance: float = 0.5,
        lang: Optional[str] = None,
        similar_to: Optional[Memory] = None,
        validate: bool = True,
    ) -> tuple[Memory, Any]:
        """
        Store a memory. Optionally validates against existing graph.

        Args:
            who: list of participants
            what: the action/fact (REQUIRED)
            why, when, where, how: other W5H fields
            importance: 0.0-1.0
            lang: language tag (informational)
            similar_to: optional reference memory to inherit where, lang,
                       and decayed importance from
            validate: if True, run CanonicalValidator before storing

        Returns:
            (Memory, ValidationResult) tuple
        """
        # Inherit from similar_to if provided (overrides defaults)
        if similar_to is not None:
            if where == "default":  # not explicitly overridden
                where = similar_to.where
            if lang is None:
                lang = similar_to.lang
            if importance == 0.5:  # default value, scale from ref
                importance = similar_to.importance * 0.8
            if not who:
                who = list(similar_to.who)  # copy

        # Build kwargs for Memory
        kwargs = dict(
            who=who or [],
            what=what,
            why=why,
            where=where,
            how=how,
            importance=importance,
            lang=lang,
        )
        if when is not None:
            kwargs["when"] = when

        memory = Memory(**kwargs)

        # Validate (unless skipped)
        result = None
        if validate:
            from cortext.core.validation import ValidationStatus
            result = self.validator.validate_write(memory, self.graph)
            self._stats["writes_total"] += 1
            if result.status == ValidationStatus.BLOCKED:
                self._stats["writes_blocked"] += 1
                # Don't store on BLOCKED
                return memory, result
            if result.status == ValidationStatus.WARN:
                self._stats["writes_warned"] += 1

        # Store
        self.graph.add_memory(memory)
        return memory, result

    # === Read API ===

    def recall(
        self,
        query: str,
        lang: str = "auto",
        max_results: int = 5,
        max_tokens: int = 200,
        touch: bool = True,
    ) -> tuple[str, Any]:
        """
        Recall memories matching the query. Returns compact context string.

        Args:
            query: natural-language query
            lang: language hint (pt, en, es, auto=detect)
            max_results: max memories to return
            max_tokens: max tokens in the packed context
            touch: if True (default), increment access_count / last_accessed on
                   each returned memory. This is the usage signal that feeds
                   E5 functional semantics (ForgetGate/decay). Audit/inspection
                   reads should pass touch=False so debugging doesn't inflate
                   access counts.

        Returns:
            (packed_context_string, RecallResult) tuple
        """
        result = self.parser.recall(query, self.graph, lang=lang, max_results=max_results)
        # Drop memories that were merged away by consolidation — the canonical
        # memory (or LLM-produced summary) represents them now. Without this,
        # consolidation would be cosmetic: duplicates would still surface.
        if result.memories:
            result.memories = [m for m in result.memories if not m.consolidated_into]
        if touch:
            for memory in result.memories:
                memory.touch()
        intent = result.metrics.get("intent")
        if isinstance(intent, dict):
            from cortext.core.recall.extractor import QueryIntent
            intent_obj = QueryIntent(**{k: v for k, v in intent.items() if k in QueryIntent.__dataclass_fields__})
        else:
            intent_obj = intent
        packed = pack_for_context(result.memories, intent_obj, max_tokens=max_tokens)
        self._stats["recalls_total"] += 1
        return packed, result

    # === Convenience API ===

    def remember_and_recall(
        self,
        what: str,
        who: Optional[list[str]] = None,
        where: str = "default",
        importance: float = 0.5,
        lang: Optional[str] = None,
    ) -> tuple[Memory, str]:
        """
        One-shot: store memory, then recall what it was stored alongside.
        Useful for "add and show context" flows.

        Returns: (stored_memory, packed_context_string)
        """
        memory, result = self.remember(
            who=who, what=what, where=where, importance=importance, lang=lang,
        )
        if result.is_blocking:
            return memory, ""
        # Recall using the new memory as context
        context, _ = self.recall(what, max_results=3)
        return memory, context

    # === Inspection / audit API ===

    @staticmethod
    def _memory_to_record(memory: Memory, query: Optional[str] = None) -> dict[str, Any]:
        """Serialize a memory to an audit record (W5H + metadata + score)."""
        when = memory.when
        record = {
            "id": memory.id,
            "who": list(memory.who or []),
            "what": memory.what,
            "why": memory.why,
            "when": when.isoformat() if hasattr(when, "isoformat") else when,
            "where": memory.where,
            "how": memory.how,
            "importance": round(memory.importance, 3),
            "access_count": memory.access_count,
            "lang": memory.lang,
        }
        if query is not None:
            record["match_score"] = round(memory.matches_text(query), 3)
        return record

    def inspect(
        self,
        query: str,
        lang: str = "auto",
        max_results: int = 5,
    ) -> dict[str, Any]:
        """
        Structured recall for auditing. Unlike recall() (which returns a
        packed string for prompt injection), inspect() exposes the full W5H
        decomposition, importance, access_count, and per-memory match score
        so a caller can audit *why* a memory surfaced.

        Returns a JSON-serializable dict.
        """
        # touch=False: auditing must not inflate access counts.
        _, result = self.recall(query, lang=lang, max_results=max_results, touch=False)
        # Keep only JSON-safe metric primitives (drop the QueryIntent object).
        metrics = {}
        if isinstance(result.metrics, dict):
            metrics = {
                k: v
                for k, v in result.metrics.items()
                if isinstance(v, (str, int, float, bool, type(None)))
            }
        return {
            "query": query,
            "namespace": self.namespace,
            "count": len(result.memories),
            "memories": [self._memory_to_record(m, query) for m in result.memories],
            "metrics": metrics,
        }

    def about(self, entity: str, max_results: int = 20) -> dict[str, Any]:
        """
        Return all memories about a given entity (who-match), ranked by
        importance then recency. For 'what do you know about X' audits.
        """
        mems = self.graph.find_memories(who=entity)
        mems.sort(key=lambda m: (m.importance, m.created_at), reverse=True)
        mems = mems[:max_results]
        return {
            "entity": entity,
            "namespace": self.namespace,
            "count": len(mems),
            "memories": [self._memory_to_record(m) for m in mems],
        }

    # === Background ===

    def run_dream_cycle(self) -> Any:
        """Run one Dream Agent consolidation cycle (if enabled)."""
        if not self.dream_agent:
            raise RuntimeError("DreamAgent not enabled. Pass enable_dream_agent=True to CortexV5().")
        return self.dream_agent.run_cycle(self.graph)

    # === Stats ===

    def stats(self) -> dict[str, Any]:
        """Combined stats: graph + writes + recalls."""
        return {
            "namespace": self.namespace,
            "graph": self.graph.stats(),
            "writes": dict(self._stats),
            "validator_policy": self.validator.policy.value,
        }

    def __repr__(self) -> str:
        return f"CortexV5(ns={self.namespace!r}, M={len(self.graph)}, validator={self.validator.policy.value})"
