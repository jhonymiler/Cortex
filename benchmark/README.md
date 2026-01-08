# Cortex Benchmark

Benchmark focado em **VALOR**, não apenas métricas brutas.

## Filosofia

Este benchmark avalia a **qualidade da informação recuperada**, não apenas velocidade ou tokens.
O Cortex não compete em quantidade, compete em **inteligência da memória**.

## Métricas de VALOR (foco principal)

| Métrica | O que mede |
|---------|------------|
| **Acurácia Semântica** | Encontra memória certa com termos diferentes |
| **Recall Contextual** | Lembra de fluxos anteriores |
| **Memória Coletiva** | Compartilha conhecimento útil entre usuários |
| **Relevância** | Retorna informação útil, não ruído |

## Métricas de Eficiência (secundárias)

| Métrica | Descrição |
|---------|-----------|
| Latência | Tempo de resposta (ms) |
| Tokens | Tamanho do contexto injetado |

## Benchmarks Disponíveis

### 1. Paper Benchmark (padrão)
Avalia o Cortex isoladamente com métricas completas para publicação.

```bash
./start_benchmark.sh
# ou
./start_benchmark.sh --paper
```

### 2. Comparison Benchmark
Compara Cortex vs Baseline vs RAG vs Mem0.

```bash
./start_benchmark.sh --compare
```

## Estrutura

```
benchmark/
├── paper_benchmark.py       # Benchmark para paper acadêmico
├── comparison_benchmark.py  # Comparativo Cortex vs RAG vs Mem0
├── agents.py                # Implementação dos agentes base
├── cortex_agent.py          # Agente Cortex
├── rag_agent.py             # Agente RAG (TF-IDF)
├── mem0_agent.py            # Agente Mem0 (salience)
├── conversation_generator.py # Gerador de cenários
└── _old/                    # Arquivos obsoletos
```

## Resultados

Os resultados são salvos em `benchmark_results/`:

```
benchmark_results/
├── paper_benchmark_YYYYMMDD_HHMMSS.json
└── comparison_YYYYMMDD_HHMMSS.json
```

## Análise

Para analisar resultados existentes:

```bash
bash ./analyze_results.sh
```

## Diferenciais do Cortex

1. **Busca Semântica**: 100% de acurácia com embeddings
2. **Memória Contextual**: Lembra de fluxos completos
3. **Conhecimento Coletivo**: Compartilha entre usuários do mesmo tenant
4. **Isolamento**: Separação automática entre tenants (PII/PCI)
5. **Consolidação**: Compacta memórias similares automaticamente

## Requisitos

- Python 3.11+
- Ollama com modelo qwen3-embedding:0.6b
- API Cortex rodando

## Configuração

Variáveis de ambiente (`.env`):

```ini
OLLAMA_URL=http://localhost:11434
CORTEX_API_URL=http://localhost:8000
CORTEX_EMBEDDING_MODEL=qwen3-embedding:0.6b
```
