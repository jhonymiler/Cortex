# ⚡ Quick Start — Cortex v3.0

> **Do zero ao funcionando em 5 minutos.**

Este guia foi testado e validado em Março de 2026. Todos os comandos funcionam conforme descrito.

---

## ✅ Checklist de Validação

Ao final deste guia você terá:

- [x] API Cortex rodando e respondendo
- [x] Ollama com modelos instalados (gemma3:4b, qwen3-embedding:0.6b)
- [x] Benchmark de validação 100% passando
- [x] Exemplo funcional de memória persistente

---

## Pré-requisitos

- **Python 3.11+** (verificar: `python --version`)
- **Ollama** instalado ([download](https://ollama.com/))
- **5 minutos** de tempo livre

---

## Passo 1: Instalação (2 minutos)

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/cortex.git
cd cortex

# Crie ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# Windows: venv\Scripts\activate

# Instale dependências básicas
pip install -e "."

# OU instale tudo (recomendado para desenvolvimento)
pip install -e ".[all]"
```

**Validação:**
```bash
python -c "from cortex.config import CortexConfig; print('✅ Cortex instalado')"
```

---

## Passo 2: Configuração (1 minuto)

```bash
# Copie o template de configuração
cp .env.example .env
```

**Edite `.env` se necessário:**

```bash
# API Cortex
CORTEX_API_URL=http://localhost:8000
CORTEX_PORT=8000

# Ollama (use localhost se está rodando localmente)
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:4b
CORTEX_EMBEDDING_MODEL=qwen3-embedding:0.6b

# Storage (JSON para dev/testes, Neo4j para produção)
CORTEX_STORAGE_BACKEND=json

# Diretório de dados
CORTEX_DATA_DIR=./data
```

> **💡 WSL Users:** Se Ollama roda no Windows, ajuste a URL:
> ```bash
> OLLAMA_URL=http://$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):11434
> ```

**Validação:**
```bash
cat .env | grep OLLAMA_URL
# Deve mostrar: OLLAMA_URL=http://localhost:11434
```

---

## Passo 3: Instale Modelos Ollama (2 minutos)

```bash
# Modelo LLM principal (3.3GB)
ollama pull gemma3:4b

# Modelo de embeddings (639MB)
ollama pull qwen3-embedding:0.6b
```

**Validação:**
```bash
ollama list | grep -E "(gemma3:4b|qwen3-embedding)"
# Deve mostrar ambos os modelos
```

**Tempo de download:**
- `gemma3:4b`: ~2-5 minutos (3.3GB)
- `qwen3-embedding:0.6b`: ~1-2 minutos (639MB)

---

## Passo 4: Inicie a API (10 segundos)

```bash
# Em um terminal separado
source venv/bin/activate
cortex-api
```

**Você verá:**
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Validação:**
```bash
# Em outro terminal
curl http://localhost:8000/health
# Resposta esperada: {"status":"healthy","service":"cortex-memory"}
```

✅ **API está rodando!**

---

## Passo 5: Teste com Benchmark (30 segundos)

```bash
# Validação rápida (7 testes unitários)
./start_benchmark.sh validation
```

**Resultado esperado:**
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

✅ **Sistema validado!**

---

## Passo 6: Use em Seu Código (1 minuto)

### Exemplo Mínimo

```python
from cortex_memory_sdk import CortexMemorySDK

# Conecta à API
sdk = CortexMemorySDK(
    namespace="meu_agente:user_123",
    cortex_url="http://localhost:8000"
)

# Armazena memória
sdk.remember({
    "who": ["João"],
    "what": "perguntou sobre fatura",
    "why": "dúvida de cobrança",
    "when": "2026-03-22T10:00:00",
    "where": "chat",
    "how": "explicou processo de pagamento"
})

# Busca memórias
result = sdk.recall("fatura do João")
print(result.to_prompt_context())
# Output: Cliente: João | Contexto: perguntou sobre fatura → explicou processo
```

Salve como `teste_cortex.py` e execute:

```bash
python teste_cortex.py
```

✅ **Memória funcionando!**

---

## Passo 7 (Opcional): Benchmark Realista

Teste com conversas reais usando LLM:

```bash
# Versão rápida (~1-2min)
./start_benchmark.sh realistic quick

# Versão completa (~5-10min)
./start_benchmark.sh realistic
```

**Resultado esperado:**
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

✅ **LLM com memória funcional!**

---

## 🎉 Pronto! Você Tem um Agente com Memória

### O que você ganhou:

- ✅ Memória persistente estruturada (W5H model)
- ✅ Busca semântica com embeddings
- ✅ Esquecimento inteligente (Ebbinghaus)
- ✅ Consolidação progressiva de memórias
- ✅ Proteção contra jailbreak (Memory Firewall)

---

## 📚 Próximos Passos

| Objetivo                          | Documentação                                  |
| --------------------------------- | --------------------------------------------- |
| Integrar com LangChain/CrewAI     | [Integrações](./integrations.md)              |
| Entender modelo W5H               | [Memory Model](../concepts/memory-model.md)   |
| Configurar Claude Desktop (MCP)   | [MCP Setup](./mcp-setup.md)                   |
| Usar Neo4j em produção            | [Storage Adapters](../architecture/storage-adapters.md) |
| Ver base científica               | [Scientific Basis](../research/scientific-basis.md) |

---

## 🔧 Troubleshooting

### Erro: "Address already in use" (porta 8000)

```bash
# Encontra processo usando a porta
lsof -ti:8000

# Mata o processo
lsof -ti:8000 | xargs kill -9

# Ou use outra porta
CORTEX_PORT=8001 cortex-api
```

### Erro: "Ollama not available"

```bash
# Verifique se Ollama está rodando
curl http://localhost:11434/api/tags

# Se não responder, inicie Ollama
ollama serve

# Teste novamente
curl http://localhost:11434/api/tags
```

### Erro: "Model not found: gemma3:4b"

```bash
# Liste modelos instalados
ollama list

# Instale se não aparecer
ollama pull gemma3:4b
ollama pull qwen3-embedding:0.6b
```

### Benchmark falha: "AttributeError: 'list' object has no attribute 'items'"

**Este bug foi corrigido em 22/03/2026.** Se você ainda vê este erro:

```bash
# Atualize para a versão mais recente
git pull origin main

# Limpe dados antigos
rm -rf data && mkdir -p data

# Rode novamente
./start_benchmark.sh validation
```

### Memórias não persistem entre reinícios

```bash
# Verifique se o diretório de dados existe
ls -la data/

# Verifique permissões
chmod -R 755 data/

# Verifique configuração
cat .env | grep CORTEX_DATA_DIR
# Deve mostrar: CORTEX_DATA_DIR=./data
```

### WSL: Ollama no Windows não conecta

```bash
# Descubra o IP do Windows
cat /etc/resolv.conf | grep nameserver | awk '{print $2}'

# Atualize .env com esse IP
OLLAMA_URL=http://172.XX.XX.XX:11434  # Use o IP que descobriu

# Teste a conexão
curl $OLLAMA_URL/api/tags
```

---

## 📊 Resultados de Performance

**Ambiente de teste:**
- OS: Linux 6.8.0-106-generic
- Python: 3.10+
- Ollama: Local (localhost:11434)
- Modelos: gemma3:4b + qwen3-embedding:0.6b

**Benchmarks (Março 2026):**

| Métrica                | Valor      | Status |
| ---------------------- | ---------- | ------ |
| Validation tests       | 7/7 (100%) | ✅      |
| Context retention      | 100%       | ✅      |
| Avg response time      | ~3000ms    | ✅      |
| Memory Firewall detect | 90%        | ✅      |
| False positives        | 0%         | ✅      |

---

## 🎓 Entendendo o Fluxo

```
1. USER INPUT
   ↓
2. SDK/API → recall(query)
   ↓
3. Embedding Service → qwen3-embedding:0.6b
   ↓
4. Memory Graph → Busca semântica + RRF + MMR
   ↓
5. Hierarchical Recall → 4 níveis (Working/Recent/Pattern/Knowledge)
   ↓
6. Context Packer → Reduz tokens 40-70%
   ↓
7. CONTEXT → Seu LLM (gemma3:4b)
   ↓
8. LLM RESPONSE
   ↓
9. SDK/API → remember(memory)
   ↓
10. Memory Graph → Armazena W5H estruturado
    ↓
11. Decay Manager → Ebbinghaus R = e^(-t/S)
    ↓
12. PERSISTIDO (JSON ou Neo4j)
```

---

## 💡 Dicas de Uso

### Para Desenvolvimento

```bash
# Hot reload da API
CORTEX_RELOAD=true cortex-api

# Logs em modo debug
LOG_LEVEL=DEBUG cortex-api

# Usa JSON storage (mais rápido para testes)
CORTEX_STORAGE_BACKEND=json
```

### Para Produção

```bash
# Sem reload
CORTEX_RELOAD=false cortex-api

# Logs em modo INFO
LOG_LEVEL=INFO

# Usa Neo4j (escalável)
CORTEX_STORAGE_BACKEND=neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=sua_senha
```

### Para Benchmarks

```bash
# Sempre limpe dados antigos antes
rm -rf data && mkdir -p data

# Rode validação primeiro
./start_benchmark.sh validation

# Depois rode realista
./start_benchmark.sh realistic quick
```

---

**Quick Start — Última atualização: 22 de Março de 2026**

*Todas as instruções foram testadas e validadas no ambiente descrito acima.*
