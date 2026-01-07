# 🧠 Cortex - Cognitive Memory for AI Agents

> **Memória de Longo Prazo que Pensa Como Humano**

---

## 🎯 O Que é o Cortex?

Cortex é um **sistema de memória cognitiva** para agentes LLM que funciona como a memória humana:

- **Lembra significado**, não texto literal
- **Consolida experiências** repetidas em padrões
- **Esquece gradualmente** o que não é importante
- **Conecta informações** por relevância semântica

---

## 💡 Diferenciais

### ❌ O que Cortex **NÃO** é

| Tecnologia | Problema | Cortex |
|------------|----------|--------|
| **RAG** | Custo por busca (embeddings) | **Zero tokens** por recall |
| **VectorDB** | Texto não estruturado | **Grafo semântico** estruturado |
| **Context Window** | Limitado, caro, não persiste | **Memória persistente** ilimitada |
| **Fine-tuning** | Caro, lento, irreversível | **Aprendizado em tempo real** |

### ✅ O que Cortex **É**

```
┌─────────────────────────────────────────────────────────┐
│                    CORTEX                                │
├─────────────────────────────────────────────────────────┤
│  🔍 Busca O(1)         │  Zero tokens por recall        │
│  🧠 Memória Semântica  │  Entity-Episode-Relation       │
│  📉 Decaimento Natural │  Ebbinghaus (curva humana)     │
│  🔗 Consolidação       │  Agrupa experiências similares │
│  🔒 Multi-tenant       │  Isolamento por namespace      │
│  🔌 Plug-and-Play      │  SDK para qualquer framework   │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 Resultados Comprovados

### Benchmark (Janeiro 2026)

| Métrica | Baseline (sem memória) | **Cortex** | Diferença |
|---------|------------------------|------------|-----------|
| **Tokens** | 49.438 | 43.255 | **-12.5%** |
| **Tempo** | 239s | 189s | **-21%** |
| **Hit Rate** | 0% | **100%** | ∞ |
| **Custo** | $1.00 | **$0.87** | **-13%** |

### Consolidação com SleepRefiner

```
PRÉ-CONSOLIDAÇÃO:  +8.7% tokens (pior que baseline)
PÓS-CONSOLIDAÇÃO: -12.5% tokens (melhor que baseline)
                  ─────────────────────────────────
                  Melhoria: 21.2 pontos percentuais
```

---

## 🏗️ Arquitetura

### Modelo W5H (Quem, O quê, Por quê, Quando, Onde, Como)

```python
Memory(
    who=["João", "Sistema de Pagamentos"],
    what="reportou erro de pagamento",
    why="cartão expirado",
    when="2026-01-07T10:30:00",
    where="suporte_cliente",
    how="orientado a atualizar dados"
)
```

### Consolidação Hierárquica

```
┌─────────────────────────────────────────────────────────┐
│  RESUMO (recall normal)                                 │
│  "Cliente resolveu problemas de pagamento"              │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  DETALHES (histórico/drill-down)                │   │
│  │  ├── "João ligou sobre cartão expirado"         │   │
│  │  ├── "Maria reportou taxa incorreta"            │   │
│  │  └── "Pedro teve problema com PIX"              │   │
│  │  (decaem 3x mais rápido, liberam espaço)        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Decaimento Cognitivo (Ebbinghaus)

```
Retrievability = e^(-t/S)

Onde:
  t = tempo desde último acesso
  S = stability (aumenta com uso, consolidação, centralidade)
```

---

## 🔌 Integração Fácil

### MCP (Claude Desktop, Cursor, etc.)

```json
{
  "mcpServers": {
    "cortex": {
      "command": "cortex-mcp"
    }
  }
}
```

### SDK Python (LangChain, CrewAI, etc.)

```python
# LangChain
from cortex.integrations import CortexLangChainMemory
chain = ConversationChain(llm=llm, memory=CortexLangChainMemory())

# CrewAI
from cortex.integrations import CortexCrewAIMemory
crew = Crew(long_term_memory=CortexCrewAIMemory())

# Decorator (qualquer função)
from cortex_memory import with_memory

@with_memory(namespace="meu_agente")
def meu_agente(msg: str, context: str = "") -> str:
    return resposta  # context já tem memórias relevantes
```

### REST API

```bash
# Lembrar
curl -X POST localhost:8000/memory/remember \
  -d '{"who":["João"], "what":"resolveu_bug", "how":"fix_timeout"}'

# Recuperar
curl -X POST localhost:8000/memory/recall \
  -d '{"query":"bug de timeout"}'
```

---

## 🎯 Casos de Uso

### 1. Assistente Pessoal
- Lembra preferências do usuário
- Mantém contexto entre sessões
- Consolida padrões de comportamento

### 2. Suporte ao Cliente
- Isola dados de cada cliente
- Aprende padrões comuns (compartilhado)
- Reduz tempo de atendimento

### 3. Assistente de Desenvolvimento
- Lembra decisões de arquitetura
- Mantém contexto do projeto
- Compartilha conhecimento entre devs

### 4. Roleplay/Games
- Memória persistente de NPCs
- Relações entre personagens
- Evolução de narrativa

---

## 📈 Roadmap

### ✅ Implementado (v3.0)
- Modelo W5H
- Decaimento Ebbinghaus
- Hub Centrality
- Consolidação Hierárquica
- SleepRefiner (consolidação em background)
- SDK Python (LangChain, CrewAI)
- Benchmark científico

### 🔜 Em Desenvolvimento
- Google ADK Adapter
- FastAgent Adapter
- Dashboard de visualização
- Multi-cliente PERSONAL vs LEARNED

### 🔮 Futuro
- Neo4j backend
- ProceduralMemory (skills, policies)
- IdentityKernel (anti-jailbreak)

---

## 📚 Documentação

| Documento | Conteúdo |
|-----------|----------|
| [API.md](API.md) | Endpoints REST |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Estrutura de camadas |
| [MCP.md](MCP.md) | Integração MCP |
| [W5H_DESIGN.md](W5H_DESIGN.md) | Design do modelo |
| [VISION.md](VISION.md) | Filosofia e roadmap |

---

## 🚀 Quick Start

```bash
# 1. Instalar
pip install cortex-memory  # ou: pip install -e ".[all]"

# 2. Iniciar API
cortex-api

# 3. Usar
from cortex_memory import with_memory

@with_memory(namespace="demo")
def assistente(msg, context=""):
    # Seu LLM aqui - context já tem memórias!
    return resposta
```

---

## 📞 Contato

- **Repositório:** [GitHub](https://github.com/seu-usuario/cortex)
- **Licença:** MIT

---

*Cortex - Porque agentes inteligentes precisam de memória inteligente.*

*Última atualização: Janeiro 2026*

