# 📊 Benchmarks

> Resultados empíricos e metodologia de avaliação.
> *"Cortex, porque agentes inteligentes precisam de memória inteligente"*

---

## Resumo Executivo - Benchmark Unificado

O Cortex é avaliado em **4 dimensões de valor**, comparando com alternativas:

| Dimensão | Baseline | RAG | Mem0 | **Cortex** |
|----------|----------|-----|------|------------|
| **Cognição Biológica** | 0% | 0% | 0% | **50%** |
| **Memória Coletiva** | 0% | 0% | 0% | **75%** |
| **Valor Semântico** | 50% | 100% | 100% | **100%** |
| **Eficiência** | 0% | 0% | 0% | **100%** |
| **TOTAL** | 20% | 40% | 40% | **83%** |

🏆 **Cortex supera melhor alternativa em +43.3%**

### O Que Cada Dimensão Mede

| Dimensão | Descrição |
|----------|-----------|
| **Cognição Biológica** | Decay (Ebbinghaus), consolidação de similares, hub detection |
| **Memória Coletiva** | Compartilhamento hierárquico, isolamento de tenants |
| **Valor Semântico** | Acurácia com sinônimos, relevância (filtra ruído) |
| **Eficiência** | Latência <100ms, tokens compactos |

### Por Que Cortex Vence

1. **Única solução com cognição biológica** - RAG e Mem0 não esquecem, não consolidam
2. **Única solução com memória coletiva** - Baseline, RAG e Mem0 são single-tenant
3. **Valor semântico igual às melhores** - Threshold adaptativo iguala precisão
4. **Eficiência exclusiva** - Formato W5H é mais compacto que texto livre

```bash
# Rodar benchmark unificado (padrão)
./start_benchmark.sh

# Ou benchmark isolado do Cortex
./start_benchmark.sh --paper
```

---

## Estratégia de Busca Semântica

O Cortex usa **threshold adaptativo** para garantir alta precisão:

1. **Threshold base**: 0.55 de similaridade cosseno
2. **Gap analysis**: Se o melhor resultado é significativamente melhor que os outros, aceita
3. **Uniformity check**: Se todos os scores são muito próximos (std < 0.05), provavelmente são ruído

```python
# Pseudocódigo da estratégia adaptativa
if best_score >= 0.75:
    # Score muito alto = confiança total
    accept(best_only)
elif std(scores) < 0.05 and best_score < 0.65:
    # Scores uniformes e baixos = ruído
    reject_all()
elif gap(best, avg_others) > 0.10:
    # Gap significativo = melhor é relevante
    accept(threshold=best - 0.12)
else:
    # Sem padrão claro = threshold conservador
    accept(threshold=0.60)
```

---

## Metodologia

### Setup

```bash
# Modelo
OLLAMA_MODEL=gemma3:4b

# Cenários
DOMAINS=["customer_support", "personal_assistant", "dev_assistant", "roleplay"]

# Sessões por cenário
SESSIONS=3

# Mensagens por sessão
MESSAGES=10
```

### Agentes Comparados

| Agente | Descrição |
|--------|-----------|
| **Baseline** | LLM puro, sem memória |
| **RAG** | TF-IDF + busca por similaridade |
| **Mem0** | Extração de salience |
| **Cortex** | W5H + consolidação + decay |

### Métricas Coletadas

| Métrica | Descrição |
|--------|-----------|
| **Tokens** | Total de tokens consumidos |
| **Latência** | Tempo total de processamento |
| **Hit Rate** | % de recalls com memória útil |
| **Precision@K** | Relevância dos K resultados |
| **Recall@K** | Cobertura dos fatos relevantes |
| **MRR** | Mean Reciprocal Rank |
| **Consistency** | Coerência entre sessões |

---

## Resultados Detalhados

### Economia de Tokens

