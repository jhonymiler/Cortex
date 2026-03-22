# 🗄️ Storage Adapters

> **Backends de persistência plugáveis para o Cortex**

*Documento Canônico — fonte única de verdade sobre storage adapters.*

---

## O Que São Storage Adapters?

Storage adapters são implementações plugáveis que definem como o Cortex persiste e recupera dados. O sistema suporta múltiplos backends:

| Backend | Use Case | Persistência |
|---------|----------|--------------|
| **JSON** | Desenvolvimento, testes | Arquivo local |
| **Neo4j** | Produção, escala | Banco de grafos |

```
┌─────────────────────────────────────────────────────────────┐
│                    MemoryGraph                              │
│                 (Lógica de negócio)                         │
├─────────────────────────────────────────────────────────────┤
│                  StorageAdapter (Interface)                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌─────────────────┐           ┌─────────────────┐        │
│   │ JSONStorage     │           │ Neo4jStorage    │        │
│   │ Adapter         │           │ Adapter         │        │
│   └────────┬────────┘           └────────┬────────┘        │
│            │                             │                  │
│            ▼                             ▼                  │
│   ┌─────────────────┐           ┌─────────────────┐        │
│   │ memory_graph    │           │   Neo4j DB      │        │
│   │     .json       │           │   (Bolt)        │        │
│   └─────────────────┘           └─────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

---

## Configuração

### Via Variável de Ambiente

```bash
# JSON (padrão)
export CORTEX_STORAGE_BACKEND=json
export CORTEX_DATA_DIR=./data

# Neo4j
export CORTEX_STORAGE_BACKEND=neo4j
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=sua_senha
```

### Via Código

```python
from cortex.core.graph import MemoryGraph
from cortex.core.storage import create_storage_adapter, JSONStorageAdapter

# Auto-detecta baseado em CORTEX_STORAGE_BACKEND
graph = MemoryGraph(storage_path="./data")

# Ou fornece adapter explicitamente
adapter = JSONStorageAdapter(storage_path="./data")
graph = MemoryGraph(storage_adapter=adapter)

# Para Neo4j
from cortex.core.storage import get_neo4j_adapter
Neo4jStorageAdapter = get_neo4j_adapter()
adapter = Neo4jStorageAdapter(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="senha"
)
graph = MemoryGraph(storage_adapter=adapter)
```

---

## StorageAdapter Interface

A interface `StorageAdapter` define todos os métodos que um backend deve implementar:

```python
from abc import ABC, abstractmethod

class StorageAdapter(ABC):
    """Interface abstrata para backends de persistência."""
    
    # Conexão
    @abstractmethod
    def connect(self) -> bool: ...
    
    @abstractmethod
    def disconnect(self) -> None: ...
    
    @abstractmethod
    def is_connected(self) -> bool: ...
    
    # Entity CRUD
    @abstractmethod
    def save_entity(self, entity: Entity) -> str: ...
    
    @abstractmethod
    def get_entity(self, entity_id: str) -> Entity | None: ...
    
    @abstractmethod
    def delete_entity(self, entity_id: str) -> bool: ...
    
    @abstractmethod
    def list_entities(self, **filters) -> list[Entity]: ...
    
    # Episode CRUD
    @abstractmethod
    def save_episode(self, episode: Episode) -> str: ...
    
    @abstractmethod
    def get_episode(self, episode_id: str) -> Episode | None: ...
    
    @abstractmethod
    def delete_episode(self, episode_id: str) -> bool: ...
    
    @abstractmethod
    def list_episodes(self, **filters) -> list[Episode]: ...
    
    # Relation CRUD
    @abstractmethod
    def save_relation(self, relation: Relation) -> str: ...
    
    @abstractmethod
    def get_relation(self, relation_id: str) -> Relation | None: ...
    
    @abstractmethod
    def delete_relation(self, relation_id: str) -> bool: ...
    
    @abstractmethod
    def list_relations(self, **filters) -> list[Relation]: ...
    
    # Index Operations
    @abstractmethod
    def save_inverted_index(self, index: InvertedIndex) -> None: ...
    
    @abstractmethod
    def load_inverted_index(self) -> InvertedIndex | None: ...
    
    # Bulk Operations
    @abstractmethod
    def save_all(self, entities, episodes, relations, inverted_index) -> None: ...
    
    @abstractmethod
    def load_all(self) -> dict[str, Any]: ...
    
    @abstractmethod
    def clear_all(self) -> None: ...
    
    # Stats
    @abstractmethod
    def get_stats(self) -> StorageStats: ...
