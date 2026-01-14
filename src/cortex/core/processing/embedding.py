"""
Embedding Service - Integração com Ollama para embeddings semânticos.

Este módulo fornece embeddings vetoriais para busca semântica no Cortex.
Usa o modelo qwen3-embedding via Ollama API.

Características:
- Cache de embeddings para evitar recálculos
- Batch processing para múltiplos textos
- Fallback para busca por tokens se embedding falhar
"""

import os
import math
import hashlib
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime

import requests


# Configurações
# Prioriza OLLAMA_URL, depois OLLAMA_BASE_URL, depois fallback
OLLAMA_URL = os.getenv("OLLAMA_URL") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("CORTEX_EMBEDDING_MODEL", "qwen3-embedding:0.6b")
EMBEDDING_DIMENSIONS = 1024  # qwen3-embedding usa 1024 dimensões
EMBEDDING_CACHE_SIZE = 1000  # Máximo de embeddings em cache


@dataclass
class EmbeddingResult:
    """Resultado de uma operação de embedding."""
    
    vector: list[float]
    dimensions: int
    model: str
    latency_ms: float
    cached: bool = False
    
    def similarity(self, other: "EmbeddingResult") -> float:
        """Calcula similaridade cosseno com outro embedding."""
        return cosine_similarity(self.vector, other.vector)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Calcula similaridade cosseno entre dois vetores.
    
    Returns:
        Valor entre -1 e 1, onde 1 = idênticos, 0 = ortogonais
    """
    if len(a) != len(b):
        return 0.0
    
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot / (norm_a * norm_b)


class EmbeddingService:
    """
    Serviço de embeddings usando Ollama.
    
    Características:
    - Cache LRU para evitar recálculos
    - Batch processing para eficiência
    - Timeout configurável
    - Fallback gracioso se Ollama não disponível
    """
    
    def __init__(
        self,
        ollama_url: str = OLLAMA_URL,
        model: str = EMBEDDING_MODEL,
        cache_size: int = EMBEDDING_CACHE_SIZE,
        timeout: int = 30,
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        
        # Cache: hash do texto -> EmbeddingResult
        self._cache: dict[str, EmbeddingResult] = {}
        self._cache_size = cache_size
        
        # Stats
        self._stats = {
            "requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "total_latency_ms": 0,
        }
    
    def _text_hash(self, text: str) -> str:
        """Gera hash do texto para cache."""
        return hashlib.md5(text.lower().strip().encode()).hexdigest()
    
    def embed(self, text: str) -> EmbeddingResult | None:
        """
        Gera embedding para um texto.
        
        Args:
            text: Texto para gerar embedding
            
        Returns:
            EmbeddingResult ou None se falhar
        """
        if not text or not text.strip():
            return None
        
        # Check cache
        text_hash = self._text_hash(text)
        if text_hash in self._cache:
            self._stats["cache_hits"] += 1
            result = self._cache[text_hash]
            result.cached = True
            return result
        
        self._stats["cache_misses"] += 1
        
        # Chama Ollama
        try:
            import time
            start = time.time()
            
            response = requests.post(
                f"{self.ollama_url}/api/embed",
                json={
                    "model": self.model,
                    "input": text.strip(),
                },
                timeout=self.timeout,
            )
            
            latency_ms = (time.time() - start) * 1000
            self._stats["requests"] += 1
            self._stats["total_latency_ms"] += latency_ms
            
            if response.status_code != 200:
                self._stats["errors"] += 1
                return None
            
            data = response.json()
            embeddings = data.get("embeddings", [])
            
            if not embeddings or not embeddings[0]:
                self._stats["errors"] += 1
                return None
            
            result = EmbeddingResult(
                vector=embeddings[0],
                dimensions=len(embeddings[0]),
                model=self.model,
                latency_ms=latency_ms,
                cached=False,
            )
            
            # Adiciona ao cache
            self._add_to_cache(text_hash, result)
            
            return result
            
        except Exception as e:
            self._stats["errors"] += 1
            return None
    
    def embed_batch(self, texts: list[str]) -> list[EmbeddingResult | None]:
        """
        Gera embeddings para múltiplos textos (mais eficiente).
        
        Args:
            texts: Lista de textos
            
        Returns:
            Lista de EmbeddingResults (None para falhas)
        """
        if not texts:
            return []
        
        # Separa cached de não-cached
        results: list[EmbeddingResult | None] = [None] * len(texts)
        to_embed: list[tuple[int, str]] = []  # (index, text)
        
        for i, text in enumerate(texts):
            if not text or not text.strip():
                continue
            
            text_hash = self._text_hash(text)
            if text_hash in self._cache:
                self._stats["cache_hits"] += 1
                result = self._cache[text_hash]
                result.cached = True
                results[i] = result
            else:
                to_embed.append((i, text.strip()))
                self._stats["cache_misses"] += 1
        
        if not to_embed:
            return results
        
        # Batch request para Ollama
        try:
            import time
            start = time.time()
            
            response = requests.post(
                f"{self.ollama_url}/api/embed",
                json={
                    "model": self.model,
                    "input": [t for _, t in to_embed],
                },
                timeout=self.timeout * len(to_embed),  # Timeout proporcional
            )
            
            latency_ms = (time.time() - start) * 1000
            self._stats["requests"] += 1
            self._stats["total_latency_ms"] += latency_ms
            
            if response.status_code != 200:
                self._stats["errors"] += 1
                return results
            
            data = response.json()
            embeddings = data.get("embeddings", [])
            
            # Mapeia embeddings de volta aos índices originais
            for (idx, text), emb in zip(to_embed, embeddings):
                if emb:
                    result = EmbeddingResult(
                        vector=emb,
                        dimensions=len(emb),
                        model=self.model,
                        latency_ms=latency_ms / len(to_embed),  # Divide pelo batch
                        cached=False,
                    )
                    results[idx] = result
                    self._add_to_cache(self._text_hash(text), result)
            
            return results
            
        except Exception as e:
            self._stats["errors"] += 1
            return results
    
    def _add_to_cache(self, key: str, result: EmbeddingResult) -> None:
        """Adiciona ao cache com eviction LRU simples."""
        if len(self._cache) >= self._cache_size:
            # Remove o primeiro (mais antigo)
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = result
    
    def find_similar(
        self,
        query_embedding: EmbeddingResult,
        candidates: list[tuple[str, list[float]]],  # (id, vector)
        top_k: int = 5,
        min_similarity: float = 0.5,
    ) -> list[tuple[str, float]]:
        """
        Encontra os candidatos mais similares ao query.
        
        Args:
            query_embedding: Embedding da query
            candidates: Lista de (id, vector) para comparar
            top_k: Número máximo de resultados
            min_similarity: Similaridade mínima para incluir
            
        Returns:
            Lista de (id, similarity) ordenada por similaridade
        """
        scores: list[tuple[str, float]] = []
        
        for cand_id, cand_vector in candidates:
            if not cand_vector:
                continue
            
            sim = cosine_similarity(query_embedding.vector, cand_vector)
            if sim >= min_similarity:
                scores.append((cand_id, sim))
        
        # Ordena por similaridade (maior primeiro)
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores[:top_k]
    
    def stats(self) -> dict[str, Any]:
        """Retorna estatísticas do serviço."""
        return {
            **self._stats,
            "cache_size": len(self._cache),
            "cache_max_size": self._cache_size,
            "model": self.model,
            "avg_latency_ms": (
                self._stats["total_latency_ms"] / self._stats["requests"]
                if self._stats["requests"] > 0
                else 0
            ),
        }
    
    def clear_cache(self) -> None:
        """Limpa o cache de embeddings."""
        self._cache.clear()


# Singleton global para reutilização
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Retorna o serviço de embedding singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
