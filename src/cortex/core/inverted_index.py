"""
InvertedIndex - Índice invertido para busca eficiente de memórias.

Este módulo implementa um índice invertido simples que mapeia
termos para IDs de episódios, permitindo busca O(1) ao invés de O(n).

Principais otimizações:
- Tokenização e normalização de termos
- Busca por termos com ranking TF-IDF simplificado
- Cache de termos por episódio
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
import math

# Importa tokenização centralizada
from cortex.core.language import tokenize, extract_key_terms


@dataclass
class InvertedIndex:
    """
    Índice invertido para busca eficiente de episódios.
    
    Mapeia: termo -> set[episode_ids]
    
    Complexidade:
    - Indexação: O(termos por episódio)
    - Busca: O(termos na query)
    - vs. O(n) da busca linear
    """
    
    # termo -> set de episode_ids
    _index: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    
    # episode_id -> termos indexados (para remoção)
    _episode_terms: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    
    # Estatísticas
    _total_episodes: int = 0
    _term_document_freq: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    def index_episode(
        self,
        episode_id: str,
        action: str,
        context: str,
        outcome: str,
    ) -> None:
        """
        Indexa um episódio por seus termos.
        
        Extrai termos de action, context e outcome e adiciona ao índice.
        """
        # Verifica se é episódio novo ANTES de adicionar
        is_new = episode_id not in self._episode_terms
        
        # Combina todos os campos
        all_text = f"{action} {context} {outcome}"
        terms = tokenize(all_text)
        
        # Adiciona ao índice
        for term in terms:
            if episode_id not in self._index[term]:
                self._index[term].add(episode_id)
                self._term_document_freq[term] += 1
            self._episode_terms[episode_id].add(term)
        
        # Atualiza contagem se é episódio novo
        if is_new:
            self._total_episodes += 1
    
    def remove_episode(self, episode_id: str) -> None:
        """Remove um episódio do índice."""
        if episode_id not in self._episode_terms:
            return
        
        # Remove de cada termo
        for term in self._episode_terms[episode_id]:
            if term in self._index:
                self._index[term].discard(episode_id)
                self._term_document_freq[term] = max(0, self._term_document_freq[term] - 1)
                
                # Remove termo vazio
                if not self._index[term]:
                    del self._index[term]
        
        # Remove do cache
        del self._episode_terms[episode_id]
        self._total_episodes = max(0, self._total_episodes - 1)
    
    def search(self, query: str, limit: int = 20) -> list[tuple[str, float]]:
        """
        Busca episódios relevantes para uma query.
        
        Retorna lista de (episode_id, score) ordenada por relevância.
        
        Usa TF-IDF simplificado:
        - TF: número de termos da query encontrados
        - IDF: log(N / df) onde df é frequência do termo
        """
        query_terms = tokenize(query)
        
        if not query_terms:
            return []
        
        # Contagem de matches por episódio
        episode_scores: dict[str, float] = defaultdict(float)
        
        for term in query_terms:
            if term not in self._index:
                continue
            
            # IDF simplificado
            df = self._term_document_freq.get(term, 1)
            idf = math.log((self._total_episodes + 1) / (df + 1)) + 1
            
            # Adiciona score para cada episódio que contém o termo
            for episode_id in self._index[term]:
                episode_scores[episode_id] += idf
        
        # Ordena por score
        sorted_episodes = sorted(
            episode_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_episodes[:limit]
    
    def get_candidates(self, query: str, limit: int = 50) -> set[str]:
        """
        Retorna set de IDs candidatos para uma query.
        
        Usado para pré-filtrar antes de calcular similaridade detalhada.
        Mais eficiente que search() quando só precisamos dos IDs.
        """
        query_terms = tokenize(query)
        
        candidates = set()
        for term in query_terms:
            if term in self._index:
                candidates.update(self._index[term])
                if len(candidates) >= limit:
                    break
        
        return candidates
    
    def stats(self) -> dict[str, Any]:
        """Retorna estatísticas do índice."""
        return {
            "total_episodes": self._total_episodes,
            "unique_terms": len(self._index),
            "avg_terms_per_episode": (
                sum(len(terms) for terms in self._episode_terms.values()) / 
                max(1, self._total_episodes)
            ),
        }
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa para persistência."""
        return {
            "index": {k: list(v) for k, v in self._index.items()},
            "episode_terms": {k: list(v) for k, v in self._episode_terms.items()},
            "total_episodes": self._total_episodes,
            "term_document_freq": dict(self._term_document_freq),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InvertedIndex":
        """Deserializa de persistência."""
        idx = cls()
        idx._index = defaultdict(set, {k: set(v) for k, v in data.get("index", {}).items()})
        idx._episode_terms = defaultdict(set, {k: set(v) for k, v in data.get("episode_terms", {}).items()})
        idx._total_episodes = data.get("total_episodes", 0)
        idx._term_document_freq = defaultdict(int, data.get("term_document_freq", {}))
        return idx
    
    def clear(self) -> None:
        """Limpa o índice."""
        self._index.clear()
        self._episode_terms.clear()
        self._total_episodes = 0
        self._term_document_freq.clear()