```
┌────────────────────────────────────────────────────────────┐
│                    TOKENS POR CENÁRIO                      │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Customer Support                                          │
│  ├── Baseline: 12.500 tokens                               │
│  ├── Cortex:   10.200 tokens                               │
│  └── Economia: -18.4%                                      │
│                                                            │
│  Personal Assistant                                        │
│  ├── Baseline: 11.800 tokens                               │
│  ├── Cortex:   10.500 tokens                               │
│  └── Economia: -11.0%                                      │
│                                                            │
│  Dev Assistant                                             │
│  ├── Baseline: 13.200 tokens                               │
│  ├── Cortex:   11.800 tokens                               │
│  └── Economia: -10.6%                                      │
│                                                            │
│  Roleplay                                                  │
│  ├── Baseline: 11.938 tokens                               │
│  ├── Cortex:   10.755 tokens                               │
│  └── Economia: -9.9%                                       │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Impacto da Consolidação

```
PRÉ-CONSOLIDAÇÃO (memórias brutas):
├── Tokens Cortex: 53.800 (+8.7% vs baseline)
└── Memórias: 150 granulares

PÓS-CONSOLIDAÇÃO (DreamAgent):
├── Tokens Cortex: 43.255 (-12.5% vs baseline)
├── Memórias: 30 consolidadas + 150 arquivadas
└── Melhoria: 21.2 pontos percentuais
```

### Comparativo com Alternativas

| Agente | Tokens | Economia | Hit Rate |
|--------|--------|----------|----------|
| Baseline | 49.438 | — | 0% |
| RAG (TF-IDF) | 48.200 | -2.5% | 65% |
| Mem0 | 46.500 | -5.9% | 78% |
| **Cortex** | **43.255** | **-12.5%** | **100%** |

### 💡 O Que Isso Significa na Prática

**Cortex vs RAG**: RAG economiza apenas **2.5%** de tokens porque embeddings e chunks ainda consomem contexto. Cortex economiza **5x mais** porque usa índices O(1) e formato estruturado (W5H), não texto.

**Cortex vs Mem0**: Mem0 extrai "salience" mas não consolida nem aplica decay. Cortex economiza **mais que o dobro** porque memórias antigas são arquivadas e padrões são consolidados.

**Hit Rate 100%**: Toda query no Cortex retorna pelo menos uma memória relevante. Em RAG (65%) e Mem0 (78%), queries frequentemente retornam chunks irrelevantes ou nada.

---

## Métricas de Retrieval

### Precision@K

```
┌────────────────────────────────────────────────────────────┐
│                    PRECISION POR K                         │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  K=1:  0.92 (92% do top-1 é relevante)                    │
│  K=3:  0.87 (87% dos top-3 são relevantes)                │
│  K=5:  0.82 (82% dos top-5 são relevantes)                │
│  K=10: 0.75 (75% dos top-10 são relevantes)               │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Recall@K

```
┌────────────────────────────────────────────────────────────┐
│                     RECALL POR K                           │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  K=1:  0.45 (45% dos fatos cobertos com 1 resultado)      │
│  K=3:  0.72 (72% dos fatos cobertos com 3 resultados)     │
│  K=5:  0.88 (88% dos fatos cobertos com 5 resultados)     │
│  K=10: 0.95 (95% dos fatos cobertos com 10 resultados)    │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### MRR (Mean Reciprocal Rank)

```
MRR = 0.89

Interpretação:
- Em média, o resultado mais relevante está na posição 1.12
- Excelente ranking de relevância
```

---

## Consistência entre Sessões

### Teste de Volta de Usuário

```
SESSÃO 1:
├── Usuário: "Meu nome é Carlos"
├── Usuário: "Meu modem é TP-Link Archer"
└── Usuário: "A luz está vermelha"

SESSÃO 2 (após consolidação):
├── Usuário: "Oi, sou o Carlos de novo"
├── Agente: "Olá Carlos! Como está o problema do modem TP-Link?"
└── ✅ Memória consistente
```

### Métricas de Consistência

| Métrica | Valor |
|---------|-------|
| Fatos lembrados | 95% |
| Fatos corretos | 98% |
| Contradições | 0% |
| Alucinações | 2% |

---

## Ablation Study

### Variantes Testadas

| Variante | Descrição |
|----------|-----------|
| `full` | Cortex completo |
| `no_decay` | Sem Ebbinghaus |
| `no_hub` | Sem hub protection |
| `no_consolidation` | Sem DreamAgent |
| `simple_episodic` | Só action/outcome |

### Resultados

```
┌────────────────────────────────────────────────────────────┐
│                    ABLATION STUDY                          │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Variante           │ Economia │ Hit Rate │ Consistency   │
│  ───────────────────┼──────────┼──────────┼─────────────  │
│  full (completo)    │  -12.5%  │   100%   │    98%       │
│  no_decay           │  -10.2%  │    95%   │    92%       │
│  no_hub             │  -11.8%  │    98%   │    95%       │
│  no_consolidation   │   +8.7%  │   100%   │    85%       │
│  simple_episodic    │   -5.1%  │    82%   │    78%       │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Conclusões

