# Curva de Ebbinghaus - Matemática Detalhada

## Fórmula Completa

```
R(t) = e^(-t / S)

onde:
  R(t) = retrievability no tempo t (0.0 a 1.0)
  t = tempo decorrido desde último acesso (em dias)
  S = stability (estabilidade base da memória, em dias)
  e = constante de Euler (≈ 2.71828)
```

## Parâmetros de Configuração

| Parâmetro | Valor Padrão | Variável de Ambiente | Descrição |
|-----------|--------------|----------------------|-----------|
| **Base Stability** | 7.0 dias | `CORTEX_DECAY_BASE_STABILITY` | Tempo para R cair para ~37% (e^-1) |
| **Forgotten Threshold** | 0.1 | `CORTEX_DECAY_FORGOTTEN_THRESHOLD` | R abaixo disso = DELETE permanente |

## Exemplos de Decaimento

### Memória Padrão (S=7.0)

| Tempo (dias) | R(t) | Status |
|--------------|------|--------|
| 0 | 1.000 | Recém-criada |
| 1 | 0.867 | Ativa |
| 3 | 0.651 | Ativa |
| 7 | 0.368 | Ativa (e^-1) |
| 14 | 0.135 | Ativa |
| 16 | 0.105 | Ativa (próximo do threshold) |
| 17 | 0.096 | **DELETADA** (abaixo de 0.1) |

### Hub (S=14.0 com 2x bonus)

| Tempo (dias) | R(t) | Status |
|--------------|------|--------|
| 0 | 1.000 | Recém-criada |
| 7 | 0.606 | Ativa |
| 14 | 0.368 | Ativa |
| 28 | 0.135 | Ativa |
| 32 | 0.105 | Ativa |
| 33 | 0.096 | **DELETADA** |

**Hub dura 2x mais** (33 dias vs 17 dias).

## Comportamento por Faixa

| R(t) | Interpretação | Ação do Sistema |
|------|---------------|-----------------|
| 1.0 | Memória recém-acessada | Máxima prioridade em recalls |
| 0.7-1.0 | Memória muito fresca | Alta prioridade |
| 0.3-0.7 | Memória ativa | Prioridade normal |
| 0.1-0.3 | Memória decaindo | Baixa prioridade, risco de esquecimento |
| < 0.1 | **ESQUECIDA** | **DELETE permanente** |

## Active Forgetting - Processo

1. **DecayManager** calcula R(t) periodicamente (ex: a cada hora)
2. Para cada memória:
   ```python
   t = (now - memory.last_accessed).days
   R = exp(-t / memory.stability)
   memory.retrievability = R
   ```
3. Se `R ≤ FORGOTTEN_THRESHOLD` (0.1):
   - **Exceção - Hub Protection**: Se `is_hub(memory)` → NÃO deletar
   - **Caso contrário**: `DELETE FROM memories WHERE id = memory.id`

## Hub Protection

### Critérios para ser Hub

Um dos seguintes:
- `access_count >= 10`
- `importance > 0.8`
- `page_rank_score > 0.7` (calculado no grafo)

### Stability Bonus

```python
if is_hub(memory):
    memory.stability *= 2.0  # Dobra o tempo de vida
```

**Efeito**: Hub com S=7.0 vira S=14.0 → esquece em 33 dias ao invés de 17

## Consolidation Bonus

Memórias que passaram por DreamAgent (consolidadas) ganham bonus:

```python
if memory.consolidated:
    memory.stability *= 2.0
```

**Acumulativo com Hub**: Hub + Consolidado = 4x stability (7.0 → 28.0 dias)

## Referência de Código

- **Cálculo de R(t)**: `src/cortex/core/learning/decay.py::calculate_retrievability()`
- **Active Forgetting**: `src/cortex/core/learning/decay.py::forget_low_retrievability()`
- **Hub Detection**: `src/cortex/core/graph/graph_algorithms.py::detect_hubs()`
