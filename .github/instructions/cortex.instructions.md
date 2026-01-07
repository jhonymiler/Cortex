---
applyTo: "**"
---

# 🧠 Cortex - Instruções para Desenvolvimento

> **Sistema de Memória Cognitiva para Agentes LLM**  
> Versão: 3.0 | Janeiro 2026

## Regras
 - Sempre entrar no ambiente virtual (`source venv/bin/activate`)
 - Sempre comitar depois de confirmado o funcionamento de uma nova feature
 - Sempre atualizar as documentações
 - NUNCA usar old MCP - apenas FastMCP (decorator-based)
 - Cortex NÃO é RAG nem VectorDB - é memória semântica baseada em grafo
 - Busca é O(1) por índice - ZERO tokens, sem embeddings
 - Nunca crie arquivos duplicados, lixo.
 - Sempre edite os arquivos mantendo a organização e arquitetura, se for necessário criar um arquivo novo, o antigo deve ser deletado.

## 📚 DOCUMENTAÇÃO DE REFERÊNCIA

**SEMPRE consulte estas documentações antes de implementar:**

- **[VISION.md](../../../docs/VISION.md)** - Filosofia, conceitos, princípios fundamentais
- **[ARCHITECTURE.md](../../../docs/ARCHITECTURE.md)** - Estrutura de camadas, fluxo de dados, consolidação
- **[API.md](../../../docs/API.md)** - Endpoints REST, payloads, exemplos
- **[MCP.md](../../../docs/MCP.md)** - Integração MCP, tools, configuração Claude Desktop
- **[DEVELOPMENT.md](../../../DEVELOPMENT.md)** - Guia de desenvolvimento, setup, decisões técnicas

**Estrutura de Pastas Importantes:**
- `sdk/python/` - SDK Python para clientes
- `sdk/typescript/` - SDK TypeScript (futuro)
- `teste-llm/` - Testes com Ollama (usa sdk/python/)
- `src/cortex/` - Código principal do Cortex

---

## 🎯 CONTEXTO DE CRIAÇÃO

### Origem (Janeiro 2026)
Criado em **5 de Janeiro de 2026** a partir de discussões sobre CME2 (PHP).

**Problema no CME2:**
- ❌ Era usado como "repositório de texto" (código completo, logs, docs)
- ✅ Deveria ser: memória semântica (significado, aprendizados, padrões)

**Decisão:**
> "Cortex deve ser como memória HUMANA - não lembra texto literal, lembra significado e consolida experiências"

### Por que Python?
1. FastMCP disponível (integração Claude Desktop)
2. Ferramentas melhores para MCP
3. Comunidade Python para LLM mais ativa

### Relação com CME2
- **CME2 (PHP)**: Validado com 79.82% economia, servidor REST standalone
- **Cortex (Python)**: Novo projeto, MCP + REST, integração Claude Desktop
- **Status**: Complementares, não substitutos

---

## 📋 VISÃO GERAL

### O que é o Cortex

Cortex é um **sistema de memória semântica agnóstico** para agentes LLM que:

- **Armazena SIGNIFICADO**, não texto bruto
- **Memória baseada em Entidades, Episódios e Relações**
- **Busca por relevância contextual**, não similaridade vetorial
- **Consolida memórias repetidas** automaticamente
- **Agnóstico de domínio** — funciona para dev, roleplay, chatbot, assistente

### Princípio Fundamental

**Cortex NÃO é RAG nem VectorDB**

| Aspecto | RAG/VectorDB | Cortex |
|---------|--------------|--------|
| Armazena | Documentos + embeddings | Fatos semânticos estruturados |
| Busca | Similaridade vetorial | Índice O(1) |
| Custo busca | Tokens (embedding) | Zero tokens |
| Estrutura | Texto não estruturado | Entity-Episode-Relation |

**Memória Humana vs Cortex:**

```
MEMÓRIA HUMANA:
├─ Não lembra de tudo literalmente
├─ Lembra do SIGNIFICADO e CONTEXTO
├─ Associa memórias por RELEVÂNCIA
└─ Consolida experiências repetidas

CORTEX:
├─ Armazena Entidades (o quê/quem)
├─ Armazena Episódios (o que aconteceu)
├─ Armazena Relações (como se conectam)
└─ Consolida automaticamente (5+ similares → padrão)
```

---

## 🏗️ ARQUITETURA

### Estrutura de Pastas

