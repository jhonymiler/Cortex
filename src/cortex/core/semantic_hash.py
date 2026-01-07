"""
Semantic Hash - Busca semântica via Feature Hashing.

Esta abordagem é INDEPENDENTE DE IDIOMA porque:
1. Não usa stopwords ou regras linguísticas
2. Usa hash determinístico de palavras
3. Similaridade por cosseno entre vetores

Funciona especialmente bem com W5H porque o LLM já
abstraiu o significado para termos normalizados.

Baseado em: Locality Sensitive Hashing (LSH) / Feature Hashing
"""

import math
from dataclasses import dataclass, field
from typing import Any
import re


# Dimensão do vetor hash (quanto maior, menos colisões)
VECTOR_DIM = 128


def _hash_word(word: str) -> int:
    """
    Hash determinístico de uma palavra.
    
    Usa algoritmo djb2 (Dan Bernstein) - simples e eficiente.
    """
    h = 5381
    for char in word:
        h = ((h << 5) + h) + ord(char)
        h &= 0xFFFFFFFF  # Mantém 32 bits
    return h


def text_to_vector(text: str, dim: int = VECTOR_DIM) -> list[float]:
    """
    Converte texto em vetor hash.
    
    Cada palavra é mapeada para um índice via hash,
    e o vetor é incrementado nesse índice.
    
    Args:
        text: Texto para vetorizar
        dim: Dimensão do vetor (default: 128)
    
    Returns:
        Vetor normalizado de floats
    
    Example:
        >>> text_to_vector("cliente solicitou reembolso")
        [0.0, 0.577, 0.0, 0.577, ..., 0.577, 0.0]
    """
    vector = [0.0] * dim
    
    if not text:
        return vector
    
    # Extrai palavras (qualquer sequência alfanumérica)
    words = re.findall(r'\w+', text.lower())
    
    # Incrementa o vetor para cada palavra
    for word in words:
        if len(word) >= 2:  # Ignora caracteres isolados
            index = _hash_word(word) % dim
            vector[index] += 1.0
    
    # Normaliza (L2 norm) para similaridade de cosseno
    magnitude = math.sqrt(sum(v * v for v in vector))
    if magnitude > 0:
        vector = [v / magnitude for v in vector]
    
    return vector


def w5h_to_vector(w5h: dict[str, str], dim: int = VECTOR_DIM) -> list[float]:
    """
    Converte W5H estruturado em vetor hash.
    
    Concatena todos os campos W5H e vetoriza.
    
    Args:
        w5h: Dicionário com campos who, what, why, how, when, where
        dim: Dimensão do vetor
    
    Returns:
        Vetor normalizado
    
    Example:
        >>> w5h_to_vector({"who": "Carlos", "what": "solicitou_reembolso"})
        [0.0, 0.5, 0.0, 0.5, ...]
    """
    # Concatena campos relevantes
    parts = []
    for key in ["who", "what", "why", "how", "when", "where"]:
        value = w5h.get(key, "")
        if value:
            # Substitui _ por espaço para tratar como palavras separadas
            parts.append(value.replace("_", " "))
    
    text = " ".join(parts)
    return text_to_vector(text, dim)


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Calcula similaridade de cosseno entre dois vetores.
    
    Retorna valor entre -1 e 1:
    - 1.0 = idênticos
    - 0.0 = ortogonais (sem relação)
    - -1.0 = opostos
    
    Como os vetores são normalizados, é só o produto escalar.
    """
    if len(vec_a) != len(vec_b):
        return 0.0
    
    return sum(a * b for a, b in zip(vec_a, vec_b))


@dataclass
class SemanticIndex:
    """
    Índice semântico baseado em hash vectors.
    
    Armazena vetores e permite busca por similaridade
    sem dependência de idioma ou stopwords.
    
    Complexidade:
    - Indexação: O(palavras no texto)
    - Busca: O(n) onde n = número de itens indexados
    
    Para escala maior, usar ANN (Approximate Nearest Neighbors).
    """
    
    dim: int = VECTOR_DIM
    
    # ID -> vetor
    _vectors: dict[str, list[float]] = field(default_factory=dict)
    
    # ID -> dados originais (para retorno)
    _data: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    def index(self, id: str, text: str = "", w5h: dict | None = None, data: dict | None = None) -> None:
        """
        Indexa um item.
        
        Args:
            id: Identificador único
            text: Texto para vetorizar (opcional se w5h fornecido)
            w5h: Dicionário W5H (priorizado sobre text)
            data: Dados adicionais para retornar na busca
        """
        if w5h:
            vector = w5h_to_vector(w5h, self.dim)
        else:
            vector = text_to_vector(text, self.dim)
        
        self._vectors[id] = vector
        self._data[id] = data or {}
    
    def remove(self, id: str) -> None:
        """Remove um item do índice."""
        self._vectors.pop(id, None)
        self._data.pop(id, None)
    
    def search(
        self, 
        query: str = "", 
        w5h: dict | None = None, 
        limit: int = 5,
        min_similarity: float = 0.1,
    ) -> list[tuple[str, float, dict]]:
        """
        Busca itens similares à query.
        
        Args:
            query: Texto de busca (opcional se w5h fornecido)
            w5h: W5H de busca (priorizado sobre query)
            limit: Máximo de resultados
            min_similarity: Similaridade mínima (0.0 a 1.0)
        
        Returns:
            Lista de (id, similaridade, dados) ordenada por similaridade
        """
        if w5h:
            query_vector = w5h_to_vector(w5h, self.dim)
        else:
            query_vector = text_to_vector(query, self.dim)
        
        # Calcula similaridade com todos os itens
        results = []
        for id, vector in self._vectors.items():
            sim = cosine_similarity(query_vector, vector)
            if sim >= min_similarity:
                results.append((id, sim, self._data.get(id, {})))
        
        # Ordena por similaridade descendente
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:limit]
    
    def clear(self) -> None:
        """Limpa o índice."""
        self._vectors.clear()
        self._data.clear()
    
    def __len__(self) -> int:
        return len(self._vectors)
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa para persistência."""
        return {
            "dim": self.dim,
            "vectors": self._vectors,
            "data": self._data,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SemanticIndex":
        """Deserializa."""
        idx = cls(dim=data.get("dim", VECTOR_DIM))
        idx._vectors = data.get("vectors", {})
        idx._data = data.get("data", {})
        return idx


# =============================================================================
# Funções de conveniência
# =============================================================================

def semantic_similarity(text_a: str, text_b: str) -> float:
    """
    Calcula similaridade semântica entre dois textos.
    
    Retorna valor entre 0 e 1.
    """
    vec_a = text_to_vector(text_a)
    vec_b = text_to_vector(text_b)
    return max(0.0, cosine_similarity(vec_a, vec_b))


def w5h_similarity(w5h_a: dict, w5h_b: dict) -> float:
    """
    Calcula similaridade entre dois W5H.
    """
    vec_a = w5h_to_vector(w5h_a)
    vec_b = w5h_to_vector(w5h_b)
    return max(0.0, cosine_similarity(vec_a, vec_b))

