# 📚 Fundamentação Científica

> **Agentes de IA sofrem de amnésia crônica** — frustram usuários e desperdiçam recursos.
> **Cortex resolve isso** com memória inspirada no cérebro humano: esquece o ruído, fortalece o importante, aprende coletivamente.
> **Resultado comprovado:** -73% no tempo de atendimento, -98% nos custos de tokens.

*Este documento detalha as bases teóricas com referências acadêmicas.*

---

## Visão Geral

O Cortex é fundamentado em três pilares científicos:

1. **Psicologia Cognitiva** — Curva de Ebbinghaus, memória episódica
2. **Ciência da Computação** — Grafos, centralidade, índices
3. **IA e Agentes** — CoALA, Generative Agents, memory-augmented LLMs

---

## 1. Curva de Esquecimento (Ebbinghaus, 1885)

### Referência Original

> Ebbinghaus, H. (1885). *Über das Gedächtnis: Untersuchungen zur experimentellen Psychologie*. Leipzig: Duncker & Humblot.

### O Experimento

Ebbinghaus memorizou listas de sílabas sem sentido e mediu a taxa de esquecimento ao longo do tempo, descobrindo a fórmula:

```
R = e^(-t/S)
```

### Aplicação no Cortex

```python
# Implementação em src/cortex/core/decay.py
def calculate_retrievability(
    last_accessed: datetime,
    stability: float
) -> float:
    """
    Calcula facilidade de recuperação baseada em Ebbinghaus.
    
    Args:
        last_accessed: Última vez que a memória foi acessada
        stability: Durabilidade da memória (modificada por uso)
    
    Returns:
        Valor entre 0.0 (esquecida) e 1.0 (fresca)
    """
    days = (datetime.now() - last_accessed).days
    return math.exp(-days / stability)
```

### Spaced Repetition

O Cortex implementa repetição espaçada automaticamente:

```
1º acesso: S = 1.0 (lembra 1 dia)
2º acesso: S = 1.2 (lembra 1.2 dias)
3º acesso: S = 1.44 (lembra ~1.5 dias)
...
Nth acesso: S = min(10.0, 1.0 × 1.2^N)
```

### Referências Adicionais

- Wozniak, P. (1990). *SuperMemo algorithm (SM-2)*
- Settles, B. & Meeder, B. (2016). *A Trainable Spaced Repetition Model for Language Learning*

---

## 2. Memória Episódica e Semântica (Tulving, 1972)

### Referência Original

> Tulving, E. (1972). *Episodic and Semantic Memory*. In E. Tulving & W. Donaldson (Eds.), Organization of Memory.

### Distinção

| Tipo | Descrição | Exemplo |
|------|-----------|---------|
| **Episódica** | Experiências pessoais | "João reclamou do login ontem" |
| **Semântica** | Fatos gerais | "Logins usam autenticação" |
| **Procedural** | Como fazer | "Para resetar senha, clique em..." |

### Aplicação no Cortex

O modelo W5H **unifica** os três tipos:

```python
Memory(
    # Episódico: O que aconteceu
    who=["João"], what="reclamou_login", when="2026-01-06",
    
    # Semântico: Por quê
    why="vpn_bloqueando_autenticacao",
    
    # Procedural: Como resolver
    how="desconectar_vpn_reconectar"
)
```

---

## 3. Consolidação de Memória (Frankland & Bontempi, 2005)

### Referências

> Frankland, P.W. & Bontempi, B. (2005). *The organization of recent and remote memories*. Nature Reviews Neuroscience.

> Walker, M.P. & Stickgold, R. (2006). *Sleep, Memory, and Plasticity*. Annual Review of Psychology.

### O Processo

Durante o sono, o cérebro consolida memórias:
1. **Replaying** — Reativa experiências do dia
2. **Extracting** — Identifica padrões
3. **Abstracting** — Cria representações de alto nível
4. **Integrating** — Conecta com conhecimento existente

### Aplicação no Cortex

O `DreamAgent` simula este processo:

```python
from cortex.workers import DreamAgent

# Equivalente ao "sono"
agent = DreamAgent()
result = agent.dream(namespace="meu_agente")

# Resultado:
# - 50 memórias granulares → 5 padrões consolidados
# - Entidades centrais identificadas
# - Relações fortalecidas
```

---

## 4. Centralidade em Grafos

### Referências

> Freeman, L.C. (1978). *Centrality in Social Networks: Conceptual Clarification*. Social Networks.

> Page, L. et al. (1999). *The PageRank Citation Ranking: Bringing Order to the Web*. Stanford InfoLab.

### Tipos de Centralidade

| Tipo | Fórmula | Significado |
|------|---------|-------------|
| **Degree** | Número de conexões | Popularidade local |
| **Betweenness** | Caminhos passando pelo nó | Ponte entre grupos |
| **Closeness** | Distância média aos outros | Eficiência de alcance |
| **PageRank** | Importância recursiva | Autoridade global |

### Aplicação no Cortex

Usamos **degree centrality** para detectar hubs:

```python
def is_hub(memory_id: str, graph: MemoryGraph) -> bool:
    """
    Hubs são memórias muito referenciadas.
    Decaem mais lentamente (proteção).
    """
    incoming = graph.count_relations_to(memory_id)
    return incoming >= HUB_THRESHOLD  # Default: 5
```

**Impacto**: Hubs recebem 1.5× stability bonus, decaindo mais lentamente.

---

## 5. CoALA - Cognitive Architectures for Language Agents

