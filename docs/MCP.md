# Integração MCP

## O que é MCP?

Model Context Protocol (MCP) é um protocolo para ferramentas que LLMs podem chamar. O Cortex implementa um servidor MCP que expõe funções de memória.

## Modelo W5H

O Cortex usa o modelo **W5H** para estruturar memórias:

| Campo | Significado | Exemplo |
|-------|-------------|---------|
| WHO | Quem participou | `["maria@email.com", "sistema"]` |
| WHAT | O que aconteceu | `"reportou erro de pagamento"` |
| WHY | Por que aconteceu | `"cartão expirado"` |
| WHEN | Quando (automático) | `timestamp` |
| WHERE | Namespace/contexto | `"suporte_cliente"` |
| HOW | Resultado/método | `"orientada a atualizar dados"` |

## Instalação

```bash
pip install cortex-memory[mcp]
```

## Configuração

### Claude Desktop

Edite `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) ou `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "cortex": {
      "command": "cortex-mcp",
      "env": {
        "CORTEX_DATA_DIR": "/path/to/your/data",
        "CORTEX_NAMESPACE": "agent:user_123"
      }
    }
  }
}
```

### Variáveis de Ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| CORTEX_DATA_DIR | ~/.cortex | Diretório de dados |
| CORTEX_NAMESPACE | default | Isolamento multi-tenant |

## Ferramentas Disponíveis

### cortex_recall

**Descrição:** OBRIGATÓRIO antes de responder ao usuário. Busca memórias relevantes.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| query | string | ✅ | Mensagem do usuário ou tópico |
| context | object | ❌ | Contexto adicional |
| limit | integer | ❌ | Máximo de resultados |

**Retorno:**
```json
{
  "entities_found": 2,
  "episodes_found": 3,
  "context_summary": "Você já viu isso antes...",
  "prompt_context": "[MEMORY CONTEXT]...",
  "entities": [...],
  "episodes": [...]
}
```

### cortex_remember (W5H) ⭐ PREFERIDO

**Descrição:** OBRIGATÓRIO após responder ao usuário. Armazena memória usando modelo W5H.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| who | array[string] | ✅ | Participantes (nomes, emails, sistemas) |
| what | string | ✅ | O que aconteceu (ação/fato) |
| why | string | ❌ | Por que aconteceu (causa) |
| how | string | ❌ | Resultado/método |
| where | string | ❌ | Namespace (default: "default") |
| importance | float | ❌ | Importância 0.0-1.0 (default: 0.5) |

**Exemplo:**
```json
{
  "who": ["maria@email.com", "payment_system"],
  "what": "reported payment error",
  "why": "expired card",
  "how": "guided to update card details",
  "importance": 0.7
}
```

**Retorno:**
```json
{
  "success": true,
  "memory_id": "abc123...",
  "who_resolved": ["entity_id_1", "entity_id_2"],
  "consolidated": false,
  "consolidation_count": 1,
  "retrievability": 1.0
}
```

### cortex_forget

**Descrição:** Esquece uma memória (marca como esquecida, não deleta).

**Parâmetros:**

| Nome | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| memory_id | string | ✅ | ID da memória a esquecer |
| reason | string | ❌ | Razão do esquecimento |

**Retorno:**
```json
{
  "success": true,
  "memory_id": "abc123...",
  "was_forgotten": false,
  "message": "Memory forgotten"
}
```

### cortex_store (Legacy)

**Descrição:** Formato antigo, ainda funciona. Prefira `cortex_remember`.

**Parâmetros:**

| Nome | Tipo | Obrigatório | Descrição |
|------|------|-------------|-----------|
| action | string | ✅ | O que foi feito (verbo) |
| outcome | string | ✅ | Resultado ou conclusão |
| participants | array | ❌ | Entidades envolvidas |
| context | string | ❌ | Situação ou cenário |
| relations | array | ❌ | Conexões descobertas |

**Participant:**
```json
{
  "type": "person",
  "name": "João",
  "identifiers": ["joao@email.com"]
}
```

**Relation:**
```json
{
  "from": "erro_404",
  "type": "caused_by",
  "to": "rota_faltando"
}
```

**Retorno:**
```json
{
  "success": true,
  "episode_id": "ep_abc123",
  "entities_created": 1,
  "consolidated": false
}
```

### cortex_stats

**Descrição:** Estatísticas do grafo de memória.

**Parâmetros:** Nenhum.

**Retorno:**
```json
{
  "total_entities": 42,
  "total_episodes": 128,
  "total_relations": 67
}
```

## Fluxo Obrigatório

O Cortex inclui instruções que orientam o LLM a seguir este fluxo:

```
1. Usuário envia mensagem
        ↓
2. LLM chama cortex_recall(query=mensagem)
        ↓
3. Cortex retorna contexto relevante
        ↓
4. LLM processa (considerando contexto)
        ↓
5. LLM responde ao usuário
        ↓
6. LLM chama cortex_remember(who, what, why, how)  [W5H]
        ↓
7. Cortex armazena com decaimento e consolidação
```

## Decaimento (Ebbinghaus)

Memórias seguem a curva de esquecimento:

- **Memórias frescas**: retrievability > 0.7
- **Memórias estáveis**: 0.4 < retrievability ≤ 0.7
- **Memórias fracas**: 0.1 < retrievability ≤ 0.4
- **Memórias esquecidas**: retrievability ≤ 0.1

Fatores que aumentam retenção:
- Acessos frequentes (spaced repetition)
- Consolidação (5+ memórias similares)
- Alta centralidade (hub nodes)

## Recursos MCP

### cortex://stats

Retorna estatísticas do grafo em texto legível.

```
Cortex Memory Statistics
========================
Entities: 42
Episodes: 128
Relations: 67
```

## Testando Localmente

```bash
# Inicia o servidor MCP em modo debug
cortex-mcp

# Em outro terminal, use o MCP Inspector
npx @modelcontextprotocol/inspector cortex-mcp
```

## Logs

O servidor MCP escreve logs para stderr. Para debug:

```bash
cortex-mcp 2>&1 | tee cortex.log
```
