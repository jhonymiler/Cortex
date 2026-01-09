# 🧠 Cortex - Development Instructions

> **Sistema de Memória Cognitiva para Agentes LLM**  
> *"Porque agentes inteligentes precisam de memória inteligente"*  
> Versão: 3.2 | Janeiro 2026

---

## 🎯 Propósito

O Cortex é um sistema de **memória cognitiva** que vai além de simples armazenamento:

| Dimensão | O que significa |
|----------|-----------------|
| **Memória Coletiva** | Conhecimento evolui e é compartilhado entre agentes/usuários |
| **Aprendizado Evolutivo** | Consolida padrões, fortalece o útil, esquece o ruído |
| **Cognição Biológica** | Ebbinghaus (decay), consolidação (sono), hubs (sinapses fortes) |
| **Alto Valor Semântico** | Recupera o que IMPORTA, não tudo que "parece similar" |
| **Eficiência de Tokens** | Máximo valor informacional com mínimo custo |

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

# ❌ Threshold fixo para embeddings (ex: 0.75)
# ✅ Threshold adaptativo com gap analysis

# ❌ Old MCP
# ✅ FastMCP (decorator-based)

# ❌ Misturar camadas (I/O em models)
# ✅ Models puros, Services com lógica
```

---

## 🔍 Estratégia de Recall

```python
# Threshold adaptativo (MemoryService._recall_by_embedding)
# 1. Score muito alto (≥0.75) → retorna top 1
# 2. Uniformidade (std < 0.05) → descarta (ruído)
# 3. Gap grande (>0.10) → ajusta threshold dinamicamente
# 4. Fallback: threshold base 0.60
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
