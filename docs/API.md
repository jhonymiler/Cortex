# API Reference

> **Veja também**: [Referência completa](./architecture/api-reference.md) | [Integrações](./getting-started/integrations.md)

---

## Base URL

```
http://localhost:8000
```

## Headers

| Header | Descrição | Obrigatório |
|--------|-----------|-------------|
| `X-Cortex-Namespace` | Namespace para isolamento de memórias | ❌ (default: "default") |
| `Content-Type` | application/json | ✅ (para POST) |

---

## Endpoints W5H (Recomendados)

### Remember (Armazenar memória W5H)

Armazena memória usando modelo W5H. Use **APÓS** responder ao usuário.

```http
POST /memory/remember
```

**Request Body:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| who | array[string] | ✅ | Participantes (nomes, emails, sistemas) |
| what | string | ✅ | O que aconteceu (ação/fato) |
| why | string | ❌ | Por quê (causa/razão) |
| how | string | ❌ | Como foi resolvido (resultado) |
| where | string | ❌ | Namespace (default: "default") |
| importance | float | ❌ | Importância 0.0-1.0 (default: 0.5) |

**Example:**

```json
{
  "who": ["João", "sistema_pagamentos"],
  "what": "reportou_erro_pagamento",
  "why": "cartao_expirado",
  "how": "orientado_atualizar_dados",
  "importance": 0.7
}
```

**Response:**

```json
{
  "success": true,
  "memory_id": "mem_abc123",
  "who_resolved": ["ent_123", "ent_456"],
  "consolidated": false,
  "retrievability": 0.95
}
```

---

### Recall (Buscar memórias)

Busca memórias relevantes. Use **ANTES** de responder ao usuário.

```http
POST /memory/recall
```

**Request Body:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| query | string | ✅ | Texto para buscar |
| context | object | ❌ | Contexto adicional (who, where) |
| limit | integer | ❌ | Máximo de resultados (default: 5) |

**Example:**

```json
{
  "query": "problema com pagamento João",
  "limit": 5
}
```

**Response:**

```json
{
  "entities_found": 2,
  "episodes_found": 3,
  "relations_found": 1,
  "context_summary": "João é cliente VIP. Já teve 2 problemas de pagamento.",
  "prompt_context": "conhece: João\nhistórico: reportou_erro→orientado_atualizar",
  "entities": [...],
  "episodes": [...]
}
```

---

### Interact (Armazenar com extração automática) ⭐ NOVO

Armazena interação com **extração automática de W5H no servidor**.
O cliente NÃO precisa extrair nada.

```http
POST /memory/interact
```

**Request Body:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| user_message | string | ✅ | Mensagem do usuário |
| assistant_response | string | ✅ | Resposta do assistente |
| user_name | string | ❌ | Nome do usuário (default: "user") |

**Example:**

```json
{
  "user_message": "Olá, meu nome é Maria e preciso de ajuda com meu pedido",
  "assistant_response": "Olá Maria! Vou verificar seu pedido. Qual o número?",
  "user_name": "Maria"
}
```

**Response:**

```json
{
  "success": true,
  "memory_id": "mem_xyz789",
  "extracted": {
    "who": ["Maria"],
    "what": "solicitou_ajuda_pedido",
    "why": "problema_com_pedido",
    "how": "assistente_solicitou_numero"
  },
  "message": "Interação armazenada com sucesso"
}
```

---

### Forget (Esquecer memória)

Marca memória como esquecida (excluída de recalls futuros).

```http
POST /memory/forget
```

**Request Body:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| memory_id | string | ✅ | ID da memória a esquecer |
| reason | string | ❌ | Motivo (para auditoria) |

**Response:**

```json
{
  "success": true,
  "memory_id": "mem_abc123",
  "was_forgotten": false,
  "message": "Memória marcada como esquecida"
}
```

---

## Endpoints Admin

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
  "entities_by_type": {"person": 10, "system": 5},
  "consolidated_episodes": 12,
  "storage_path": "/data/cortex"
}
```

---

### Memory Health

```http
GET /memory/health
```

**Response:**

```json
{
  "orphan_entities": 3,
  "lonely_episodes": 2,
  "weak_relations": 5,
  "avg_episode_importance": 0.65,
  "avg_relation_strength": 0.72,
  "health_score": 85
}
```

---

### Clear Memories

⚠️ **Perigoso!** Remove todas as memórias do namespace.

```http
POST /memory/clear
```

**Response:**

```json
{
  "success": true,
  "entities_deleted": 42,
  "episodes_deleted": 128,
  "relations_deleted": 67
}
```

---

### List Namespaces

```http
GET /namespaces
```

**Response:**

```json
{
  "active": ["default", "agente_a", "agente_b"],
  "persisted": ["default", "agente_a"],
  "stats": {"total_namespaces": 3}
}
```

---

### Update Episode (Consolidação) ⭐ NOVO

Atualiza campos de um episódio. Usado pelo DreamAgent para marcar memórias como consolidadas.

```http
PATCH /memory/episode/{episode_id}
```

**Request Body:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| consolidated_into | string | ❌ | ID da memória resumo (pai) |
| is_summary | boolean | ❌ | Se é resumo de consolidação |
| importance | float | ❌ | Nova importância (0.0-1.0) |

**Example:**

```json
{
  "consolidated_into": "mem_summary_123",
  "importance": 0.3
}
```

**Response:**

```json
{
  "success": true,
  "episode_id": "mem_abc123",
  "updated": true
}
```

**Efeitos:**
- Memórias com `consolidated_into` decaem **3x mais rápido**
- Memórias com `consolidated_into` são **excluídas do recall normal**
- Para incluí-las, use `context.include_consolidated = true` no recall

---

## Health Check

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

## Códigos de Erro

| Código | Descrição |
|--------|-----------|
| 200 | Sucesso |
| 400 | Request inválido |
| 404 | Memória não encontrada |
| 500 | Erro interno |

---

## Exemplos cURL

```bash
# Remember (W5H)
curl -X POST http://localhost:8000/memory/remember \
  -H "Content-Type: application/json" \
  -H "X-Cortex-Namespace: meu_agente" \
  -d '{
    "who": ["João", "suporte"],
    "what": "resolveu_problema",
    "why": "erro_de_login",
    "how": "reset_de_senha"
  }'

# Recall
curl -X POST http://localhost:8000/memory/recall \
  -H "Content-Type: application/json" \
  -H "X-Cortex-Namespace: meu_agente" \
  -d '{"query": "João login"}'

# Interact (extração automática)
curl -X POST http://localhost:8000/memory/interact \
  -H "Content-Type: application/json" \
  -H "X-Cortex-Namespace: meu_agente" \
  -d '{
    "user_message": "Oi, sou Maria",
    "assistant_response": "Olá Maria, como posso ajudar?"
  }'

# Stats
curl http://localhost:8000/memory/stats \
  -H "X-Cortex-Namespace: meu_agente"

# Clear (cuidado!)
curl -X POST http://localhost:8000/memory/clear \
  -H "X-Cortex-Namespace: meu_agente"
```
