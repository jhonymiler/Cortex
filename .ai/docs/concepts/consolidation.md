# 🔄 Síntese Automática de Padrões
*(Consolidação Hierárquica)*

> **A dor:** 100 atendimentos sobre o mesmo problema = 100 registros separados que ninguém analisa.
> **A solução:** Cortex agrupa automaticamente experiências similares em insights acionáveis.
> **O resultado:** Conhecimento que escala sem análise manual.

*Documento Canônico — fonte única de verdade sobre consolidação de memórias.*

---

## O Que é Consolidação?

Consolidação é o processo de **agrupar memórias similares em resumos de alto nível**, inspirado no processo de consolidação de memória durante o sono humano.

```
ANTES (10 memórias granulares):
├── "Carlos ligou sobre modem"
├── "Luz vermelha piscando"
├── "Técnico verificou cabo"
├── "Problema era conexão solta"
├── "Carlos agradeceu"
└── ... (mais 5 similares)

DEPOIS (1 memória consolidada + 10 arquivadas):
├── RESUMO: "Cliente resolveu problemas de internet via suporte técnico"
│   └── occurrence_count: 10
│   └── is_summary: True
│
└── ARQUIVADAS (linked via consolidated_into):
    ├── "Carlos ligou sobre modem" → consolidated_into: RESUMO_ID
    ├── "Luz vermelha piscando" → consolidated_into: RESUMO_ID
    └── ... (decaem 3x mais rápido)
```

---

## Modelo Hierárquico

### Estrutura de Dados

```
┌─────────────────────────────────────────────────────────────┐
│  CONSOLIDADA (recall normal)                                │
│  ══════════════════════════                                 │
│  "Cliente expressou gratidão após resolução"                │
│  is_summary=True, occurrence_count=15                       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  GRANULARES (só drill-down/rollback)                │   │
│  │  ═══════════════════════════════════                │   │
│  │  ├── "Carlos ligou com problema de modem"           │   │
│  │  │   └── consolidated_into: <ID_RESUMO>             │   │
│  │  ├── "Técnico verificou luz vermelha"               │   │
│  │  │   └── consolidated_into: <ID_RESUMO>             │   │
│  │  ├── "Problema era cabo desconectado"               │   │
│  │  │   └── consolidated_into: <ID_RESUMO>             │   │
│  │  └── "Carlos agradeceu"                             │   │
│  │      └── consolidated_into: <ID_RESUMO>             │   │
│  │                                                     │   │
│  │  (decaem 3x mais rápido que memórias normais)       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Campos em Memory

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `consolidated_from` | `list[str]` | IDs das memórias que originaram este resumo |
| `consolidated_into` | `str \| None` | ID do resumo pai (se foi consolidada) |
| `is_summary` | `bool` | True se é um resumo de consolidação |
| `occurrence_count` | `int` | Quantas memórias este resumo representa |

### Propriedades Derivadas

```python
@property
def is_consolidated(self) -> bool:
    """True se é pai (tem filhas)."""
    return len(self.consolidated_from) > 0 or self.is_summary

@property
def was_consolidated(self) -> bool:
    """True se é filha (tem pai)."""
    return self.consolidated_into is not None
```

---

## DreamAgent: Consolidação em Background

O `DreamAgent` é um worker que executa consolidação similar ao processo de consolidação durante o sono:

### Uso

```python
from cortex.workers import DreamAgent

agent = DreamAgent(
    cortex_url="http://localhost:8000",
    llm_url="http://localhost:11434",
    llm_model="gemma3:4b"
)

result = agent.dream(namespace="meu_agente")

print(f"Memórias analisadas: {result.memories_analyzed}")
print(f"Memórias refinadas: {result.memories_refined}")
print(f"Entidades extraídas: {result.entities_extracted}")
print(f"Padrões encontrados: {result.patterns_found}")
```

### O Que o DreamAgent Faz

1. **Busca memórias brutas** do namespace
2. **Agrupa por similaridade** (semântica + temporal)
3. **Gera resumo** usando LLM
4. **Cria memória consolidada** com `is_summary=True`
5. **Marca originais** com `consolidated_into=<ID_RESUMO>`

---

## Comportamento de Recall

### Padrão: Só Consolidadas

Por padrão, `recall()` **exclui memórias já consolidadas**:

```python
# MemoryGraph.recall()
if not include_consolidated:
    episodes = [ep for ep in episodes 
                if not ep.consolidated_into]  # Exclui filhas
