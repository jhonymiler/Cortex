# ⚙️ Configuração de Ambiente

## Quick Start

```bash
# 1. Copie o arquivo de exemplo
cp .env.example .env

# 2. Edite com suas credenciais
nano .env  # ou vim, code, etc.

# 3. Configure ao menos uma das opções:
#    - GOOGLE_API_KEY (para agent.py)
#    - Ou apenas use Ollama local (crew_agent.py)
```

## Variáveis Disponíveis

### Cortex API

```bash
# Diretório onde as memórias são salvas (padrão: ~/.cortex)
CORTEX_DATA_DIR=/caminho/customizado

# Porta da API REST (padrão: 8000)
CORTEX_API_PORT=8000

# Host da API REST (padrão: 127.0.0.1)
CORTEX_API_HOST=127.0.0.1
```

### Google Gemini

```bash
# API Key do Google AI Studio
# Obtenha em: https://aistudio.google.com/apikey
GOOGLE_API_KEY=sua-api-key-aqui
```

### Ollama

```bash
# URL do Ollama local (padrão: http://localhost:11434)
OLLAMA_URL=http://localhost:11434

# Modelo padrão
OLLAMA_MODEL=gemma3:4b
```

## Uso em Código

### Python

```python
import os
from dotenv import load_dotenv

# Carrega .env
load_dotenv()

# Acessa variáveis
api_key = os.getenv("GOOGLE_API_KEY")
cortex_dir = os.getenv("CORTEX_DATA_DIR", "~/.cortex")
```

### CLI

```bash
# As variáveis são carregadas automaticamente se você usar python-dotenv
# ou você pode exportar manualmente:
export $(cat .env | grep -v '^#' | xargs)
```

## Segurança

⚠️ **NUNCA commit o arquivo `.env` no git!**

- ✅ `.env.example` está no git (valores de exemplo)
- ❌ `.env` está no `.gitignore` (seus valores reais)

## Troubleshooting

### "API Key não encontrada"

```bash
# Verifique se .env existe
ls -la .env

# Verifique o conteúdo (sem mostrar a key completa)
grep GOOGLE_API_KEY .env | head -c 30

# Ou exporte diretamente
export GOOGLE_API_KEY=sua-chave
```

### "Cortex API não está saudável"

```bash
# Verifique se a porta está correta
curl http://localhost:8000/health

# Ou use a porta configurada
curl http://localhost:${CORTEX_API_PORT:-8000}/health
```
