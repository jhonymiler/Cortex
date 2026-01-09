# 🧠 Cortex

> **Sistema de Memória Cognitiva para Agentes LLM**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## ⚡ Quick Start (2 minutos)

```bash
pip install -e "."
cortex-api &
```

```python
from cortex_memory import with_memory

@with_memory(namespace="meu_agente")
def agent(msg, context=""):
    return meu_llm.generate(context + msg)
```

[→ Instalação completa](docs/getting-started/quickstart.md)

---

## 🛤️ Escolha sua Jornada

| Você quer... | Comece aqui |
|--------------|-------------|
| **Usar o Cortex** | [Quick Start](docs/getting-started/quickstart.md) → [Integrações](docs/getting-started/integrations.md) |
| **Entender como funciona** | [Modelo W5H](docs/concepts/memory-model.md) → [Arquitetura](docs/architecture/overview.md) |
| **Contribuir/Pesquisar** | [Base Científica](docs/research/scientific-basis.md) → [Benchmarks](docs/research/benchmarks.md) |
| **Avaliar para negócio** | [Proposta de Valor](docs/business/value-proposition.md) → [Posicionamento](docs/business/competitive-position.md) |

---

## 📊 Resultados (Benchmark Unificado)

| Dimensão | Baseline | RAG | Mem0 | **Cortex** |
|----------|----------|-----|------|------------|
| Cognição Biológica | 0% | 0% | 0% | **50%** |
| Memória Coletiva | 0% | 0% | 0% | **75%** |
| Valor Semântico | 50% | 100% | 100% | **100%** |
| Eficiência | 0% | 0% | 0% | **100%** |
| **TOTAL** | 20% | 40% | 40% | **83%** |

🏆 **Cortex supera melhor alternativa em +43.3%**

```bash
# Rodar benchmark
./start_benchmark.sh
```

> O benchmark mede 4 dimensões de valor que nenhuma alternativa suporta:
> cognição biológica, memória coletiva, valor semântico e eficiência.

[→ Ver benchmark completo](docs/research/benchmarks.md)

---

## 🎯 O Problema

Agentes LLM sofrem de **amnésia crônica**:

```
❌ SEM CORTEX                    ✅ COM CORTEX
─────────────────────────────────────────────────
"Qual seu nome?"                 "Olá João! Como 
"Qual seu nome?"                  está o problema
"Qual seu nome?" (10x)            do login?"
```

[→ Ver casos de uso](docs/business/value-proposition.md#casos-de-uso-por-indústria)

---

## 🔌 Integrações

### MCP (Claude Desktop)

```json
{
  "mcpServers": {
    "cortex": { "command": "cortex-mcp" }
  }
}
```

### SDK Python

```python
# LangChain
from cortex.integrations import CortexLangChainMemory
chain = ConversationChain(llm=llm, memory=CortexLangChainMemory())

# CrewAI
from cortex.integrations import CortexCrewAIMemory
crew = Crew(long_term_memory=CortexCrewAIMemory())
```

[→ Ver todas integrações](docs/getting-started/integrations.md)

---

## 📚 Documentação

### Para Usuários

| Documento | Descrição |
|-----------|-----------|
| [Quick Start](docs/getting-started/quickstart.md) | Do zero ao funcionando |
| [Integrações](docs/getting-started/integrations.md) | MCP, SDK, REST |

### Conceitos

| Documento | Descrição |
|-----------|-----------|
| [Modelo W5H](docs/concepts/memory-model.md) | Como memórias são estruturadas |
| [Decaimento](docs/concepts/cognitive-decay.md) | Curva de Ebbinghaus |
| [Consolidação](docs/concepts/consolidation.md) | DreamAgent e hierarquia |
| [Shared Memory](docs/concepts/shared-memory.md) | Multi-tenant |

### Arquitetura

| Documento | Descrição |
|-----------|-----------|
| [Overview](docs/architecture/overview.md) | Visão técnica |
| [API](docs/API.md) | Endpoints REST |
| [MCP](docs/MCP.md) | Tools MCP |

### Pesquisa

| Documento | Descrição |
|-----------|-----------|
| [Base Científica](docs/research/scientific-basis.md) | Fundamentação |
| [Benchmarks](docs/research/benchmarks.md) | Resultados |
| [Paper](docs/PAPER_TEMPLATE.md) | Template do paper |

### Negócio

| Documento | Descrição |
|-----------|-----------|
| [Proposta de Valor](docs/business/value-proposition.md) | ROI e impacto |
| [Posicionamento](docs/business/competitive-position.md) | vs RAG, VectorDB |
| [Roadmap](docs/business/roadmap.md) | Visão estratégica |

---

## 🧪 Testes

```bash
# Unitários
pytest tests/ -v

# Benchmark
./start_benchmark.sh --quick
```

---

## 🤝 Contribuindo

```bash
pip install -e ".[all,dev]"
pytest tests/ -v
ruff check src/
```

[→ Ver roadmap para contribuidores](docs/business/roadmap.md#como-contribuir)

---

## 📄 Licença

MIT — use, modifique, distribua livremente.

---

<p align="center">
  <strong>🧠 Cortex — Porque agentes inteligentes precisam lembrar.</strong>
</p>
