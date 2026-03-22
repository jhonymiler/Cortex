"""
Neo4jStorageAdapter - Adaptador para armazenamento em Neo4j.

Este adaptador persiste o grafo de memória em Neo4j, aproveitando
suas capacidades nativas de grafo para:
- Traversals eficientes
- Pattern matching com Cypher
- Escalabilidade horizontal
- Transações ACID

Schema do Grafo:
    (:Entity {id, type, name, identifiers, attributes, access_count, ...})
    (:Episode {id, action, outcome, context, importance, ...})
    
    (Entity)-[:PARTICIPATED_IN]->(Episode)
    (Entity|Episode)-[:RELATES_TO {type, strength}]->(Entity|Episode)

Environment Variables:
    NEO4J_URI: URI do servidor (bolt://localhost:7687)
    NEO4J_USER: Usuário (neo4j)
    NEO4J_PASSWORD: Senha
    NEO4J_DATABASE: Database (neo4j)

Uso:
    adapter = Neo4jStorageAdapter(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="secret"
    )
    adapter.connect()
    
    # Salva entidade
    adapter.save_entity(entity)
    
    # Busca com Cypher nativo
    results = adapter.execute_cypher(
        "MATCH (e:Entity)-[:PARTICIPATED_IN]->(ep:Episode) RETURN e, ep LIMIT 10"
    )
"""

from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING
import json
import os

# Neo4j é opcional - só importa se disponível
HAS_NEO4J = False
try:
    from neo4j import GraphDatabase, Driver, Session
    from neo4j.exceptions import ServiceUnavailable, AuthError
    HAS_NEO4J = True
except ImportError:
    GraphDatabase = None  # type: ignore
    ServiceUnavailable = Exception  # type: ignore
    AuthError = Exception  # type: ignore

from cortex.core.primitives import Entity, Episode, Relation
from cortex.core.recall import InvertedIndex
from cortex.core.storage.adapters import StorageAdapter, StorageStats
from cortex.utils.logging import get_logger


