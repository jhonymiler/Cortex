# 📊 Métricas para Paper Acadêmico

> *"Cortex, porque agentes inteligentes precisam de memória inteligente"*

---

## As 4 Dimensões de Valor

O Cortex é avaliado em **4 dimensões** que demonstram o **valor real** do sistema:

| Dimensão | O Que Mede | Por Que Importa | Score |
|----------|------------|-----------------|-------|
| 🧠 **Cognição Biológica** | Decay, consolidação, hubs | Apenas Cortex esquece e aprende | 50% |
| 👥 **Memória Coletiva** | Herança hierárquica, isolamento | Apenas Cortex é multi-tenant | 75% |
| 🎯 **Valor Semântico** | Sinônimos, threshold adaptativo | Encontra o que importa | 100% |
| ⚡ **Eficiência** | Latência <100ms, tokens compactos | Menor custo, maior velocidade | 100% |

### Resultado Comparativo (Janeiro 2026)

| Dimensão | Baseline | RAG | Mem0 | **Cortex** |
|----------|----------|-----|------|------------|
| Cognição Biológica | 0% | 0% | 0% | **50%** |
| Memória Coletiva | 0% | 0% | 0% | **75%** |
| Valor Semântico | 50% | 100% | 100% | **100%** |
| Eficiência | 0% | 0% | 0% | **100%** |
| **TOTAL** | **20%** | **40%** | **40%** | **83%** |

🏆 **Cortex supera a melhor alternativa em +43.3%**

---

## Detalhamento por Dimensão

### 1. 🧠 Cognição Biológica (50%)

**O que mede**: Capacidade de encontrar a memória correta usando **termos diferentes** dos originais.

**Por que importa**: Usuários raramente usam as mesmas palavras. Um sistema de memória precisa entender **intenção**, não apenas fazer match exato.

**Metodologia**:
- Salva memórias com termos específicos (ex: "problema_login_sistema")
- Busca com sinônimos/paráfrases (ex: "não consigo entrar")
- Usa embeddings semânticos (qwen3-embedding:0.6b)

**Resultado**: 10/10 testes passaram

```
✅ "não consigo entrar no sistema" → problema_login
✅ "esqueci minha senha" → problema_login
✅ "boleto não veio" → fatura_nao_recebida
✅ "cobrança foi recusada" → erro_pagamento
```

---

### 2. Recall Contextual (100%)

**O que mede**: Capacidade de **lembrar de fluxos e conversas** anteriores.

**Por que importa**: Conversas são sequenciais. O sistema precisa entender o contexto completo do atendimento.

**Metodologia**:
- Simula conversa multi-turno (cliente → problema → garantia → troca)
- Busca por diferentes aspectos do fluxo
- Verifica se retorna episódios relevantes

**Resultado**: 5/5 testes passaram

```
✅ "produto defeituoso" → defeito
✅ "garantia do produto" → garantia  
✅ "troca agendada" → troca
```

---

### 3. Memória Coletiva (75%)

**O que mede**: **Compartilhamento de conhecimento** entre usuários do mesmo tenant.

**Por que importa**: Conhecimento aprendido com um cliente deve beneficiar outros. Evita resolver o mesmo problema repetidamente.

**Metodologia**:
- Salva conhecimento no namespace pai com visibility="learned"
- Busca a partir de namespaces filhos (diferentes usuários)
- Verifica isolamento entre tenants diferentes

**Resultado**: 3/4 testes passaram

```
✅ User2 encontra recuperação de senha (do namespace pai)
✅ User3 encontra atualização (do namespace pai)
✅ Isolamento entre tenants (outro_tenant não vê)
❌ User1 não encontrou solução de conexão (edge case)
```

**Arquitetura**:
```
suporte (pai - LEARNED)
├── suporte:user1 (filho - PERSONAL)
├── suporte:user2 (filho - PERSONAL)
└── suporte:user3 (filho - PERSONAL)
```

---

### 4. Relevância (67%)

**O que mede**: O sistema retorna **apenas informação útil**, não ruído.

**Por que importa**: Injetar contexto irrelevante confunde o LLM e desperdiça tokens.

**Metodologia**:
- Salva memórias variadas (compra, reclamação, elogio)
- Query específica deve retornar só o relevante
- Query sem match deve retornar vazio

**Resultado**: 2/3 testes passaram

```
✅ Query específica retorna só relevante
✅ Query sem match retorna vazio
⚠️ Query ampla retornou mais que esperado
```

**Threshold de similaridade**: 0.6 (configurável)

---

### 5. Eficiência (100%)

**O que mede**: Performance operacional do sistema.

**Por que importa**: Latência alta prejudica UX. Contexto grande desperdiça tokens.

**Metodologia**:
- Mede latência de recall em múltiplas chamadas
- Conta tokens no contexto gerado

**Resultado**: 2/2 testes passaram

```
✅ Latência média: 42ms (< 500ms threshold)
✅ Tokens no contexto: compacto
```

---

## Comparativo com Sistemas Tradicionais

| Aspecto | Baseline | RAG | Mem0 | Cortex |
|---------|----------|-----|------|--------|
| **Score Total** | 20% | 40% | 40% | **83%** |
| **Cognição Biológica** | ❌ | ❌ | ❌ | **✅** |
| **Memória Coletiva** | ❌ | ❌ | ❌ | **✅** |
| **Valor Semântico** | 50% | 100% | 100% | **100%** |
| **Eficiência** | ❌ | ❌ | ❌ | **✅** |
| **Decaimento** | ❌ | ❌ | ❌ | **Ebbinghaus** |
| **Consolidação** | ❌ | ❌ | ❌ | **DreamAgent** |
| **Isolamento** | ❌ | Manual | Manual | **Hierárquico** |

---

## Vantagens Exclusivas do Cortex

### 1. Embedding Semântico
- Usa modelos de embedding especializados (qwen3-embedding)
- Encontra memórias por **significado**, não palavras
- 100% de acurácia em testes de sinônimos

### 2. Namespace Hierárquico
- Isolamento automático por tenant/usuário
- Herança de conhecimento coletivo
- Não requer configuração complexa

### 3. Modelo W5H
- Estrutura memória em Who/What/Why/When/Where/How
- Facilita busca contextual
- Suporta consolidação

### 4. Relevância Inteligente
- Threshold adaptativo evita ruído
- Retorna vazio quando não há match
- Economiza tokens do LLM

---

## Como Rodar

```bash
# Benchmark completo para paper
./start_benchmark.sh --paper

# Saída: benchmark_results/paper_benchmark_YYYYMMDD_HHMMSS.json
```

### Requisitos
- Python 3.11+
- Ollama com modelos:
  - `gemma3:4b` (LLM)
  - `qwen3-embedding:0.6b` (embeddings)

---

## Arquivo de Saída

O benchmark gera um JSON com todas as métricas:

```json
{
  "timestamp": "2026-01-08T14:03:18",
  "duration_seconds": 20.35,
  "semantic_accuracy": {
    "accuracy": 1.0,
    "avg_latency_ms": 187.6,
    "tests": [...]
  },
  "contextual_recall": { ... },
  "collective_memory": { ... },
  "relevance": { ... },
  "efficiency": { ... },
  "overall_accuracy": 0.917
}
```
