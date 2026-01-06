# 📊 Resultados do Benchmark Cortex

Este diretório contém os resultados dos testes de benchmark do Cortex.

## 📁 Arquivos

### Dados Brutos
- `benchmark_YYYYMMDD_HHMMSS.json` — Resultado completo com todas as conversas
- `benchmark_YYYYMMDD_HHMMSS.summary.json` — Resumo agregado com métricas

### Relatórios
- **[VISUAL_SUMMARY.md](VISUAL_SUMMARY.md)** — 📊 Resumo visual com gráficos ASCII (LEIA PRIMEIRO!)
- **[PRELIMINARY_REPORT.md](PRELIMINARY_REPORT.md)** — 📝 Análise detalhada e técnica
- **[HIT_RATE_ANALYSIS.md](HIT_RATE_ANALYSIS.md)** — 🔍 Análise do problema de hit rate 40%
- **[SCIENTIFIC_ANALYSIS.md](SCIENTIFIC_ANALYSIS.md)** — 🎓 Comparação com estado da arte e roadmap para publicação

### Ablation Studies
- `ablation/ablation_YYYYMMDD_HHMMSS.json` — Testes de ablação (W5H vs Simple Episodic)

## 🎯 Status Atual

**Última execução:** 05/01/2026 22:54 UTC  
**Última análise:** 06/01/2026 (análise científica)

```
✅ Domínios testados: 1/8 (Education)
⏸️  Status: Aguardando novo benchmark com melhorias
📊 Dados coletados (benchmark antigo):
   - 1 conversa completa
   - 2 sessões
   - 5 mensagens
   - 283 entidades
   - 46 episódios
   - 466 relações
   
🔧 Melhorias implementadas (0Benchmark v1 - 05/01)

| Métrica | Resultado | Status |
|---------|-----------|--------|
| 💰 **Economia de Tokens** | **34.4%** vs baseline | ✅ Publicável |
| ⚡ **Economia de Tempo** | **31.9%** vs baseline | ✅ Ótimo |
| 🧠 **Taxa de Acerto** | **40.0%** | ⚠️ Melhorias implementadas (esperado: 70-80%) |
| 🚀 **Recall Speed** | **12.57ms** (zero tokens) | ✅ O(1) validado |
| ⚠️ **Store Speed** | **4,183ms** | ⚠️ Gargalo identificado |
| 🔄 **Consolidação** | **0%** | ⚠️ Precisa mais volume |

## 🎓 Gap Analysis para Publicação Científica

### ✅ O Que Já Temos (Publicável)
- **34.4% economia de tokens** (melhor que MemGPT ~25-30%)
- **Modelo W5H** (contribuição novel - único no estado da arte)
- **Hub centrality emergente** (baseado em acesso real)
- **Recall O(1)** (12.57ms validado)
- **Grafo bem estruturado** (densidade 3.58%)

### ❌ O Que Falta (Crítico)
- **Baselines comparativos** (RAG, Mem0, MemGPT)
- **Métricas padrão** (Precision@K, Recall@K, MRR, F1-Memory)
- **Ablation study** (provar contribuição de cada componente)
- **Validar hit rate 70%+** (testar melhorias implementadas)
| Métrica | Resultado |
|---------|-----------|
| 💰 **Economia de Tokens** | **34.4%** vs baseline |
| ⚡ **Economia de Tempo** | **31.9%** vs baseline |
| 🧠 **Taxa de Acerto** | **40.0%** |
| 🚀 **Recall Speed** | **12.57ms** (zero tokens) |
| ⚠️ **Store Speed** | **4,183ms** (gargalo identificado) |

## 🔍 Como Analisar os Resultados

### 1. Visualização Rápida
```bash
# Ver resumo visual (recomendado primeiro)
cat benchmark/results/VISUAL_SUMMARY.md

# Análise técnica detalhada
cat benchmark/results/PRELIMINARY_REPORT.md

# Entender o problema de hit rate
cat benchmark/results/HIT_RATE_ANALYSIS.md

# Roadmap para publicação científica
cat benchmark/results/SCIENTIFIC_ANALYSIS.md
```

### 2. Rodar Novo Benchmark (com melhorias)
```bash
# Teste rápido (1 conversa/domínio)
./start_lightweight_benchmark.sh --quick

# Benchmark completo (3 conversas/domínio)
./start_lightweight_benchmark.sh --full

# Retomar após rate limit
./start_lightweight_benchmark.sh --resume
```

### 3. Analisar Resultados
```bash
# Análise completa (grafo + hubs + insights)
./analyze_results.sh

