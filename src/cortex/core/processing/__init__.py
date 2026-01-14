"""
Cortex Processing - Text and embedding utilities.

Components:
- EmbeddingService: Generates embeddings using Ollama
- Language utilities: Tokenization and text processing
- SemanticHash: Fast semantic similarity
- MemoryNormalizer: Normalizes memory data
"""

from cortex.core.processing.embedding import EmbeddingService
from cortex.core.processing.language import tokenize
from cortex.core.processing.semantic_hash import (
    text_to_vector,
    w5h_to_vector,
    semantic_similarity,
    w5h_similarity,
)
from cortex.core.processing.memory_normalizer import MemoryNormalizer

__all__ = [
    "EmbeddingService",
    "tokenize",
    "text_to_vector",
    "w5h_to_vector",
    "semantic_similarity",
    "w5h_similarity",
    "MemoryNormalizer",
]
