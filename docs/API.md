# API Reference

## Base URL

```
http://localhost:8000
```

## Autenticação

Atualmente sem autenticação. Em produção, adicione bearer token via middleware.

---

## Endpoints

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "cortex-memory"
}
```

---

### Store Memory

Armazena uma memória após interação.

```http
POST /memory/store
Content-Type: application/json
```

**Request Body:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| action | string | ✅ | Verbo do que foi feito |
| outcome | string | ✅ | Resultado ou conclusão |
| participants | array | ❌ | Entidades envolvidas |
| context | string | ❌ | Situação ou cenário |
| relations | array | ❌ | Conexões descobertas |

**Participant Object:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| type | string | Tipo da entidade |
| name | string | Nome da entidade |
| identifiers | array | Identificadores únicos |

**Relation Object:**

| Campo | Tipo | Descrição |
|-------|------|-----------|
| from | string | Nome da entidade origem |
| type | string | Tipo da relação |
| to | string | Nome da entidade destino |

**Example:**

```json
{
  "action": "analyzed_log",
  "outcome": "found 3 errors, cause: missing route",
  "participants": [
    {
      "type": "file",
      "name": "apache.log",
      "identifiers": ["sha256:abc123", "/var/log/apache.log"]
    }
  ],
  "context": "debugging session",
  "relations": [
    {
      "from": "error_404",
      "type": "caused_by",
      "to": "missing_route"
    }
  ]
}
```

**Response:**

```json
{
  "success": true,
  "episode_id": "ep_abc123",
  "entities_created": 1,
  "entities_updated": 0,
  "relations_created": 1,
  "consolidated": false,
  "consolidation_count": 1
}
```

---

### Recall Memories

Busca memórias relevantes antes de responder.

```http
POST /memory/recall
Content-Type: application/json
```

**Request Body:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| query | string | ✅ | Texto para buscar |
| context | object | ❌ | Contexto adicional |
| limit | integer | ❌ | Máximo de resultados (default: 5) |

**Example:**

```json
{
  "query": "análise de logs apache",
  "context": {
    "entity_types": ["file"],
    "current_task": "debugging"
  },
  "limit": 5
}
```

**Response:**

```json
{
  "entities_found": 2,
  "episodes_found": 3,
  "relations_found": 1,
  "context_summary": "Você já analisou apache.log 5 vezes. Padrão: erros 404.",
  "prompt_context": "[MEMORY CONTEXT]\nEntities known:\n  - apache.log (file)\n...",
  "entities": [
    {
      "id": "ent_abc",
      "type": "file",
      "name": "apache.log",
      "access_count": 5
    }
  ],
  "episodes": [
    {
      "id": "ep_xyz",
      "action": "analyzed_log",
      "outcome": "found 3 errors",
      "occurrence_count": 5,
      "is_pattern": true
    }
  ]
}
```

---

### Get Statistics

```http
GET /memory/stats
```

**Response:**

```json
{
  "total_entities": 42,
  "total_episodes": 128,
  "total_relations": 67,
  "entities_by_type": {
    "file": 15,
    "person": 10,
    "concept": 17
  },
  "consolidated_episodes": 12,
  "storage_path": "/home/user/.cortex"
}
```

---

### Clear Memories

⚠️ **Perigoso!** Remove todas as memórias.

```http
DELETE /memory/clear
```

**Response:**

```json
{
  "success": true,
  "message": "All memories cleared"
}
```

---

## Códigos de Erro

| Código | Descrição |
|--------|-----------|
| 200 | Sucesso |
| 400 | Request inválido |
| 500 | Erro interno |

## Exemplos cURL

```bash
# Store
curl -X POST http://localhost:8000/memory/store \
  -H "Content-Type: application/json" \
  -d '{"action": "test", "outcome": "success"}'

# Recall
curl -X POST http://localhost:8000/memory/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'

# Stats
curl http://localhost:8000/memory/stats

# Clear
curl -X DELETE http://localhost:8000/memory/clear
```
