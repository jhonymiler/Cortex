---
name: recall-system
description: Comprehensive guide for memory recall, ranking algorithms, and context optimization.
  Use when implementing queries, debugging low relevance results, optimizing token usage via
  context packing, or understanding hybrid ranking (RRF+MMR), hierarchical recall (4 levels),
  and BFS graph expansion. Mention when working with RecallResult, ranking.py, context_packer.py.
---

# Sistema de Recall (Recuperação de Memória)

Sistema multi-camada para busca e ranking de memórias com otimização de tokens e relevância.

## Quando Usar

- Implementar queries de busca de memórias
- Debugar resultados de baixa relevância ou recall vazio
- Otimizar consumo de tokens (context packing)
- Entender algoritmos de ranking (RRF, MMR, Hybrid)
- Trabalhar com recall hierárquico (4 níveis de memória)
- Implementar BFS graph expansion para contexto adicional

## Pipeline de Recall (7 Etapas)

1. **Embedding Similarity**: Busca por similaridade semântica (cosine)
2. **Inverted Index**: Busca por keywords (fallback quando embedding falha)
3. **RRF Fusion**: Reciprocal Rank Fusion — combina múltiplos sinais de ranking
4. **Hierarchical Ranking**: Prioriza por 4 níveis (Working → Recent → Patterns → Knowledge)
5. **MMR Diversity**: Maximal Marginal Relevance — evita redundância (+40% diversidade)
6. **BFS Graph Expansion**: Explora vizinhança para contexto adicional (+30% contexto)
7. **Context Packing**: Compressão inteligente (40-70% token reduction)

## 4 Níveis Hierárquicos

| Nível | Janela Temporal | Conteúdo | Peso |
|-------|-----------------|----------|------|
| **Working** | Últimos minutos | Contexto ativo da sessão | 1.0 |
| **Recent** | Últimos dias | Episódios recentes | 0.8 |
| **Patterns** | Últimas semanas | Padrões consolidados | 0.6 |
| **Knowledge** | Todo histórico | Conhecimento coletivo | 0.4 |

**Importância**: Working memory tem 2.5x mais peso que Knowledge — prioriza contexto imediato.

## Algoritmos de Ranking

### RRF (Reciprocal Rank Fusion)

Combina múltiplos sinais de ranking:

```
RRF_score = Σ (1 / (k + rank_i))  onde k=60
```

**Sinais combinados**:
- Similaridade semântica (embedding)
- Keyword match (inverted index)
- Recência (timestamp)
- Import ância (importance score)
- Frequência de acesso (access_count)

### MMR (Maximal Marginal Relevance)

Evita redundância maximizando diversidade:

```
MMR_score = λ * relevance - (1-λ) * max_similarity_to_selected
```

**λ = 0.7**: 70% relevância, 30% diversidade

**Resultado**: +40% diversidade em resultados, menos repetição

### Hybrid Ranking

Combina RRF + MMR sequencialmente:
1. RRF para fusion de sinais
2. MMR para diversificação
3. Hierarchical para priorização temporal

## Context Packing (Otimização de Tokens)

Reduz 40-70% de tokens mantendo informação relevante.

**Pipeline**:
1. **Priority Scoring**: importância × retrievability × recência
2. **Grouping**: Agrupa memórias redundantes
3. **Summarization**: Hierarquiza detalhes (conceitos-chave → detalhes → metadados)

**Exemplo**:
- Input: 10 memórias, 5.000 tokens
- Output: Top 6 memórias agrupadas, 1.800 tokens (64% redução)

## BFS Graph Expansion

Explora vizinhança no grafo para contexto adicional.

**Processo**:
1. Recall inicial retorna top-N memórias
2. BFS explora entidades e relações conectadas (1-2 hops)
3. Adiciona contexto relevante não capturado por similaridade semântica

**Ganho**: +30% contexto relacionado, especialmente útil para raciocínio causal

## Threshold de Similaridade

**Padrão**: 0.25

**Ajustar por domínio**:
- **Sistemas técnicos** (alta precisão): 0.35-0.45
- **Roleplay** (alta criatividade): 0.15-0.25
- **Suporte** (balanceado): 0.25-0.30

**Efeito**: Threshold maior = menos resultados, mais precisos; menor = mais resultados, mais diversos

## Troubleshooting

| Problema | Causa Provável | Solução |
|----------|----------------|---------|
| Recall vazio | Threshold muito alto | Reduzir threshold ou verificar embedding |
| Resultados irrelevantes | Embedding ruim ou threshold baixo | Aumentar threshold, verificar qualidade do embedding |
| Alta latência | Muitos resultados | Limitar top_k, otimizar índices Neo4j |
| Redundância alta | MMR desabilitado | Habilitar MMR com λ=0.7 |
| Falta de contexto | BFS desabilitado | Habilitar BFS expansion (1-2 hops) |

## Referências

- [RANKING-ALGORITHMS.md](references/RANKING-ALGORITHMS.md) — Matemática detalhada de RRF, MMR, Hybrid
- [HIERARCHICAL-RECALL.md](references/HIERARCHICAL-RECALL.md) — Implementação de 4 níveis de memória
- [CONTEXT-PACKING.md](references/CONTEXT-PACKING.md) — Algoritmo de compressão de tokens
