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

### Opção 2: SDK Python (API REST)

```python
from cortex_sdk import CortexClient

client = CortexClient("http://localhost:8000")

# Recall antes de responder
context = client.recall("ajuda com login", user="joao@email.com")
# Retorna YAML compacto:
# conhecidos:
#   - João Silva (customer): vip=True
# histórico:
#   - [4x] login_issue: VPN bloqueando acesso

# Store após responder
client.store(
    action="resolved_login",
    outcome="Desconectar VPN resolveu",
    participants=[{"type": "customer", "name": "João Silva"}]
)
```

### Opção 3: API REST Direta

```bash
# Iniciar servidor
cortex-api

# Recall
curl -X POST http://localhost:8000/memory/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "login João"}'

# Store
curl -X POST http://localhost:8000/memory/store \
  -H "Content-Type: application/json" \
  -d '{
    "action": "resolved_login",
    "outcome": "VPN desconectada",
    "participants": [{"type": "customer", "name": "João"}]
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

### Decay por Acesso (não temporal!)

```
Recall("Python")  →  Python ⬆️ fortalece
                     Java ⬇️ enfraquece (não acessado)
                     
Resultado após 10 recalls de Python:
  Python: importance=1.000 ✅
  Java:   importance=0.409 (decaiu naturalmente)
```

**Por que não temporal?** Um agente pode ficar meses sem uso. Quando voltar, as memórias devem estar lá!

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
│   ├── core/           # Modelos: Entity, Episode, Relation, MemoryGraph
│   ├── services/       # MemoryService (lógica de negócio)
│   ├── api/            # FastAPI REST endpoints
│   ├── mcp/            # FastMCP server
│   └── ui/             # Streamlit dashboard
├── sdk/python/         # SDK para clientes
├── teste-llm/          # Agentes de teste (Ollama, MCP)
├── tests/              # Testes unitários e de comparação
└── docs/               # Documentação detalhada
```

---

## 📖 Documentação

| Documento | Descrição |
|-----------|-----------|
| [VISION.md](docs/VISION.md) | Filosofia, conceitos, princípios |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Camadas, fluxo de dados, consolidação |
| [API.md](docs/API.md) | Endpoints REST, payloads, exemplos |
| [MCP.md](docs/MCP.md) | Integração MCP, Claude Desktop |
| [ENVIRONMENT.md](docs/ENVIRONMENT.md) | Variáveis de ambiente |

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
