# 🧠 Cortex

> **Sistema de Memória Cognitiva para Agentes LLM**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🎯 O que é o Cortex?

Cortex é um sistema de **memória semântica agnóstico** para agentes LLM que:

- **Armazena SIGNIFICADO**, não texto bruto
- **Usa Entidades, Episódios e Relações** — como memória humana
- **Busca por relevância contextual**, não similaridade vetorial
- **Consolida memórias repetidas** automaticamente
- **Funciona para qualquer domínio** — dev, roleplay, chatbot, assistente

### Diferencial

```
OUTROS (RAG/VectorDB):
├─ Armazenam texto/embeddings
├─ Buscam por similaridade (caro, impreciso)
└─ Não detectam contradições

CORTEX:
├─ Armazena FATOS SEMÂNTICOS (entidades, episódios, relações)
├─ Busca por GRAFO (O(1), preciso)
├─ Consolida padrões automaticamente
└─ Agnóstico de domínio
```

---

## 🚀 Instalação

```bash
# Básico
pip install cortex-memory

# Com MCP
pip install cortex-memory[mcp]

# Com API REST
pip install cortex-memory[api]

# Tudo
pip install cortex-memory[all]

# Desenvolvimento
pip install -e ".[all,dev]"
```

---

## 🎭 Uso com MCP (Claude Desktop)

### 1. Configure `claude_desktop_config.json`

```json
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

### 2. Reinicie Claude Desktop

O Cortex estará disponível com as ferramentas:
- `cortex_recall` — Buscar memórias (ANTES de responder)
- `cortex_store` — Armazenar memória (APÓS responder)
- `cortex_stats` — Estatísticas

---

## 🌐 Uso com API REST

### 1. Inicie o servidor

```bash
cortex-api
# ou
uvicorn cortex.api.app:app --reload
```

### 2. Endpoints

```bash
# Buscar memórias
curl -X POST http://localhost:8000/memory/recall \
  -H "Content-Type: application/json" \
  -d '{"query": "análise de logs"}'

# Armazenar memória
curl -X POST http://localhost:8000/memory/store \
  -H "Content-Type: application/json" \
  -d '{
    "action": "analyzed_log",
    "outcome": "found 3 errors",
    "participants": [
      {"type": "file", "name": "apache.log"}
    ]
  }'

# Estatísticas
curl http://localhost:8000/memory/stats
```

---

## 📚 Conceitos

### Entity (Entidade)
Qualquer "coisa" — pessoa, arquivo, conceito, personagem, produto.

```python
Entity(type="person", name="João", identifiers=["joao@email.com"])
Entity(type="character", name="Elena", identifiers=["vampire_queen"])
Entity(type="file", name="config.yaml", identifiers=["sha256:abc123"])
```

### Episode (Episódio)
Qualquer "acontecimento" — ação + participantes + resultado.

```python
Episode(
    action="debugged",
    participants=["user_123", "file_config"],
    context="development session",
    outcome="found missing semicolon"
)
```

### Relation (Relação)
Qualquer "conexão" — causal, associativa, temporal.

```python
Relation(from_id="error_404", type="caused_by", to_id="missing_route")
Relation(from_id="elena", type="loves", to_id="marcus")
```

---

## 🔄 Fluxo Obrigatório

```
1. Usuário envia mensagem
        ↓
2. Agente chama cortex_recall(query=mensagem)
        ↓
3. Cortex retorna contexto relevante
        ↓
4. Agente processa (com contexto)
        ↓
5. Agente responde ao usuário
        ↓
6. Agente chama cortex_store(action, outcome, ...)
        ↓
7. Cortex armazena e consolida
```

---

## 🧪 Desenvolvimento

```bash
# Clone
git clone https://github.com/seu-usuario/cortex.git
cd cortex

# Instale
pip install -e ".[all,dev]"

# Testes
pytest tests/ -v

# Lint
ruff check src/
ruff format src/
```

---

## 📖 Documentação

- [Arquitetura](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [MCP Integration](docs/MCP.md)

---

## 📄 Licença

MIT
