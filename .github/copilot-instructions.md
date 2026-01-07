# 🧠 Cortex - Development Instructions

> **Sistema de Memória Cognitiva para Agentes LLM**  
> Versão: 3.1 | Janeiro 2026

---

## 📚 Documentação

A documentação é **modular** e segue o princípio D.R.Y.:

- **Conceitos**: `docs/concepts/` (fonte única de verdade)
- **Início rápido**: `docs/getting-started/`
- **Arquitetura**: `docs/architecture/`
- **Pesquisa**: `docs/research/`
- **Negócio**: `docs/business/`

Ao documentar, **referencie** os conceitos centrais em vez de duplicá-los.

---

## ⚡ Quick Reference

### Comandos Essenciais

```bash
source venv/bin/activate      # SEMPRE antes de qualquer comando
pip install -e ".[all,dev]"   # Instalar
cortex-api                    # Iniciar API
pytest tests/ -v              # Testes
./start_benchmark.sh --quick  # Benchmark
```

### Arquitetura Core

```
Entity (coisa) ←→ Memory (W5H) ←→ Relation (conexão)
                      │
                MemoryGraph (índices O(1))
                      │
        ┌─────────────┼─────────────┐
        │             │             │
    DecayManager  SharedMemory  DreamAgent
```

---

## 🔬 Modelo W5H

> Documentação: `docs/concepts/memory-model.md`

```python
Memory(
    who=["João", "sistema"],
    what="resolveu_bug",
    why="timeout_conexao",
    how="adicionou_pool",
    where="projeto_x",
    when=datetime.now()
)
```

---

## 📉 Decaimento (Ebbinghaus)

> Documentação: `docs/concepts/cognitive-decay.md`

```python
R = e^(-t/S)  # Retrievability

# Stability aumenta com:
# - Acessos frequentes
# - Consolidação (is_summary=True)
# - Hub centrality (5+ referências)
```

---

## 🔄 Consolidação

> Documentação: `docs/concepts/consolidation.md`

```python
# DreamAgent consolida memórias similares
from cortex.workers import DreamAgent

agent = DreamAgent()
result = agent.dream(namespace="meu_agente")

# Memórias filhas: consolidated_into → ID do resumo
# Decaem 3x mais rápido
# Excluídas do recall normal
```

---

## 🔒 Shared Memory

> Documentação: `docs/concepts/shared-memory.md`

```
PERSONAL: user:123 → Dados isolados do usuário
SHARED:   shared   → Visível a todos
LEARNED:  learned  → Padrões anonimizados
```

---

## 📊 SDK

> Documentação: `docs/getting-started/integrations.md`

```python
# Decorator
@with_memory(namespace="meu_agente")
def agent(msg, context=""): ...

# LangChain
memory = CortexLangChainMemory(namespace="lc")

# CrewAI
crew = Crew(long_term_memory=CortexCrewAIMemory(namespace="crew"))
```

---

## 🚨 O QUE NÃO FAZER

```python
# ❌ Duplicar explicações de conceitos
# ✅ Referenciar: Ver [Modelo W5H](docs/concepts/memory-model.md)

# ❌ Usar embeddings/vectors
# ✅ Usar índices O(1) do MemoryGraph

# ❌ Old MCP
# ✅ FastMCP (decorator-based)

# ❌ Misturar camadas (I/O em models)
# ✅ Models puros, Services com lógica
```

---

## 📝 Commits

```
feat: nova funcionalidade
fix: correção de bug
docs: documentação
refactor: sem mudar comportamento
test: testes
bench: benchmark
```

---

*Última atualização: Janeiro 2026*