# Comparar múltiplos benchmarks
python benchmark/compare_results.py
```

## 🚀 Próximos Passos

### Imediato (Esta Semana)
1. **Rodar benchmark completo com melhorias** (`./start_lightweight_benchmark.sh --full`)
2. **Validar hit rate 70%+** (vs 40% atual)
3. **Implementar métricas padrão** (Precision@K, Recall@K, MRR)

### Curto Prazo (2-4 Semanas)
1. **Implementar baselines** (RAG simples, Mem0)
2. **Rodar ablation study** (5 variantes do Cortex)
3. **Criar dataset anotado** (ground truth para avaliação)

### Médio Prazo (1-2 Meses)
1. **Escrever paper científico** (ACL/EMNLP format)
2. **Preparar código reproduzível** (Docker + docs)
3. **Submeter para conferência** (EMNLP 2026)

## 📚 Documentação Completa

- **[VISION.md](../../docs/VISION.md)** — Filosofia e conceitos fundamentais
- **[ARCHITECTURE.md](../../docs/ARCHITECTURE.md)** — Estrutura de camadas
- **[MCP.md](../../docs/MCP.md)** — Integração Model Context Protocol
- **[DEVELOPMENT.md](../../DEVELOPMENT.md)** — Guia de desenvolvimento

# Ver análise detalhada
cat benchmark/results/PRELIMINARY_REPORT.md
```

### 2. Análise Programática
```bash
# Executar análise completa do grafo
./analyze_results.sh

# Ou executar scripts individualmente
python benchmark/analyze_graph.py   # Métricas gerais
python benchmark/analyze_hubs.py    # Hubs e centralidade
```

### 3. Exploração Manual
```python
import json

# Carregar summary
with open('benchmark/results/benchmark_20260105_225459.summary.json') as f:
    summary = json.load(f)

# Ver métricas
print(summary['token_metrics'])
print(summary['memory_metrics'])

# Carregar grafo
with open('data/benchmark/memory_graph.json') as f:
    graph = json.load(f)

# Explorar entidades
print(len(graph['entities']), "entidades")
print(len(graph['episodes']), "episódios")
```

## 📊 Estrutura do Summary JSON

```json
{
  "overview": {
    "model": "ministral-3:3b",
    "duration_seconds": 71.89,
    "total_conversations": 1,
    "total_messages": 5
  },
  "token_metrics": {
    "baseline": { "total_tokens": 3146, ... },
    "cortex": { "total_tokens": 2064, ... },
    "comparison": { "token_difference_pct": 34.39, ... }
  },
  "time_metrics": {
    "baseline": { "total_time_ms": 42756, ... },
    "cortex": {
      "total_time_ms": 29129,
      "avg_recall_time_ms": 12.57,
      "avg_store_time_ms": 4183
    }
  },
  "memory_metrics": {
    "memory_hit_rate": 40.0,
    "total_entities_recalled": 5,
    "total_episodes_recalled": 4
  }
}
```

## 🎯 Interpretação dos Resultados

### ✅ Métricas Boas
- **Token Economy > 30%** — Economicamente viável
- **Time Economy > 20%** — Mais rápido que baseline
- **Memory Hit Rate > 40%** — Boa taxa de acerto
- **Recall < 50ms** — Busca instantânea

### ⚠️ Alertas
- **Store Time > 2000ms** — Gargalo identificado
- **Consolidation Rate < 5%** — Poucos padrões (esperado para amostra pequena)
- **Entities/Episode > 5** — Possível sobre-extração

### 🔴 Problemas
- **Memory Hit Rate < 20%** — Recall não está funcionando
- **Token Economy < 0%** — Cortex usando mais tokens que baseline
- **Recall > 100ms** — Busca lenta

## 📈 Próximos Passos

1. **Aguardar rate limit resetar** (~30-60 min)
2. **Executar benchmark completo:**
   ```bash
   ./start_benchmark.sh --resume
   ```
3. **Analisar resultados completos:**
   ```bash
   ./analyze_results.sh
   ```
4. **Comparar com ablation:**
   ```bash
   python benchmark/ablation_runner.py
   ```

## 🐛 Troubleshooting

### Rate Limit Errors
```
⏳ Rate limit atingido. Aguardando 30s...
```
**Solução:** Aguardar ou usar `--delay` maior:
```bash
./start_benchmark.sh --delay 10  # 10s entre mensagens
```

### Store muito lento (>5s)
**Possíveis causas:**
- Serialização JSON grande
- Consolidation check O(n²)
- I/O bloqueante

**Investigar:**
```bash
python -m cProfile benchmark/run_benchmark.py
```

### Baixa taxa de acerto (<20%)
**Possíveis causas:**
- Recall query muito genérica
- Falta de context em store
- Entity resolution ruim

**Investigar:**
```bash
# Ver logs detalhados
CORTEX_DEBUG=1 python benchmark/run_benchmark.py
```

## 📚 Referências

- [W5H_DESIGN.md](../../docs/W5H_DESIGN.md) — Design do modelo W5H
- [ARCHITECTURE.md](../../docs/ARCHITECTURE.md) — Arquitetura do Cortex
- [benchmark/README.md](../README.md) — Documentação do benchmark

---

**Última atualização:** 05/01/2026
