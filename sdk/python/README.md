# Cortex Memory SDK

SDK Python para integração com o serviço Cortex Memory.

## Instalação

```bash
pip install cortex-memory-sdk
```

## Uso Básico

```python
from cortex_memory_sdk import CortexMemorySDK

# Cria cliente
sdk = CortexMemorySDK(
    namespace="support:user_123",
    api_url="http://localhost:8000",  # ou env CORTEX_API_URL
)

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

## Integrações

### LangChain

```python
from cortex_memory_sdk import CortexMemorySDK
from integrations import CortexLangChainMemory
from langchain.chains import LLMChain

sdk = CortexMemorySDK(namespace="agent:user_123")
memory = CortexLangChainMemory(sdk=sdk)

chain = LLMChain(llm=llm, memory=memory, prompt=prompt)
response = chain.run("Olá, sou Maria")  # Auto recall/store!
```

### CrewAI

```python
from cortex_memory_sdk import CortexMemorySDK
from integrations import CortexCrewAIMemory

sdk = CortexMemorySDK(namespace="crew:mission_1")
memory = CortexCrewAIMemory(sdk)

# Enriquece task com contexto
enriched = memory.enrich_task_description(
    "Pesquisar tendências de mercado"
)

# Armazena resultado
memory.remember_task("Pesquisa", "Encontradas 5 tendências", "Researcher")
```

### Google ADK

```python
from cortex_memory_sdk import CortexMemorySDK
from integrations import CortexADKMemory

sdk = CortexMemorySDK(namespace="agent:user_123")
memory = CortexADKMemory(sdk)

# Busca contexto
context = memory.get_context("histórico do cliente")

# Armazena após resposta
memory.after_response(user_input, agent_response)
```

## Arquitetura

```
┌─────────────────────────────────────────────────────┐
│                   Seu Agente                        │
│  (LangChain / CrewAI / Google ADK / Custom)         │
└──────────────────────┬──────────────────────────────┘
                       │ texto
                       ▼
┌─────────────────────────────────────────────────────┐
│              CortexMemorySDK                        │
│                                                     │
│   ┌────────────┐    ┌─────────────┐                │
│   │  Extractor │ → │  Normalizer │   ← local       │
│   └────────────┘    └─────────────┘                │
│          │                                          │
│          ▼                                          │
│   ┌─────────────────────────────────┐              │
│   │         HTTP Client             │──────────────┼──→ API Cortex
│   └─────────────────────────────────┘              │
└─────────────────────────────────────────────────────┘
```

## API

### `CortexMemorySDK`

| Método | Descrição |
|--------|-----------|
| `remember(action)` | Armazena Action estruturada |
| `observe(text)` | Armazena observação bruta |
| `process(text)` | Extrai Action ou armazena como observação |
| `recall(query)` | Busca memórias relevantes |
| `clean_response(text)` | Remove marcadores [MEMORY] |

### Contratos

```python
@dataclass
class Action:
    verb: str           # Obrigatório
    subject: str = ""   # Quem
    object: str = ""    # O quê
    modifiers: tuple = ()  # Contexto adicional

@dataclass
class W5H:
    who: str    # ← subject
    what: str   # ← verb_object
    when: str   # ← timestamp
    where: str  # ← namespace
    how: str    # ← modifiers
    why: str    # ← explícito
```

## Variáveis de Ambiente

| Variável | Descrição | Default |
|----------|-----------|---------|
| `CORTEX_API_URL` | URL da API Cortex | `http://localhost:8000` |
| `CORTEX_API_KEY` | Chave de autenticação | _(vazio)_ |

## Desenvolvimento

```bash
# Instala dependências de dev
pip install -e ".[dev]"

# Roda testes
pytest tests/ -v
```

## Licença

MIT
