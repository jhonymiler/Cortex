# Development Guide - Cortex Python

## 📍 Contexto de Criação (Janeiro 2026)

### Origem
Projeto criado em **5 de Janeiro de 2026** a partir de discussões sobre CME2 (PHP).

### Problema Identificado no CME2
CME2 estava sendo usado como "repositório de texto" em vez de **memória semântica real**:
- ❌ Armazenando código completo, logs, documentos
- ✅ Deveria armazenar: significado, aprendizados, padrões

### Decisão Arquitetural
> **"Cortex deve ser como memória HUMANA"**
> - Não lembra texto literal revisado
> - Lembra: "revisei X, tinha bug Y, corrigi com Z, resultado W"
> - Consolida experiências repetidas em padrões

### Por que Python?
1. **FastMCP** disponível (integração Claude Desktop)
2. Ferramentas melhores para MCP
3. Comunidade Python para LLM mais ativa
4. Novo projeto = arquitetura limpa

---

## 🏗️ Arquitetura

### Princípio Fundamental
**Cortex NÃO é RAG nem VectorDB**

| Aspecto | RAG/VectorDB | Cortex |
|---------|--------------|--------|
| Armazena | Documentos + embeddings | Fatos semânticos estruturados |
| Busca | Similaridade vetorial | Índice O(1) |
| Custo busca | Tokens (embedding) | Zero tokens |
| Estrutura | Texto não estruturado | Entity-Episode-Relation |

### Core Models

#### Entity (Entidade)
```python
Entity(
    type="person",           # Tipo livre (person, file, concept)
    name="João Silva",       # Nome principal
    identifiers=["email@x"], # IDs alternativos
    attributes={}            # Dados adicionais
)
```

#### Episode (Experiência)
```python
Episode(
    action="debugged",                    # O que foi feito
    participants=["entity_1", "entity_2"], # Quem participou
    context="fixing authentication",      # Contexto
    outcome="bug fixed"                   # Resultado
)
```

#### Relation (Conexão)
```python
Relation(
    from_id="bug_123",
    relation_type="caused_by",
    to_id="token_expiry",
    strength=0.9
)
```

### MemoryGraph
Armazena e indexa tudo:
```python
# Índices O(1):
self._entities_by_name: dict[str, Entity]
self._episodes: list[Episode]
self._relations: list[Relation]
```

---

## 🔄 Fluxo de Uso

### 1. Recall (ANTES de responder)
```python
result = service.recall(
    query="Help with Python auth",
    entities=["user", "authentication"]
)
# Retorna: entidades relacionadas + episódios passados + relações
```

### 2. Agente processa e responde

### 3. Store (DEPOIS de responder)
```python
service.store(
    entities=[
        EntityInput(type="issue", name="Auth Bug #123")
    ],
    episodes=[
        EpisodeInput(
            action="fixed",
            participants=["user", "Auth Bug #123"],
            outcome="Token refresh implemented"
        )
    ]
)
```

---

## 🎯 Decisões Técnicas

### 1. FastMCP (não old MCP)
```python
# ✅ Escolhido: decorator-based, moderno
mcp = FastMCP("cortex")

@mcp.tool()
async def cortex_store(...):
    ...

# ❌ Rejeitado: old MCP (verboso)
server = Server("cortex")
@server.call_tool()
```

### 2. Single MemoryService
MCP e API compartilham **mesma lógica**:
```python
# services/memory_service.py
class MemoryService:
    def store(...) -> StoreResponse: ...
    def recall(...) -> RecallResponse: ...

# mcp/server.py
service = MemoryService()
@mcp.tool()
async def cortex_store(...):
    return service.store(...)

# api/app.py
service = MemoryService()
@app.post("/memory/store")
async def store(...):
    return service.store(...)
```

### 3. Pydantic para Validação
```python
class StoreRequest(BaseModel):
    entities: list[EntityInput]
    episodes: list[EpisodeInput]
    relations: list[RelationInput] = []
```

### 4. Consolidação Automática
```python
# Se 5+ episódios similares → mescla em padrão
if len(similar_episodes) >= 5:
    consolidate_into_pattern()
```

### 5. Busca sem LLM
```python
# O(1) por índice, zero tokens
def find_entity_by_name(name: str) -> Entity | None:
    return self._entities_by_name.get(name.lower())
```