```

### Drill-Down: Incluir Granulares

Para buscar detalhes históricos:

```python
result = graph.recall(
    query="problemas de internet do Carlos",
    include_consolidated=True  # Inclui filhas
)
```

### Rollback: Recuperar Originais

Se uma consolidação estiver incorreta:

```python
# Buscar filhas de um resumo
granular_memories = [
    m for m in graph.all_memories() 
    if m.consolidated_into == summary_id
]

# Limpar consolidação
for m in granular_memories:
    m.consolidated_into = None
```

---

## Decaimento Acelerado para Filhas

Memórias que **já foram consolidadas** decaem **3x mais rápido**:

```python
# Memory.retrievability
if self.was_consolidated:
    consolidation_modifier = 0.33  # 3x mais rápido
else:
    consolidation_modifier = 1.0

return math.exp(-t / (S * consolidation_modifier))
```

### Justificativa

- Resumos são suficientes para contexto normal
- Granulares são histórico/backup
- Grafo se "limpa" naturalmente ao longo do tempo
- Economia de espaço sem perda de informação crítica

---

## Quando Consolidar?

### Triggers Automáticos

1. **Threshold de similaridade**: 5+ memórias muito similares
2. **Temporal**: Memórias do mesmo "evento" (janela de 1h)
3. **Namespace**: Mesmo namespace = mesmo contexto

### Trigger Manual

```python
# Via API
POST /memory/consolidate
X-Cortex-Namespace: meu_agente

# Via MCP
cortex_consolidate(namespace="meu_agente")

# Via Worker
agent.dream(namespace="meu_agente")
```

---

## Exemplo Completo

### Antes da Consolidação

```python
# 5 memórias sobre o mesmo problema
memories = [
    Memory(who=["Carlos"], what="ligou_suporte", ...),
    Memory(who=["Carlos"], what="relatou_luz_vermelha", ...),
    Memory(who=["Carlos", "Técnico"], what="verificou_modem", ...),
    Memory(who=["Técnico"], what="identificou_cabo_solto", ...),
    Memory(who=["Carlos"], what="agradeceu_resolucao", ...),
]
```

### Após DreamAgent

```python
# 1 resumo (retornado em recall normal)
summary = Memory(
    who=["Carlos", "Técnico"],
    what="resolveu_problema_internet",
    why="cabo_ethernet_desconectado",
    how="reconectou_cabo_modem_funcionando",
    is_summary=True,
    occurrence_count=5,
    consolidated_from=[m.id for m in memories]
)

# 5 originais (arquivadas, linked ao resumo)
for m in memories:
    m.consolidated_into = summary.id
    # Agora decaem 3x mais rápido
```

---

## Configuração

```bash
# .env
CORTEX_CONSOLIDATION_THRESHOLD=5     # Mínimo de memórias similares
CORTEX_CONSOLIDATION_WINDOW_HOURS=1  # Janela temporal
```

---

## 🧭 Próximos Passos

Escolha seu caminho baseado no que você quer fazer agora:

> **🚀 Quer executar o DreamAgent agora?**
> 
> ```python
> from cortex.workers import DreamAgent
> 
> agent = DreamAgent(
>     cortex_url="http://localhost:8000",
>     llm_url="http://localhost:11434",
>     llm_model="gemma3:4b"
> )
> result = agent.dream(namespace="meu_agente")
> print(f"Consolidados: {result.summaries_created}")
> ```
> → [Integrações: Workers](../getting-started/integrations.md)

> **🔬 Quer entender como memórias consolidadas decaem diferente?**
> 
> Memórias-resumo (pais) decaem **2x mais lento**. Memórias arquivadas (filhas) decaem **3x mais rápido**.
> → [Decaimento Cognitivo](./cognitive-decay.md)

> **💡 Quer ver o impacto da consolidação nos tokens?**
> 
> **Sem consolidação**: +8.7% tokens vs baseline (memórias brutas acumulam).
> **Com consolidação**: -12.5% tokens vs baseline.
> **Delta**: 21.2 pontos percentuais de melhoria.
> → [Benchmarks: Impacto da Consolidação](../research/benchmarks.md#impacto-da-consolidação)

> **🏢 Quer consolidar padrões entre múltiplos usuários?**
> 
> O DreamAgent pode promover padrões comuns de PERSONAL para LEARNED (anonimizado).
> → [Memória Compartilhada](./shared-memory.md#promoção-personal--learned)

---

## Fundamentação Científica

- **Consolidação sináptica** (Frankland & Bontempi, 2005)
- **Sleep-dependent memory consolidation** (Walker & Stickgold, 2006)
- **Generative Agents** (Park et al., 2023) - Reflexões como consolidação

---

*Documento canônico de consolidação — Última atualização: Janeiro 2026*

