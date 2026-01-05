# Integração MCP

## O que é MCP?

Model Context Protocol (MCP) é um protocolo para ferramentas que LLMs podem chamar. O Cortex implementa um servidor MCP que expõe funções de memória.

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
        "CORTEX_DATA_DIR": "/path/to/your/data"
      }
    }
  }
}
```

### Variáveis de Ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| CORTEX_DATA_DIR | ~/.cortex | Diretório de dados |

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

### cortex_store

**Descrição:** OBRIGATÓRIO após responder ao usuário. Armazena a interação.

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
6. LLM chama cortex_store(action, outcome, ...)
        ↓
7. Cortex armazena e consolida
```

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
