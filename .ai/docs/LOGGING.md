# Cortex Logging System

Sistema de auditoria e logging para rastreamento completo de operações no Cortex.

## 📋 Visão Geral

O Cortex possui um sistema de logging centralizado que registra todas as operações importantes:

- **Audit Logs**: Rastreamento completo de CRUD (Create, Read, Update, Delete)
- **Performance Logs**: Métricas de tempo e recursos
- **General Logs**: Informações gerais de debug e operação
- **Logs Rotativos**: Rotação automática por tamanho (10MB por arquivo)
- **Formato JSON**: Logs estruturados para análise automatizada (opcional)

## 🚀 Uso Rápido

### Logging Básico

```python
from cortex.utils.logging import get_logger

logger = get_logger("meu_modulo")

logger.debug("Mensagem de debug")
logger.info("Operação concluída")
logger.warning("Atenção: recurso deprecado")
logger.error("Erro ao processar dados")
```

### Audit Logging (Rastreamento de Operações)

```python
from cortex.utils.logging import get_audit_logger

audit = get_audit_logger("memory_graph")

# Registra criação
audit.log_create("episode", episode_id="ep_123", action="test", user_id="user_456")

# Registra atualização
audit.log_update("entity", entity_id="ent_789", changes=["name", "email"])

# Registra acesso
audit.log_access("memory", memory_id="mem_abc", user_id="user_456", query="busca")

# Registra exclusão
audit.log_delete("episode", episode_id="ep_old", reason="expired")
```

### Performance Logging (Métricas)

```python
from cortex.utils.logging import get_performance_logger

perf = get_performance_logger("embedding_service")

# Opção 1: Context manager (recomendado)
with perf.measure("embed_text"):
    embedding = service.embed(text)

# Opção 2: Manual
perf.start("recall_memories")
memories = graph.recall(query)
perf.end("recall_memories", count=len(memories))

# Opção 3: Métrica direta
perf.log_metric("embedding", duration_ms=45.2, dimensions=1024, cached=False)
```

## ⚙️ Configuração

Configure via variáveis de ambiente no arquivo `.env`:

```bash
# Nível de logging
LOG_LEVEL=INFO                      # DEBUG | INFO | WARNING | ERROR | CRITICAL

# Diretórios
LOG_DIR=logs                        # Logs gerais
AUDIT_DIR=logs/audit                # Logs de auditoria

# Opções
LOG_ENABLE_CONSOLE=true             # Mostrar logs no console
LOG_ENABLE_FILE=true                # Salvar em arquivos
LOG_ENABLE_JSON=false               # Formato JSON (recomendado para produção)
```

### Níveis de Log

- **DEBUG**: Informações detalhadas para desenvolvimento
- **INFO**: Confirmação de operações normais
- **WARNING**: Avisos de situações incomuns (mas não críticas)
- **ERROR**: Erros que precisam atenção
- **CRITICAL**: Falhas graves do sistema

## 📁 Estrutura de Arquivos

```
logs/
├── general.log           # Logs gerais do sistema
├── audit.log             # Logs de auditoria (CRUD operations)
├── performance.log       # Métricas de performance
├── error.log             # Apenas erros
└── audit/
    ├── memory_graph_20260115.log     # Audit por componente
    ├── memory_service_20260115.log
    └── embedding_service_20260115.log
```

## 📊 Formato dos Logs

### Formato Texto (padrão)

```
2026-01-15 03:22:45 - memory_graph - INFO - Memory stored: action='analyze_bug', episode=ep_123 (23.4ms)
2026-01-15 03:22:46 - embedding_service - DEBUG - Embedding generated: dimensions=1024, latency=45.2ms
```

### Formato JSON (produção)

```json
{
  "timestamp": "2026-01-15T03:22:45.123456",
  "level": "INFO",
  "logger": "audit.memory_graph",
  "message": "CREATE episode",
  "operation": "CREATE",
  "entity_type": "episode",
  "episode_id": "ep_123",
  "action": "analyze_bug",
  "participants": 2
}
```

## 🔍 Exemplos de Uso

### 1. Logging em Módulo Customizado

```python
from cortex.utils.logging import get_logger, get_performance_logger

class MeuServico:
    def __init__(self):
        self.logger = get_logger("meu_servico")
        self.perf = get_performance_logger("meu_servico")

    def processar(self, dados):
        self.logger.info(f"Processando {len(dados)} itens")

        with self.perf.measure("processar_dados", item_count=len(dados)):
            # ... processamento ...
            resultado = self._processar_interno(dados)

        self.logger.info(f"Processamento concluído: {len(resultado)} resultados")
        return resultado
```

### 2. Debugging com Logs

