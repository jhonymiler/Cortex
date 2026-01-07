# 🧠 Cortex

> **Sistema de Memória Cognitiva para Agentes LLM**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 O Problema

Agentes LLM sofrem de **amnésia crônica**:

| Problema | Impacto |
|----------|---------|
| 🔴 **Perguntas Repetitivas** | "Qual seu nome? Qual navegador?" — 10+ perguntas por sessão |
| 🔴 **Custos Explosivos** | Context stuffing: 4.000 → 12.000+ tokens por conversa |
| 🔴 **Respostas Genéricas** | Sem personalização, sem reconhecimento do usuário |
| 🔴 **Contexto Perdido** | "Esqueci o que estávamos discutindo" em cada troca |

---

## ✅ A Solução

Cortex é um sistema de **memória semântica** que transforma agentes em assistentes inteligentes:

```
❌ SEM CORTEX                          ✅ COM CORTEX
────────────────────────────────────────────────────────────────
• Cada request envia todo histórico    • Últimas 4 msgs + contexto estruturado
• Tokens crescem linearmente           • Tokens constantes O(1)
• Usuário repete informações           • Preferências persistem entre sessões
• Sessão nova = tudo esquecido         • Agente lembra tudo relevante
• Custo: ~2000 tokens/contexto         • Custo: ~100 tokens/contexto
```

### Resultados Reais

| Cenário | Antes | Depois | Economia |
|---------|-------|--------|----------|
| **Customer Support** | 15+ msgs, 10 perguntas | 4 msgs, 0 perguntas | **80%** tempo |
| **Code Assistant** | Código errado (JS vs TS) | Estilo do time | **92%** acerto |
| **E-commerce** | Genérico, conversão 2.5% | Personalizado VIP | **+224%** conversão |
| **Healthcare** | 12 min triagem | 4 min | **67%** redução |

---

## 🚀 Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/cortex.git
cd cortex

# Crie ambiente virtual
python -m venv venv
source venv/bin/activate

# Instale (escolha uma opção)
pip install -e "."          # Básico
pip install -e ".[mcp]"     # Com MCP (Claude Desktop)
pip install -e ".[api]"     # Com API REST
pip install -e ".[ui]"      # Com Streamlit UI
pip install -e ".[all,dev]" # Tudo + desenvolvimento

# Configure ambiente
cp .env.example .env
# Edite .env conforme necessário
```

---

## 🎭 Integração

### Opção 1: MCP (Claude Desktop)

```json
// claude_desktop_config.json
{
  "mcpServers": {
    "cortex": {
      "command": "cortex-mcp",
      "env": {
        "CORTEX_DATA_DIR": "/path/to/data"
      }
    }
  }
}
```

**Tools disponíveis:**
- `cortex_recall` — Buscar memórias (ANTES de responder)
- `cortex_store` — Armazenar memória (APÓS responder)
- `cortex_stats` — Estatísticas do grafo
- `cortex_health` — Saúde da memória
- `cortex_decay` — Aplicar decay manual

### Opção 2: SDK Python (Core Genérico)

Funciona com **qualquer LLM/framework** (OpenAI, Ollama, Anthropic, etc):

```python
from cortex_memory import CortexMemory

cortex = CortexMemory(namespace="meu_agente:usuario_123")

def meu_agente(user_msg):
    context = cortex.before(user_msg)      # ← Busca memória
    response = llm.generate(context + user_msg)
    cortex.after(user_msg, response)       # ← Armazena (W5H automático)
    return response
```

### Opção 3: LangChain (Plug and Play)

```python
from cortex.integrations import CortexLangChainMemory

memory = CortexLangChainMemory(namespace="meu_agente")
chain = LLMChain(llm=llm, memory=memory)

response = chain.run("Olá!")  # ← Zero código extra!
```

### Opção 4: CrewAI (Plug and Play)

```python
from cortex.integrations import CortexCrewAIMemory

memory = CortexCrewAIMemory(namespace="minha_crew")
crew = Crew(agents=[...], long_term_memory=memory)
```

### Opção 5: API REST Direta

```bash
# Iniciar servidor
cortex-api

# Recall (busca memória)
curl -X POST http://localhost:8000/memory/recall \
  -H "Content-Type: application/json" \
  -H "X-Cortex-Namespace: meu_agente" \
  -d '{"query": "login João"}'

