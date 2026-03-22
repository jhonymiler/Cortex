---
name: storage-adapters
description: Complete guide for storage backends (JSON vs Neo4j), adapter pattern implementation,
  configuration, migrations, performance tuning, and troubleshooting.
  Use when choosing storage backend, configuring Neo4j, implementing custom adapters,
  debugging persistence issues, or understanding CRUD operations.
  Mention when working with StorageAdapter, Neo4jAdapter, JSONAdapter, or database configuration.
---

# Storage Adapters (Persistência)

Sistema de persistência baseado em Adapter Pattern com suporte para JSON (dev/testes) e Neo4j (produção).

## Quando Usar

- Escolher entre JSON e Neo4j para um projeto
- Configurar Neo4j em produção
- Debugar problemas de persistência (conexão, performance, dados)
- Implementar operações CRUD (Create, Read, Update, Delete)
- Entender constraints, índices e otimizações de schema

## JSON vs Neo4j - Decisão Rápida

| Critério | JSON | Neo4j |
|----------|------|-------|
| **Fase** | Dev/testes | **Produção (SEMPRE)** |
| **Volume** | <10k memórias | >10k memórias |
| **Performance** | OK para dev | <50ms recalls |
| **Graph traversal** | Limitado | Nativo, otimizado |
| **Dados** | **Descartáveis** | Persistentes |

**REGRA**: JSON apenas dev/testes — **Produção sempre Neo4j**.

## Configuração Rápida

### JSON (Dev)
```bash
# .env
CORTEX_STORAGE_BACKEND=json
CORTEX_DATA_DIR=./data
```

**Limitações**: Sem ACID, performance degrada >10k, graph algorithms in-memory.

### Neo4j (Produção)
```bash
# Docker
docker run -d --name cortex-neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password neo4j:5.15

# .env
CORTEX_STORAGE_BACKEND=neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=your_password
```

## Schema Neo4j (Resumo)

**Nodes**:
- `Entity` (id, type, name, identifiers[], namespace)
- `Memory` (id, who[], what, why, when, where, how, importance, stability, embedding[])

**Relationships**:
- `RELATES_TO` (Entity → Entity) - com relation_type, strength, polarity
- `INVOLVES` (Memory → Entity)

**Índices obrigatórios** para performance <50ms:
- `entity_id`, `memory_id` (UNIQUE)
- `namespace`, `when`, `importance` (ÍNDICES)

## Operações CRUD

```python
# Create
adapter.add_entity(entity)
adapter.add_memory(memory)  # Cria INVOLVES automaticamente

# Read
entity = adapter.get_entity(entity_id)
memories = adapter.get_memories_by_namespace(namespace)
results = adapter.search_memories(query, threshold=0.25)

# Update
adapter.update_memory(memory_id, updates)

# Delete
adapter.delete_memory(memory_id)  # Soft delete
adapter.purge_memory(memory_id)   # Hard delete (permanente)
```

## Troubleshooting Rápido

| Problema | Solução |
|----------|---------|
| `ConnectionError` | Verificar Neo4j rodando: `docker ps` |
| `AuthError` | Checar `NEO4J_PASSWORD` em `.env` |
| Recalls lentos (>500ms) | Criar índices (ver NEO4J-SCHEMA.md) |
| `OutOfMemory` | Aumentar heap: `dbms.memory.heap.max_size=4G` |

## Referências

- [NEO4J-SCHEMA.md](references/NEO4J-SCHEMA.md) — Schema completo + queries Cypher + índices
- [PERFORMANCE-TUNING.md](references/PERFORMANCE-TUNING.md) — Otimizações avançadas Neo4j