```python
# Configure nível DEBUG temporariamente
import os
os.environ["LOG_LEVEL"] = "DEBUG"

from cortex.utils.logging import CortexLogger, get_logger

# Re-inicialize com force=True
CortexLogger.initialize(level=10, force=True)  # 10 = DEBUG

logger = get_logger("debug_session")
logger.debug("Informação detalhada de debug")
```

### 3. Análise de Performance

```python
# Leia métricas de performance
import json
from pathlib import Path

perf_log = Path("logs/performance.log")
for line in perf_log.read_text().splitlines():
    if "recall" in line and "duration_ms" in line:
        print(line)

# Se usando JSON:
if "enable_json=true":
    for line in perf_log.read_text().splitlines():
        data = json.loads(line)
        if data["operation"] == "recall":
            print(f"Recall: {data['duration_ms']}ms, {data['episodes_found']} episodes")
```

## 🛠️ Integração com Componentes Cortex

O logging já está integrado automaticamente nos principais componentes:

### MemoryGraph
- ✅ Criação/atualização de entidades e episódios
- ✅ Operações de recall (com métricas de performance)
- ✅ Consolidação de episódios
- ✅ Detecção de contradições

### EmbeddingService
- ✅ Geração de embeddings (com latência e cache hits)
- ✅ Erros de conexão com Ollama
- ✅ Timeouts e falhas

### MemoryService
- ✅ Store e recall de memórias (com métricas)
- ✅ Criação de entidades e relações
- ✅ Namespace isolation

## 🚨 Troubleshooting

### Logs Não Estão Sendo Gerados

1. Verifique se `LOG_ENABLE_FILE=true` no `.env`
2. Verifique permissões da pasta `logs/`
3. Force re-inicialização: `CortexLogger.initialize(force=True)`

### Logs Muito Verbosos

```bash
# Reduza o nível de logging
LOG_LEVEL=WARNING  # Apenas warnings e errors
```

### Embeddings Falhando Silenciosamente

```bash
# Aumente nível de log e verifique logs
LOG_LEVEL=DEBUG
cat logs/general.log | grep -i "embedding"
```

Agora você verá mensagens como:
```
ERROR - Embedding connection error: url=http://localhost:11434, error=Connection refused
```

## 📝 Boas Práticas

1. **Use níveis apropriados**:
   - `DEBUG`: Apenas para desenvolvimento
   - `INFO`: Operações normais
   - `WARNING`: Situações incomuns
   - `ERROR`: Falhas que precisam atenção

2. **Inclua contexto**:
   ```python
   # ❌ Ruim
   logger.error("Falhou")

   # ✅ Bom
   logger.error(f"Falha ao gerar embedding para episódio {episode_id}: {error}")
   ```

3. **Use performance logging**:
   - Para operações > 100ms
   - Para operações críticas de performance
   - Para análise de gargalos

4. **Audit logging para compliance**:
   - Todas as operações de CRUD
   - Acessos a dados sensíveis
   - Alterações de configuração

## 🔐 Segurança e Privacidade

- **Não logue senhas ou tokens**: Sempre sanitize dados sensíveis
- **PII (Personal Identifiable Information)**: Use hashing para IDs de usuários
- **Rotação automática**: Logs antigos são rotacionados automaticamente
- **Permissões**: Certifique-se que `logs/` tem permissões adequadas

```python
# ❌ NÃO FAÇA ISSO
logger.info(f"User login: email={email}, password={password}")

# ✅ FAÇA ISSO
import hashlib
user_hash = hashlib.sha256(email.encode()).hexdigest()[:8]
logger.info(f"User login: user_hash={user_hash}")
```

## 🧪 Testes

Execute os testes de logging:

```bash
python tests/test_logging_system.py
```

Saída esperada:
```
✅ All logging tests passed!

Logging system is working correctly:
  - Basic logging ✓
  - Audit logging ✓
  - Performance logging ✓
  - Cortex integration ✓
  - Log rotation ✓
```

## 📊 Monitoramento em Produção

### Opção 1: Análise Manual

```bash
# Logs recentes
tail -f logs/general.log

# Apenas erros
grep -i error logs/general.log

# Operações lentas (> 100ms)
grep -E "duration_ms=[0-9]{3,}" logs/performance.log
```

### Opção 2: Ferramentas de Análise

Com `LOG_ENABLE_JSON=true`, você pode usar ferramentas como:

- **jq**: Análise de JSON no terminal
  ```bash
  cat logs/audit.log | jq '.operation' | sort | uniq -c
  ```

- **Elasticsearch + Kibana**: Para logs em produção de larga escala

- **Grafana Loki**: Para agregação e visualização de logs

---

**Documentação Completa**: [docs/](../README.md)
**Código**: [src/cortex/utils/logging.py](../src/cortex/utils/logging.py)
**Testes**: [tests/test_logging_system.py](../tests/test_logging_system.py)
