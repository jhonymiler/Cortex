# ⚡ Quick Start

> *"Cortex, porque agentes inteligentes precisam de memória inteligente"*
> 
> **Objetivo**: Do zero ao funcionando em 2 minutos.

---

## O Que Você Vai Obter

| Dimensão | Benefício | Score Benchmark |
|----------|-----------|-----------------|
| 🧠 **Cognição Biológica** | Esquece ruído, lembra importante | 50% |
| 👥 **Memória Coletiva** | Conhecimento compartilhado entre agentes | 75% |
| 🎯 **Valor Semântico** | Sinônimos funcionam, threshold adaptativo | 100% |
| ⚡ **Eficiência** | 16ms latência, tokens compactos | 100% |

**Total: 83%** vs 40% (RAG, Mem0)

---

## Pré-requisitos

- Python 3.11+
- (Opcional) Ollama para LLM local

---

## 1. Instalação (30 segundos)

```bash
# Clone
git clone https://github.com/seu-usuario/cortex.git
cd cortex

# Ambiente virtual
python -m venv venv
source venv/bin/activate

# Instale (escolha uma opção)
pip install -e "."              # Básico
pip install -e ".[mcp]"         # + MCP (Claude Desktop)
pip install -e ".[all]"         # Tudo
```

---

## 2. Configuração (30 segundos)

```bash
cp .env.example .env
```

Edite `.env` se necessário:

```bash
# Se Ollama está em outra máquina (ex: WSL → Windows)
OLLAMA_URL=http://192.168.1.100:11434

# Modelo para inferência
OLLAMA_MODEL=gemma3:4b

# Modelo de embeddings (opcional)
CORTEX_EMBEDDING_MODEL=qwen3-embedding:0.6b
```

> **Nota**: O Cortex usa threshold adaptativo para embeddings,
> ajustando automaticamente baseado no modelo usado.

---

## 3. Inicie a API (10 segundos)

```bash
cortex-api
```

Teste:
```bash
curl http://localhost:8000/health
# {"status": "healthy"}
```

---

## 4. Use em Seu Código (50 segundos)

### Opção A: SDK Python (recomendado)

```python
from cortex_memory_sdk import CortexMemorySDK

# Cria cliente
sdk = CortexMemorySDK(namespace="meu_agente:user_123")

# Armazena memória estruturada
sdk.remember({
    "verb": "apresentou",
    "subject": "joao",
    "object": "nome",
})

# Busca memórias
result = sdk.recall("João")
print(result.to_prompt_context())
# Output: who:joao what:apresentou_nome
```

### Opção B: Integração Completa

```python
from cortex_memory_sdk import CortexMemorySDK

sdk = CortexMemorySDK(namespace="meu_agente:user_123")

def meu_agente(user_msg):
    # 1. Busca memória
    result = sdk.recall(user_msg, limit=5)
    context = result.to_prompt_context()
    
    # 2. Seu LLM aqui
    response = meu_llm.generate(f"Contexto:\n{context}\n\n{user_msg}")
    
    # 3. Armazena memória (estruturada)
    sdk.remember({
        "verb": "respondeu",
        "subject": "agente",
        "object": "pergunta",
    })
    
    return response
```

### Opção C: LangChain

```python
from cortex.integrations import CortexLangChainMemory
from langchain.chains import ConversationChain

memory = CortexLangChainMemory(namespace="meu_agente")
chain = ConversationChain(llm=meu_llm, memory=memory)

response = chain.run("Olá!")  # Memória automática!
```

### Opção D: CrewAI

```python
from cortex.integrations import CortexCrewAIMemory
from crewai import Crew

crew = Crew(
    agents=[...],
    long_term_memory=CortexCrewAIMemory(namespace="minha_crew")
)
```

---

## 5. Verifique que Funciona

```bash
# Ver estatísticas
curl http://localhost:8000/memory/stats \
  -H "X-Cortex-Namespace: meu_agente"

# Buscar memórias
curl -X POST http://localhost:8000/memory/recall \
  -H "Content-Type: application/json" \
  -H "X-Cortex-Namespace: meu_agente" \
  -d '{"query": "João"}'
```

---

## Pronto! 🎉

Você agora tem um agente com memória persistente.

---

## Próximos Passos

| Quer... | Vá para... |
|---------|------------|
| Ver todas as integrações | [Integrações](./integrations.md) |
| Entender como funciona | [Modelo de Memória](../concepts/memory-model.md) |
| Usar com Claude Desktop | [MCP](./mcp-setup.md) |
| Ver exemplos por domínio | [Exemplos](./examples/) |

---

## Troubleshooting Comum

### API não inicia

```bash
# Verifique se a porta está livre
lsof -i :8000

# Ou use outra porta
CORTEX_API_PORT=8001 cortex-api
```

### Ollama não conecta (WSL)

```bash
# Use o IP do Windows, não localhost
OLLAMA_URL=http://$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}'):11434
```

### Memórias não persistem

```bash
# Verifique o diretório de dados
ls -la ~/.cortex/
# Deve ter: entities.json, episodes.json, relations.json
```

---

*Quick Start — Última atualização: Janeiro 2026*

