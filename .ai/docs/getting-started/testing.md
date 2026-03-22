# 🧪 Guia Completo de Testes — Cortex v3.0

> **Como validar que o Cortex está funcionando corretamente**

Este guia cobre todos os tipos de testes disponíveis no Cortex, desde validação rápida até benchmarks realistas com LLM.

---

## 📋 Pré-requisitos

Antes de rodar qualquer teste:

1. **API rodando:**
   ```bash
   cortex-api
   # Em outro terminal, verifique: curl http://localhost:8000/health
   ```

2. **Ollama configurado:**
   ```bash
   ollama list | grep -E "(gemma3:4b|qwen3-embedding)"
   # Deve mostrar ambos os modelos
   ```

3. **Ambiente virtual ativo:**
   ```bash
   source venv/bin/activate
   ```

---

## 🚀 Testes Rápidos (< 1 minuto)

### 1. Health Check

Verifica se a API está respondendo:

```bash
curl http://localhost:8000/health
```

**Resposta esperada:**
```json
{
  "status": "healthy",
  "service": "cortex-memory"
}
```

### 2. Ollama Check

Verifica se Ollama está acessível:

```bash
curl http://localhost:11434/api/tags
```

**Resposta esperada:** Lista de modelos em JSON

### 3. Modelos Instalados

```bash
ollama list | grep -E "(gemma3:4b|qwen3-embedding)"
```

**Resposta esperada:**
```
gemma3:4b                         a2af6cc3eb7f    3.3 GB    X minutes ago
qwen3-embedding:0.6b              ac6da0dfba84    639 MB    X minutes ago
```

---

## ✅ Validation Benchmark (30 segundos)

Testa as 7 funcionalidades principais do sistema:

```bash
./start_benchmark.sh validation
```

### O que é testado:

1. **Feature flags** - Todas as melhorias ativas
2. **Consolidação progressiva** - Threshold 2 vs 5
3. **Hierarchical recall** - 4 níveis de memória
4. **Attention mechanism** - Re-ranking com atenção
5. **Forget gate** - Filtragem de ruído
6. **SM-2 adaptive** - Easiness factor ajustável
7. **Backward compatibility** - Legacy mode funciona

### Resultado esperado:

```
============================================================
SUMÁRIO DOS TESTES
============================================================
✅ PASSOU: Todas as Melhorias Ativas
✅ PASSOU: Consolidação Progressiva
✅ PASSOU: Hierarchical Recall
✅ PASSOU: Attention Mechanism
✅ PASSOU: Forget Gate
✅ PASSOU: SM-2 Adaptive
✅ PASSOU: Backward Compatibility

RESULTADO: 7/7 testes passaram (100.0%)
```

### Se falhar:

```bash
# Limpe dados antigos
rm -rf data && mkdir -p data

# Rode novamente
./start_benchmark.sh validation
```

---

## 🎭 Realistic Benchmark (1-10 minutos)

Testa com **LLM real** em **conversas reais**:

### Quick Mode (1-2 minutos)

```bash
./start_benchmark.sh realistic quick
```

### Full Mode (5-10 minutos)

```bash
./start_benchmark.sh realistic
```

### Cenários testados:

#### 1. Customer Support (3 turnos)

```
Dia 1: "Não consigo fazer login"
  → Sistema armazena problema

Dia 2: "Ainda não consegui resolver"
  → Sistema lembra do problema anterior ✓

Dia 3: "Consegui resolver! Como exporto dados?"
  → Sistema lembra da resolução e ajuda com nova questão ✓
```

#### 2. Personal Assistant (2 turnos)

```
Semana 1: "Prefiro reuniões 9-11h"
  → Sistema armazena preferência

Semana 2: "Agende reunião com marketing"
  → Sistema lembra preferência de horário ✓
```

### Resultado esperado (Março 2026):

```
📋 Customer Support:
  WITH memory:
    Context retention: 100%
    Avg response time: 4830ms
    Memories stored: 3
    Conversation coherence: 100%

📋 Personal Assistant:
  WITH memory:
    Context retention: 100%
    Avg response time: 1555ms
    Memories stored: 2
    Conversation coherence: 100%
```

### Arquivo de saída:

```bash
ls -lh benchmark_results/realistic_benchmark_*.json
# Contém todos os detalhes do benchmark
```

---

## 🧬 Testes Unitários (pytest)

### Todos os testes:

```bash
pytest tests/
```

### Excluir testes lentos:

```bash
pytest -m "not slow" tests/
```

### Com cobertura:

```bash
pytest --cov=src/cortex --cov-report=html tests/
# Relatório HTML em: htmlcov/index.html
```

### Por módulo:

```bash
# Apenas testes de storage
pytest tests/test_storage.py

# Apenas testes de memory graph
pytest tests/test_memory_graph.py

# Apenas testes de recall
pytest tests/test_recall.py
```

### Resultados esperados:

```
======================== test session starts =========================
collected 130 items

tests/test_config.py ................                          [ 12%]
tests/test_memory_graph.py .............................       [ 34%]
tests/test_storage.py ....................                     [ 50%]
tests/test_recall.py ......................                    [ 67%]
tests/test_decay.py .................                          [ 80%]
tests/test_attention.py .............                          [ 90%]
tests/test_consolidation.py .............                     [100%]

======================== 130 passed in 45.2s ========================
```

