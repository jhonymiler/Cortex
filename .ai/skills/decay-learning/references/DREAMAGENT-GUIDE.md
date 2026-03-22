# DreamAgent - Guia de Configuração e Troubleshooting

Worker em background que consolida memórias brutas em conhecimento estruturado.

## Modos de Execução

### 1. Continuous (Contínuo)

Processa continuamente a cada N minutos.

```bash
# .env
DREAMAGENT_ENABLED=true
DREAMAGENT_MODE=continuous
DREAMAGENT_INTERVAL=15  # minutos
```

**Quando usar**: Produção com volume constante de memórias.

### 2. Batch (Lote)

Processa quando acumular X memórias não consolidadas.

```bash
# .env
DREAMAGENT_ENABLED=true
DREAMAGENT_MODE=batch
DREAMAGENT_BATCH_SIZE=100
```

**Quando usar**: Volume intermitente, economizar recursos.

### 3. Scheduled (Agendado)

Roda em horários específicos via cron job externo.

```bash
# .env
DREAMAGENT_ENABLED=false  # Desabilita worker interno

# Crontab
0 2 * * * cd /path/to/cortex && python -m cortex.workers.dream_agent
```

**Quando usar**: Janelas de manutenção definidas (ex: madrugada).

### 4. Disabled (Desabilitado)

```bash
# .env
DREAMAGENT_ENABLED=false
```

**Quando usar**: Dev/testes, ou quando consolidação não é necessária.

## Processo de Consolidação

### Etapa 1: Refine (Refinamento)

**Objetivo**: Normalizar memórias brutas.

- Corrige typos via LLM
- Remove duplicatas (semantic similarity > 0.95)
- Normaliza formatos (datas, nomes, entidades)

**Input**: Memórias com `consolidated=False`
**Output**: Memórias limpas

### Etapa 2: Extract Patterns (Extração de Padrões)

**Objetivo**: Identificar padrões recorrentes.

**Exemplos**:
- "Erro X sempre ocorre às 3AM" → padrão temporal
- "Usuários do tipo Y sempre perguntam Z" → padrão comportamental
- "Feature A sempre depende de B" → padrão de dependência

**Técnica**: Clustering de memórias similares + análise temporal

### Etapa 3: Promote (Promoção)

**Objetivo**: Elevar padrões para conhecimento coletivo.

```
Memória individual → Pattern Memory → Collective Knowledge
```

**Namespace upgrade**:
```
tenant_x/projeto_a/user_123 → tenant_x/projeto_a/patterns
```

### Etapa 4: Mark Consolidated

**Marca memória como consolidada**:

```python
memory.consolidated = True
memory.stability *= 2.0  # Consolidation bonus
```

**Efeito**: Memória consolidada dura 2x mais tempo.

## Benefícios Mensuráveis

| Métrica | Sem DreamAgent | Com DreamAgent | Ganho |
|---------|----------------|----------------|-------|
| **Recall latency** | 250ms | 100ms | **60% mais rápido** |
| **Duplicatas** | ~15% | <2% | **87% redução** |
| **Padrões descobertos** | 0 | Automático | **Insights grátis** |

## Troubleshooting

### Problema: DreamAgent não consolida

**Possíveis causas**:

1. **Worker desabilitado**
   ```bash
   # Verificar
   echo $DREAMAGENT_ENABLED

   # Solução
   export DREAMAGENT_ENABLED=true
   ```

2. **Intervalo muito alto**
   ```bash
   # Se interval=1440 (1 dia), pode demorar
   DREAMAGENT_INTERVAL=15  # Reduzir para 15 min
   ```

3. **Batch size muito alto**
   ```bash
   # Se batch_size=1000 mas só tem 50 memórias
   DREAMAGENT_BATCH_SIZE=50  # Ajustar
   ```

4. **Erro no worker (logs)**
   ```bash
   tail -f logs/dreamagent.log
   # Verificar erros de LLM, conexão, etc
   ```

### Problema: Consolidação muito lenta

**Causas**:

- LLM lento (Ollama em CPU)
- Muitas memórias acumuladas

**Soluções**:

```bash
# 1. Processar em batches menores
DREAMAGENT_BATCH_SIZE=20

# 2. Usar LLM mais rápido
OLLAMA_MODEL=gemma3:4b  # Mais rápido que modelos maiores

# 3. Paralelizar (se múltiplos cores)
DREAMAGENT_WORKERS=4
```

### Problema: Padrões errados detectados

**Causa**: Threshold de similaridade muito baixo.

**Solução**:

```bash
# Aumentar threshold para clustering
DREAMAGENT_PATTERN_THRESHOLD=0.85  # Padrão 0.75
```

## Monitoramento

### Métricas-Chave

```python
# Via API
GET /api/v1/metrics/dreamagent

{
  "total_consolidated": 1234,
  "patterns_extracted": 56,
  "avg_consolidation_time_ms": 120,
  "last_run": "2026-03-22T14:30:00Z",
  "status": "running"
}
```

### Logs

```bash
# Logs estruturados
tail -f logs/dreamagent.log | jq .

{
  "timestamp": "2026-03-22T14:30:00Z",
  "event": "consolidation_complete",
  "batch_size": 50,
  "duration_ms": 6000,
  "patterns_found": 3
}
```

## Referência de Código

- **Worker**: `src/cortex/workers/dream_agent.py`
- **Consolidação**: `src/cortex/core/consolidation/episode.py`
- **Config**: `src/cortex/config.py` (variáveis DREAMAGENT_*)
