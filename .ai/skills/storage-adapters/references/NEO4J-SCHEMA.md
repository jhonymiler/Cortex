# Neo4j Schema Completo

Schema detalhado para Cortex com queries Cypher, constraints e índices.

## Nodes

### Entity

```cypher
CREATE (e:Entity {
  id: "uuid",
  type: "person",  // person, file, system, product, character
  name: "João Silva",
  identifiers: ["joao@email.com", "João", "joão.silva"],
  attributes: {cargo: "dev", time: "backend"},
  namespace: "tenant_x/projeto_y"
})
```

| Propriedade | Tipo | Obrigatório | Descrição |
|-------------|------|-------------|-----------|
| `id` | String (UUID) | Sim | Identificador único |
| `type` | String | Sim | Tipo de entidade |
| `name` | String | Sim | Nome legível |
| `identifiers` | List[String] | Sim | Aliases (email, username, apelidos) |
| `attributes` | Map | Não | Metadados livres (JSON) |
| `namespace` | String | Sim | Isolamento por tenant |

### Memory

```cypher
CREATE (m:Memory {
  id: "uuid",
  who: ["João Silva", "API"],
  what: "debugou timeout",
  why: "conexão não fechava",
  when: datetime("2026-03-22T14:30:00Z"),
  where: "tenant_x/projeto_y/backend",
  how: "adicionou connection pooling",
  importance: 0.75,
  stability: 7.0,
  retrievability: 1.0,
  access_count: 0,
  consolidated: false,
  embedding: [0.1, 0.2, ...] // 1024 dims
})
```

| Propriedade | Tipo | Obrigatório | Descrição |
|-------------|------|-------------|-----------|
| `id` | String (UUID) | Sim | Identificador único |
| `who` | List[String] | Sim | Participantes (entity names/ids) |
| `what` | String | Sim | Ação/fato principal |
| `why` | String | Não | Causa/motivação |
| `when` | DateTime | Sim | Timestamp |
| `where` | String | Sim | Namespace |
| `how` | String | Não | Resultado/método |
| `importance` | Float (0-1) | Sim | Score de importância |
| `stability` | Float | Sim | Base de decaimento (dias) |
| `retrievability` | Float (0-1) | Sim | R(t) = e^(-t/S) |
| `access_count` | Int | Sim | Vezes acessada |
| `consolidated` | Boolean | Sim | Passou por DreamAgent |
| `embedding` | List[Float] | Não | Vector semântico (1024 dims) |

## Relationships

### RELATES_TO (Entity → Entity)

```cypher
CREATE (e1:Entity)-[:RELATES_TO {
  relation_type: "caused_by",
  strength: 0.8,
  polarity: 0.0
}]->(e2:Entity)
```

| Propriedade | Tipo | Descrição |
|-------------|------|-----------|
| `relation_type` | String | Tipo (caused_by, fixed_by, part_of, etc) |
| `strength` | Float (0-1) | Força da relação |
| `polarity` | Float (-1 a +1) | Valência (negativo/neutro/positivo) |

### INVOLVES (Memory → Entity)

```cypher
CREATE (m:Memory)-[:INVOLVES]->(e:Entity)
```

**Sem propriedades** - apenas conexão entre memória e entidades participantes.

## Constraints (Unicidade)

```cypher
// Entity
CREATE CONSTRAINT entity_id IF NOT EXISTS
FOR (e:Entity) REQUIRE e.id IS UNIQUE;

// Memory
CREATE CONSTRAINT memory_id IF NOT EXISTS
FOR (m:Memory) REQUIRE m.id IS UNIQUE;
```

**Essenciais** - garantem integridade referencial.

## Índices (Performance)

### Básicos (Obrigatórios)

```cypher
// Namespace (filtragem por tenant)
CREATE INDEX entity_namespace IF NOT EXISTS
FOR (e:Entity) ON (e.namespace);

CREATE INDEX memory_namespace IF NOT EXISTS
FOR (m:Memory) ON (m.namespace);

// Timestamp (ordenação temporal)
CREATE INDEX memory_when IF NOT EXISTS
FOR (m:Memory) ON (m.when);

// Importance (ranking)
CREATE INDEX memory_importance IF NOT EXISTS
FOR (m:Memory) ON (m.importance);
```

**Resultado**: Queries <50ms com >100k memórias.

### Índice Vetorial (Embedding)

```cypher
CALL db.index.vector.createNodeIndex(
  'memory_embedding_index',
  'Memory',
  'embedding',
  1024,      // dimensões (qwen3-embedding)
  'cosine'   // métrica de similaridade
)
```

**Resultado**: Similarity search <10ms vs >200ms sem índice.

### Composto (Otimização Avançada)

```cypher
// Namespace + Timestamp (queries temporais por tenant)
CREATE INDEX memory_namespace_when IF NOT EXISTS
FOR (m:Memory) ON (m.namespace, m.when);

// Retrievability (active forgetting)
CREATE INDEX memory_retrievability IF NOT EXISTS
FOR (m:Memory) ON (m.retrievability);
```

## Queries Comuns

### 1. Buscar Memórias por Namespace

```cypher
MATCH (m:Memory)
WHERE m.namespace STARTS WITH $tenant_namespace
RETURN m
ORDER BY m.when DESC
LIMIT 100
```

### 2. Buscar Memórias por Entidade

```cypher
MATCH (m:Memory)-[:INVOLVES]->(e:Entity)
WHERE e.id = $entity_id
RETURN m
ORDER BY m.importance DESC, m.when DESC
LIMIT 50
```

### 3. Similarity Search (Vector)

```cypher
CALL db.index.vector.queryNodes(
  'memory_embedding_index',
  100,                    // top_k
  $query_embedding        // [0.1, 0.2, ...]
) YIELD node, score
WHERE score >= $threshold  // ex: 0.25
RETURN node AS memory, score
```

### 4. Graph Traversal (BFS)

```cypher
MATCH path = (m:Memory)-[:INVOLVES*1..2]-(related:Entity)
WHERE m.id = $memory_id
RETURN DISTINCT related
```

### 5. Active Forgetting (Delete com R<0.1)

```cypher
MATCH (m:Memory)
WHERE m.retrievability < 0.1
  AND NOT EXISTS((m)<-[:HUB]-())  // Protege hubs
DELETE m
```

### 6. PageRank (Hub Detection)

```cypher
CALL gds.pageRank.stream({
  nodeProjection: 'Memory',
  relationshipProjection: 'INVOLVES'
})
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS memory, score
WHERE score > 0.7
RETURN memory.id, score
ORDER BY score DESC
```

## Migração (Futuro)

**Status atual**: JSON é descartável, começar direto com Neo4j.

**Se necessário** (JSON → Neo4j):

```python
# Pseudocódigo
for namespace in json_data:
    for entity in namespace.entities:
        CREATE (:Entity {...})
    for memory in namespace.memories:
        CREATE (:Memory {...})
    for relation in namespace.relations:
        MATCH (e1:Entity {id: relation.from_id})
        MATCH (e2:Entity {id: relation.to_id})
        CREATE (e1)-[:RELATES_TO {...}]->(e2)
```

## Referência de Código

- **Schema init**: `src/cortex/core/storage/neo4j_adapter.py::_initialize_schema()`
- **CRUD**: `src/cortex/core/storage/neo4j_adapter.py`
- **Queries**: `src/cortex/core/graph/memory_graph.py`