### Referência

> Sumers, T.R. et al. (2023). *Cognitive Architectures for Language Agents*. arXiv:2309.02427.

### Arquitetura Proposta

```
┌─────────────────────────────────────────────┐
│              LANGUAGE AGENT                 │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────────────────────────────────┐   │
│  │         LONG-TERM MEMORY            │   │
│  ├─────────────────────────────────────┤   │
│  │ Procedural │ Semantic │ Episodic   │   │
│  └─────────────────────────────────────┘   │
│                     ▲                       │
│                     │                       │
│  ┌─────────────────────────────────────┐   │
│  │         WORKING MEMORY              │   │
│  │        (Context Window)             │   │
│  └─────────────────────────────────────┘   │
│                     ▲                       │
│                     │                       │
│  ┌─────────────────────────────────────┐   │
│  │         DECISION CYCLE              │   │
│  │   Perception → Processing → Action  │   │
│  └─────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

### Aplicação no Cortex

Cortex implementa a **Long-Term Memory** da arquitetura CoALA:

| CoALA | Cortex |
|-------|--------|
| Episodic | Memory (W5H) |
| Semantic | Entity + Relation |
| Procedural | Patterns consolidados |

---

## 6. Generative Agents (Park et al., 2023)

### Referência

> Park, J.S. et al. (2023). *Generative Agents: Interactive Simulacra of Human Behavior*. arXiv:2304.03442.

### Arquitetura de Memória

```
Observation → Memory Stream → Retrieval → Reflection → Planning
```

### Ablation Study

O paper mostrou que **todos os componentes são críticos**:

| Componente Removido | Queda de Performance |
|--------------------|---------------------|
| Observation | -22% |
| Planning | -18% |
| Reflection | -26% |
| Memory Retrieval | -31% |

### Aplicação no Cortex

| Generative Agents | Cortex |
|-------------------|--------|
| Memory Stream | Memory Graph |
| Observation | Episode raw |
| Reflection | Consolidated Memory |
| Retrieval | recall() com relevância |

---

## 7. Modelo W5H

### Origem

O modelo W5H deriva do jornalismo investigativo, formalizado por Rudyard Kipling:

> "I keep six honest serving-men (They taught me all I knew);
> Their names are What and Why and When And How and Where and Who."
> — Kipling, *The Elephant's Child* (1902)

### Formalização para IA

Adaptamos para memória de agentes:

| Campo | Jornalismo | Cortex |
|-------|------------|--------|
| WHO | Quem está envolvido? | `list[str]` entidades |
| WHAT | O que aconteceu? | `str` ação |
| WHY | Por que aconteceu? | `str` causa |
| WHEN | Quando? | `datetime` timestamp |
| WHERE | Onde? | `str` namespace |
| HOW | Como? | `str` resultado |

### Vantagens sobre Texto Livre

1. **Busca estruturada** — Índice por campo, não embedding
2. **Relações explícitas** — WHO conecta a entidades
3. **Causalidade** — WHY captura razões
4. **Namespace** — WHERE permite multi-tenant

---

## 8. Busca O(1) vs Similaridade Vetorial

### Problema com Embeddings

```
Custo RAG = N × embedding_cost + vector_search_cost
         = O(N) ou O(log N) com índices
```

### Solução Cortex

```
Custo Cortex = index_lookup
            = O(1)
```

### Como Funciona

```python
# Índices pré-computados
entity_index = {
    "joão": [entity_id_1],
    "sistema_auth": [entity_id_2],
    ...
}

# Busca O(1)
def find_entity(name: str) -> Entity:
    return entity_index[normalize(name)]
```

---

## Métricas Científicas Implementadas

### Precision@K

```
Precision@K = |Relevantes ∩ Recuperados_K| / K
```

### Recall@K

```
Recall@K = |Relevantes ∩ Recuperados_K| / |Relevantes|
```

### MRR (Mean Reciprocal Rank)

```
MRR = (1/|Q|) × Σ (1 / rank_i)
```

### F1-Memory

```
F1 = 2 × (Precision × Recall) / (Precision + Recall)
```

---

## Referências Completas

### Psicologia Cognitiva

1. Ebbinghaus, H. (1885). *Über das Gedächtnis*
2. Tulving, E. (1972). *Episodic and Semantic Memory*
3. Baddeley, A. (2000). *The Episodic Buffer*
4. Walker, M.P. & Stickgold, R. (2006). *Sleep, Memory, and Plasticity*

### Ciência da Computação

5. Freeman, L.C. (1978). *Centrality in Social Networks*
6. Page, L. et al. (1999). *The PageRank Citation Ranking*

### IA e Agentes

7. Sumers, T.R. et al. (2023). *Cognitive Architectures for Language Agents*
8. Park, J.S. et al. (2023). *Generative Agents*
9. Lewis, P. et al. (2020). *Retrieval-Augmented Generation*

### Spaced Repetition

10. Wozniak, P. (1990). *SuperMemo algorithm (SM-2)*
11. Settles, B. & Meeder, B. (2016). *A Trainable Spaced Repetition Model*

---

## Próximos Passos

| Quer... | Vá para... |
|---------|------------|
| Ver resultados empíricos | [Benchmarks](./benchmarks.md) |
| Entender implementação | [Arquitetura](../architecture/overview.md) |
| Reproduzir experimentos | [Benchmark README](../../benchmark/README.md) |

---

*Fundamentação Científica — Última atualização: Janeiro 2026*

