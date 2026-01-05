# Arquitetura do Cortex

## Visão Geral

O Cortex é construído em camadas bem definidas para máxima manutenibilidade:

```
┌─────────────────────────────────────────────────────────┐
│                    Interfaces                           │
│              ┌───────────┐  ┌───────────┐              │
│              │  MCP      │  │  REST API │              │
│              │  Server   │  │  FastAPI  │              │
│              └─────┬─────┘  └─────┬─────┘              │
├────────────────────┴──────────────┴─────────────────────┤
│                    Services                             │
│              ┌───────────────────────┐                 │
│              │    MemoryService      │                 │
│              │  (Lógica de Negócio)  │                 │
│              └───────────┬───────────┘                 │
├──────────────────────────┴──────────────────────────────┤
│                    Core                                 │
│     ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│     │  Entity  │  │ Episode  │  │ Relation │          │
│     └────┬─────┘  └────┬─────┘  └────┬─────┘          │
│          └─────────────┴─────────────┘                 │
│                        │                               │
│              ┌─────────┴─────────┐                    │
│              │    MemoryGraph    │                    │
│              │   (Grafo + Index) │                    │
│              └───────────────────┘                    │
├─────────────────────────────────────────────────────────┤
│                    Storage                              │
│              ┌───────────────────────┐                 │
│              │   JSON / SQLite       │                 │
│              └───────────────────────┘                 │
└─────────────────────────────────────────────────────────┘
```

## Camada Core

### Entity

Representa qualquer "coisa" no universo de discurso:
- **type**: Categoria livre (person, file, concept, character)
- **name**: Nome legível para humanos
- **identifiers**: Formas de reconhecer (email, hash, apelido)
- **attributes**: Metadados flexíveis

### Episode

Representa qualquer "acontecimento":
- **action**: Verbo do que aconteceu
- **participants**: Entidades envolvidas (IDs)
- **context**: Situação/cenário
- **outcome**: Resultado
- **occurrence_count**: Consolidação

### Relation

Representa qualquer "conexão":
- **from_id**: Origem
- **relation_type**: Tipo da relação (livre)
- **to_id**: Destino
- **strength**: Força (0.0 - 1.0)

### MemoryGraph

Grafo de memória com índices para busca O(1):
- Índice por nome de entidade
- Índice por tipo de entidade
- Índice por relação (from/to)
- Persistência automática

## Camada Services

### MemoryService

Orquestrador principal que:
- Recebe requests validados (Pydantic)
- Resolve entidades existentes
- Cria episódios
- Detecta consolidação
- Cria relações

## Camada Interfaces

### MCP Server (FastMCP)

Ferramentas MCP:
- `cortex_recall`: Busca memórias
- `cortex_store`: Armazena memória
- `cortex_stats`: Estatísticas

### REST API (FastAPI)

Endpoints HTTP:
- `POST /memory/recall`
- `POST /memory/store`
- `GET /memory/stats`

## Fluxo de Dados

### Store

```
Request → Validate → Resolve Entities → Create Episode → 
  Check Consolidation → Create Relations → Persist → Response
```

### Recall

```
Query → Extract Concepts → Search Entities → Search Episodes →
  Filter by Context → Rank by Relevance → Format Response
```

## Consolidação

Quando episódios similares ocorrem 5+ vezes:
1. Detecta padrão comum
2. Cria episódio consolidado
3. Arquiva episódios individuais
4. Mantém contagem de ocorrências

```python
Episode(
    action="analyzed_log",
    outcome="pattern: 404 errors from missing routes",
    occurrence_count=15,
    is_consolidated=True
)
```

## Persistência

### JSON (Default)

```
~/.cortex/
├── entities.json
├── episodes.json
├── relations.json
└── indices.json
```

### SQLite (Futuro)

```sql
CREATE TABLE entities (...);
CREATE TABLE episodes (...);
CREATE TABLE relations (...);
CREATE INDEX idx_entity_name ON entities(name);
```
