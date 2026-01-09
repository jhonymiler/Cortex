# 📊 Cortex Benchmark

> *"Porque agentes inteligentes precisam de memória inteligente"*

## Visão Geral

Este benchmark mede o **valor real** do Cortex comparando com alternativas (Baseline, RAG, Mem0).

### 5 Dimensões de Valor

| Dimensão | O que mede | Por que importa |
|----------|-----------|-----------------|
| **Cognição Biológica** | Decay, consolidação, hubs | Só Cortex esquece e aprende |
| **Memória Coletiva** | Compartilhamento, isolamento | Só Cortex é multi-tenant |
| **Valor Semântico** | Acurácia, relevância | Encontra o que importa |
| **Eficiência** | Latência, tokens | Menos custo, mais valor |
| **Segurança** | Anti-jailbreak, IdentityKernel | Proteção contra ataques |

## Uso Rápido

```bash
# Benchmark unificado (recomendado)
./start_benchmark.sh

# Ou diretamente
python -m benchmark.unified_benchmark

# Apenas métricas do Cortex (para paper)
./start_benchmark.sh --paper
```

## Resultados Atuais

| Dimensão | Baseline | RAG | Mem0 | **Cortex** |
|----------|----------|-----|------|------------|
| Cognição Biológica | 0% | 0% | 0% | **100%** |
| Memória Coletiva | 0% | 0% | 0% | **75%** |
| Valor Semântico | 50% | 100% | 100% | **100%** |
| Eficiência | 0% | 0% | 0% | **100%** |
| Segurança | 0% | 0% | 0% | **100%** |
| **TOTAL** | 15% | 31% | 23% | **93%** |

🏆 **Cortex supera melhor alternativa em +62%**

## Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `unified_benchmark.py` | Benchmark principal com 5 dimensões |
| `paper_benchmark.py` | Benchmark isolado para métricas acadêmicas |
| `agents.py` | Agentes de comparação (Baseline, Cortex) |
| `cortex_agent.py` | Implementação do agente Cortex |
| `rag_agent.py` | Baseline RAG (TF-IDF) |
| `mem0_agent.py` | Baseline Mem0 |

## Configuração

```bash
# Variáveis de ambiente
export OLLAMA_URL=http://localhost:11434
export OLLAMA_MODEL=gemma3:4b
export CORTEX_EMBEDDING_MODEL=qwen3-embedding:0.6b
```

## Interpretação dos Resultados

### Cognição Biológica
- **100%**: Hub detection + consolidação funcionando
- **50%**: Apenas um dos dois funcionando
- **0%**: Sistema não implementa cognição biológica

### Memória Coletiva
- **100%**: Herança de namespace + isolamento perfeitos
- **75%**: Maioria dos testes passando
- **0%**: Sistema é single-tenant

### Valor Semântico
- **100%**: Encontra memória correta com sinônimos + filtra ruído
- **50%**: Só acerta com termos exatos

### Eficiência
- **100%**: Latência <100ms + tokens compactos
- **0%**: Não otimizado

## Resultados são salvos em

```
benchmark/results/
├── unified_YYYYMMDD_HHMMSS.json
└── paper_YYYYMMDD_HHMMSS.json
```
