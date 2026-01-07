# Cortex Python SDK

SDK Python para integração de memória cognitiva em agentes LLM.
Modelo W5H (Who, What, Why, When, Where, How).

## 📁 Estrutura

```
sdk/python/
├── cortex_sdk.py        # Cliente REST baixo-nível
├── cortex_memory.py     # Core genérico (before/after)
└── integrations/
    ├── langchain.py     # Adaptador LangChain (BaseMemory)
    └── crewai.py        # Adaptador CrewAI (long_term_memory)
```

---

## 🚀 Instalação

```bash
# Copiar para seu projeto
cp -r sdk/python/ seu_projeto/cortex/

# Ou adicionar ao PYTHONPATH
export PYTHONPATH=/path/to/cortex/sdk/python:$PYTHONPATH
```

---

## 📖 Uso

### 1. Core Genérico (qualquer framework)

O método mais simples - funciona com qualquer LLM/framework:

```python
from cortex_memory import CortexMemory

cortex = CortexMemory(namespace="meu_agente:usuario_123")

def meu_agente(user_msg):
    # ANTES: Busca contexto de memória
    context = cortex.before(user_msg)
    
    # Seu LLM aqui (OpenAI, Ollama, Anthropic, etc)
    response = llm.generate(context + user_msg)
    
    # DEPOIS: Armazena (extração W5H automática no servidor)
    cortex.after(user_msg, response)
    
    return response
```

### 2. Decorator (mais limpo)

```python
from cortex_memory import with_memory

@with_memory(namespace="meu_agente")
def meu_agente(user_msg: str, context: str = "") -> str:
    # context já contém a memória injetada automaticamente
    return llm.generate(context + user_msg)

# Uso - recall/store automáticos!
response = meu_agente("Olá, sou Maria")
```

### 3. LangChain (plug and play)

```python
from cortex.integrations import CortexLangChainMemory
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI

# Cria memória Cortex
memory = CortexLangChainMemory(namespace="meu_agente")

# Usa normalmente com LangChain
llm = ChatOpenAI()
chain = LLMChain(llm=llm, memory=memory, prompt=prompt)

# Zero código extra - recall/store automáticos!
response = chain.run("Olá, sou Maria")
```

### 4. CrewAI (plug and play)

```python
from cortex.integrations import CortexCrewAIMemory
from crewai import Crew, Agent, Task

# Cria memória Cortex
memory = CortexCrewAIMemory(namespace="minha_crew")

# Usa com CrewAI
crew = Crew(
    agents=[...],
    tasks=[...],
    memory=True,
    long_term_memory=memory,  # Plug and play!
)
```

### 5. Cliente REST (baixo nível)

Para controle total sobre recall/store:

```python
from cortex_sdk import CortexClient

client = CortexClient(namespace="meu_agente")

# ANTES de responder
memories = client.recall(query="problema com pagamento")
print(memories['prompt_context'])

# DEPOIS de responder (W5H manual)
client.remember(
    who=["usuario_123", "sistema_pagamentos"],
    what="reportou_erro_pagamento",
    why="cartao_expirado",
    how="orientado_atualizar_dados",
)
```

---

## 🔧 API Reference

### CortexMemory (Core)

```python
cortex = CortexMemory(
    namespace="default",           # Isolamento de memórias
    cortex_url="http://localhost:8000",
    auto_inject=True,              # Formata contexto automaticamente
)

# Hooks principais
context = cortex.before(user_message)      # Busca memória
cortex.after(user_message, response)       # Armazena

# Métodos diretos
result = cortex.recall(query, limit=5)     # RecallResult
result = cortex.store_interaction(msg, resp)  # StoreResult
result = cortex.store_w5h(who, what, ...)  # StoreResult manual
```

### CortexClient (REST)

```python
client = CortexClient(
    base_url="http://localhost:8000",
    namespace="default"
)

# Métodos W5H
client.remember(who, what, why="", how="", importance=0.5)
client.recall(query, who=None, limit=10)
client.forget(memory_id, reason="")

# Admin
client.stats()       # Estatísticas
client.health()      # Métricas de saúde
client.clear()       # ⚠️ Limpa namespace!
```

---

## 📊 Modelo W5H

| Campo | Descrição | Obrigatório |
|-------|-----------|-------------|
| **WHO** | Participantes (nomes, emails, sistemas) | ✅ |
| **WHAT** | O que aconteceu (ação/fato) | ✅ |
| **WHY** | Por quê (causa/razão) | ❌ |
| **WHEN** | Quando (automático) | - |
| **WHERE** | Namespace/contexto | ❌ |
| **HOW** | Resultado/método | ❌ |

---

## 🔌 Endpoint /memory/interact

O endpoint `/memory/interact` permite armazenar interações com **extração automática de W5H no servidor**. O cliente não precisa extrair nada:

```python
# POST /memory/interact
{
    "user_message": "Olá, meu nome é João e preciso de ajuda",
    "assistant_response": "Olá João! Como posso ajudar?",
    "user_name": "João"
}

# Response
{
    "success": true,
    "memory_id": "abc123",
    "extracted": {
        "who": ["João"],
        "what": "solicitou_ajuda",
        "why": "primeiro_contato",
        "how": "assistente_ofereceu_ajuda"
    }
}
```

---

## 📚 Documentação

- [API Reference](../../docs/API.md)
- [W5H Design](../../docs/W5H_DESIGN.md)
- [Architecture](../../docs/ARCHITECTURE.md)
- [MCP Integration](../../docs/MCP.md)
