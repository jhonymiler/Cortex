# 📉 Gerenciamento Automático de Relevância
*(Baseado na Curva de Ebbinghaus)*

> **A dor:** Sistemas tradicionais acumulam tudo para sempre — aumentando ruído, custo e confusão.
> **A solução:** Cortex esquece ativamente o que é inútil para focar no sinal, como seu cérebro.
> **O resultado:** -98% tokens desperdiçados com contexto irrelevante.

*Documento Canônico — fonte única de verdade sobre decaimento de memórias.*

---

## Por Que Isso Importa

A **Cognição Biológica** é uma das [4 dimensões de valor](../research/benchmarks.md) do Cortex:

| Dimensão | Score | Cortex é Único? |
|----------|-------|-----------------|
| 🧠 **Cognição Biológica** | **50%** | ✅ **Exclusivo** |
| 👥 Memória Coletiva | 75% | ✅ Exclusivo |
| 🎯 Valor Semântico | 100% | Empata |
| ⚡ Eficiência | 100% | ✅ Exclusivo |

**Nenhum concorrente** (Baseline, RAG, Mem0) implementa decaimento ou consolidação.

---

## Fundamento Científico

O Cortex implementa decaimento de memória baseado na **Curva de Esquecimento de Ebbinghaus** (1885), uma das descobertas mais replicadas da psicologia cognitiva.

### A Fórmula

```
R = e^(-t/S)
```

| Variável | Significado | Unidade |
|----------|-------------|---------|
| **R** | Retrievability (facilidade de recuperar) | 0.0 - 1.0 |
| **t** | Tempo desde último acesso | Dias |
| **S** | Stability (durabilidade da memória) | Dias |

### Interpretação Visual

```
Retrievability
    1.0 ┤████████████
        │    ████████
    0.7 │        ████████ ← Limite "fresh"
        │            ████████
    0.4 │                ████████ ← Limite "stable"
        │                    ████████
    0.1 │                        ████████ ← Limite "forgotten"
    0.0 └────────────────────────────────────► Tempo
         0    7    14   21   28   35   42 dias
```

---

## Implementação no Cortex

### DecayManager

```python
from cortex.core import DecayManager, DecayConfig

config = DecayConfig(
    base_stability_days=7.0,      # Stability base
    consolidation_bonus=2.0,      # Memórias consolidadas: 2x
    hub_bonus=1.5,                # Hubs: 1.5x
    high_importance_bonus=1.3,    # Importance > 0.7: 1.3x
    forgotten_threshold=0.1,      # Abaixo = "esquecida"
    hub_reference_threshold=5,    # 5+ referências = hub
)

manager = DecayManager(config)
```

### Cálculo de Stability

A stability de uma memória é modificada por múltiplos fatores:

```python
S = base_stability 
    × (1 + log(access_count))      # Repetição espaçada
    × consolidation_bonus          # Se consolidada
    × hub_bonus                    # Se é hub
    × importance_bonus             # Se importante
```

---

## Fatores que Aumentam Stability

| Fator | Multiplicador | Descrição |
|-------|---------------|-----------|
| **Access Count** | `1 + log(N)` | Cada acesso reforça |
| **Consolidação** | `2.0×` | Memórias resumidas são mais duráveis |
| **Hub Centrality** | `1.5×` | Muito referenciada = importante |
| **High Importance** | `1.3×` | Importância declarada > 0.7 |
| **Memória Filha** | `0.33×` | Já consolidada = decai 3x mais rápido |

---

## Ciclo de Vida da Memória

```
┌─────────────────────────────────────────────────────────────┐
│                    CICLO DE VIDA                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  FRESH (R > 0.7)                                           │
│  └─ Recém-criada ou acessada                               │
│       │                                                     │
│       ▼ (dias passam sem acesso)                           │
│                                                             │
│  STABLE (0.4 < R ≤ 0.7)                                    │
│  └─ Ainda recuperável, começando a desvanecer              │
│       │                                                     │
│       ▼ (mais dias passam)                                 │
│                                                             │
│  FADING (0.1 < R ≤ 0.4)                                    │
│  └─ Difícil recuperar, prioridade baixa                    │
│       │                                                     │
│       ▼ (sem acesso prolongado)                            │
│                                                             │
│  FORGOTTEN (R ≤ 0.1)                                       │
│  └─ Marcada, excluída de recalls normais                   │
│     (não deletada, disponível para recovery)               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Spaced Repetition (Anti-Decay)

Quando uma memória é **acessada**, sua stability aumenta:

```python
def touch(memory: Memory) -> None:
    """Acessa memória, reforçando-a."""
    memory.access_count += 1
    memory.last_accessed = datetime.now()
    memory.stability = min(10.0, memory.stability * 1.2)
