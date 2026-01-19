"""
Advanced Ranking Algorithms for Memory Retrieval.

Implements state-of-the-art ranking techniques inspired by Graphiti:

1. RRF (Reciprocal Rank Fusion): Combines multiple ranking signals
2. MMR (Maximal Marginal Relevance): Balances relevance with diversity

These algorithms significantly improve recall quality by:
- Fusing TF-IDF, embedding similarity, and importance scores
- Avoiding redundant/similar results in the final set
- Providing more diverse and representative memory samples
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable
import math

from cortex.core.primitives import Episode
from cortex.core.processing.embedding import cosine_similarity


@dataclass
class RankedItem:
    """Item with ranking metadata."""

    id: str
    item: Any  # Episode, Entity, etc.
    score: float
    source: str  # Which ranker produced this score
    embedding: list[float] | None = None


class ReciprocalRankFusion:
    """
    Reciprocal Rank Fusion (RRF) - Combines multiple rankings.

    RRF is a simple but highly effective rank fusion algorithm that
    combines rankings from different sources (TF-IDF, embeddings, importance).

    Formula: RRF_score(d) = Σ 1/(k + rank_i(d))

    Where:
    - k is a constant (default 60) that dampens the effect of high ranks
    - rank_i(d) is the rank of document d in ranking i

    Properties:
    - Doesn't require score calibration between rankers
    - Robust to outliers
    - Works well even when individual rankers are weak

    Reference: Cormack et al., "Reciprocal Rank Fusion outperforms
    Condorcet and individual Rank Learning Methods" (SIGIR 2009)
    """

    def __init__(self, k: int = 60):
        """
        Args:
            k: Ranking constant (higher = more weight to lower ranks).
               Default 60 works well empirically.
        """
        self.k = k

    def fuse(
        self,
        rankings: dict[str, list[RankedItem]],
        limit: int = 10,
    ) -> list[RankedItem]:
        """
        Fuse multiple rankings into a single unified ranking.

        Args:
            rankings: Dict of {source_name: [RankedItem, ...]}
                      Each list should be sorted by relevance (best first)
            limit: Maximum items to return

        Returns:
            Unified ranking sorted by RRF score (best first)
        """
        # Accumulate RRF scores
        rrf_scores: dict[str, float] = defaultdict(float)
        items_by_id: dict[str, RankedItem] = {}
        source_contributions: dict[str, dict[str, float]] = defaultdict(dict)

        for source_name, ranked_items in rankings.items():
            for rank, item in enumerate(ranked_items):
                # RRF formula: 1 / (k + rank)
                # rank is 0-indexed, so add 1 to make it 1-indexed
                contribution = 1.0 / (self.k + rank + 1)
                rrf_scores[item.id] += contribution
                source_contributions[item.id][source_name] = contribution

                # Keep the item with best embedding (for MMR later)
                if item.id not in items_by_id:
                    items_by_id[item.id] = item
                elif item.embedding and not items_by_id[item.id].embedding:
                    items_by_id[item.id].embedding = item.embedding

        # Sort by RRF score
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        # Build result with fused scores
        results = []
        for item_id in sorted_ids[:limit]:
            item = items_by_id[item_id]
            item.score = rrf_scores[item_id]
            item.source = "rrf"
            results.append(item)

        return results

    def fuse_simple(
        self,
        rankings: list[list[str]],
        limit: int = 10,
    ) -> list[tuple[str, float]]:
        """
        Simplified fusion for ID-only rankings.

        Args:
            rankings: List of rankings, each a list of IDs (best first)
            limit: Maximum items to return

        Returns:
            List of (id, rrf_score) tuples sorted by score
        """
        rrf_scores: dict[str, float] = defaultdict(float)

        for ranking in rankings:
            for rank, doc_id in enumerate(ranking):
                rrf_scores[doc_id] += 1.0 / (self.k + rank + 1)

        sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_items[:limit]


class MaximalMarginalRelevance:
    """
    Maximal Marginal Relevance (MMR) - Balances relevance and diversity.

    MMR iteratively selects items that are:
    1. Highly relevant to the query
    2. Not too similar to already-selected items

    Formula: MMR = arg max [λ * Sim(d, Q) - (1-λ) * max(Sim(d, S))]

    Where:
    - λ (lambda) balances relevance vs diversity (0.7 = 70% relevance)
    - Sim(d, Q) is similarity between document d and query Q
    - max(Sim(d, S)) is max similarity between d and selected set S

    Properties:
    - Reduces redundancy in results
    - Ensures coverage of different aspects/topics
    - Configurable relevance-diversity tradeoff

    Reference: Carbonell & Goldstein, "The Use of MMR, Diversity-Based
    Reranking for Reordering Documents and Producing Summaries" (SIGIR 1998)
    """

    def __init__(self, lambda_param: float = 0.7):
        """
        Args:
            lambda_param: Tradeoff between relevance (1.0) and diversity (0.0).
                         Default 0.7 = 70% relevance, 30% diversity.
        """
        self.lambda_param = lambda_param

    def select(
        self,
        candidates: list[RankedItem],
        query_embedding: list[float] | None = None,
        limit: int = 10,
        similarity_fn: Callable[[list[float], list[float]], float] | None = None,
    ) -> list[RankedItem]:
        """
        Select diverse, relevant items using MMR.

        Args:
            candidates: Items to select from (should have embeddings)
            query_embedding: Query embedding for relevance calculation
            limit: Maximum items to select
            similarity_fn: Custom similarity function (default: cosine)

        Returns:
            Selected items balancing relevance and diversity
        """
        if not candidates:
            return []

        if similarity_fn is None:
            similarity_fn = cosine_similarity

        # If no embeddings available, fall back to score-based selection
        has_embeddings = any(c.embedding for c in candidates)

        if not has_embeddings or query_embedding is None:
            # Fallback: just use original scores with simple deduplication
            return self._select_by_score(candidates, limit)

        selected: list[RankedItem] = []
        remaining = list(candidates)

        while remaining and len(selected) < limit:
            best_item = None
            best_mmr_score = float('-inf')

            for candidate in remaining:
                if not candidate.embedding:
                    # No embedding, use original score as relevance
                    relevance = candidate.score
                else:
                    # Compute query relevance
                    relevance = similarity_fn(candidate.embedding, query_embedding)

                # Compute max similarity to already selected items
                max_sim_to_selected = 0.0
                if selected and candidate.embedding:
                    for sel in selected:
                        if sel.embedding:
                            sim = similarity_fn(candidate.embedding, sel.embedding)
                            max_sim_to_selected = max(max_sim_to_selected, sim)

                # MMR score
                mmr_score = (
                    self.lambda_param * relevance -
                    (1 - self.lambda_param) * max_sim_to_selected
                )

                if mmr_score > best_mmr_score:
                    best_mmr_score = mmr_score
                    best_item = candidate

            if best_item:
                best_item.score = best_mmr_score
                best_item.source = "mmr"
                selected.append(best_item)
                remaining.remove(best_item)
            else:
                break

        return selected

    def _select_by_score(
        self,
        candidates: list[RankedItem],
        limit: int,
    ) -> list[RankedItem]:
        """Fallback selection using original scores with simple diversity."""
        # Sort by score
        sorted_candidates = sorted(candidates, key=lambda x: x.score, reverse=True)

        selected: list[RankedItem] = []
        seen_actions: set[str] = set()  # Simple deduplication by action

        for candidate in sorted_candidates:
            if len(selected) >= limit:
                break

            # Simple diversity: avoid same action twice
            if hasattr(candidate.item, 'action'):
                action_key = candidate.item.action.lower().strip()[:20]
                if action_key in seen_actions:
                    continue
                seen_actions.add(action_key)

            selected.append(candidate)

        return selected


class HybridRanker:
    """
    Hybrid Ranker - Combines RRF fusion with MMR diversity.

    Pipeline:
    1. Collect rankings from multiple sources (TF-IDF, embeddings, importance)
    2. Fuse with RRF to get unified ranking
    3. Apply MMR to ensure diversity in final results

    This is the main entry point for advanced ranking in Cortex.
    """

    def __init__(
        self,
        rrf_k: int = 60,
        mmr_lambda: float = 0.7,
        enable_mmr: bool = True,
    ):
        """
        Args:
            rrf_k: RRF constant (higher = more weight to lower ranks)
            mmr_lambda: MMR relevance-diversity tradeoff
            enable_mmr: Whether to apply MMR after RRF
        """
        self.rrf = ReciprocalRankFusion(k=rrf_k)
        self.mmr = MaximalMarginalRelevance(lambda_param=mmr_lambda)
        self.enable_mmr = enable_mmr

    def rank_episodes(
        self,
        episodes: list[Episode],
        query: str,
        query_embedding: list[float] | None = None,
        tfidf_scores: dict[str, float] | None = None,
        embedding_scores: dict[str, float] | None = None,
        importance_weight: float = 0.3,
        limit: int = 10,
    ) -> list[tuple[Episode, float]]:
        """
        Rank episodes using hybrid RRF + MMR approach.

        Args:
            episodes: Episodes to rank
            query: Query text
            query_embedding: Pre-computed query embedding (optional)
            tfidf_scores: Pre-computed TF-IDF scores {episode_id: score}
            embedding_scores: Pre-computed embedding similarity scores
            importance_weight: Weight for episode importance (0-1)
            limit: Maximum results

        Returns:
            List of (episode, final_score) tuples sorted by relevance
        """
        if not episodes:
            return []

        # Build rankings from different sources
        rankings: dict[str, list[RankedItem]] = {}

        # 1. TF-IDF ranking
        if tfidf_scores:
            tfidf_items = []
            for ep in episodes:
                score = tfidf_scores.get(ep.id, 0.0)
                tfidf_items.append(RankedItem(
                    id=ep.id,
                    item=ep,
                    score=score,
                    source="tfidf",
                    embedding=getattr(ep, 'embedding', None),
                ))
            tfidf_items.sort(key=lambda x: x.score, reverse=True)
            rankings["tfidf"] = tfidf_items

        # 2. Embedding similarity ranking
        if embedding_scores:
            emb_items = []
            for ep in episodes:
                score = embedding_scores.get(ep.id, 0.0)
                emb_items.append(RankedItem(
                    id=ep.id,
                    item=ep,
                    score=score,
                    source="embedding",
                    embedding=getattr(ep, 'embedding', None),
                ))
            emb_items.sort(key=lambda x: x.score, reverse=True)
            rankings["embedding"] = emb_items

        # 3. Importance ranking (native to Cortex)
        importance_items = []
        for ep in episodes:
            # Combine importance with retrievability proxy
            score = ep.importance * (1 + importance_weight * ep.occurrence_count)
            importance_items.append(RankedItem(
                id=ep.id,
                item=ep,
                score=score,
                source="importance",
                embedding=getattr(ep, 'embedding', None),
            ))
        importance_items.sort(key=lambda x: x.score, reverse=True)
        rankings["importance"] = importance_items

        # 4. Recency ranking (cognitive boost for recent memories)
        from datetime import datetime
        recency_items = []
        now = datetime.now()
        for ep in episodes:
            if ep.timestamp:
                hours_old = (now - ep.timestamp).total_seconds() / 3600
                # Exponential decay: recent = high score
                score = math.exp(-hours_old / 168)  # 168h = 1 week half-life
            else:
                score = 0.5
            recency_items.append(RankedItem(
                id=ep.id,
                item=ep,
                score=score,
                source="recency",
                embedding=getattr(ep, 'embedding', None),
            ))
        recency_items.sort(key=lambda x: x.score, reverse=True)
        rankings["recency"] = recency_items

        # If no explicit rankings provided, compute similarity-based
        if not tfidf_scores and not embedding_scores:
            similarity_items = []
            for ep in episodes:
                # Use episode's similarity_score method
                score = ep.similarity_score(query, {})
                similarity_items.append(RankedItem(
                    id=ep.id,
                    item=ep,
                    score=score,
                    source="similarity",
                    embedding=getattr(ep, 'embedding', None),
                ))
            similarity_items.sort(key=lambda x: x.score, reverse=True)
            rankings["similarity"] = similarity_items

        # Fuse with RRF
        fused = self.rrf.fuse(rankings, limit=limit * 2)  # Get extra for MMR

        # Apply MMR for diversity
        if self.enable_mmr and len(fused) > 1:
            diverse = self.mmr.select(
                candidates=fused,
                query_embedding=query_embedding,
                limit=limit,
            )
        else:
            diverse = fused[:limit]

        # Convert back to (Episode, score) tuples
        return [(item.item, item.score) for item in diverse]

    def rank_entities(
        self,
        entities: list[Any],
        query: str,
        query_embedding: list[float] | None = None,
        limit: int = 10,
    ) -> list[tuple[Any, float]]:
        """
        Rank entities using hybrid approach.

        Args:
            entities: Entities to rank
            query: Query text
            query_embedding: Pre-computed query embedding
            limit: Maximum results

        Returns:
            List of (entity, final_score) tuples
        """
        if not entities:
            return []

        rankings: dict[str, list[RankedItem]] = {}

        # 1. Name match ranking
        query_lower = query.lower()
        name_items = []
        for ent in entities:
            name_lower = ent.name.lower()
            if query_lower in name_lower or name_lower in query_lower:
                score = 1.0
            elif any(query_lower in ident.lower() for ident in ent.identifiers):
                score = 0.8
            else:
                score = 0.1
            name_items.append(RankedItem(
                id=ent.id,
                item=ent,
                score=score,
                source="name_match",
            ))
        name_items.sort(key=lambda x: x.score, reverse=True)
        rankings["name_match"] = name_items

        # 2. Access frequency ranking
        freq_items = []
        for ent in entities:
            score = min(1.0, ent.access_count / 10.0)  # Normalize to 0-1
            freq_items.append(RankedItem(
                id=ent.id,
                item=ent,
                score=score,
                source="frequency",
            ))
        freq_items.sort(key=lambda x: x.score, reverse=True)
        rankings["frequency"] = freq_items

        # Fuse and return
        fused = self.rrf.fuse(rankings, limit=limit)
        return [(item.item, item.score) for item in fused]