---

## 🔍 Validação de Código

### Linting (PEP8)

```bash
ruff check .
```

**Resposta esperada:** Sem erros

Se houver erros:
```bash
# Auto-fix quando possível
ruff check --fix .
```

### Formatação

```bash
# Verifica formatação
ruff format --check .

# Formata automaticamente
ruff format .
```

### Type Checking

```bash
mypy src/cortex/
```

**Resposta esperada:** Sem erros de tipo

---

## 🐛 Debugging de Testes

### Logs detalhados:

```bash
# Modo debug no benchmark
LOG_LEVEL=DEBUG ./start_benchmark.sh validation
```

### Ver logs da API:

```bash
# Terminal onde cortex-api está rodando mostra logs em tempo real

# Ou veja logs salvos
tail -f logs/general.log
tail -f logs/audit/audit.log
```

### Limpar estado entre testes:

```bash
# Remove todos os dados
rm -rf data

# Recria diretório
mkdir -p data

# Rode testes limpos
./start_benchmark.sh validation
```

---

## 📊 Interpretando Resultados

### Validation Benchmark

| Teste                  | O que valida                              | Esperado |
| ---------------------- | ------------------------------------------ | -------- |
| Feature flags          | Config tem todas flags ativas             | PASSOU   |
| Consolidação           | Threshold 2 consolida mais rápido que 5   | PASSOU   |
| Hierarchical recall    | Retorna memórias dos 4 níveis            | PASSOU   |
| Attention mechanism    | Re-ranking melhora ordenação             | PASSOU   |
| Forget gate            | Filtra memórias irrelevantes             | PASSOU   |
| SM-2 adaptive          | EF aumenta/diminui corretamente          | PASSOU   |
| Backward compatibility | Legacy mode desabilita melhorias         | PASSOU   |

### Realistic Benchmark

| Métrica               | O que significa                          | Alvo  |
| --------------------- | ---------------------------------------- | ----- |
| Context retention     | % de contexto lembrado corretamente      | 100%  |
| Avg response time     | Tempo médio de resposta do LLM           | <10s  |
| Memories stored       | Quantidade de memórias armazenadas       | 2-5   |
| Conversation coherence| LLM mantém coerência com contexto        | 100%  |

---

## 🔧 Troubleshooting

### Validation falha: "AttributeError: 'list' object has no attribute 'items'"

**Causa:** Bug corrigido em 22/03/2026

**Solução:**
```bash
git pull origin main
rm -rf data && mkdir -p data
./start_benchmark.sh validation
```

### Realistic falha: "Ollama not available"

**Causa:** API não consegue conectar ao Ollama

**Solução:**
```bash
# Verifique que Ollama está rodando
curl http://localhost:11434/api/tags

# Verifique .env
cat .env | grep OLLAMA_URL

# Teste conexão
curl $OLLAMA_URL/api/tags
```

### Realistic falha: "Model not found"

**Causa:** Modelos não instalados

**Solução:**
```bash
ollama pull gemma3:4b
ollama pull qwen3-embedding:0.6b
ollama list | grep -E "(gemma3|qwen3)"
```

### Testes muito lentos

**Causa:** Embeddings não em cache

**Solução:**
```bash
# Use quick mode
./start_benchmark.sh realistic quick

# Ou aguarde - primeira execução é sempre mais lenta
# (cold start dos modelos Ollama)
```

### Pytest falha com ImportError

**Causa:** Ambiente virtual não ativo ou dependências faltando

**Solução:**
```bash
source venv/bin/activate
pip install -e ".[all]"
pytest tests/
```

---

## 🎯 Checklist Completo de Testes

Antes de fazer commit/deploy:

```bash
# 1. Linting
ruff check .

# 2. Type checking
mypy src/cortex/

# 3. Testes unitários
pytest tests/

# 4. Validation benchmark
./start_benchmark.sh validation

# 5. Realistic benchmark (quick)
./start_benchmark.sh realistic quick
```

**Todos devem passar ✅**

---

## 📈 Histórico de Resultados

### Março 2026 (v3.0.0)

- **Validation:** 7/7 (100%)
- **Realistic Customer Support:** 100% context retention
- **Realistic Personal Assistant:** 100% context retention
- **Bug fix:** AttributeError em adapters.py corrigido
- **Ambiente:** Linux 6.8.0-106, Python 3.10, gemma3:4b + qwen3-embedding:0.6b

### Janeiro 2026 (v2.1)

- **Validation:** 3/7 (42.9%) - antes do bug fix
- **Realistic:** Falhou por erro de conexão Ollama
- **Issues:** lista/dict mismatch em memory_graph.py

---

## 📚 Recursos Adicionais

- [Performance Analysis](.ai/docs/PERFORMANCE_ANALYSIS.md)
- [Benchmarks Research](.ai/docs/research/benchmarks.md)
- [Scientific Basis](.ai/docs/research/scientific-basis.md)

---

**Guia de Testes — Última atualização: 22 de Março de 2026**
