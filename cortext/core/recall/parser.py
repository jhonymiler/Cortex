"""
StructuralQueryParser — uses an Extractor + matches against MemoryGraph.

The Parser is the elem. 4 (interpreter) of the detector: a dedicated
component that knows the W5H schema and matches queries to memories
deterministically. The LLM is NOT the interpreter; it can be the
fallback (via LLMExtractor) but the primary path is structural.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from cortext.core.recall.extractor import Extractor, QueryIntent
from cortext.core.recall.extractors.regex_lang import RegexExtractor
from cortext.core.recall.pack import pack_for_context

if TYPE_CHECKING:
    from cortext.core.memory import Memory
    from cortext.core.graph import MemoryGraph, RecallResult


class StructuralQueryParser:
    """
    Recall memories by matching query intent (W5H) to memory contents.

    Three modes of operation (in order):
      1. Structural match (W5H exact/partial) — free, fast
      2. Token Jaccard (semantic fallback, language-agnostic) — free
      3. Embedding similarity (multilingual跨语) — optional, requires
         sentence-transformers
    """

    def __init__(
        self,
        extractor: Optional[Extractor] = None,
        embedding_recall: Optional["EmbeddingRecall"] = None,
        enable_semantic_fallback: bool = True,
        enable_embedding_recall: bool = True,
    ) -> None:
        """
        Args:
            extractor: pluggable Extractor (default: RegexExtractor with PT/EN/ES)
            embedding_recall: optional EmbeddingRecall for cross-language semantic
            enable_semantic_fallback: if True, use token Jaccard when structural returns few results
            enable_embedding_recall: if True, use embeddings (when available) as 3rd tier
        """
        from cortext.core.recall.embedding import EmbeddingRecall
        self.extractor = extractor or RegexExtractor()
        self.embedding_recall = embedding_recall or EmbeddingRecall()
        self.enable_semantic_fallback = enable_semantic_fallback
        self.enable_embedding_recall = enable_embedding_recall

    def parse(self, query: str, lang: str = "auto") -> QueryIntent:
        """Parse query into W5H intent."""
        return self.extractor.extract(query, lang=lang)

    def recall(
        self,
        query: str,
        graph: "MemoryGraph",
        lang: str = "auto",
        max_results: int = 5,
    ) -> "RecallResult":
        """
        Recall memories matching the query, structurally first.

        Returns RecallResult with memories, sorted by structural + token relevance.
        """
        from cortext.core.graph import RecallResult

        intent = self.parse(query, lang=lang)
        result = RecallResult()
        result.metrics["intent"] = intent.to_dict()
        result.metrics["extractor"] = type(self.extractor).__name__

        # 1. Structural match (W5H exact/partial)
        if intent.is_structured():
            structural = self._find_by_intent(intent, graph, max_results)
            # structural is list of (memory, score) tuples
            result.memories.extend(m for m, _ in structural)
            result.metrics["structural_match_count"] = len(structural)

        # 2. Token Jaccard fallback
        if len(result.memories) < 2 and self.enable_semantic_fallback:
            seen_ids = {m.id for m in result.memories}
            semantic = self._semantic_fallback(query, graph, max_results)
            for mem, _ in semantic:
                if mem.id not in seen_ids:
                    result.memories.append(mem)
                    seen_ids.add(mem.id)
            result.metrics["semantic_fallback_count"] = len(semantic)

        return result

    def pack(
        self,
        matches: list["Memory"],
        intent: Optional[QueryIntent] = None,
        max_tokens: int = 200,
    ) -> str:
        """Pack matches into compact context string."""
        return pack_for_context(matches, intent, max_tokens)

    def recall_and_pack(
        self,
        query: str,
        graph: "MemoryGraph",
        lang: str = "auto",
        max_results: int = 5,
        max_tokens: int = 200,
    ) -> str:
        """Convenience: recall + pack in one call."""
        result = self.recall(query, graph, lang=lang, max_results=max_results)
        return self.pack(result.memories, intent=result.metrics.get("intent"), max_tokens=max_tokens)

    # === Private helpers ===

    def _find_by_intent(
        self, intent: QueryIntent, graph: "MemoryGraph", max_results: int
    ) -> list[tuple["Memory", float]]:
        """Find memories matching the W5H intent. Returns (memory, score) sorted by score."""
        scored: list[tuple["Memory", float]] = []
        for mem in graph.iter_memories():
            score = self._match_score(intent, mem)
            if score >= 0.3:
                scored.append((mem, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:max_results]

    def _match_score(self, intent: QueryIntent, memory: "Memory") -> float:
        """Score how well a memory matches the intent (0-1)."""
        score = 0.0
        weight_sum = 0.0

        # Who match (weight 0.5)
        if intent.who:
            mem_who = set(w.lower() for w in (memory.who or []))
            intent_who = set(w.lower() for w in intent.who)
            if mem_who and intent_who:
                overlap = len(mem_who & intent_who) / len(intent_who)
                score += 0.5 * overlap
            weight_sum += 0.5

        # What match (weight 0.3)
        if intent.what:
            mem_what = (memory.what or "").lower()
            intent_what = intent.what.lower()
            if mem_what and intent_what:
                if intent_what in mem_what or mem_what in intent_what:
                    score += 0.3
                else:
                    intent_tokens = set(intent_what.split())
                    mem_tokens = set(mem_what.split())
                    if intent_tokens and mem_tokens:
                        token_overlap = len(intent_tokens & mem_tokens) / len(intent_tokens)
                        score += 0.3 * token_overlap
            weight_sum += 0.3

        # Where / location boost
        if intent.query_type == "location" and memory.where and memory.where != "default":
            score += 0.1
            weight_sum += 0.1

        if weight_sum == 0:
            return 0.0
        return min(1.0, score / weight_sum) if weight_sum > 0 else 0.0

    def _semantic_fallback(
        self, query: str, graph: "MemoryGraph", max_results: int
    ) -> list[tuple["Memory", float]]:
        """Token Jaccard fallback (language-agnostic)."""
        if not query or not query.strip():
            return []

        # Strip stopwords
        from cortext.core.memory import _tokenize
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        scored: list[tuple["Memory", float]] = []
        for mem in graph.iter_memories():
            mem_text = (mem.what or "") + " " + " ".join(mem.who or []) + " " + (mem.where or "")
            mem_tokens = _tokenize(mem_text)
            if not mem_tokens:
                continue
            overlap = len(query_tokens & mem_tokens) / len(query_tokens)
            if overlap >= 0.3:
                scored.append((mem, overlap))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:max_results]
