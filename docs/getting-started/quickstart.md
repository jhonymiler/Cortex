# ⚡ Quick Start

> **Objetivo**: Do zero ao funcionando em 2 minutos.

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

# Modelo a usar
OLLAMA_MODEL=gemma3:4b
```

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

### Opção A: Decorator (mais simples)

```python
from cortex_memory import with_memory

@with_memory(namespace="meu_agente")
def meu_agente(msg: str, context: str = "") -> str:
    # context já contém memórias relevantes!
    return f"[Com contexto: {context}] Resposta para: {msg}"

# Uso
resposta = meu_agente("Olá, sou João!")
# Memória armazenada automaticamente
```

### Opção B: Core Genérico

```python
from cortex_memory import CortexMemory

cortex = CortexMemory(namespace="meu_agente")

def meu_agente(user_msg):
    # 1. Busca memória
    context = cortex.before(user_msg)
    
    # 2. Seu LLM aqui
    response = meu_llm.generate(context + user_msg)
    
    # 3. Armazena memória
    cortex.after(user_msg, response)
    
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

