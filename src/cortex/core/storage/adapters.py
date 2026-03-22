"""
Storage Adapters - Interface abstrata para persistência de memória.

O Cortex suporta múltiplos backends de armazenamento:
- JSON (padrão, local)
- Neo4j (produção, grafo nativo)
- SQLite (futuro)

Uso:
    from cortex.core.storage.adapters import create_storage_adapter
    
    # Auto-detecta baseado em CORTEX_STORAGE_BACKEND
    adapter = create_storage_adapter()
    
    # Ou especifica explicitamente
    adapter = create_storage_adapter(backend="neo4j", uri="bolt://localhost:7687")

O MemoryGraph usa o adapter transparentemente:
    graph = MemoryGraph(storage_adapter=adapter)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import os
import json

from cortex.core.primitives import Entity, Episode, Relation
from cortex.core.recall import InvertedIndex
from cortex.utils.logging import get_logger


@dataclass
class StorageStats:
    """Estatísticas do storage."""
    entities_count: int
    episodes_count: int
    relations_count: int
    backend: str
    connected: bool
    last_sync: Optional[datetime] = None


class StorageAdapter(ABC):
    """
    Interface abstrata para adaptadores de armazenamento.
    
    Todos os backends (JSON, Neo4j, SQLite) implementam esta interface.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """Estabelece conexão com o backend."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Fecha conexão com o backend."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Verifica se está conectado."""
        pass
    
    # ==================== ENTITY OPERATIONS ====================
    
    @abstractmethod
    def save_entity(self, entity: Entity) -> bool:
        """Salva ou atualiza uma entidade."""
        pass
    
    @abstractmethod
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Busca entidade por ID."""
        pass
    
    @abstractmethod
    def get_all_entities(self) -> dict[str, Entity]:
        """Retorna todas as entidades."""
        pass
    
    @abstractmethod
    def delete_entity(self, entity_id: str) -> bool:
        """Remove uma entidade."""
        pass
    
    # ==================== EPISODE OPERATIONS ====================
    
    @abstractmethod
    def save_episode(self, episode: Episode) -> bool:
        """Salva ou atualiza um episódio."""
        pass
    
    @abstractmethod
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Busca episódio por ID."""
        pass
    
    @abstractmethod
    def get_all_episodes(self) -> dict[str, Episode]:
        """Retorna todos os episódios."""
        pass
    
    @abstractmethod
    def delete_episode(self, episode_id: str) -> bool:
        """Remove um episódio."""
        pass
    
    # ==================== RELATION OPERATIONS ====================
    
    @abstractmethod
    def save_relation(self, relation: Relation) -> bool:
        """Salva ou atualiza uma relação."""
        pass
    
    @abstractmethod
    def get_relation(self, relation_id: str) -> Optional[Relation]:
        """Busca relação por ID."""
        pass
    
    @abstractmethod
    def get_all_relations(self) -> dict[str, Relation]:
        """Retorna todas as relações."""
        pass
    
    @abstractmethod
    def delete_relation(self, relation_id: str) -> bool:
        """Remove uma relação."""
        pass
    
    @abstractmethod
    def get_relations_by_node(
        self, 
        node_id: str, 
        direction: str = "both"
    ) -> list[Relation]:
        """
        Busca relações por nó.
        
        Args:
            node_id: ID do nó (entidade ou episódio)
            direction: "from", "to" ou "both"
        """
        pass
    
    # ==================== INDEX OPERATIONS ====================
    
    @abstractmethod
    def save_inverted_index(self, index: InvertedIndex) -> bool:
        """Salva o índice invertido."""
        pass
    
    @abstractmethod
    def load_inverted_index(self) -> Optional[InvertedIndex]:
        """Carrega o índice invertido."""
        pass
    
    # ==================== BULK OPERATIONS ====================
    
    @abstractmethod
    def save_all(
        self,
        entities: dict[str, Entity],
        episodes: dict[str, Episode],
        relations: dict[str, Relation],
        inverted_index: InvertedIndex,
    ) -> bool:
        """Salva todos os dados de uma vez (transação)."""
        pass
    
    @abstractmethod
    def load_all(self) -> tuple[
        dict[str, Entity],
        dict[str, Episode],
        dict[str, Relation],
        Optional[InvertedIndex],
    ]:
        """Carrega todos os dados."""
        pass
    
    @abstractmethod
    def clear_all(self) -> bool:
        """Limpa todos os dados."""
        pass
    
    # ==================== STATS ====================
    
    @abstractmethod
    def get_stats(self) -> StorageStats:
        """Retorna estatísticas do storage."""
        pass


