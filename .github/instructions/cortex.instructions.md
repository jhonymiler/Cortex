---
applyTo: "**"
---

# 🧠 Cortex - Instruções para Desenvolvimento

> **Sistema de Memória Cognitiva para Agentes LLM**  
> Versão: 3.0 | Janeiro 2026

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
└─ Consolida automaticamente
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
│   │   └── app.py         # Aplicação FastAPI
│   │
│   └── mcp/               # MCP Server (FastMCP)
│       └── server.py      # Servidor MCP
│
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

```python
# ✅ CORRETO
from pydantic import BaseModel      # Validação
from fastapi import FastAPI         # API REST
from fastmcp import FastMCP         # MCP Server

# ❌ ERRADO - Reinventar a roda
class MyCustomValidator: ...
class MyHttpServer: ...
```

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

### POST /memory/store
Armazena um episódio após interação.

### POST /memory/recall
Busca memórias relevantes antes de responder.

### GET /memory/stats
Estatísticas do grafo.

### DELETE /memory/clear
Limpa todas as memórias (com cuidado!).

---

## 🎭 MCP TOOLS

### cortex_recall
**OBRIGATÓRIO antes de responder ao usuário.**

### cortex_store
**OBRIGATÓRIO após responder ao usuário.**

### cortex_stats
Estatísticas do grafo.

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

*Última atualização: 05 de Janeiro de 2026*
