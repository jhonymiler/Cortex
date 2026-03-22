# 📡 API Reference

> Documentação completa dos endpoints REST.

---

## Base URL

```
http://localhost:8000
```

## Headers

| Header | Descrição | Obrigatório |
|--------|-----------|-------------|
| `X-Cortex-Namespace` | Namespace para isolamento | Sim |
| `X-Cortex-User` | ID do usuário (shared memory) | Não |
| `Content-Type` | `application/json` | Sim |

---

## Endpoints

### Health Check

```http
GET /health
```

**Response**
```json
{
  "status": "healthy"
}
```

---

### Recall (Buscar Memórias)

```http
POST /memory/recall
```

**Request Body**
```json
{
  "query": "login do João",
  "limit": 10,
  "min_importance": 0.0,
  "include_forgotten": false
}
```

| Campo | Tipo | Descrição | Default |
|-------|------|-----------|---------|
| `query` | string | Texto de busca | — |
| `limit` | int | Máximo de resultados | 10 |
| `min_importance` | float | Filtro de importância | 0.0 |
| `include_forgotten` | bool | Incluir esquecidas | false |

**Response**
```json
{
  "success": true,
  "memories": [
    {
      "id": "uuid",
      "who": ["João", "sistema_auth"],
      "what": "reclamou_login",
      "why": "vpn_bloqueando",
      "how": "resolvido_desconectando",
      "when": "2026-01-07T10:30:00",
      "where": "suporte",
      "importance": 0.8,
      "retrievability": 0.95
    }
  ],
  "entities": [
    {
      "id": "uuid",
      "name": "João",
      "type": "person",
      "attributes": {"email": "joao@example.com"}
    }
  ],
  "context_summary": "João (person) reclamou de login por causa de VPN..."
}
```

---

### Remember (Armazenar W5H)

```http
POST /memory/remember
```

**Request Body**
```json
{
  "who": ["João", "sistema_auth"],
  "what": "resolveu_problema_login",
  "why": "vpn_estava_bloqueando",
  "how": "desconectou_vpn",
  "importance": 0.8
}
```

| Campo | Tipo | Descrição | Obrigatório |
|-------|------|-----------|-------------|
| `who` | list[str] | Participantes | Sim |
| `what` | str | Ação/fato | Sim |
| `why` | str | Causa | Não |
| `how` | str | Resultado | Não |
| `importance` | float | 0.0-1.0 | Não (0.5) |

**Response**
```json
{
  "success": true,
  "memory_id": "uuid",
  "entities_created": ["sistema_auth"],
  "entities_updated": ["João"],
  "consolidated": false
}
```

---

### Interact (Recall + Store)

```http
POST /memory/interact
```

**Request Body**
```json
{
  "user_message": "Meu login não funciona",
  "assistant_response": "Vou verificar sua conta, João",
  "user_name": "João"
}
```

| Campo | Tipo | Descrição | Obrigatório |
|-------|------|-----------|-------------|
| `user_message` | str | Mensagem do usuário | Sim |
| `assistant_response` | str | Resposta do assistente | Sim |
| `user_name` | str | Nome do usuário | Não |

**Response**
```json
{
  "success": true,
  "context_used": "...",
  "memory_stored": {
    "id": "uuid",
    "who": ["João"],
    "what": "reportou_problema_login",
    "why": null,
    "how": "verificando_conta"
  }
}
```

---

### Stats (Estatísticas)

```http
GET /memory/stats
```

**Response**
```json
{
  "total_entities": 150,
  "total_memories": 500,
  "total_relations": 800,
  "active_memories": 450,
  "fading_memories": 40,
  "forgotten_memories": 10,
  "consolidated_memories": 50,
  "hub_entities": ["João", "sistema_auth", "projeto_x"]
}
```

---

### Forget (Esquecer)

```http
POST /memory/forget/{memory_id}
```

**Request Body**
```json
{
  "reason": "Informação incorreta"
}
```

**Response**
```json
{
  "success": true,
  "memory_id": "uuid",
  "forgotten": true
}
```

---

### Clear (Limpar Namespace)

```http
DELETE /memory/clear
```

**Response**
```json
{
  "success": true,
  "entities_deleted": 150,
  "memories_deleted": 500,
  "relations_deleted": 800
}
```

---

### Decay (Aplicar Decaimento)

```http
POST /memory/decay
```

**Response**
```json
{
  "success": true,
  "memories_decayed": 100,
  "memories_forgotten": 5
}
```

---

### Consolidate (Consolidar)

```http
POST /memory/consolidate
```

**Response**
```json
{
  "success": true,
  "memories_analyzed": 100,
  "memories_consolidated": 20,
  "summaries_created": 5
}
```

---

### Update Memory

```http
PATCH /memory/episode/{memory_id}
```

**Request Body**
```json
{
  "importance": 0.9,
  "consolidated_into": "parent_uuid"
}
```

**Response**
```json
{
  "success": true,
  "memory_id": "uuid",
  "updated_fields": ["importance", "consolidated_into"]
}
```

---

## Códigos de Status

| Código | Descrição |
|--------|-----------|
| 200 | Sucesso |
| 400 | Request inválido |
| 404 | Não encontrado |
| 422 | Erro de validação |
| 500 | Erro interno |

---

## Exemplos cURL

### Recall

```bash
curl -X POST http://localhost:8000/memory/recall \
  -H "Content-Type: application/json" \
  -H "X-Cortex-Namespace: meu_agente" \
  -d '{"query": "login João"}'
```

### Remember

```bash
curl -X POST http://localhost:8000/memory/remember \
  -H "Content-Type: application/json" \
  -H "X-Cortex-Namespace: meu_agente" \
  -d '{
    "who": ["João", "sistema_auth"],
    "what": "resolveu_problema_login",
    "why": "vpn_bloqueando",
    "how": "desconectou_vpn"
  }'
```

### Stats

```bash
curl http://localhost:8000/memory/stats \
  -H "X-Cortex-Namespace: meu_agente"
```

---

## Rate Limits

| Endpoint | Limite |
|----------|--------|
| `/memory/recall` | 100/min |
| `/memory/remember` | 50/min |
| `/memory/interact` | 50/min |
| Outros | 20/min |

---

## Próximos Passos

| Quer... | Vá para... |
|---------|------------|
| Ver integrações | [Integrações](../getting-started/integrations.md) |
| Entender MCP | [MCP](../MCP.md) |
| Ver arquitetura | [Overview](./overview.md) |

---

*API Reference — Última atualização: Janeiro 2026*