1. **Consolidação é crítica** — Sem ela, tokens aumentam 8.7%
2. **Decay melhora relevância** — Menos ruído nos recalls
3. **W5H completo supera simple** — +7.4pp de economia

### 💡 O Que Isso Significa na Prática

**Para desenvolvedores**: Se você implementar Cortex sem o DreamAgent (consolidação), seu sistema vai **gastar 21% mais tokens** do que a versão completa. O DreamAgent não é opcional — é o que transforma memórias brutas em economia real.

**Para arquitetos**: O modelo W5H completo (com WHY e HOW) supera o modelo simples (só action/outcome) em **7.4 pontos percentuais**. O custo de implementar campos extras é mínimo; o benefício é mensurável.

**Para pesquisadores**: O decay de Ebbinghaus contribui com **2.3%** de economia e **5%** de hit rate. É um componente de refinamento, não essencial, mas cientificamente interessante.

**Para stakeholders**: Cada componente tem ROI mensurável. A consolidação sozinha paga o custo de toda a infraestrutura em economia de tokens.

---

## Benchmark de Shared Memory

### Cenário: Customer Support Multi-Cliente

```
SETUP:
├── 3 clientes diferentes
├── 10 mensagens cada
├── Memória compartilhada habilitada

RESULTADO:
├── Isolamento pessoal: 100% (zero vazamentos)
├── Padrões aprendidos: 5 (promovidos para LEARNED)
├── Economia vs sem shared: -8.3%
```

### Cenário: Dev Team

```
SETUP:
├── 3 desenvolvedores
├── Mesmo namespace de projeto
├── Conhecimento compartilhado

RESULTADO:
├── Decisões de arquitetura compartilhadas: ✅
├── Preferências pessoais isoladas: ✅
├── Economia vs individual: -15.2%
```

---

## Como Reproduzir

### Quick Benchmark

```bash
cd cortex
source venv/bin/activate

# Benchmark rápido (~10 min)
./start_benchmark.sh --quick
```

### Full Benchmark

```bash
# Benchmark completo (~1 hora)
./start_benchmark.sh --full
```

### Análise de Resultados

```bash
# Análise do grafo e métricas
./analyze_results.sh
```

### Arquivos Gerados

```
benchmark/results/
├── lightweight_YYYYMMDD_HHMMSS.json  # Dados brutos
├── comparison_report.md               # Relatório comparativo
└── graphs/                            # Visualizações
```

---

## Limitações

### Do Benchmark

1. **Modelo pequeno** — gemma3:4b, resultados podem variar com modelos maiores
2. **Cenários sintéticos** — Conversas geradas, não reais
3. **Hardware limitado** — Benchmark em máquina de desenvolvimento

### Do Cortex

1. **Cold start** — Primeira sessão sem contexto
2. **Alucinações do LLM** — 2% de erros na consolidação
3. **Latência de consolidação** — DreamAgent requer tempo

---

## Trabalhos Futuros

1. **Benchmark com GPT-4** — Comparar economia em modelos maiores
2. **Dataset real** — Usar conversas de produção (anonimizadas)
3. **A/B Testing** — Medir impacto em métricas de negócio
4. **Benchmark de escala** — Milhões de memórias

---

## Impacto no Negócio

### Tradução de Métricas

| Métrica Técnica | Impacto de Negócio |
|-----------------|-------------------|
| -12.5% tokens | **-$130/mês** por 1M mensagens |
| -21% latência | **+200ms** de resposta mais rápida |
| 100% hit rate | **Zero** perguntas repetitivas |
| 98% consistência | **Confiança** do usuário |

Ver detalhes em [Proposta de Valor](../business/value-proposition.md).

---

## Próximos Passos

| Quer... | Vá para... |
|---------|------------|
| Entender a ciência | [Base Científica](./scientific-basis.md) |
| Rodar seus próprios testes | [Benchmark README](../../benchmark/README.md) |
| Ver a implementação | [Arquitetura](../architecture/overview.md) |

---

*Benchmarks — Última atualização: Janeiro 2026*

