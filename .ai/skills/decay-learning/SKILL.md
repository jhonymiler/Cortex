---
name: decay-learning
description: Guide for cognitive decay (Ebbinghaus forgetting curve), spaced repetition (SM-2 adaptive),
  importance calculation, hub protection, and consolidation via DreamAgent.
  Use when implementing memory retention, active forgetting, importance scoring,
  or understanding how retrievability decays over time. Mention when working with
  DecayManager, memory_attention.py, contradiction.py, or DreamAgent.
---

# Decaimento Cognitivo e Aprendizado

Sistema inspirado em neurociência cognitiva para simular esquecimento natural, reforço por repetição espaçada, e consolidação progressiva de memórias.

## Quando Usar

- Implementar cálculo de retrievability (recuperabilidade)
- Entender por que memórias antigas "desaparecem" de recalls
- Configurar forgotten threshold e active forgetting
- Trabalhar com importância automática (hub detection)
- Implementar spaced repetition (SM-2 adaptativo)
- Debugar comportamento de DreamAgent (consolidação background)

## Conceitos-Chave

### Curva de Ebbinghaus
- **Fórmula**: `R(t) = e^(-t/S)` onde R=retrievability, t=tempo (dias), S=stability
- **Threshold**: R ≤ 0.1 → memória **deletada permanentemente**
- **Base Stability**: 7.0 dias (configurável via `CORTEX_DECAY_BASE_STABILITY`)

### Active Forgetting
- **Benefício**: 30% menos ruído em recalls
- **Hub Protection**: Memórias críticas (hubs) nunca são esquecidas — ganham 2x stability bonus
- **Detecção**: PageRank identifica hubs automaticamente

### SM-2 Adaptativo (Spaced Repetition)
- Ajusta stability baseado em padrão de acesso
- Memórias frequentes → stability aumenta → decaem mais lentamente
- **Resultado**: +25% mais retenção de memórias importantes

### Importância Automática
**Não marcar manualmente** — sistema infere via:
- 40% Frequency (`access_count`)
- 30% Hub Score (PageRank)
- 20% Consolidation (passou por DreamAgent)
- 10% Explicit Flag (marcação manual, raro)

### DreamAgent (Consolidação Background)
Worker que refina memórias brutas e extrai padrões.

**Modos**: Continuous (a cada N min) | Batch (quando acumular X) | Scheduled (cron) | Disabled

**Processo**: Refine → Extract Patterns → Promote to Collective → Mark Consolidated (2x stability)

**Benefício**: 60% mais rápido em recall, menos ruído, padrões descobertos

### Detecção de Contradições
Quando memórias conflitantes são detectadas:
- **MERGE**: Combina via LLM (contradição leve)
- **CONFLICT**: Mantém ambas + flag + notifica (irreconciliável)
- **SUPERSEDE**: Nova sobrescreve antiga
- **TEMPORAL_SEQUENCE**: Ordena cronologicamente (mudança de estado)

## Referências

- [EBBINGHAUS-CURVE.md](references/EBBINGHAUS-CURVE.md) — Matemática detalhada da curva de esquecimento
- [SPACED-REPETITION.md](references/SPACED-REPETITION.md) — Implementação SM-2 adaptativo
- [DREAMAGENT-GUIDE.md](references/DREAMAGENT-GUIDE.md) — Configuração e troubleshooting do worker