```

---

## JSONStorageAdapter

Backend padrão que salva dados em arquivo JSON.

### Características

- ✅ Zero dependências externas
- ✅ Backward compatible com dados existentes
- ✅ Ideal para desenvolvimento e testes
- ❌ Não escala para milhões de memórias
- ❌ Load completo em memória

### Estrutura do Arquivo

```json
{
  "entities": {
    "uuid-1": { "id": "uuid-1", "type": "person", "name": "João", ... },
    "uuid-2": { "id": "uuid-2", "type": "concept", "name": "login", ... }
  },
  "episodes": {
    "uuid-3": { "id": "uuid-3", "action": "resolveu_bug", ... }
  },
  "relations": {
    "uuid-4": { "from_id": "uuid-1", "to_id": "uuid-3", ... }
  },
  "inverted_index": {
    "tokens": { "login": ["uuid-2"], "joao": ["uuid-1"] },
    ...
  },
  "saved_at": "2026-01-15T10:30:00"
}
```

---

## Neo4jStorageAdapter

Backend de produção usando Neo4j como banco de grafos.

### Características

- ✅ Escala para milhões de nós e relacionamentos
- ✅ Queries Cypher nativas para travessias complexas
- ✅ Transações ACID
- ✅ Índices e constraints nativos
- ❌ Requer Neo4j (container ou serviço)
- ❌ Dependência opcional (`pip install neo4j`)

### Schema Neo4j

```cypher
// Constraints (unicidade)
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE
CREATE CONSTRAINT episode_id IF NOT EXISTS FOR (e:Episode) REQUIRE e.id IS UNIQUE
CREATE CONSTRAINT relation_id IF NOT EXISTS FOR (r:CortexRelation) REQUIRE r.id IS UNIQUE

// Índices (busca rápida)
CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)
CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)
CREATE INDEX episode_action IF NOT EXISTS FOR (e:Episode) ON (e.action)
CREATE INDEX episode_namespace IF NOT EXISTS FOR (e:Episode) ON (e.namespace)
```

### Modelo de Dados

```
(:Entity {id, type, name, identifiers[], attributes})
    │
    │ [:PARTICIPATED_IN]
    ▼
(:Episode {id, action, outcome, context, importance, ...})
    │
    │ [:RELATES_TO {strength, type}]
    ▼
(:Entity) ou (:Episode)
```

### Métodos Avançados

```python
# Executa Cypher customizado
adapter.execute_cypher("MATCH (e:Entity) RETURN count(e)")

# Encontra caminhos entre nós
paths = adapter.find_paths(
    start_id="entity-1",
    end_id="entity-2",
    max_depth=3
)

# Busca vizinhos de um nó
neighbors = adapter.get_neighbors(
    node_id="entity-1",
    depth=2
)
```

---

## Docker Setup

### docker-compose.yml

```yaml
services:
  neo4j:
    image: neo4j:5.15-community
    ports:
      - "7474:7474"  # Browser
      - "7687:7687"  # Bolt
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_PLUGINS=["apoc"]
    volumes:
      - neo4j_data:/data

  cortex-api:
    build:
      dockerfile: docker/Dockerfile.api
    environment:
      - CORTEX_STORAGE_BACKEND=neo4j
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
    depends_on:
      - neo4j

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf
```

### Iniciar Ambiente

```bash
# Definir senha do Neo4j
export NEO4J_PASSWORD=cortex_memory_2026

# Subir todos os serviços
docker compose up -d

# Verificar logs
docker compose logs -f cortex-api

# Acessar Neo4j Browser
open http://localhost:7474
```

---

## Implementando Novo Adapter

Para criar um novo backend (ex: PostgreSQL, DynamoDB):

```python
from cortex.core.storage import StorageAdapter, StorageStats

class PostgresStorageAdapter(StorageAdapter):
    """Adapter para PostgreSQL."""
    
    def __init__(self, connection_string: str):
        self._conn_str = connection_string
        self._conn = None
    
    def connect(self) -> bool:
        import psycopg2
        self._conn = psycopg2.connect(self._conn_str)
        return True
    
    def save_entity(self, entity: Entity) -> str:
        # Implementar INSERT/UPDATE
        ...
    
    # ... implementar todos os métodos abstratos
```

---

## 🧭 Próximos Passos

> **🚀 Quer usar Neo4j agora?**
> 
> ```bash
> # 1. Instalar dependência
> pip install neo4j>=5.0.0
> 
> # 2. Subir Neo4j
> docker compose up -d neo4j
> 
> # 3. Configurar ambiente
> export CORTEX_STORAGE_BACKEND=neo4j
> export NEO4J_URI=bolt://localhost:7687
> export NEO4J_PASSWORD=sua_senha
> 
> # 4. Rodar API
> cortex-api
> ```

> **🔬 Quer migrar dados de JSON para Neo4j?**
> 
> ```python
> # Carrega do JSON
> json_adapter = JSONStorageAdapter("./data/old")
> json_adapter.connect()
> data = json_adapter.load_all()
> 
> # Salva no Neo4j
> neo4j_adapter = Neo4jStorageAdapter(uri="bolt://localhost:7687")
> neo4j_adapter.connect()
> neo4j_adapter.save_all(**data)
> ```

---

*Documento canônico de storage adapters — Última atualização: Janeiro 2026*
