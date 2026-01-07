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
Request → Validate → Resolve Entities → Create Memory → 
  Check Consolidation → Create Relations → Apply Decay → Persist → Response
```

### Recall

```
Query → Extract Concepts → Search Entities → Search Memories →
  Filter by Retrievability → Rank by Relevance → Format Response
```

## Modelo W5H

O Cortex usa o modelo **W5H** para estruturar memórias de forma agnóstica:

| Campo | Significado | Exemplo |
|-------|-------------|---------|
| WHO | Participantes | `["maria@email.com", "sistema_pagamentos"]` |
| WHAT | Ação/fato | `"reportou erro de pagamento"` |
| WHY | Causa/razão | `"cartão expirado"` |
| WHEN | Timestamp | `"2026-01-06T10:30:00"` |
| WHERE | Namespace | `"suporte_cliente"` |
| HOW | Resultado | `"orientada a atualizar dados"` |

### Por que W5H?

1. **Unifica** semantic/episodic/procedural em um modelo
2. **Explicita** causa (WHY) que normalmente fica implícita
3. **Organiza** por namespace (WHERE) naturalmente
4. **Agnóstico** de domínio (dev, chatbot, roleplay)

Ver detalhes em [W5H_DESIGN.md](W5H_DESIGN.md).

## Decaimento (Ebbinghaus) ✅

Implementado em `src/cortex/core/decay.py`.

Memórias seguem a **Curva de Esquecimento** de Ebbinghaus:

```
R = e^(-t/S)

Onde:
  R = retrievability (facilidade de recuperação)
  t = tempo desde último acesso (dias)
  S = stability (modificada por acessos, consolidação, centralidade)
```

### DecayManager

```python
from cortex.core import DecayManager, DecayConfig

config = DecayConfig(
    base_stability_days=7.0,      # Stability base em dias
    consolidation_bonus=2.0,      # Bonus para memórias consolidadas
    hub_bonus=1.5,                # Bonus para hubs
    high_importance_bonus=1.3,    # Bonus para importance > 0.7
    forgotten_threshold=0.1,      # Abaixo disso = esquecida
    hub_reference_threshold=5,    # 5+ referências = hub
)

manager = DecayManager(config)
retrievability = manager.calculate_retrievability(memory.last_accessed, memory.stability)
```

### Fatores que aumentam Stability:

| Fator | Bonus | Descrição |
|-------|-------|-----------|
| Access Count | `1 + log(access_count)` | Cada acesso reforça |
| Consolidação | `2.0x` | Memórias consolidadas são mais duráveis |
| Hub Centrality | `1.5x` | Memórias muito referenciadas decaem menos |
| High Importance | `1.3x` | Importância > 0.7 recebe bonus |

### Lifecycle de Memória:

```
Fresh (R > 0.7) → Stable (R > 0.4) → Fading (R > 0.1) → Forgotten
```

Memórias "forgotten" não são deletadas, apenas marcadas e excluídas de recalls normais.

---

## Shared Memory (Isolamento) ✅

Implementado em `src/cortex/core/shared_memory.py`.

### Níveis de Visibilidade

| Nível | Descrição | Exemplo |
|-------|-----------|---------|
| `personal` | Dados do usuário específico | "Nome: João", "Pedido #123" |
| `shared` | Visível a todos no namespace | "Política de devolução" |
| `learned` | Padrões aprendidos | "Clientes perguntam muito sobre X" |

### SharedMemoryManager

```python
from cortex.core import SharedMemoryManager

manager = SharedMemoryManager()

# Namespace pessoal do usuário
personal_ns = manager.get_personal_namespace("user_123")
# → "user:user_123"