```
cortex/
├── src/cortex/
│   ├── core/              # Modelos de domínio (sem I/O)
│   │   ├── entity.py      # Entidade (qualquer "coisa")
│   │   ├── episode.py     # Episódio (qualquer "acontecimento")
│   │   ├── relation.py    # Relação (conexão entre coisas)
│   │   └── memory_graph.py # Grafo de memória
│   │
│   ├── services/          # Lógica de negócio
│   │   └── memory_service.py  # Orquestrador principal
│   │
│   ├── api/               # API REST (FastAPI)
│   │   └── app.py         # Endpoints + /memory/interact
│   │
│   └── mcp/               # MCP Server (FastMCP)
│       └── server.py      # Servidor MCP
│
├── sdk/python/            # SDK Python para clientes
│   ├── cortex_sdk.py      # Cliente REST baixo-nível
│   ├── cortex_memory.py   # Core genérico (before/after hooks)
│   └── integrations/      # Adaptadores para frameworks
│       ├── langchain.py   # LangChain BaseMemory
│       └── crewai.py      # CrewAI long_term_memory
│
├── benchmark/             # Sistema de benchmark
├── tests/                 # Testes
├── docs/                  # Documentação
└── pyproject.toml         # Configuração do projeto
```

### Camadas

```
┌─────────────────────────────────────────────────────────┐
│                    API / MCP                            │
│              (Pontos de entrada)                        │
├─────────────────────────────────────────────────────────┤
│                    Services                             │
│              (Lógica de negócio)                        │
├─────────────────────────────────────────────────────────┤
│                    Core                                 │
│           (Modelos + MemoryGraph)                       │
└─────────────────────────────────────────────────────────┘
```

---

## 📚 MODELOS DE DOMÍNIO

### Entity (Entidade)

Representa qualquer "coisa" mencionada — **agnóstico de domínio**.

```python
@dataclass
class Entity:
    id: str                    # UUID
    type: str                  # Livre: "person", "file", "character"...
    name: str                  # Nome legível
    identifiers: list[str]     # Formas de reconhecer
    attributes: dict           # Metadados flexíveis
    access_count: int          # Reforço por uso
```

**Exemplos por domínio:**
```python
# Dev
Entity(type="file", name="apache.log", identifiers=["sha256:abc"])

# Roleplay  
Entity(type="character", name="Elena", identifiers=["vampire_queen"])

# Chatbot
Entity(type="customer", name="Maria", identifiers=["maria@email.com"])
```

### Episode (Episódio)

Representa qualquer "acontecimento" — **agnóstico de domínio**.

```python
@dataclass
class Episode:
    id: str
    action: str                # Verbo: "analyzed", "met", "resolved"
    participants: list[str]    # IDs das entidades envolvidas
    context: str               # Situação/cenário
    outcome: str               # Resultado
    occurrence_count: int      # Quantas vezes similar ocorreu
    is_consolidated: bool      # Se é padrão consolidado
```

### Relation (Relação)

Representa qualquer "conexão" — **agnóstico de domínio**.

```python
@dataclass
class Relation:
    from_id: str               # Entity/Episode ID
    relation_type: str         # Livre: "caused_by", "loves", "resolved"
    to_id: str                 # Entity/Episode ID
    strength: float            # 0.0 - 1.0 (reforça com uso)
```

---

## 🔧 REGRAS DE CÓDIGO

### 1. Use Bibliotecas Renomadas

**NUNCA reinventar a roda - usar bibliotecas maduras:**

```python
# ✅ CORRETO
from pydantic import BaseModel      # Validação
from fastapi import FastAPI         # API REST
from fastmcp import FastMCP         # MCP Server (DECORATOR-BASED)

# ❌ ERRADO - Reinventar a roda
class MyCustomValidator: ...
class MyHttpServer: ...

# ❌ ERRADO - Old MCP (verboso)
from mcp import Server
server = Server("cortex")
```

**Por que FastMCP?**
- Decorator-based (moderno, limpo)
- Integração nativa com Claude Desktop
- Menos boilerplate

### 2. Separação Clara de Camadas

```python
# ✅ CORRETO
# core/ → Modelos puros (sem I/O externo)
# services/ → Lógica de negócio
# api/ → Entrada HTTP
# mcp/ → Entrada MCP

# ❌ ERRADO - Misturar responsabilidades
class Entity:
    def save_to_database(self): ...  # Modelo não faz I/O!
```

### 3. API e MCP Compartilham Service

```python
# services/memory_service.py - Lógica única
class MemoryService:
    def store(self, request: StoreRequest) -> StoreResponse: ...
    def recall(self, request: RecallRequest) -> RecallResponse: ...

# api/app.py - Usa o service
@app.post("/memory/store")
def store(request: StoreRequest, service = Depends(get_service)):
    return service.store(request)

# mcp/server.py - Usa o MESMO service
@mcp.tool()
def cortex_store(...) -> dict:
    return service.store(StoreRequest(...)).model_dump()
```

### 4. Type Hints Obrigatórios

