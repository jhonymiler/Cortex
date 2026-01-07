# 🧠 Cortex - Cursor Rules

> **Sistema de Memória Cognitiva para Agentes LLM**  
> Versão: 3.1 | Janeiro 2026 | Modelo W5H

---

## 📚 Documentação Modular

A documentação do Cortex é organizada em **módulos independentes** seguindo o princípio D.R.Y.:

| Categoria | Documentos |
|-----------|------------|
| **Início Rápido** | [quickstart.md](../../docs/getting-started/quickstart.md), [integrations.md](../../docs/getting-started/integrations.md) |
| **Conceitos** | [memory-model.md](../../docs/concepts/memory-model.md), [cognitive-decay.md](../../docs/concepts/cognitive-decay.md), [consolidation.md](../../docs/concepts/consolidation.md), [shared-memory.md](../../docs/concepts/shared-memory.md) |
| **Arquitetura** | [overview.md](../../docs/architecture/overview.md), [api-reference.md](../../docs/architecture/api-reference.md) |
| **Pesquisa** | [scientific-basis.md](../../docs/research/scientific-basis.md), [benchmarks.md](../../docs/research/benchmarks.md) |
| **Negócio** | [value-proposition.md](../../docs/business/value-proposition.md), [roadmap.md](../../docs/business/roadmap.md) |

---

## 📋 REGRAS GERAIS

### Ambiente
- **SEMPRE** ativar venv antes de qualquer comando: `source venv/bin/activate`
- **SEMPRE** comitar após confirmar funcionamento de feature
- **NUNCA** criar arquivos duplicados ou lixo
- **SEMPRE** responder em português
- **SEMPRE** atualizar documentações (referenciar, não duplicar)
- **SEMPRE** realizar testes unitários

### Arquitetura
- Cortex **NÃO é RAG** nem VectorDB
- Memória baseada em **grafo semântico** (Entity-Memory-Relation)
- Busca por **índice O(1)** - ZERO tokens, sem embeddings
- Usar apenas **FastMCP** (decorator-based) - NUNCA old MCP

---

## 🚀 COMANDOS ÚTEIS

### Desenvolvimento

```bash
# Setup
pip install -e ".[all,dev]"

# Serviços
cortex-api                    # API REST
cortex-mcp                    # MCP Server

# Testes
pytest tests/ -v

# Lint
ruff check src/
ruff format src/
```

### Benchmark

```bash
# Rápido (~10 min)
./start_benchmark.sh --quick

# Completo (~1 hora)
./start_benchmark.sh --full

# Análise
./analyze_results.sh
```

---

## 📁 ESTRUTURA

```
cortex/
├── src/cortex/
│   ├── core/              # Modelos puros (sem I/O)
│   │   ├── entity.py      # Entidade + centrality_score
│   │   ├── memory.py      # Memory W5H
│   │   ├── relation.py    # Relação
│   │   ├── memory_graph.py
│   │   ├── decay.py       # DecayManager (Ebbinghaus)
│   │   └── shared_memory.py # SharedMemoryManager
│   ├── services/          # MemoryService
│   ├── api/               # FastAPI REST
│   ├── mcp/               # FastMCP Server
│   └── workers/           # DreamAgent
│
├── sdk/python/            # SDK Python
│   ├── cortex_sdk.py      # Cliente REST
│   ├── cortex_memory.py   # Core genérico
│   └── integrations/      # LangChain, CrewAI
│
├── benchmark/             # Sistema de benchmark
│   ├── cortex_agent.py    # CortexAgent
│   ├── rag_agent.py       # RAG Baseline
│   ├── mem0_agent.py      # Mem0 Baseline
│   └── scientific_metrics.py
│
├── docs/                  # Documentação modular
│   ├── getting-started/   # Quickstart, Integrações
│   ├── concepts/          # W5H, Decay, Consolidation
│   ├── architecture/      # Overview, API
│   ├── research/          # Scientific basis, Benchmarks
│   └── business/          # Value prop, Roadmap
│
└── tests/                 # Testes unitários
```

---

## 🔬 MODELO W5H

> Ver documentação completa: [docs/concepts/memory-model.md](../../docs/concepts/memory-model.md)

| Campo | Descrição |
|-------|-----------|
| WHO | Participantes (entidades) |
| WHAT | O que aconteceu |
| WHY | Por quê |
| WHEN | Quando |
| WHERE | Namespace |
| HOW | Resultado |

---

## 📊 MÉTRICAS

| Métrica | Descrição |
|---------|-----------|
| Precision@K | Relevantes / K |
| Recall@K | Recuperados / Total |
| MRR | Mean Reciprocal Rank |
| Consistency | Coerência entre sessões |

---

## 📝 COMMITS

```
feat: nova funcionalidade
fix: correção de bug
docs: documentação
refactor: sem mudar comportamento
test: testes
bench: benchmark
```

---

## 🎯 STATUS DO PROJETO

### ✅ Completo
- Core models (Entity, Memory, Relation, MemoryGraph)
- MemoryService + DecayManager + SharedMemoryManager
- SDK Python (Core + LangChain + CrewAI)
- DreamAgent (consolidação hierárquica)
- Benchmark científico
- Documentação modular

### 🔜 Próximo
- Google ADK Adapter
- FastAgent Adapter
- PostgreSQL backend
- Dashboard de visualização

---

*Última atualização: Janeiro 2026*
