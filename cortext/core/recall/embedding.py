"""
Embedding-based semantic recall (multilingual).

Uses sentence-transformers with a multilingual model for跨语
semantic matching. The schema (W5H) is universal, but the VALUES
can be in any language — embeddings bridge that gap.

OPTIONAL: if sentence-transformers is not installed, this module
imports gracefully and the embedding level of recall is skipped.

Model: paraphrase-multilingual-MiniLM-L12-v2
  - 100+ languages (PT, EN, ES, FR, DE, ZH, JA, KO, AR, ...)
  - ~100MB on disk
  - ~50ms per query on CPU, ~10ms on GPU
  - MIT license
  - https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from cortext.core.memory import Memory


# Lazy import to avoid hard dependency
_MODEL = None
_MODEL_NAME = None


def _try_load_model(model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
    """Try to load the sentence-transformers model. Returns None if unavailable."""
    global _MODEL, _MODEL_NAME
    if _MODEL is not None and _MODEL_NAME == model_name:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(model_name)
        _MODEL_NAME = model_name
        return _MODEL
    except ImportError:
        return None


def is_available() -> bool:
    """Check if embedding-based recall is available (sentence-transformers installed)."""
    return _try_load_model() is not None


def cosine_similarity(a, b) -> float:
    """Cosine similarity between two numpy arrays (or lists)."""
    import numpy as np
    a = np.asarray(a)
    b = np.asarray(b)
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class EmbeddingRecall:
    """
    Multilingual semantic recall via sentence-transformers.

    Falls back to no-op (returns empty results) if sentence-transformers
    is not installed — caller should check `is_available()` first.
    """

    def __init__(
        self,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        cache_embeddings: bool = True,
    ) -> None:
        """
        Args:
            model_name: HuggingFace model name
            cache_embeddings: cache memory embeddings to avoid recomputing
        """
        self.model_name = model_name
        self.cache_embeddings = cache_embeddings
        self._cache: dict[str, list[float]] = {}  # memory_id -> embedding

    def is_available(self) -> bool:
        return _try_load_model(self.model_name) is not None

    def _memory_to_text(self, memory: "Memory") -> str:
        """Project a memory to a text representation for embedding."""
        parts: list[str] = []
        if memory.who:
            parts.append(",".join(memory.who))
        if memory.what:
            parts.append(memory.what)
        if memory.why:
            parts.append(memory.why)
        if memory.where and memory.where != "default":
            parts.append(f"@{memory.where}")
        if memory.how:
            parts.append(memory.how)
        return " | ".join(parts) if parts else (memory.what or "")

    def embed(self, text: str) -> Optional[list[float]]:
        """Embed a single text. Returns None if model unavailable."""
        model = _try_load_model(self.model_name)
        if model is None:
            return None
        vec = model.encode(text, convert_to_numpy=True)
        return vec.tolist()

    def rank_memories(
        self,
        query: str,
        memories: list["Memory"],
        top_k: int = 5,
        min_similarity: float = 0.3,
    ) -> list[tuple["Memory", float]]:
        """
        Rank memories by semantic similarity to query.

        Args:
            query: the search query
            memories: list of Memory to search
            top_k: return top-k results
            min_similarity: drop results below this threshold

        Returns:
            list of (Memory, similarity_score) sorted by score desc
        """
        model = _try_load_model(self.model_name)
        if model is None:
            return []

        if not memories:
            return []

        # Build memory texts
        mem_texts = [self._memory_to_text(m) for m in memories]

        # Encode in batch (1 query + N memories)
        all_texts = [query] + mem_texts
        try:
            embeddings = model.encode(all_texts, convert_to_numpy=True)
        except Exception:
            return []

        # Cosine similarity
        query_emb = embeddings[0]
        mem_embs = embeddings[1:]
        scored: list[tuple["Memory", float]] = []
        for mem, mem_emb in zip(memories, mem_embs):
            sim = cosine_similarity(query_emb, mem_emb)
            if sim >= min_similarity:
                scored.append((mem, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