```python
# ✅ CORRETO
def find_entity(name: str, limit: int = 10) -> list[Entity]:
    ...

# ❌ ERRADO
def find_entity(name, limit=10):
    ...
```

### 5. Docstrings em Tudo

```python
# ✅ CORRETO
def recall(self, query: str, context: dict) -> RecallResult:
    """
    Busca memórias relevantes para uma query.
    
    Args:
        query: Texto para buscar
        context: Contexto adicional para filtrar
    
    Returns:
        RecallResult com entidades, episódios e relações
    """
```

### 6. Serialização via Pydantic

```python
# ✅ CORRETO - Pydantic para I/O
class StoreRequest(BaseModel):
    action: str
    outcome: str
    participants: list[ParticipantInput] = []

# Dataclasses para domínio interno
@dataclass
class Episode:
    action: str
    outcome: str
```

---

## 🚨 O QUE NÃO FAZER

### 1. Nunca armazenar texto bruto grande

```python
# ❌ PROIBIDO
episode = Episode(context="Aqui estão 10.000 linhas de log: ...")

# ✅ CORRETO
episode = Episode(
    action="analyzed_log",
    outcome="found 3 errors, cause: missing route"
)
```

### 2. Nunca usar embeddings/vectors

```python
# ❌ PROIBIDO - Cortex não é RAG
results = vector_db.similarity_search(embedding)

# ✅ CORRETO - Busca por grafo
results = graph.recall(query, context)
```

### 3. Nunca duplicar entidades

```python
# ❌ PROIBIDO
entity1 = Entity(name="João", identifiers=["joao@email.com"])
entity2 = Entity(name="João Silva", identifiers=["joao@email.com"])

# ✅ CORRETO - Usar resolve_entity
entity = graph.resolve_entity(name="João", identifiers=["joao@email.com"])
# Retorna existente se identifier já existe
```

### 4. Nunca enviessar para um domínio

```python
# ❌ PROIBIDO - Termos específicos de dev
class ProjectFile(Entity): ...
class DebugSession(Episode): ...

# ✅ CORRETO - Termos genéricos
Entity(type="file", ...)  # type é livre
Episode(action="analyzed", ...)  # action é livre
```

---

## 📋 API ENDPOINTS

### POST /memory/remember (W5H)
Armazena memória usando modelo W5H.

```python
{
    "who": ["user", "FastAPI"],
    "what": "asked_about_routing",
    "why": "building_web_app",
    "how": "explained_decorators",
    "where": "namespace"
}
```

### POST /memory/recall
Busca memórias relevantes antes de responder.

### POST /memory/interact
Endpoint completo: recall + store em uma chamada (para SDK).

### GET /memory/stats
Estatísticas do grafo.

### DELETE /memory/clear
Limpa todas as memórias (com cuidado!).

---

## 🎭 MCP TOOLS

### cortex_recall
**OBRIGATÓRIO antes de responder ao usuário.**

### cortex_remember (W5H)
**OBRIGATÓRIO após responder ao usuário.**

```python
cortex_remember(
    who=["user", "FastAPI"],
    what="asked_about_routing",
    why="building_web_app",
    how="explained_decorators",
    where="namespace"
)
```

### cortex_stats
Estatísticas do grafo.

---

## 🔌 SDK PYTHON

### Arquitetura Core + Adaptadores

```
CortexMemory (Core Genérico)
    ├── before(user_message) → contexto
    └── after(user_message, response) → store
         │
         ├── LangChain Adapter (BaseMemory)
         ├── CrewAI Adapter (long_term_memory)
         └── @with_memory decorator (qualquer função)
```

### Uso Direto (Decorator)

```python
from cortex_memory import with_memory

@with_memory(namespace="meu_agente")
def meu_agente(user_message: str, context: str = "") -> str:
    # context já contém memórias relevantes
    return f"Resposta para: {user_message}"
```

### LangChain

```python
from integrations.langchain import CortexLangChainMemory

memory = CortexLangChainMemory(namespace="langchain_agent")
chain = ConversationChain(llm=llm, memory=memory)
```

### CrewAI

```python
from integrations.crewai import CortexCrewAIMemory

crew = Crew(
    agents=[...],
    long_term_memory=CortexCrewAIMemory(namespace="crewai_agent")
)
```

---

## 🔄 FLUXO OBRIGATÓRIO

```
1. USUÁRIO envia mensagem
        ↓
2. AGENTE chama cortex_recall(query=mensagem)
        ↓
3. CORTEX retorna contexto relevante
        ↓
4. AGENTE processa (com contexto)
        ↓
5. AGENTE responde ao usuário
        ↓
6. AGENTE chama cortex_store(action, outcome, ...)
        ↓
7. CORTEX armazena e consolida
```

---

## 🧪 TESTES

### Cobertura Atual

