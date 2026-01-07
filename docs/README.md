# 📚 Documentação do Cortex

> **Sistema de Memória Cognitiva para Agentes LLM**

---

## 🛤️ Navegação por Jornada

| Você quer... | Comece aqui |
|--------------|-------------|
| **Usar rapidamente** | [Quick Start](./getting-started/quickstart.md) → [Integrações](./getting-started/integrations.md) |
| **Entender como funciona** | [Modelo W5H](./concepts/memory-model.md) → [Arquitetura](./architecture/overview.md) |
| **Contribuir/Pesquisar** | [Base Científica](./research/scientific-basis.md) → [Benchmarks](./research/benchmarks.md) |
| **Avaliar para negócio** | [Proposta de Valor](./business/value-proposition.md) → [Posicionamento](./business/competitive-position.md) |

---

## 📁 Estrutura

```
docs/
├── getting-started/        # ⚡ Início Rápido
│   ├── quickstart.md       # Do zero ao funcionando
│   └── integrations.md     # MCP, SDK, LangChain, CrewAI
│
├── concepts/               # 📚 Fonte Única de Verdade (D.R.Y.)
│   ├── memory-model.md     # Modelo W5H
│   ├── cognitive-decay.md  # Curva de Ebbinghaus
│   ├── consolidation.md    # DreamAgent e hierarquia
│   └── shared-memory.md    # Multi-tenant com isolamento
│
├── architecture/           # 🏗️ Visão Técnica
│   ├── overview.md         # Diagrama de camadas
│   └── api-reference.md    # Endpoints REST
│
├── research/               # 🔬 Fundamentação
│   ├── scientific-basis.md # Referências acadêmicas
│   └── benchmarks.md       # Resultados empíricos
│
├── business/               # 💰 Stakeholders
│   ├── value-proposition.md    # ROI e impacto
│   ├── competitive-position.md # vs RAG, VectorDB
│   └── roadmap.md              # Eras estratégicas
│
├── API.md                  # Referência REST (legado)
├── MCP.md                  # Integração MCP
└── PAPER_TEMPLATE.md       # Template do paper
```

---

## 📚 Conceitos Centrais

Estes documentos são a **fonte única de verdade** (D.R.Y.):

| Conceito | Arquivo | Descrição |
|----------|---------|-----------|
| **W5H** | [memory-model.md](./concepts/memory-model.md) | Who, What, Why, When, Where, How |
| **Ebbinghaus** | [cognitive-decay.md](./concepts/cognitive-decay.md) | Curva de esquecimento R = e^(-t/S) |
| **Consolidação** | [consolidation.md](./concepts/consolidation.md) | DreamAgent e hierarquia |
| **Shared Memory** | [shared-memory.md](./concepts/shared-memory.md) | Personal, Shared, Learned |

> Ao documentar, **referencie** estes conceitos. Não duplique.

---

## 🔗 Links Rápidos

- [README principal](../README.md)
- [API REST](./API.md)
- [MCP Tools](./MCP.md)
- [Benchmark](../benchmark/README.md)
- [SDK Python](../sdk/python/README.md)

---

*Índice de Documentação — Última atualização: Janeiro 2026*

