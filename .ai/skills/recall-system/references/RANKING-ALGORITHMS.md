# Algoritmos de Ranking Detalhados

## RRF (Reciprocal Rank Fusion)

### Fórmula

```
RRF_score(item) = Σ (1 / (k + rank_i))
onde:
  k = 60 (constante de suavização)
  rank_i = ranking do item na lista i
```

### Processo

1. Gerar múltiplas listas ranqueadas (embedding, keywords, recência, importância)
2. Para cada item, calcular RRF score somando contribuições de todas as listas
3. Ordenar por RRF score final

### Vantagens

- Combina sinais heterogêneos sem pesos manuais
- Robusto a outliers
- Não requer normalização de scores

---

## MMR (Maximal Marginal Relevance)

### Fórmula

```
MMR_score = λ * Sim(D_i, Q) - (1-λ) * max(Sim(D_i, D_j))
onde:
  D_i = documento candidato
  Q = query
  D_j = documentos já selecionados
  λ = 0.7 (balanceamento relevância/diversidade)
```

### Processo Iterativo

1. Selecionar item mais relevante (max similarity to query)
2. Para próximo item: maximizar (relevância - similaridade_com_selecionados)
3. Repetir até atingir top_k

### Resultado

+40% diversidade vs ranking puramente por relevância

---

## Hybrid Ranking (RRF + MMR)

### Pipeline Sequencial

```
Input Query
  ↓
RRF Fusion (combina sinais)
  ↓
Hierarchical Weighting (temporal priority)
  ↓
MMR Diversification (evita redundância)
  ↓
BFS Graph Expansion (adiciona contexto)
  ↓
Context Packing (comprime tokens)
  ↓
RecallResult (memories + metadata)
```

### Configuração

```python
recall_config = {
    "rrf_k": 60,
    "mmr_lambda": 0.7,
    "hierarchical_weights": {
        "working": 1.0,
        "recent": 0.8,
        "patterns": 0.6,
        "knowledge": 0.4
    },
    "bfs_depth": 2,
    "context_packing_enabled": True
}
```

---

## Referência de Código

- **RRF**: `src/cortex/core/recall/ranking.py::reciprocal_rank_fusion()`
- **MMR**: `src/cortex/core/recall/ranking.py::maximal_marginal_relevance()`
- **Hybrid**: `src/cortex/core/recall/ranking.py::hybrid_ranking()`
- **BFS**: `src/cortex/core/graph/graph_algorithms.py::bfs_traversal()`