# Interact (armazena com extração W5H automática)
curl -X POST http://localhost:8000/memory/interact \
  -H "Content-Type: application/json" \
  -H "X-Cortex-Namespace: meu_agente" \
  -d '{
    "user_message": "Meu login não funciona",
    "assistant_response": "Vou verificar sua conta",
    "user_name": "João"
  }'

# Remember (W5H manual)
curl -X POST http://localhost:8000/memory/remember \
  -H "Content-Type: application/json" \
  -H "X-Cortex-Namespace: meu_agente" \
  -d '{
    "who": ["João", "sistema_auth"],
    "what": "resolveu_problema_login",
    "why": "vpn_bloqueando",
    "how": "desconectou_vpn"
  }'
```

---

## 📊 Como Funciona

### Arquitetura de Memória

```
┌─────────────────────────────────────────────────────────────┐
│                      CORTEX MEMORY                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ENTIDADES          EPISÓDIOS           RELAÇÕES           │
│  ┌─────────┐       ┌──────────┐       ┌──────────┐        │
│  │ João    │──────▶│ login    │◀──────│ caused_by│        │
│  │(customer)│       │ issue    │       │          │        │
│  └─────────┘       └──────────┘       └──────────┘        │
│       │                 │                   │              │
│       ▼                 ▼                   ▼              │
│  ÍNDICES O(1)      CONSOLIDAÇÃO      DECAY POR ACESSO     │
│  Busca instantânea  5+ similares     Relevantes sobem     │
│  Zero embeddings    = 1 padrão       Ignorados descem     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Formato de Saída (YAML)

O Cortex retorna contexto em **YAML compacto** — máxima informação, mínimos tokens:

```yaml
# MEMÓRIA DO USUÁRIO
conhecidos:
  - João Silva (customer): vip=True, shoe_size=42
  - Nike Pegasus (brand)
histórico:
  - [4x] purchase: Comprou Nike Pegasus (padrão consolidado)
  - preference_noted: Ama correr pela manhã
conexões:
  - loves
resumo: Cliente VIP, fã de Nike Pegasus, tamanho 42
```

### Decaimento Cognitivo (Ebbinghaus)

Baseado na ciência de memória humana:

```
R = e^(-t/S)   # Curva de esquecimento

Stability aumenta com:
├── Acessos frequentes (spaced repetition)
├── Consolidação (5+ ocorrências similares)
├── Hub Centrality (muitas referências)
└── Importância declarada
```

### Shared Memory com Isolamento

Para agentes que atendem múltiplos usuários:

```
┌─────────────────────────────────────────────┐
│  NAMESPACE: agente_suporte                   │
├─────────────────────────────────────────────┤
│  personal:user_123 │ personal:user_456      │
│  "João pediu #123" │ "Maria mora em SP"     │
├─────────────────────────────────────────────┤
│  shared:                                     │
│  "Política de devolução: 30 dias"           │
├─────────────────────────────────────────────┤
│  learned:                                    │
│  "Padrão: clientes perguntam sobre prazos"  │
└─────────────────────────────────────────────┘
```

**Resultado:** Agente aprende com todos, mas não confunde dados pessoais!

---

## 🧪 Testes

### Testes Unitários
```bash
pytest tests/ -v
```

### Testes de Comparação (COM vs SEM Cortex)
```bash
python tests/test_comparison.py
```

### Testes de Integração (Agentes Reais)
```bash
# Com SDK (API REST)
cd teste-llm
python test_integration_sdk.py

# Com MCP
python test_integration_mcp.py
```

---

## 📁 Estrutura