```

Este comportamento replica a **repetição espaçada** humana:
- Primeira vez: lembra por 1 dia
- Segunda vez: lembra por 3 dias
- Terceira vez: lembra por 7 dias
- ...e assim por diante

---

## Hub Protection

Memórias muito referenciadas (hubs) são protegidas:

```python
def is_hub(memory: Memory, graph: MemoryGraph) -> bool:
    """Verifica se memória é um hub."""
    incoming_relations = graph.count_relations_to(memory.id)
    return incoming_relations >= 5  # Threshold configurável
```

### Por Que Proteger Hubs?

```
Memory: "João é gerente de projetos"
├── Referenciado por: "João aprovou o orçamento"
├── Referenciado por: "João delegou tarefa para Maria"
├── Referenciado por: "João conduziu a reunião de sprint"
├── Referenciado por: "João resolveu conflito com cliente"
└── Referenciado por: "João mentor do estagiário"

→ 5 referências = HUB
→ João é central para o contexto
→ Decai mais lentamente (1.5× stability)
```

---

## Configuração via Ambiente

```bash
# .env
CORTEX_DECAY_BASE_STABILITY=7.0
CORTEX_DECAY_CONSOLIDATION_BONUS=2.0
CORTEX_DECAY_HUB_BONUS=1.5
CORTEX_DECAY_IMPORTANCE_BONUS=1.3
CORTEX_DECAY_FORGOTTEN_THRESHOLD=0.1
CORTEX_DECAY_HUB_THRESHOLD=5
```

---

## API de Decay

### Aplicar Decay Manual

```bash
POST /memory/decay
X-Cortex-Namespace: meu_agente

# Aplica decay a todas as memórias do namespace
```

### MCP Tool

```python
cortex_decay(namespace="meu_agente")
```

### Verificar Retrievability

```python
memory = graph.get_memory(memory_id)
print(f"Retrievability: {memory.retrievability:.2f}")
print(f"Status: {'fresh' if memory.retrievability > 0.7 else 'fading'}")
```

---

## Memórias "Esquecidas"

Memórias com `R ≤ 0.1` são marcadas como `forgotten`:

```python
memory.metadata["forgotten"] = True
```

**Comportamento**:
- Excluídas de recalls normais
- **Não deletadas** (disponíveis para recovery)
- Podem ser "relembradas" se acessadas diretamente

---

## Impacto no Recall

Por padrão, `recall()` filtra memórias por retrievability:

```python
# Memórias com R < threshold são excluídas
memories = [m for m in memories if m.retrievability >= min_retrievability]
```

Para incluir memórias esquecidas:

```python
result = graph.recall(query, include_forgotten=True)
```

---

## 🧭 Próximos Passos

Escolha seu caminho baseado no que você quer fazer agora:

> **🚀 Quer aplicar decay manualmente?**
> 
> Use a API para forçar decay em um namespace:
> ```bash
> curl -X POST http://localhost:8000/memory/decay \
>   -H "X-Cortex-Namespace: meu_agente"
> 
> # Resposta:
> # {"success": true, "memories_decayed": 42, "memories_forgotten": 3}
> ```
> → [API Reference: Decay](../architecture/api-reference.md)

> **🔬 Quer entender como consolidação afeta o decay?**
> 
> Memórias consolidadas decaem **2x mais lento**. Memórias já consolidadas (filhas) decaem **3x mais rápido**.
> → [Consolidação Hierárquica](./consolidation.md)

> **💡 Quer ver quanto o decay impacta nos resultados?**
> 
> No ablation study, remover decay reduz economia em **2.3%** e hit rate em **5%**.
> → [Benchmarks: Ablation Study](../research/benchmarks.md#ablation-study)

> **⚙️ Quer configurar os parâmetros de decay?**
> 
> Todas as variáveis são configuráveis via `.env`:
> ```bash
> CORTEX_DECAY_BASE_STABILITY=7.0
> CORTEX_DECAY_CONSOLIDATION_BONUS=2.0
> CORTEX_DECAY_HUB_BONUS=1.5
> CORTEX_DECAY_FORGOTTEN_THRESHOLD=0.1
> ```

---

## Referências Científicas

- Ebbinghaus, H. (1885). *Über das Gedächtnis*
- Wozniak, P. (1990). SuperMemo algorithm (SM-2)
- Settles, B. & Meeder, B. (2016). *A Trainable Spaced Repetition Model*

---

*Documento canônico de decaimento cognitivo — Última atualização: Janeiro 2026*

