# 🔌 Integrações

> Todas as formas de conectar o Cortex ao seu agente.

---

## Resumo

| Método | Melhor para | Complexidade |
|--------|-------------|--------------|
| [MCP](#mcp-claude-desktop) | Claude Desktop, Cursor | ⭐ Fácil |
| [Decorator](#decorator) | Scripts Python simples | ⭐ Fácil |
| [LangChain](#langchain) | Chains existentes | ⭐⭐ Médio |
| [CrewAI](#crewai) | Multi-agentes | ⭐⭐ Médio |
| [Core Genérico](#core-genérico) | Controle total | ⭐⭐⭐ Avançado |
| [REST API](#rest-api) | Qualquer linguagem | ⭐⭐⭐ Avançado |

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

## Decorator

O método mais simples para scripts Python:

```python
from cortex_memory import with_memory

@with_memory(namespace="meu_agente")
def meu_agente(msg: str, context: str = "") -> str:
    """
    context: Automaticamente preenchido com memórias relevantes
    Retorno: Armazenado automaticamente como memória
    """
    return f"Respondendo com contexto: {context}"

# Uso
resposta = meu_agente("Olá, sou João!")
```

### Parâmetros

```python
@with_memory(
    namespace="meu_agente",        # Namespace para isolamento
    cortex_url="http://localhost:8000",  # URL da API
    context_window=5               # Máximo de memórias no contexto
)
```

---

## LangChain

Integração plug-and-play com LangChain:

```python
from cortex.integrations import CortexLangChainMemory
from langchain.chains import ConversationChain
from langchain.llms import OpenAI

# Configurar memória
memory = CortexLangChainMemory(
    namespace="lc_agent",
    cortex_url="http://localhost:8000"
)

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

### Com Chat Models

```python
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationChain

memory = CortexLangChainMemory(namespace="chat_agent")
chain = ConversationChain(
    llm=ChatOpenAI(model="gpt-4"),
    memory=memory
)
```

---

## CrewAI

Memória de longo prazo para crews:

```python
from cortex.integrations import CortexCrewAIMemory
from crewai import Agent, Task, Crew

# Configurar memória compartilhada
memory = CortexCrewAIMemory(namespace="minha_crew")

# Criar agentes
researcher = Agent(
    role="Pesquisador",
    goal="Encontrar informações",
    backstory="Especialista em pesquisa"
)

writer = Agent(
    role="Escritor",
    goal="Escrever conteúdo",
    backstory="Escritor experiente"
)

# Criar crew com memória
crew = Crew(
    agents=[researcher, writer],
    long_term_memory=memory  # ← Cortex aqui!
)

# Executar
result = crew.kickoff()
# Memórias compartilhadas entre agentes!
```

---

## Core Genérico

Controle total sobre o fluxo:

```python
from cortex_memory import CortexMemory

cortex = CortexMemory(
    namespace="meu_agente",
    cortex_url="http://localhost:8000",
    context_window=10
)

def meu_agente(user_message: str) -> str:
    # 1. Buscar memória relevante
    context = cortex.before(user_message)
    
    # 2. Processar com seu LLM
    prompt = f"""
    Contexto de memória:
    {context}
    
    Mensagem do usuário:
    {user_message}
    """
    response = meu_llm.generate(prompt)
    
    # 3. Armazenar memória
    cortex.after(user_message, response)
    
    return response
```

### Métodos Disponíveis

| Método | Descrição |
|--------|-----------|
| `before(msg)` | Busca memórias relevantes |
| `after(msg, response)` | Armazena com extração W5H |
| `recall(query)` | Busca manual |
| `remember(who, what, ...)` | Armazena W5H manual |

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