---

## 🚀 Setup e Uso

### Instalação
```bash
cd /home/jhony/Documentos/projetos/IA/memorias/cortex
pip install -e ".[all,dev]"
```

### Testes
```bash
pytest tests/ -v
```

### MCP Server (Claude Desktop)
```bash
cortex-mcp
```

### API REST
```bash
cortex-api
# ou
uvicorn cortex.api.app:app --reload
```

---

## 📂 Estrutura de Arquivos

```
cortex/
├── src/cortex/
│   ├── core/
│   │   ├── entity.py           # Entity model
│   │   ├── episode.py          # Episode model
│   │   ├── relation.py         # Relation model
│   │   └── memory_graph.py     # Storage + índices
│   ├── services/
│   │   └── memory_service.py   # 🎯 Orquestrador único
│   ├── mcp/
│   │   └── server.py           # FastMCP (3 tools + 1 resource)
│   └── api/
│       └── app.py              # FastAPI (4 endpoints)
├── tests/
│   ├── test_core.py            # Entity, Episode, Relation
│   ├── test_memory_service.py  # MemoryService
│   └── conftest.py             # Fixtures
├── docs/
│   ├── ARCHITECTURE.md         # Arquitetura detalhada
│   ├── API.md                  # Referência API REST
│   ├── MCP.md                  # Integração MCP
│   └── VISION.md               # Filosofia e conceitos
└── .github/
    └── instructions/
        └── cortex.instructions.md  # Regras Copilot
```

---

## 🧪 Testes Criados

### test_core.py
- `TestEntity`: create, matches, serialization
- `TestEpisode`: create, serialization
- `TestRelation`: create, serialization

### test_memory_service.py
- `TestStoreValidation`
- `TestRecallBasic`
- `TestConsolidation`
- `TestPydanticModels`
- `TestEdgeCases`
- `TestIntegration`

---

## 🔗 Relação com CME2

| Aspecto | CME2 (PHP) | Cortex (Python) |
|---------|------------|-----------------|
| **Status** | Validado (79.82% economia) | Novo, não testado |
| **Arquitetura** | REST API standalone | MCP + REST API |
| **Uso** | Servidor independente | Integração Claude Desktop |
| **Linguagem** | PHP | Python |
| **Target** | Qualquer LLM | Claude Desktop via MCP |

**Cortex NÃO substitui CME2** - são complementares:
- CME2: Servidor PHP para qualquer LLM via HTTP
- Cortex: Integração nativa MCP para Claude

---

## ✅ Status Atual (5 Jan 2026)

### Completo
- ✅ 23 arquivos criados
- ✅ Git inicializado (commit `0d8b2fb`)
- ✅ Documentação completa
- ✅ Testes escritos
- ✅ pyproject.toml configurado

### Pendente
- ⏳ `pip install -e ".[all,dev]"` (não executado)
- ⏳ `pytest tests/ -v` (não validado)
- ⏳ Teste MCP real
- ⏳ Teste API real
- ⏳ Integração Claude Desktop

---

## 🎓 Conceitos-Chave

### Domain-Agnostic
Entity `type` e `name` são **strings livres**:
- Desenvolvimento: `type="file"`, `name="auth.py"`
- Roleplay: `type="character"`, `name="Gandalf"`
- Chatbot: `type="user"`, `name="customer_123"`

### Consolidação
5+ episódios similares viram **padrão**:
```python
# Antes:
Episode("user forgot password") x5

# Depois (consolidado):
Episode("password reset pattern", occurrence_count=5)
```

### Sem LLM na Busca
```python
# ❌ RAG/VectorDB: LLM para cada busca (tokens $$$)
embedding = llm.embed(query)
results = db.similarity_search(embedding)

# ✅ Cortex: índice (zero tokens)
entity = graph.find_entity_by_name("user")
```

---

## 📝 Próximos Passos

1. **Validar instalação**: `pip install -e ".[all,dev]"`
2. **Rodar testes**: `pytest tests/ -v`
3. **Testar MCP**: configurar em `claude_desktop_config.json`
4. **Benchmark**: comparar com CME2 (se aplicável)
5. **Iteração**: ajustar baseado em uso real
