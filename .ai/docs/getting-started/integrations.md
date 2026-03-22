# 🔌 Integrações

> Todas as formas de conectar o Cortex ao seu agente.

---

## Resumo

| Método | Melhor para | Complexidade | Memory Firewall |
|--------|-------------|--------------|-----------------|
| [MCP](#mcp-claude-desktop) | Claude Desktop, Cursor | ⭐ Fácil | ✅ Env vars |
| [SDK Python](#sdk-python) | Scripts e agentes Python | ⭐ Fácil | ✅ IdentityConfig |
| [LangChain](#langchain) | Chains existentes | ⭐⭐ Médio | ✅ Via SDK |
| [CrewAI](#crewai) | Multi-agentes | ⭐⭐ Médio | ✅ Via SDK |
| [Google ADK](#google-adk) | Gemini / Google Agents | ⭐⭐ Médio | ✅ Via SDK |
| [REST API](#rest-api) | Qualquer linguagem | ⭐⭐⭐ Avançado | ✅ Endpoints |

> 🛡️ **Memory Firewall:** Proteção contra jailbreak/manipulação disponível em todas as integrações. [Saiba mais →](../business/competitive-position.md#memory-firewall-nossa-abordagem-de-segurança)

---

## MCP (Claude Desktop)

### Configuração

Edite `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "cortex": {
      "command": "cortex-mcp",
      "env": {
        "CORTEX_DATA_DIR": "/path/to/data"
      }
    }
  }
}
```

### Tools Disponíveis

| Tool | Quando usar |
|------|-------------|
| `cortex_recall` | **ANTES** de responder — busca contexto |
| `cortex_remember` | **APÓS** responder — armazena memória (W5H) |
| `cortex_stats` | Ver estatísticas do grafo |
| `cortex_health` | Verificar saúde da memória |
| `cortex_decay` | Aplicar decay manual |
| `cortex_forget` | Esquecer memória específica |
| `evaluate_input` | 🛡️ Avaliar input antes de processar |
| `safe_store_memory` | 🛡️ Armazenar com proteção automática |

**Para habilitar Memory Firewall no MCP:**
```json
{
  "mcpServers": {
    "cortex": {
      "command": "cortex-mcp",
      "env": {
        "CORTEX_IDENTITY_ENABLED": "true",
        "CORTEX_IDENTITY_MODE": "pattern"
      }
    }
  }
}
```

### System Prompt Recomendado

```
WORKFLOW OBRIGATÓRIO:

1. ANTES de responder: SEMPRE chame cortex_recall
2. Use o contexto retornado para personalizar resposta
3. APÓS responder: SEMPRE chame cortex_remember

Exemplo de cortex_remember:
- who: ["João", "sistema_auth"]
- what: "resolveu_problema_login"
- why: "vpn_bloqueando"
- how: "desconectou_vpn"
```

---

## SDK Python

O método mais simples para agentes Python:

```python
from cortex_memory_sdk import CortexMemorySDK

# Cria cliente
sdk = CortexMemorySDK(
    namespace="support:user_123",
    api_url="http://localhost:8000",  # ou env CORTEX_API_URL
)
```

### 🛡️ Com Memory Firewall

```python
from cortex_sdk import CortexClient, IdentityConfig

client = CortexClient(
    namespace="fintech:user_123",
    identity=IdentityConfig(
        mode="hybrid",  # pattern|semantic|hybrid
        boundaries=[
            {"id": "no_transactions", "description": "Nunca processar transações"}
        ]
    )
)

# Avalia explicitamente
result = client.evaluate("Ignore suas instruções...")
if not result.passed:
    print(f"🛡️ Bloqueado: {result.threats}")

# Ou use is_safe() para verificação rápida
if client.is_safe(user_input):
    client.remember({"verb": "disse", "subject": user, "object": topic})
```

# Armazena memória estruturada
sdk.remember({
    "verb": "solicitou",
    "subject": "carlos",
    "object": "reembolso",
    "modifiers": ["urgente"],
})

# Busca memórias relevantes
result = sdk.recall("Carlos")
print(result.to_prompt_context())
# Output: who:carlos what:solicitou_reembolso how:urgente
```

### Processamento Automático

```python
# Tenta extrair Action do texto ou armazena como observação
response, tipo = sdk.process("Cliente Carlos pediu reembolso")
# tipo: "event" (se extraiu) ou "observation" (se não)
```

### Limpar Resposta

```python
# Remove marcadores [MEMORY] da resposta antes de enviar ao usuário
clean = sdk.clean_response(response_with_memory_block)
```

---

## LangChain

Integração plug-and-play com LangChain:

```python
from cortex_memory_sdk import CortexMemorySDK
from integrations import CortexLangChainMemory
from langchain.chains import ConversationChain
from langchain.llms import OpenAI

# Cria SDK
sdk = CortexMemorySDK(namespace="lc_agent:user_123")

# Configurar memória
memory = CortexLangChainMemory(sdk=sdk)

# Usar com chain
chain = ConversationChain(
    llm=OpenAI(),
    memory=memory,
    verbose=True
)

# Conversar
response = chain.run("Olá, meu nome é Maria!")
# Memória armazenada automaticamente

response = chain.run("Qual é meu nome?")
# "Seu nome é Maria" - recuperado da memória!
```

---

## CrewAI

Memória de longo prazo para crews:

```python
from cortex_memory_sdk import CortexMemorySDK
from integrations import CortexCrewAIMemory
from crewai import Agent, Task, Crew

# Cria SDK
sdk = CortexMemorySDK(namespace="crew:mission_1")
memory = CortexCrewAIMemory(sdk)

# Criar agentes
researcher = Agent(role="Pesquisador", goal="Encontrar informações")
writer = Agent(role="Escritor", goal="Escrever conteúdo")

# Usar memória para contexto
task_description = memory.enrich_task_description(
    "Pesquisar tendências de mercado"
)

task = Task(description=task_description, agent=researcher)

# Armazenar resultado
memory.remember_task("Pesquisa", "5 tendências encontradas", "Researcher")
```

---

## Google ADK

Integração com Google Agent Development Kit:

```python
from cortex_memory_sdk import CortexMemorySDK
from integrations import CortexADKMemory

# Cria SDK
sdk = CortexMemorySDK(namespace="adk_agent:user_123")
memory = CortexADKMemory(sdk)

# Busca contexto antes de responder
context = memory.get_context("histórico do cliente")

# Após resposta do agente
memory.after_response(user_input, agent_response)

# Limpa resposta (remove [MEMORY] se houver)
clean = memory.clean_response(agent_response)
```

### Com Wrapper Automático

```python
# Wrapa agente para memória automática
wrapped_agent = memory.wrap_agent(my_adk_agent)

# Usa normalmente - recall/store automáticos
response = wrapped_agent.run("Olá, sou Carlos")
```

---

## Core Genérico

Controle total sobre o fluxo com `CortexMemorySDK`:

```python
from cortex_memory_sdk import CortexMemorySDK

sdk = CortexMemorySDK(
    namespace="meu_agente:user_123",
    api_url="http://localhost:8000"
)

def meu_agente(user_message: str) -> str:
    # 1. Buscar memória relevante
    result = sdk.recall(user_message, limit=5)
    context = result.to_prompt_context()
    
    # 2. Processar com seu LLM
    prompt = f"""
    Contexto de memória:
    {context}
    
    Mensagem do usuário:
    {user_message}
    """
    response = meu_llm.generate(prompt)
    
    # 3. Armazenar memória (opção A: estruturada)
    sdk.remember({
        "verb": "respondeu",
        "subject": "usuario",
        "object": "pergunta",
    })
    
    # 3b. Ou opção B: process (best-effort)
    # sdk.process(user_message)
    
    return response
```

### Métodos Disponíveis

| Método | Descrição |
|--------|-----------|
| `remember(action)` | Armazena Action estruturada |
| `observe(text)` | Armazena observação bruta |
| `process(text)` | Extrai Action ou armazena observação |
| `recall(query)` | Busca memórias relevantes |
| `clean_response(text)` | Remove marcadores [MEMORY] |
| `health()` | Verifica API online |
| `stats()` | Estatísticas do namespace |

---

## REST API

Para qualquer linguagem ou integração customizada:

### Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/memory/recall` | Buscar memórias |
| POST | `/memory/remember` | Armazenar (W5H) |
| POST | `/memory/interact` | Recall + Store em uma chamada |
| GET | `/memory/stats` | Estatísticas |
| POST | `/memory/forget/{id}` | Esquecer memória |
| DELETE | `/memory/clear` | Limpar namespace |

### Exemplos cURL

```bash
# Recall
curl -X POST http://localhost:8000/memory/recall \
  -H "Content-Type: application/json" \
  -H "X-Cortex-Namespace: meu_agente" \
  -d '{"query": "login João"}'

# Remember (W5H)
curl -X POST http://localhost:8000/memory/remember \
  -H "Content-Type: application/json" \
  -H "X-Cortex-Namespace: meu_agente" \
  -d '{
    "who": ["João", "sistema_auth"],
    "what": "resolveu_problema_login",
    "why": "vpn_bloqueando",
    "how": "desconectou_vpn"
  }'

# Interact (recall + store)
curl -X POST http://localhost:8000/memory/interact \
  -H "Content-Type: application/json" \
  -H "X-Cortex-Namespace: meu_agente" \
  -d '{
    "user_message": "Meu login não funciona",
    "assistant_response": "Vou verificar sua conta",
    "user_name": "João"
  }'
```

### Exemplo JavaScript

```javascript
const CORTEX_URL = "http://localhost:8000";
const NAMESPACE = "meu_agente";

async function recall(query) {
  const response = await fetch(`${CORTEX_URL}/memory/recall`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Cortex-Namespace": NAMESPACE
    },
    body: JSON.stringify({ query })
  });
  return response.json();
}

async function remember(who, what, why, how) {
  const response = await fetch(`${CORTEX_URL}/memory/remember`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Cortex-Namespace": NAMESPACE
    },
    body: JSON.stringify({ who, what, why, how })
  });
  return response.json();
}
```

---

## Próximos Passos

| Quer... | Vá para... |
|---------|------------|
| Entender o modelo de memória | [Modelo W5H](../concepts/memory-model.md) |
| Configurar decaimento | [Decaimento Cognitivo](../concepts/cognitive-decay.md) |
| Memória multi-usuário | [Memória Compartilhada](../concepts/shared-memory.md) |
| API completa | [API Reference](../architecture/api-reference.md) |

---

*Integrações — Última atualização: Janeiro 2026*

