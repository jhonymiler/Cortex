"""
StructuralQueryParser — uses an Extractor + matches against MemoryGraph.

The Parser is the elem. 4 (interpreter) of the detector: a dedicated
component that knows the W5H schema and matches queries to memories
deterministically. The LLM is NOT the interpreter; it can be the
fallback (via LLMExtractor) but the primary path is structural.

Every tier generates candidates from the graph's inverted indexes and scores
only those, so recall cost follows the number of matching memories, not the
size of the graph. Memories merged away by consolidation are excluded before
ranking, so they never take a top-k slot.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Iterable, Optional

from cortext.core.recall.extractor import Extractor, QueryIntent
from cortext.core.recall.extractors.regex_lang import RegexExtractor
from cortext.core.recall.pack import pack_for_context
from cortext.core.text import fold, tokenize, tokenize_all

if TYPE_CHECKING:
    from cortext.core.memory import Memory
    from cortext.core.graph import MemoryGraph, RecallResult
    from cortext.core.recall.embedding import EmbeddingRecall


def _candidates(graph: "MemoryGraph", ids: Iterable[str]) -> list["Memory"]:
    get = graph.get_memory
    out = []
    for i in ids:
        m = get(i)
        if m is not None and not m.consolidated_into:
            out.append(m)
    return out


def _rank_key(item: tuple["Memory", float]) -> tuple:
    mem, score = item
    # Score first; importance, then recency, break ties deterministically.
    return (-score, -mem.importance, -mem.created_at.timestamp())


class StructuralQueryParser:
    """
    Recall memories by matching query intent (W5H) to memory contents.

    Three tiers, in order:
      1. Structural match (W5H exact/partial) — index lookup by who + what
      2. Token coverage (language-agnostic) — index lookup by query tokens
      3. Embedding similarity (multilingual) — optional, needs
         sentence-transformers; only when 1+2 found too little
    """

    def __init__(
        self,
        extractor: Optional[Extractor] = None,
        embedding_recall: Optional["EmbeddingRecall"] = None,
        enable_semantic_fallback: bool = True,
        enable_embedding_recall: bool = True,
    ) -> None:
        self.extractor = extractor or RegexExtractor()
        if embedding_recall is None and enable_embedding_recall:
            from cortext.core.recall.embedding import EmbeddingRecall

            embedding_recall = EmbeddingRecall()
        self.embedding_recall = embedding_recall
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
        """Recall memories matching the query, structurally first."""
        from cortext.core.graph import RecallResult

        t0 = time.perf_counter()
        intent = self.parse(query, lang=lang)
        result = RecallResult()
        result.metrics["intent"] = intent.to_dict()
        result.metrics["extractor"] = type(self.extractor).__name__
        result.intent = intent  # type: ignore[attr-defined]

        # 1. Structural match (W5H exact/partial)
        if intent.is_structured():
            structural = self._find_by_intent(intent, graph, max_results)
            result.memories.extend(m for m, _ in structural)
            result.metrics["structural_match_count"] = len(structural)

        # 2. Token coverage fallback
        if len(result.memories) < 2 and self.enable_semantic_fallback:
            seen_ids = {m.id for m in result.memories}
            semantic = self._semantic_fallback(query, graph, max_results)
            for mem, _ in semantic:
                if mem.id not in seen_ids and len(result.memories) < max_results:
                    result.memories.append(mem)
                    seen_ids.add(mem.id)
            result.metrics["semantic_fallback_count"] = len(semantic)

        # 3. Embedding tier (cross-language / paraphrase), only when needed
        if (
            not result.memories
            and self.enable_embedding_recall
            and self.embedding_recall is not None
            and self.embedding_recall.is_available()
        ):
            pool = [m for m in graph.iter_memories() if not m.consolidated_into]
            ranked = self.embedding_recall.rank_memories(query, pool, top_k=max_results, min_similarity=0.45)
            result.memories.extend(m for m, _ in ranked)
            result.metrics["embedding_match_count"] = len(ranked)

        result.metrics["latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)
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
        return self.pack(result.memories, intent=getattr(result, "intent", None), max_tokens=max_tokens)

    # === Private helpers ===

    def _find_by_intent(
        self, intent: QueryIntent, graph: "MemoryGraph", max_results: int
    ) -> list[tuple["Memory", float]]:
        """Find memories matching the W5H intent. Returns (memory, score) sorted by score.

        Candidates come from the indexes in two waves. Participants first: a
        memory that matches every name in ``who`` outscores any memory that
        matches none (who weighs 0.5 against what's 0.3), so when the first
        wave already fills ``max_results`` above that ceiling, the what-only
        candidates (often thousands for a common verb) are never scored.
        """
        who_sets = [graph.ids_for_who(w) for w in intent.who]
        who_ids: set[str] = set().union(*who_sets) if who_sets else set()

        def score_all(ids: Iterable[str]) -> list[tuple["Memory", float]]:
            out = []
            for mem in _candidates(graph, ids):
                hits = sum(1 for ws in who_sets if mem.id in ws)
                score = self._match_score(intent, mem, who_hits=hits)
                if score >= 0.3:
                    out.append((mem, score))
            return out

        scored = score_all(who_ids)
        weight_sum = (0.5 if intent.who else 0.0) + (0.3 if intent.what else 0.0)
        if intent.query_type == "location":
            weight_sum += 0.1
        ceiling_without_who = ((0.3 if intent.what else 0.0) + (0.1 if intent.query_type == "location" else 0.0)) / (weight_sum or 1)
        scored.sort(key=_rank_key)
        filled = len(scored) >= max_results and scored[max_results - 1][1] > ceiling_without_who

        if not filled:
            more: set[str] = set()
            what_tokens = tokenize(intent.what)
            if what_tokens:
                more |= graph.ids_for_tokens(what_tokens, prefix=True)
            if intent.where:
                more |= graph.ids_for_tokens(tokenize(intent.where))
            more -= who_ids
            if more:
                scored.extend(score_all(more))
                scored.sort(key=_rank_key)
        # Relative cutoff: drop matches under half the best score.
        if scored:
            floor = 0.5 * scored[0][1]
            scored = [item for item in scored if item[1] >= floor]
        return scored[:max_results]

    @staticmethod
    def _who_matches(name: str, mem_who: list[str]) -> bool:
        key = fold(name)
        key_tokens = tokenize(name)
        for w in mem_who:
            fw = fold(w)
            if fw == key:
                return True
            # "Maria" matches "Maria Silva": every word of the name is a word of w
            if key_tokens and key_tokens <= tokenize(w):
                return True
        return False

    def _match_score(self, intent: QueryIntent, memory: "Memory", who_hits: Optional[int] = None) -> float:
        """Score how well a memory matches the intent (0-1).

        ``who_hits`` (how many intent names the memory matches) can be passed
        when the caller already knows it from the index.
        """
        score = 0.0
        weight_sum = 0.0

        # Who match (weight 0.5)
        if intent.who:
            mem_who = memory.who or []
            if mem_who:
                hits = who_hits if who_hits is not None else sum(1 for w in intent.who if self._who_matches(w, mem_who))
                score += 0.5 * hits / len(intent.who)
            weight_sum += 0.5

        # What match (weight 0.3)
        if intent.what:
            mem_what = fold(memory.what or "")
            intent_what = fold(intent.what)
            if mem_what and intent_what:
                if intent_what in mem_what or mem_what in intent_what:
                    score += 0.3
                else:
                    intent_tokens = set(intent_what.split())
                    mem_tokens = set(mem_what.split())
                    if intent_tokens and mem_tokens:
                        score += 0.3 * len(intent_tokens & mem_tokens) / len(intent_tokens)
            weight_sum += 0.3

        # Where / location boost
        if intent.query_type == "location" and memory.where and memory.where != "default":
            score += 0.1
            weight_sum += 0.1

        if weight_sum == 0:
            return 0.0
        return min(1.0, score / weight_sum)

    def _semantic_fallback(
        self, query: str, graph: "MemoryGraph", max_results: int
    ) -> list[tuple["Memory", float]]:
        """Token match over the inverted index (language-agnostic).

        Scored straight from the postings, never by re-tokenizing memories.
        A memory qualifies when either:
          - it covers >= 30% of the query's tokens (short, keyword queries), or
          - it covers >= 50% of the IDF mass of the query tokens the graph
            knows, through at least one informative (not ubiquitous) term.
        The second rule is what makes long natural prompts work: an agent's
        prompt has 10-30 words, most of which no memory contains; words absent
        from the vocabulary carry no evidence either way.
        Ranked by the IDF mass matched (+0.25 when a query term names one of
        the memory's participants), then importance and recency; results
        under half the best score are dropped.
        """
        if not query or not query.strip():
            return []
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        import math

        n = max(1, len(graph))
        hits: dict[str, int] = {}
        mass: dict[str, float] = {}
        best: dict[str, float] = {}
        matched: dict[str, set[str]] = {}
        known_mass = 0.0
        for t in query_tokens:
            postings = graph.ids_for_token(t)
            if not postings:
                continue
            idf = math.log(1 + n / len(postings))
            known_mass += idf
            for mid in postings:
                hits[mid] = hits.get(mid, 0) + 1
                mass[mid] = mass.get(mid, 0.0) + idf
                matched.setdefault(mid, set()).add(t)
                if idf > best.get(mid, 0.0):
                    best[mid] = idf
        if not hits:
            return []

        need_all = 0.3 * len(query_tokens)
        # "Informative": the term is in at most ~10% of memories (small graphs exempt).
        informative = math.log(1 + n / max(1.0, 0.1 * n)) if n >= 20 else 0.0
        scored: list[tuple["Memory", float]] = []
        rejected: list["Memory"] = []
        get = graph.get_memory
        for mid, h in hits.items():
            mem = get(mid)
            if mem is None or mem.consolidated_into:
                continue
            # A query term naming a participant outweighs a mere mention, and
            # anchors the match even when the name is everywhere (a customer's
            # own namespace mentions the customer in most memories).
            is_participant = bool(mem.who) and not tokenize_all(*mem.who).isdisjoint(query_tokens)
            if h < need_all and not (mass[mid] >= 0.5 * known_mass and (best[mid] >= informative or is_participant)):
                rejected.append(mem)
                continue
            scored.append((mem, mass[mid] / known_mass + (0.25 if is_participant else 0.0) + h * 1e-3))
        scored.sort(key=_rank_key)
        if scored:
            top_mem, top_score = scored[0]
            top_terms = matched.get(top_mem.id, set())
            # Relative cutoff: a result must score at least half of the best one,
            # so a strong match isn't diluted by memories that merely share a
            # common word (each of those costs prompt tokens).
            before_cut = [m for m, _ in scored]
            scored = [item for item in scored if item[1] >= 0.5 * top_score]
            # ...except a memory NEWER than the best one, sharing one of its
            # matched terms with real weight: it may be its correction
            # ("actually make the canary 10%" after "canary at 5%"). The context
            # is packed oldest-first, so the agent reads the correction last.
            kept = {m.id for m, _ in scored}
            # the shared term must be rare (a subject like "canary", not "deploy")
            rare = {t for t in top_terms if graph.document_frequency(t) <= max(2, 0.1 * n)}
            newer = [m for m in rejected + before_cut
                     if m.id not in kept and m.created_at > top_mem.created_at
                     and matched.get(m.id, set()) & rare]
            if newer:  # at most one: a correction is usually a single, latest statement
                latest = max(newer, key=lambda m: m.created_at)
                scored.append((latest, mass[latest.id] / known_mass))
        return scored[:max_results]
