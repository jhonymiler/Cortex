# Performance Tuning - Neo4j para Cortex

Otimizações avançadas para alcançar recalls <50ms com >100k memórias.

## Configuração de Memória

### `neo4j.conf`

```ini
# Heap (memória JVM)
dbms.memory.heap.initial_size=2G
dbms.memory.heap.max_size=4G

# Page Cache (cache de disco)
dbms.memory.pagecache.size=2G

# Threads
dbms.threads.worker_count=8

# Query timeout
dbms.transaction.timeout=30s
dbms.lock.acquisition.timeout=10s
```

**Regra de ouro**:
- `heap` = 50% RAM disponível (max 31G)
- `pagecache` = 50% do restante
- Exemplo: 16GB RAM → heap=4G, pagecache=6G

## Índices - Checklist

### ✅ Obrigatórios

```cypher
// Unicidade
CREATE CONSTRAINT entity_id FOR (e:Entity) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT memory_id FOR (m:Memory) REQUIRE m.id IS UNIQUE;

// Filtragem
CREATE INDEX entity_namespace FOR (e:Entity) ON (e.namespace);
CREATE INDEX memory_namespace FOR (m:Memory) ON (m.namespace);

// Ordenação/Ranking
CREATE INDEX memory_when FOR (m:Memory) ON (m.when);
CREATE INDEX memory_importance FOR (m:Memory) ON (m.importance);

// Vector search
CALL db.index.vector.createNodeIndex('memory_embedding_index', 'Memory', 'embedding', 1024, 'cosine');
```

### ⚡ Recomendados (Alta Performance)

```cypher
// Compostos
CREATE INDEX memory_namespace_when FOR (m:Memory) ON (m.namespace, m.when);
CREATE INDEX memory_namespace_importance FOR (m:Memory) ON (m.namespace, m.importance);

// Active Forgetting
CREATE INDEX memory_retrievability FOR (m:Memory) ON (m.retrievability);

// Hub Detection
CREATE INDEX memory_access_count FOR (m:Memory) ON (m.access_count);
```

## Query Optimization

### 1. Use EXPLAIN e PROFILE

```cypher
// Planejamento (sem executar)
EXPLAIN
MATCH (m:Memory)
WHERE m.namespace = 'tenant_x/projeto_y'
RETURN m;

// Profiling (executa + métricas)
PROFILE
MATCH (m:Memory)
WHERE m.namespace = 'tenant_x/projeto_y'
RETURN m;
```

**Verificar**:
- `NodeIndexSeek` (bom) vs `NodeByLabelScan` (ruim)
- `db hits` (quanto menor, melhor)
- `rows` (quantos resultados intermediários)

### 2. Filtrar Cedo

```cypher
// ❌ Ruim - filtra depois
MATCH (m:Memory)-[:INVOLVES]->(e:Entity)
WHERE m.namespace = 'tenant_x'
RETURN m, e;

// ✅ Bom - filtra antes
MATCH (m:Memory)
WHERE m.namespace = 'tenant_x'
MATCH (m)-[:INVOLVES]->(e:Entity)
RETURN m, e;
```

### 3. Limitar Resultados

```cypher
// ❌ Ruim - traz tudo, limita no app
MATCH (m:Memory) RETURN m;

// ✅ Bom - limita no banco
MATCH (m:Memory)
RETURN m
LIMIT 100;
```

### 4. Usar Parâmetros

```cypher
// ❌ Ruim - recompila query
MATCH (m:Memory {id: "abc-123"}) RETURN m;

// ✅ Bom - reutiliza plano
MATCH (m:Memory {id: $memory_id}) RETURN m;
```

## Batch Operations

### Import em Lote

```cypher
// ❌ Ruim - N inserts separados
CREATE (:Memory {id: "1", ...});
CREATE (:Memory {id: "2", ...});
// ...

// ✅ Bom - UNWIND batch
UNWIND $memories AS mem
CREATE (m:Memory)
SET m = mem;
```

**Ganho**: 10-50x mais rápido para imports grandes.

### Update em Lote

```cypher
// Atualizar retrievability de múltiplas memórias
UNWIND $updates AS update
MATCH (m:Memory {id: update.id})
SET m.retrievability = update.retrievability;
```

## Warmup Cache

Após restart, cache está frio. Warmup:

```cypher
// Carregar índices na memória
CALL db.index.fulltext.awaitEventuallyConsistentIndexRefresh();

// Pré-carregar memórias recentes
MATCH (m:Memory)
WHERE m.when > datetime() - duration({days: 7})
RETURN count(m);
```

## Monitoring

### Métricas-Chave

```cypher
// Tamanho do banco
CALL apoc.meta.stats() YIELD nodeCount, relCount, labels, relTypes;

// Cache hit rate
CALL dbms.queryJmx('org.neo4j:instance=kernel#0,name=Page cache')
YIELD attributes
RETURN attributes.hitRatio;
```

**Target**: Hit ratio > 95%

### Queries Lentas

```cypher
// Top 10 queries mais lentas
CALL dbms.listQueries()
YIELD query, elapsedTimeMillis, queryId
WHERE elapsedTimeMillis > 1000
RETURN query, elapsedTimeMillis
ORDER BY elapsedTimeMillis DESC
LIMIT 10;

// Matar query lenta
CALL dbms.killQuery($queryId);
```

## Troubleshooting Performance

| Sintoma | Causa Provável | Solução |
|---------|----------------|---------|
| Recalls >500ms | Índices faltando | Criar índices namespace/when/importance |
| `OutOfMemory` | Heap pequeno | Aumentar `dbms.memory.heap.max_size` |
| Hit ratio <80% | Page cache pequeno | Aumentar `dbms.memory.pagecache.size` |
| CPU 100% | Query ineficiente | PROFILE + otimizar (filtrar cedo, limitar) |
| Lock timeout | Transações longas | Reduzir batch size, aumentar timeout |

## Benchmarks Esperados

Com configuração otimizada:

| Operação | Volume | Latência Alvo |
|----------|--------|---------------|
| **Get by ID** | 100k memories | <5ms |
| **Namespace filter** | 100k memories, 1k no namespace | <20ms |
| **Vector search** | 100k memories, top 100 | <10ms |
| **BFS traversal** | 2 hops, 50 nodes | <30ms |
| **Batch insert** | 1k memories | <500ms |
| **Active forgetting** | 100k memories, delete 5k | <2s |

## Referência de Código

- **Connection pool**: `src/cortex/core/storage/neo4j_adapter.py::__init__()`
- **Batch operations**: `src/cortex/core/storage/neo4j_adapter.py::batch_insert()`
- **Query builder**: `src/cortex/core/graph/memory_graph.py`