```
tests/
├── test_core.py               # Entity, Episode, Relation
├── test_memory_service.py     # MemoryService completo
│   ├── TestStoreValidation
│   ├── TestRecallBasic
│   ├── TestConsolidation
│   ├── TestPydanticModels
│   ├── TestEdgeCases
│   └── TestIntegration
└── conftest.py                # Fixtures compartilhadas
```

### Estrutura

```python
# tests/test_memory_service.py
def test_store_creates_episode():
    service = MemoryService()
    result = service.store(StoreRequest(
        action="test_action",
        outcome="test_outcome"
    ))
    assert result.success
    assert result.episode_id is not None

def test_recall_finds_related():
    ...

def test_consolidation_merges_similar():
    ...
```

### Rodar Testes

```bash
pytest tests/ -v
```

---

## 🚀 COMANDOS ÚTEIS

```bash
# Instalar dependências
pip install -e ".[all,dev]"

# Rodar API REST
cortex-api
# ou
uvicorn cortex.api.app:app --reload

# Rodar MCP Server
cortex-mcp

# Testes
pytest tests/ -v

# Lint
ruff check src/

# Formatar
ruff format src/
```

---

## 📝 REGRAS DE COMMIT

```
feat: nova funcionalidade
fix: correção de bug
docs: documentação
refactor: refatoração sem mudar comportamento
test: adicionar/modificar testes
```

---

## 📊 STATUS DO PROJETO

### Completo ✅
- Core models (Entity, Memory/Episode, Relation, MemoryGraph)
- MemoryService (store, recall, consolidation)
- **DecayManager** (Ebbinghaus decay + hub protection)
- **SharedMemoryManager** (isolamento personal/shared/learned)
- **SleepRefiner** (consolidação em background com LLM)
- **Consolidação Hierárquica** (resumo → granulares, filhas decaem 3x mais rápido)
- API REST com endpoints W5H + /memory/interact + PATCH /memory/episode/{id}
- MCP Server (cortex_recall, cortex_remember, cortex_forget, cortex_stats)
- SDK Python (Core + Adaptadores LangChain/CrewAI) com extração [MEMORY]
- CortexAgent otimizado (-50% chamadas LLM, extração inline)
- Benchmark científico completo:
  - Métricas: Precision@K, Recall@K, MRR, Consistency
  - Baselines: RAG (TF-IDF), Mem0
  - Ablation Study (8 variantes)
  - Shared Memory Benchmark
  - Resultado: **-12.5% tokens vs baseline**
- Documentação completa
- Variáveis de ambiente normalizadas (.env)

### Próximos Passos 🎯
1. Adicionar adaptador Google ADK
2. Adicionar adaptador FastAgent
3. Dashboard com visualização de retrievability
4. SleepRefiner com suporte multi-cliente (PERSONAL vs LEARNED)
5. Paper científico com resultados do benchmark

---

## 🔑 CONCEITOS-CHAVE

### Consolidação Hierárquica
```python
# SleepRefiner cria hierarquia pai/filho:

# RESUMO (pai) - retornado no recall normal
Memory(
    what="Cliente_resolveu_problemas_pagamento",
    is_summary=True,
    consolidated_from=["id1", "id2", "id3"],
    occurrence_count=3
)

# GRANULARES (filhas) - só drill-down/rollback
Memory(id="id1", what="erro_cartao", consolidated_into="resumo_id")
Memory(id="id2", what="expirou_data", consolidated_into="resumo_id")
Memory(id="id3", what="taxa_incorreta", consolidated_into="resumo_id")
# Filhas decaem 3x mais rápido (consolidation_modifier=0.33)
# Filhas são excluídas do recall normal
```

### SleepRefiner (Consolidação em Background)
```python
from cortex.workers import SleepRefiner

refiner = SleepRefiner()
result = refiner.refine(namespace="meu_agente")
# Analisa memórias → extrai padrões → cria resumos → marca originais
```

### Busca sem Tokens
```python
# ❌ RAG/VectorDB: custo por busca
embedding = llm.embed(query)  # $$$ tokens
results = db.similarity_search(embedding)

# ✅ Cortex: zero tokens
entity = graph.find_entity_by_name("user")  # O(1) índice
episodes = graph.get_episodes_by_participant(entity.id)
```

### Domain-Agnostic
```python
# Desenvolvimento
Entity(type="file", name="auth.py")
Episode(action="debugged", outcome="bug fixed")

# Roleplay
Entity(type="character", name="Gandalf")
Episode(action="cast_spell", outcome="defeated Balrog")

# Chatbot
Entity(type="customer", name="Maria")
Episode(action="resolved_issue", outcome="ticket closed")
```

---

*Última atualização: 07 de Janeiro de 2026*
