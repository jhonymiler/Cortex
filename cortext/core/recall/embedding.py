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

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from cortext.core.memory import Memory


# Lazy import to avoid hard dependency
_MODEL = None
_MODEL_NAME = None
_UNAVAILABLE = False  # memoized failure: a missing package is not re-imported per call


def _package_installed() -> bool:
    import importlib.util

    return importlib.util.find_spec("sentence_transformers") is not None


def _try_load_model(model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
    """Try to load the sentence-transformers model. Returns None if unavailable.

    A failed import is remembered for the life of the process: without that,
    every write and recall would repeat the import's filesystem search.
    """
    global _MODEL, _MODEL_NAME, _UNAVAILABLE
    if _MODEL is not None and _MODEL_NAME == model_name:
        return _MODEL
    if _UNAVAILABLE:
        return None
    try:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(model_name)
        _MODEL_NAME = model_name
        return _MODEL
    except Exception:
        _UNAVAILABLE = True
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
        self._cache: dict[str, tuple[str, object]] = {}  # memory_id -> (text, vector)

    def is_available(self) -> bool:
        # Cheap negative path: don't load a 100MB model just to learn the
        # package is absent.
        if _UNAVAILABLE or (_MODEL is None and not _package_installed()):
            return False
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

        import numpy as np

        # Encode only what is not cached (memories are immutable in practice;
        # the cache key includes the text so an edit re-embeds).
        texts = [self._memory_to_text(m) for m in memories]
        missing = [
            i for i, (m, t) in enumerate(zip(memories, texts))
            if not self.cache_embeddings or self._cache.get(m.id, ("",))[0] != t
        ]
        try:
            query_emb = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
            if missing:
                vecs = model.encode([texts[i] for i in missing], convert_to_numpy=True, normalize_embeddings=True)
                for i, v in zip(missing, vecs):
                    self._cache[memories[i].id] = (texts[i], v)
        except Exception:
            return []

        if self.cache_embeddings:
            matrix = np.stack([self._cache[m.id][1] for m in memories])
        else:
            matrix = np.stack([self._cache.pop(m.id)[1] for m in memories])
        sims = matrix @ query_emb
        order = np.argsort(-sims)[:top_k]
        return [(memories[i], float(sims[i])) for i in order if sims[i] >= min_similarity]