# Para recall, combina personal + shared + learned
namespaces = manager.get_recall_namespaces("user_123")
# → ["user:user_123", "shared", "learned"]
```

### Casos de Uso

1. **Customer Support**: Agente atende múltiplos clientes, isola dados pessoais
2. **Dev Team**: Múltiplos devs compartilham conhecimento do projeto
3. **Healthcare**: Dados de pacientes estritamente isolados

## Consolidação Hierárquica ✅

### SleepRefiner (`src/cortex/workers/sleep_refiner.py`)

Consolida memórias em background, similar ao processo de consolidação durante o sono:

```
┌─────────────────────────────────────────────────────────┐
│  CONSOLIDADA (recall normal)                            │
│  "Cliente expressou gratidão após resolução"            │
│  is_summary=True, occurrence_count=15                   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  GRANULARES (só drill-down/rollback)            │   │
│  │  ├── "Carlos ligou com problema de modem"       │   │
│  │  ├── "Técnico verificou luz vermelha"           │   │
│  │  ├── "Problema era cabo desconectado"           │   │
│  │  └── "Carlos agradeceu"                         │   │
│  │  (consolidated_into → ID do resumo acima)       │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Campos de Consolidação em Memory:

| Campo | Descrição |
|-------|-----------|
| `consolidated_from` | IDs das memórias que originaram este resumo |
| `consolidated_into` | ID do resumo pai (se esta foi consolidada) |
| `is_summary` | True se é um resumo de consolidação |
| `is_consolidated` | Property: True se é pai (tem consolidated_from) |
| `was_consolidated` | Property: True se é filho (tem consolidated_into) |

### Decaimento Acelerado para Filhas

Memórias que JÁ FORAM consolidadas (`was_consolidated=True`) decaem **3x mais rápido**:

```python
# Memory.retrievability
if self.was_consolidated:
    consolidation_modifier = 0.33  # 3x mais rápido
```

Isso permite que o grafo se "limpe" naturalmente, mantendo apenas resumos e memórias recentes.

### Recall Inteligente

Por padrão, `recall()` **exclui memórias filhas** (já consolidadas):

```python
# MemoryGraph.recall()
if not include_consolidated:
    episodes = [ep for ep in episodes if not ep.metadata.get("consolidated_into")]
```

Para drill-down (buscar detalhes), use:
```python
result = graph.recall(query, context={"include_consolidated": True})
```

### Uso do SleepRefiner

```python
from cortex.workers import SleepRefiner

refiner = SleepRefiner()
result = refiner.refine(namespace="meu_agente")

print(f"Analisadas: {result.memories_analyzed}")
print(f"Refinadas: {result.memories_refined}")
print(f"Entidades: {result.entities_extracted}")
print(f"Padrões: {result.patterns_found}")
print(f"Resumo: {result.consolidated_summary}")
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

---

## SDK Python

O SDK fornece três níveis de abstração:

### 1. Core Genérico (`cortex_memory.py`)

Hooks simples para qualquer framework:

```python
from cortex_memory import CortexMemory

cortex = CortexMemory(namespace="meu_agente")

context = cortex.before(user_message)    # Busca memória
cortex.after(user_message, response)     # Armazena (W5H automático)
```

### 2. Adaptadores de Framework (`integrations/`)

Plug-and-play para frameworks populares:

```python
# LangChain
from cortex.integrations import CortexLangChainMemory
memory = CortexLangChainMemory(namespace="...")
chain = LLMChain(llm=llm, memory=memory)

# CrewAI
from cortex.integrations import CortexCrewAIMemory
memory = CortexCrewAIMemory(namespace="...")
crew = Crew(..., long_term_memory=memory)
```

### 3. Cliente REST (`cortex_sdk.py`)

Controle total sobre chamadas à API:

```python
from cortex_sdk import CortexClient

client = CortexClient(namespace="...")
memories = client.recall(query)
client.remember(who=[...], what="...", ...)
```

### Diagrama SDK

```
┌─────────────────────────────────────────────────────────────────┐
│                      SEU AGENTE LLM                              │
└─────────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Core Genérico  │  │   LangChain     │  │    CrewAI       │
│  before/after   │  │   BaseMemory    │  │  LongTermMemory │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┴────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   Cortex API    │
                    │   /memory/*     │
                    └─────────────────┘
```