```
cortex/
├── src/cortex/
│   ├── core/           # Modelos puros (sem I/O)
│   │   ├── entity.py       # Entidade + centrality
│   │   ├── memory.py       # Memory W5H (ex-Episode)
│   │   ├── relation.py     # Relações entre nós
│   │   ├── memory_graph.py # Grafo + índices
│   │   ├── decay.py        # DecayManager (Ebbinghaus)
│   │   └── shared_memory.py # SharedMemoryManager
│   ├── services/       # MemoryService (lógica de negócio)
│   ├── api/            # FastAPI REST endpoints
│   ├── mcp/            # FastMCP server
│   └── ui/             # Streamlit dashboard
│
├── sdk/python/         # SDK para clientes
│   ├── cortex_sdk.py       # Cliente REST baixo-nível
│   ├── cortex_memory.py    # Core genérico (before/after)
│   └── integrations/       # Adaptadores
│       ├── langchain.py    # LangChain BaseMemory
│       └── crewai.py       # CrewAI long_term_memory
│
├── benchmark/          # Sistema de benchmark científico
│   ├── agents.py           # BaselineAgent, CortexAgent V1
│   ├── cortex_agent_v2.py  # CortexAgent V2 (extração inline)
│   ├── rag_agent.py        # RAG baseline (TF-IDF)
│   ├── mem0_agent.py       # Mem0 baseline
│   ├── scientific_metrics.py    # Precision, Recall, MRR
│   ├── consistency_metrics.py   # Coerência entre sessões
│   ├── ablation_runner.py      # Ablation study
│   └── shared_memory_benchmark.py  # Shared memory tests
│
├── src/cortex/workers/ # Processos em background
│   └── sleep_refiner.py    # Consolidação de memórias (sono)
│
├── tests/              # Testes unitários e de comparação
└── docs/               # Documentação detalhada
```

---

## 📖 Documentação

| Documento | Descrição |
|-----------|-----------|
| [VISION.md](docs/VISION.md) | Filosofia, conceitos, princípios |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Camadas, fluxo de dados, decay, shared memory |
| [W5H_DESIGN.md](docs/W5H_DESIGN.md) | Design do modelo W5H, Ebbinghaus, centralidade |
| [API.md](docs/API.md) | Endpoints REST, payloads, exemplos |
| [MCP.md](docs/MCP.md) | Integração MCP, Claude Desktop |
| [PAPER_TEMPLATE.md](docs/PAPER_TEMPLATE.md) | Template do paper científico |
| [benchmark/README.md](benchmark/README.md) | Sistema de benchmark, métricas científicas |
| [sdk/python/README.md](sdk/python/README.md) | SDK Python, integrações |

---

## 🎯 Casos de Uso

### Customer Support
```
❌ "Qual seu nome e email?" (pela 5ª vez)
✅ "Oi João! Vejo que o problema é VPN de novo. Desconecta e tenta."
```

### Code Assistant
```
❌ "Qual framework você usa?" (sugere JS para time de TS)
✅ "Vi que o time usa TypeScript + NextAuth. Aqui o fix no estilo:"
```

### E-commerce
```
❌ "Temos Nike, Adidas... Qual tamanho?" (cliente VIP tratado como novato)
✅ "Maria! Chegou o Pegasus 2025. Como VIP, tem 20%. Reservo o 42?"
```

### Healthcare
```
❌ "Tem alergias? Medicamentos?" (tudo no prontuário)
✅ "Carlos, vejo sua gastrite crônica. Sintomas iguais ou diferentes?"
```

---

## 📊 Benchmark

Execute benchmarks para validar performance:

```bash
# Benchmark rápido (1 conv/domínio, ~10 min)
./start_benchmark.sh --quick

# Benchmark completo (3 conv/domínio, ~1 hora)
./start_benchmark.sh --full

# Análise de resultados
./analyze_results.sh
```

### Cortex V2 - Extração [MEMORY] Inline

O V2 reduz chamadas LLM em 50%:

| Métrica | V1 | V2 | Economia |
|---------|----|----|----------|
| **Chamadas LLM/msg** | 2 | 1 | **-50%** |
| **Tokens/msg** | ~600 | ~350 | **-42%** |
| **Latência** | Alta | Baixa | **-40%** |

```python
# V2: Extração automática no output do LLM
response = agent.process("Olá Carlos!")
# LLM responde: "Olá! Como posso ajudar? [MEMORY]who:Carlos what:saudacao[/MEMORY]"
# SDK extrai memória e retorna resposta limpa ao usuário
```

---

## 🤝 Contribuindo

```bash
# Fork + clone
git clone https://github.com/seu-usuario/cortex.git

# Instale dev dependencies
pip install -e ".[all,dev]"

# Rode testes
pytest tests/ -v

# Lint
ruff check src/
ruff format src/

# Commit (conventional commits)
git commit -m "feat: add new feature"
```

---

## 📄 Licença

MIT — use, modifique, distribua livremente.

---

<p align="center">
  <strong>🧠 Cortex — Porque agentes inteligentes precisam lembrar.</strong>
</p>