class JSONStorageAdapter(StorageAdapter):
    """
    Adaptador de armazenamento em JSON local.
    
    Este é o backend padrão, compatível com versões anteriores.
    Salva em um único arquivo memory_graph.json.
    """
    
    def __init__(self, storage_path: Path | str | None = None):
        self.storage_path = Path(storage_path) if storage_path else None
        self._logger = get_logger("json_storage")
        self._connected = False
        self._last_sync: Optional[datetime] = None
        
        # Cache em memória
        self._entities: dict[str, Entity] = {}
        self._episodes: dict[str, Episode] = {}
        self._relations: dict[str, Relation] = {}
        self._inverted_index: Optional[InvertedIndex] = None
    
    def connect(self) -> bool:
        """Carrega dados do arquivo se existir."""
        if self.storage_path:
            self._load_from_file()
        self._connected = True
        return True
    
    def disconnect(self) -> None:
        """Salva dados antes de desconectar."""
        if self._connected and self.storage_path:
            self._save_to_file()
        self._connected = False
    
    def is_connected(self) -> bool:
        return self._connected
    
    # ==================== ENTITY OPERATIONS ====================
    
    def save_entity(self, entity: Entity) -> bool:
        self._entities[entity.id] = entity
        self._save_to_file()
        return True
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._entities.get(entity_id)
    
    def get_all_entities(self) -> dict[str, Entity]:
        return self._entities.copy()
    
    def delete_entity(self, entity_id: str) -> bool:
        if entity_id in self._entities:
            del self._entities[entity_id]
            self._save_to_file()
            return True
        return False
    
    # ==================== EPISODE OPERATIONS ====================
    
    def save_episode(self, episode: Episode) -> bool:
        self._episodes[episode.id] = episode
        self._save_to_file()
        return True
    
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        return self._episodes.get(episode_id)
    
    def get_all_episodes(self) -> dict[str, Episode]:
        return self._episodes.copy()
    
    def delete_episode(self, episode_id: str) -> bool:
        if episode_id in self._episodes:
            del self._episodes[episode_id]
            self._save_to_file()
            return True
        return False
    
    # ==================== RELATION OPERATIONS ====================
    
    def save_relation(self, relation: Relation) -> bool:
        self._relations[relation.id] = relation
        self._save_to_file()
        return True
    
    def get_relation(self, relation_id: str) -> Optional[Relation]:
        return self._relations.get(relation_id)
    
    def get_all_relations(self) -> dict[str, Relation]:
        return self._relations.copy()
    
    def delete_relation(self, relation_id: str) -> bool:
        if relation_id in self._relations:
            del self._relations[relation_id]
            self._save_to_file()
            return True
        return False
    
    def get_relations_by_node(
        self, 
        node_id: str, 
        direction: str = "both"
    ) -> list[Relation]:
        results = []
        for relation in self._relations.values():
            if direction in ("from", "both") and relation.from_id == node_id:
                results.append(relation)
            elif direction in ("to", "both") and relation.to_id == node_id:
                results.append(relation)
        return results
    
    # ==================== INDEX OPERATIONS ====================
    
    def save_inverted_index(self, index: InvertedIndex) -> bool:
        self._inverted_index = index
        self._save_to_file()
        return True
    
    def load_inverted_index(self) -> Optional[InvertedIndex]:
        return self._inverted_index
    
    # ==================== BULK OPERATIONS ====================
    
    def save_all(
        self,
        entities: dict[str, Entity],
        episodes: dict[str, Episode],
        relations: dict[str, Relation],
        inverted_index: InvertedIndex,
    ) -> bool:
        self._entities = entities
        self._episodes = episodes
        self._relations = relations
        self._inverted_index = inverted_index
        self._save_to_file()
        return True
    
    def load_all(self) -> tuple[
        dict[str, Entity],
        dict[str, Episode],
        dict[str, Relation],
        Optional[InvertedIndex],
    ]:
        self._load_from_file()
        return (
            self._entities,
            self._episodes,
            self._relations,
            self._inverted_index,
        )
    
    def clear_all(self) -> bool:
        self._entities = {}
        self._episodes = {}
        self._relations = {}
        self._inverted_index = None
        self._save_to_file()
        return True
    
    # ==================== STATS ====================
    
    def get_stats(self) -> StorageStats:
        return StorageStats(
            entities_count=len(self._entities),
            episodes_count=len(self._episodes),
            relations_count=len(self._relations),
            backend="json",
            connected=self._connected,
            last_sync=self._last_sync,
        )
    
    # ==================== PRIVATE METHODS ====================
    
    def _save_to_file(self) -> None:
        """Persiste dados em arquivo JSON."""
        if not self.storage_path:
            return
        
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        data = {
            "entities": {k: v.to_dict() for k, v in self._entities.items()},
            "episodes": {k: v.to_dict() for k, v in self._episodes.items()},
            "relations": {k: v.to_dict() for k, v in self._relations.items()},
            "inverted_index": self._inverted_index.to_dict() if self._inverted_index else None,
            "saved_at": datetime.now().isoformat(),
        }
        
        graph_file = self.storage_path / "memory_graph.json"
        with open(graph_file, "w") as f:
            json.dump(data, f, indent=2)
        
        self._last_sync = datetime.now()
    
    def _load_from_file(self) -> None:
        """Carrega dados de arquivo JSON."""
        if not self.storage_path:
            return
        
        graph_file = self.storage_path / "memory_graph.json"
        if not graph_file.exists():
            return
        
        with open(graph_file) as f:
            data = json.load(f)
        
        # Carrega entidades
        self._entities = {}
        for entity_data in data.get("entities", {}).values():
            entity = Entity.from_dict(entity_data)
            self._entities[entity.id] = entity
        
        # Carrega episódios
        self._episodes = {}
        for episode_data in data.get("episodes", {}).values():
            episode = Episode.from_dict(episode_data)
            self._episodes[episode.id] = episode
        
        # Carrega relações
        self._relations = {}
        for relation_data in data.get("relations", {}).values():
            relation = Relation.from_dict(relation_data)
            self._relations[relation.id] = relation
        
        # Carrega índice invertido
        if data.get("inverted_index"):
            self._inverted_index = InvertedIndex.from_dict(data["inverted_index"])
        
        self._last_sync = datetime.now()