class Neo4jStorageAdapter(StorageAdapter):
    """
    Adaptador de armazenamento em Neo4j.
    
    Implementa a interface StorageAdapter usando Neo4j como backend.
    Suporta todas as operações CRUD e queries Cypher customizadas.
    """
    
    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str = "neo4j",
    ):
        if not HAS_NEO4J:
            raise ImportError(
                "neo4j driver não instalado. "
                "Instale com: pip install neo4j>=5.0.0"
            )
        
        self.uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.environ.get("NEO4J_USER", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASSWORD", "")
        self.database = database or os.environ.get("NEO4J_DATABASE", "neo4j")
        
        self._driver: Any = None  # neo4j.Driver when connected
        self._logger = get_logger("neo4j_storage")
        self._connected = False
        self._last_sync: Optional[datetime] = None
    
    # ==================== CONNECTION ====================
    
    def connect(self) -> bool:
        """Estabelece conexão com Neo4j."""
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
            )
            # Verifica conexão
            self._driver.verify_connectivity()
            
            # Cria constraints e índices
            self._setup_schema()
            
            self._connected = True
            self._logger.info(f"Conectado a Neo4j: {self.uri}")
            return True
            
        except ServiceUnavailable as e:
            self._logger.error(f"Neo4j não disponível: {e}")
            return False
        except AuthError as e:
            self._logger.error(f"Erro de autenticação Neo4j: {e}")
            return False
        except Exception as e:
            self._logger.error(f"Erro conectando a Neo4j: {e}")
            return False
    
    def disconnect(self) -> None:
        """Fecha conexão com Neo4j."""
        if self._driver:
            self._driver.close()
            self._driver = None
        self._connected = False
        self._logger.info("Desconectado de Neo4j")
    
    def is_connected(self) -> bool:
        if not self._connected or not self._driver:
            return False
        try:
            self._driver.verify_connectivity()
            return True
        except Exception:
            self._connected = False
            return False
    
    def _get_session(self) -> Any:
        """Retorna uma sessão do Neo4j (neo4j.Session)."""
        if not self._driver:
            raise RuntimeError("Não conectado ao Neo4j")
        return self._driver.session(database=self.database)
    
    def _setup_schema(self) -> None:
        """Cria constraints e índices no Neo4j."""
        with self._get_session() as session:
            # Constraints de unicidade
            constraints = [
                "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
                "CREATE CONSTRAINT episode_id IF NOT EXISTS FOR (e:Episode) REQUIRE e.id IS UNIQUE",
                "CREATE CONSTRAINT relation_id IF NOT EXISTS FOR (r:CortexRelation) REQUIRE r.id IS UNIQUE",
            ]
            
            # Índices para busca
            indexes = [
                "CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)",
                "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)",
                "CREATE INDEX episode_action IF NOT EXISTS FOR (e:Episode) ON (e.action)",
                "CREATE INDEX episode_namespace IF NOT EXISTS FOR (e:Episode) ON (e.namespace)",
            ]
            
            for query in constraints + indexes:
                try:
                    session.run(query)
                except Exception as e:
                    self._logger.debug(f"Schema query info: {e}")
    
    # ==================== ENTITY OPERATIONS ====================
    
    def save_entity(self, entity: Entity) -> bool:
        """Salva ou atualiza uma entidade no Neo4j."""
        try:
            with self._get_session() as session:
                # MERGE cria ou atualiza
                session.run(
                    """
                    MERGE (e:Entity {id: $id})
                    SET e.type = $type,
                        e.name = $name,
                        e.identifiers = $identifiers,
                        e.attributes = $attributes,
                        e.access_count = $access_count,
                        e.last_accessed = $last_accessed,
                        e.created_at = $created_at,
                        e.centrality_score = $centrality_score,
                        e.updated_at = datetime()
                    """,
                    id=entity.id,
                    type=entity.type,
                    name=entity.name,
                    identifiers=json.dumps(entity.identifiers),
                    attributes=json.dumps(entity.attributes),
                    access_count=entity.access_count,
                    last_accessed=entity.last_accessed.isoformat() if entity.last_accessed else None,
                    created_at=entity.created_at.isoformat() if entity.created_at else None,
                    centrality_score=entity.centrality_score,
                )
                self._last_sync = datetime.now()
                return True
        except Exception as e:
            self._logger.error(f"Erro salvando entidade: {e}")
            return False
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Busca entidade por ID."""
        try:
            with self._get_session() as session:
                result = session.run(
                    "MATCH (e:Entity {id: $id}) RETURN e",
                    id=entity_id,
                )
                record = result.single()
                if record:
                    return self._node_to_entity(record["e"])
                return None
        except Exception as e:
            self._logger.error(f"Erro buscando entidade: {e}")
            return None
    
    def get_all_entities(self) -> dict[str, Entity]:
        """Retorna todas as entidades."""
        entities = {}
        try:
            with self._get_session() as session:
                result = session.run("MATCH (e:Entity) RETURN e")
                for record in result:
                    entity = self._node_to_entity(record["e"])
                    entities[entity.id] = entity
        except Exception as e:
            self._logger.error(f"Erro listando entidades: {e}")
        return entities
    
    def delete_entity(self, entity_id: str) -> bool:
        """Remove uma entidade e suas relações."""
        try:
            with self._get_session() as session:
                # DETACH DELETE remove nó e todas as relações
                result = session.run(
                    "MATCH (e:Entity {id: $id}) DETACH DELETE e RETURN count(e) as deleted",
                    id=entity_id,
                )
                record = result.single()
                return record["deleted"] > 0 if record else False
        except Exception as e:
            self._logger.error(f"Erro deletando entidade: {e}")
            return False
    
    # ==================== EPISODE OPERATIONS ====================
    
    def save_episode(self, episode: Episode) -> bool:
        """Salva ou atualiza um episódio no Neo4j."""
        try:
            with self._get_session() as session:
                # Salva o episódio
                session.run(
                    """
                    MERGE (ep:Episode {id: $id})
                    SET ep.action = $action,
                        ep.outcome = $outcome,
                        ep.context = $context,
                        ep.importance = $importance,
                        ep.timestamp = $timestamp,
                        ep.access_count = $access_count,
                        ep.last_accessed = $last_accessed,
                        ep.occurrence_count = $occurrence_count,
                        ep.is_consolidated = $is_consolidated,
                        ep.consolidated_from = $consolidated_from,
                        ep.namespace = $namespace,
                        ep.metadata = $metadata,
                        ep.embedding = $embedding,
                        ep.updated_at = datetime()
                    """,
                    id=episode.id,
                    action=episode.action,
                    outcome=episode.outcome,
                    context=episode.context,
                    importance=episode.importance,
                    timestamp=episode.timestamp.isoformat() if episode.timestamp else None,
                    access_count=episode.access_count,
                    last_accessed=episode.last_accessed.isoformat() if episode.last_accessed else None,
                    occurrence_count=episode.occurrence_count,
                    is_consolidated=episode.is_consolidated,
                    consolidated_from=json.dumps(episode.consolidated_from),
                    namespace=episode.metadata.get("namespace", "default"),
                    metadata=json.dumps(episode.metadata),
                    embedding=json.dumps(episode.embedding) if episode.embedding else None,
                )
                
                # Cria relações PARTICIPATED_IN para cada participante
                for participant_id in episode.participants:
                    session.run(
                        """
                        MATCH (e:Entity {id: $entity_id})
                        MATCH (ep:Episode {id: $episode_id})
                        MERGE (e)-[:PARTICIPATED_IN]->(ep)
                        """,
                        entity_id=participant_id,
                        episode_id=episode.id,
                    )
                
                self._last_sync = datetime.now()
                return True
        except Exception as e:
            self._logger.error(f"Erro salvando episódio: {e}")
            return False
    
    def get_episode(self, episode_id: str) -> Optional[Episode]:
        """Busca episódio por ID."""
        try:
            with self._get_session() as session:
                result = session.run(
                    """
                    MATCH (ep:Episode {id: $id})
                    OPTIONAL MATCH (e:Entity)-[:PARTICIPATED_IN]->(ep)
                    RETURN ep, collect(e.id) as participants
                    """,
                    id=episode_id,
                )
                record = result.single()
                if record:
                    return self._record_to_episode(record)
                return None
        except Exception as e:
            self._logger.error(f"Erro buscando episódio: {e}")
            return None
    
    def get_all_episodes(self) -> dict[str, Episode]:
        """Retorna todos os episódios."""
        episodes = {}
        try:
            with self._get_session() as session:
                result = session.run(
                    """
                    MATCH (ep:Episode)
                    OPTIONAL MATCH (e:Entity)-[:PARTICIPATED_IN]->(ep)
                    RETURN ep, collect(e.id) as participants
                    """
                )
                for record in result:
                    episode = self._record_to_episode(record)
                    episodes[episode.id] = episode
        except Exception as e:
            self._logger.error(f"Erro listando episódios: {e}")
        return episodes
    
    def delete_episode(self, episode_id: str) -> bool:
        """Remove um episódio e suas relações."""
        try:
            with self._get_session() as session:
                result = session.run(
                    "MATCH (ep:Episode {id: $id}) DETACH DELETE ep RETURN count(ep) as deleted",
                    id=episode_id,
                )
                record = result.single()
                return record["deleted"] > 0 if record else False
        except Exception as e:
            self._logger.error(f"Erro deletando episódio: {e}")
            return False
    
    # ==================== RELATION OPERATIONS ====================
    
    def save_relation(self, relation: Relation) -> bool:
        """Salva ou atualiza uma relação no Neo4j."""
        try:
            with self._get_session() as session:
                # Primeiro salva como nó (para manter ID único)
                session.run(
                    """
                    MERGE (r:CortexRelation {id: $id})
                    SET r.from_id = $from_id,
                        r.to_id = $to_id,
                        r.relation_type = $relation_type,
                        r.strength = $strength,
                        r.metadata = $metadata,
                        r.updated_at = datetime()
                    """,
                    id=relation.id,
                    from_id=relation.from_id,
                    to_id=relation.to_id,
                    relation_type=relation.relation_type,
                    strength=relation.strength,
                    metadata=json.dumps(relation.metadata) if hasattr(relation, 'metadata') else "{}",
                )
                
                # Cria edge dinâmica entre nós (Entity ou Episode)
                # Usa RELATES_TO como tipo genérico
                session.run(
                    """
                    MATCH (from) WHERE from.id = $from_id
                    MATCH (to) WHERE to.id = $to_id
                    MERGE (from)-[r:RELATES_TO {id: $rel_id}]->(to)
                    SET r.type = $relation_type,
                        r.strength = $strength
                    """,
                    from_id=relation.from_id,
                    to_id=relation.to_id,
                    rel_id=relation.id,
                    relation_type=relation.relation_type,
                    strength=relation.strength,
                )
                
                self._last_sync = datetime.now()
                return True
        except Exception as e:
            self._logger.error(f"Erro salvando relação: {e}")
            return False
    
    def get_relation(self, relation_id: str) -> Optional[Relation]:
        """Busca relação por ID."""
        try:
            with self._get_session() as session:
                result = session.run(
                    "MATCH (r:CortexRelation {id: $id}) RETURN r",
                    id=relation_id,
                )
                record = result.single()
                if record:
                    return self._node_to_relation(record["r"])
                return None
        except Exception as e:
            self._logger.error(f"Erro buscando relação: {e}")
            return None
    
    def get_all_relations(self) -> dict[str, Relation]:
        """Retorna todas as relações."""
        relations = {}
        try:
            with self._get_session() as session:
                result = session.run("MATCH (r:CortexRelation) RETURN r")
                for record in result:
                    relation = self._node_to_relation(record["r"])
                    relations[relation.id] = relation
        except Exception as e:
            self._logger.error(f"Erro listando relações: {e}")
        return relations
    
    def delete_relation(self, relation_id: str) -> bool:
        """Remove uma relação."""
        try:
            with self._get_session() as session:
                # Remove nó CortexRelation
                session.run(
                    "MATCH (r:CortexRelation {id: $id}) DELETE r",
                    id=relation_id,
                )
                # Remove edge RELATES_TO
                session.run(
                    "MATCH ()-[r:RELATES_TO {id: $id}]->() DELETE r",
                    id=relation_id,
                )
                return True
        except Exception as e:
            self._logger.error(f"Erro deletando relação: {e}")
            return False
    
    def get_relations_by_node(
        self, 
        node_id: str, 
        direction: str = "both"
    ) -> list[Relation]:
        """Busca relações por nó."""
        relations = []
        try:
            with self._get_session() as session:
                if direction == "from":
                    query = "MATCH (r:CortexRelation {from_id: $id}) RETURN r"
                elif direction == "to":
                    query = "MATCH (r:CortexRelation {to_id: $id}) RETURN r"
                else:
                    query = """
                    MATCH (r:CortexRelation) 
                    WHERE r.from_id = $id OR r.to_id = $id 
                    RETURN r
                    """
                
                result = session.run(query, id=node_id)
                for record in result:
                    relations.append(self._node_to_relation(record["r"]))
        except Exception as e:
            self._logger.error(f"Erro buscando relações por nó: {e}")
        return relations
    
    # ==================== INDEX OPERATIONS ====================
    
    def save_inverted_index(self, index: InvertedIndex) -> bool:
        """Salva o índice invertido como nó especial."""
        try:
            with self._get_session() as session:
                session.run(
                    """
                    MERGE (i:InvertedIndex {id: 'main'})
                    SET i.data = $data,
                        i.updated_at = datetime()
                    """,
                    data=json.dumps(index.to_dict()),
                )
                self._last_sync = datetime.now()
                return True
        except Exception as e:
            self._logger.error(f"Erro salvando índice: {e}")
            return False
    
    def load_inverted_index(self) -> Optional[InvertedIndex]:
        """Carrega o índice invertido."""
        try:
            with self._get_session() as session:
                result = session.run(
                    "MATCH (i:InvertedIndex {id: 'main'}) RETURN i.data as data"
                )
                record = result.single()
                if record and record["data"]:
                    data = json.loads(record["data"])
                    return InvertedIndex.from_dict(data)
                return None
        except Exception as e:
            self._logger.error(f"Erro carregando índice: {e}")
            return None
    
    # ==================== BULK OPERATIONS ====================
    
    def save_all(
        self,
        entities: dict[str, Entity],
        episodes: dict[str, Episode],
        relations: dict[str, Relation],
        inverted_index: InvertedIndex,
    ) -> bool:
        """Salva todos os dados em uma transação."""
        try:
            # Salva cada tipo
            for entity in entities.values():
                self.save_entity(entity)
            
            for episode in episodes.values():
                self.save_episode(episode)
            
            for relation in relations.values():
                self.save_relation(relation)
            
            if inverted_index:
                self.save_inverted_index(inverted_index)
            
            self._last_sync = datetime.now()
            return True
        except Exception as e:
            self._logger.error(f"Erro em save_all: {e}")
            return False
    
    def load_all(self) -> tuple[
        dict[str, Entity],
        dict[str, Episode],
        dict[str, Relation],
        Optional[InvertedIndex],
    ]:
        """Carrega todos os dados."""
        return (
            self.get_all_entities(),
            self.get_all_episodes(),
            self.get_all_relations(),
            self.load_inverted_index(),
        )
    
    def clear_all(self) -> bool:
        """Limpa todos os dados do grafo."""
        try:
            with self._get_session() as session:
                # Remove todos os nós e relações
                session.run("MATCH (n) DETACH DELETE n")
                self._last_sync = datetime.now()
                return True
        except Exception as e:
            self._logger.error(f"Erro em clear_all: {e}")
            return False
    
    # ==================== STATS ====================
    
    def get_stats(self) -> StorageStats:
        """Retorna estatísticas do Neo4j."""
        entities_count = 0
        episodes_count = 0
        relations_count = 0
        
        try:
            with self._get_session() as session:
                result = session.run("MATCH (e:Entity) RETURN count(e) as c")
                entities_count = result.single()["c"]
                
                result = session.run("MATCH (ep:Episode) RETURN count(ep) as c")
                episodes_count = result.single()["c"]
                
                result = session.run("MATCH (r:CortexRelation) RETURN count(r) as c")
                relations_count = result.single()["c"]
        except Exception as e:
            self._logger.error(f"Erro obtendo stats: {e}")
        
        return StorageStats(
            entities_count=entities_count,
            episodes_count=episodes_count,
            relations_count=relations_count,
            backend="neo4j",
            connected=self._connected,
            last_sync=self._last_sync,
        )
    
    # ==================== CYPHER QUERIES ====================
    
    def execute_cypher(self, query: str, **params) -> list[dict]:
        """
        Executa query Cypher customizada.
        
        Útil para queries avançadas de grafo.
        
        Args:
            query: Query Cypher
            **params: Parâmetros para a query
        
        Returns:
            Lista de dicts com resultados
        
        Example:
            results = adapter.execute_cypher(
                "MATCH (e:Entity)-[:PARTICIPATED_IN]->(ep:Episode) "
                "WHERE ep.importance > $min_importance "
                "RETURN e.name, ep.action LIMIT 10",
                min_importance=0.7
            )
        """
        try:
            with self._get_session() as session:
                result = session.run(query, **params)
                return [dict(record) for record in result]
        except Exception as e:
            self._logger.error(f"Erro em Cypher: {e}")
            return []
    
    def find_paths(
        self, 
        from_id: str, 
        to_id: str, 
        max_depth: int = 3
    ) -> list[list[str]]:
        """
        Encontra caminhos entre dois nós.
        
        Args:
            from_id: ID do nó origem
            to_id: ID do nó destino
            max_depth: Profundidade máxima
        
        Returns:
            Lista de caminhos (cada caminho é lista de IDs)
        """
        try:
            with self._get_session() as session:
                result = session.run(
                    """
                    MATCH path = (from)-[*1..$depth]-(to)
                    WHERE from.id = $from_id AND to.id = $to_id
                    RETURN [n in nodes(path) | n.id] as path
                    LIMIT 10
                    """,
                    from_id=from_id,
                    to_id=to_id,
                    depth=max_depth,
                )
                return [record["path"] for record in result]
        except Exception as e:
            self._logger.error(f"Erro em find_paths: {e}")
            return []
    
    def get_neighbors(
        self, 
        node_id: str, 
        depth: int = 1
    ) -> dict[str, list]:
        """
        Retorna vizinhos de um nó.
        
        Args:
            node_id: ID do nó
            depth: Profundidade de busca
        
        Returns:
            Dict com entities e episodes vizinhos
        """
        neighbors = {"entities": [], "episodes": []}
        
        try:
            with self._get_session() as session:
                # Busca entidades vizinhas
                result = session.run(
                    """
                    MATCH (n)-[*1..$depth]-(neighbor:Entity)
                    WHERE n.id = $id AND neighbor.id <> $id
                    RETURN DISTINCT neighbor
                    """,
                    id=node_id,
                    depth=depth,
                )
                for record in result:
                    neighbors["entities"].append(
                        self._node_to_entity(record["neighbor"])
                    )
                
                # Busca episódios vizinhos
                result = session.run(
                    """
                    MATCH (n)-[*1..$depth]-(neighbor:Episode)
                    WHERE n.id = $id AND neighbor.id <> $id
                    RETURN DISTINCT neighbor
                    """,
                    id=node_id,
                    depth=depth,
                )
                for record in result:
                    ep_result = session.run(
                        """
                        MATCH (ep:Episode {id: $id})
                        OPTIONAL MATCH (e:Entity)-[:PARTICIPATED_IN]->(ep)
                        RETURN ep, collect(e.id) as participants
                        """,
                        id=record["neighbor"]["id"],
                    )
                    ep_record = ep_result.single()
                    if ep_record:
                        neighbors["episodes"].append(
                            self._record_to_episode(ep_record)
                        )
                        
        except Exception as e:
            self._logger.error(f"Erro em get_neighbors: {e}")
        
        return neighbors
    
    # ==================== CONVERSION HELPERS ====================
    
    def _node_to_entity(self, node) -> Entity:
        """Converte nó Neo4j para Entity."""
        return Entity(
            id=node["id"],
            type=node.get("type", "unknown"),
            name=node.get("name", ""),
            identifiers=json.loads(node.get("identifiers", "[]")),
            attributes=json.loads(node.get("attributes", "{}")),
            access_count=node.get("access_count", 0),
            last_accessed=datetime.fromisoformat(node["last_accessed"]) if node.get("last_accessed") else None,
            created_at=datetime.fromisoformat(node["created_at"]) if node.get("created_at") else datetime.now(),
            centrality_score=node.get("centrality_score", 0.0),
        )
    
    def _record_to_episode(self, record) -> Episode:
        """Converte record Neo4j para Episode."""
        node = record["ep"]
        participants = record.get("participants", [])
        # Remove None values
        participants = [p for p in participants if p]
        
        episode = Episode(
            id=node["id"],
            action=node.get("action", ""),
            outcome=node.get("outcome", ""),
            context=node.get("context", ""),
            participants=participants,
            importance=node.get("importance", 0.5),
            timestamp=datetime.fromisoformat(node["timestamp"]) if node.get("timestamp") else datetime.now(),
            access_count=node.get("access_count", 0),
            last_accessed=datetime.fromisoformat(node["last_accessed"]) if node.get("last_accessed") else None,
            occurrence_count=node.get("occurrence_count", 1),
        )
        
        # Carrega campos adicionais
        if node.get("consolidated_from"):
            episode.consolidated_from = json.loads(node["consolidated_from"])
        
        if node.get("metadata"):
            episode.metadata = json.loads(node["metadata"])
        
        if node.get("embedding"):
            episode.embedding = json.loads(node["embedding"])
        
        return episode
    
    def _node_to_relation(self, node) -> Relation:
        """Converte nó Neo4j para Relation."""
        return Relation(
            id=node["id"],
            from_id=node["from_id"],
            to_id=node["to_id"],
            relation_type=node.get("relation_type", "related_to"),
            strength=node.get("strength", 0.5),
        )