# ==================== FACTORY ====================

def create_storage_adapter(
    backend: str | None = None,
    storage_path: Path | str | None = None,
    **kwargs,
) -> StorageAdapter:
    """
    Cria um adaptador de storage baseado no backend especificado.
    
    Args:
        backend: "json" ou "neo4j" (default: env CORTEX_STORAGE_BACKEND ou "json")
        storage_path: Caminho para JSON storage (ignorado para Neo4j)
        **kwargs: Argumentos específicos do backend (uri, user, password para Neo4j)
    
    Returns:
        StorageAdapter configurado
    
    Examples:
        # JSON (padrão)
        adapter = create_storage_adapter(storage_path="./data/my_agent")
        
        # Neo4j
        adapter = create_storage_adapter(
            backend="neo4j",
            uri="bolt://localhost:7687",
            user="neo4j",
            password="secret"
        )
    """
    backend = backend or os.environ.get("CORTEX_STORAGE_BACKEND", "json")
    
    if backend.lower() == "json":
        adapter = JSONStorageAdapter(storage_path=storage_path)
        adapter.connect()
        return adapter
    
    elif backend.lower() == "neo4j":
        # Import dinâmico para não exigir neo4j driver se não usar
        from cortex.core.storage.neo4j_adapter import Neo4jStorageAdapter
        
        uri = kwargs.get("uri") or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        user = kwargs.get("user") or os.environ.get("NEO4J_USER", "neo4j")
        password = kwargs.get("password") or os.environ.get("NEO4J_PASSWORD", "")
        database = kwargs.get("database") or os.environ.get("NEO4J_DATABASE", "neo4j")
        
        adapter = Neo4jStorageAdapter(
            uri=uri,
            user=user,
            password=password,
            database=database,
        )
        adapter.connect()
        return adapter
    
    else:
        raise ValueError(f"Backend não suportado: {backend}. Use 'json' ou 'neo4j'.")
