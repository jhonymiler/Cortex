# 🧠 Cortex - AI Coding Agent Instructions

> **Sistema de Memória Cognitiva para Agentes LLM**  
> *"Porque agentes inteligentes precisam de memória inteligente"*  
> Versão: 3.2 | Fevereiro 2026

---

## 🎯 O Que é Cortex? (Conceito Central)

**Cortex NÃO é RAG nem VectorDB.** É uma camada de memória cognitiva que complementa LLMs:

```
LLM (raciocina) + CORTEX (lembra/evolui) + RAG (busca docs estáticos)
```

**5 Diferenciadores Únicos:**
1. **Cognição Biológica** - Decay (Ebbinghaus), consolidação (sono), hubs (sinapses)
2. **Memória Coletiva** - Shared/Learned namespaces com isolamento LGPD/GDPR
3. **Busca O(1)** - Índices invertidos, ZERO tokens em embeddings
4. **Threshold Adaptativo** - Gap analysis, não similarity fixa
5. **Memory Firewall** - Anti-jailbreak (IdentityKernel)

---

## 📚 Documentação Modular (D.R.Y.)

**SEMPRE referencie, NUNCA duplique conceitos:**

| Tópico | Fonte Canônica |
|--------|----------------|
| Modelo W5H | [`docs/concepts/memory-model.md`](../docs/concepts/memory-model.md) |
| Decay (Ebbinghaus) | [`docs/concepts/cognitive-decay.md`](../docs/concepts/cognitive-decay.md) |
| Consolidação | [`docs/concepts/consolidation.md`](../docs/concepts/consolidation.md) |
| Shared Memory | [`docs/concepts/shared-memory.md`](../docs/concepts/shared-memory.md) |
| Arquitetura | [`docs/architecture/overview.md`](../docs/architecture/overview.md) |
| Integrações | [`docs/getting-started/integrations.md`](../docs/getting-started/integrations.md) |

---

## ⚡ Setup & Comandos Essenciais

### Ambiente (CRÍTICO)
```bash
# 1. SEMPRE ative venv ANTES de qualquer comando
source venv/bin/activate

# 2. Instalar dependências
pip install -e ".[all,dev]"    # Tudo (API + MCP + UI + Benchmark)
pip install -e ".[api]"        # Só API
pip install -e ".[mcp]"        # Só MCP

# 3. Baixar modelos Ollama (local LLM)
ollama pull gemma3:4b          # LLM para consolidação
ollama pull qwen3-embedding:0.6b  # Embeddings semânticos
```

### Serviços
```bash
cortex-api                     # API REST (porta 8000)
cortex-ui                      # UI Streamlit (porta 8501)
cd mcp && uvx cortex-mcp       # MCP Server (FastMCP)

# Debug porta em uso:
lsof -ti:8000 | xargs kill -9  # Mata processo na porta 8000
CORTEX_PORT=8001 cortex-api    # Usa porta alternativa
```

### Testes & Qualidade
```bash
pytest tests/ -v               # Todos os testes
pytest tests/core/ -v          # Só core
pytest -k "test_decay"         # Teste específico

ruff check src/                # Lint
ruff format src/               # Format
mypy src/                      # Type check
```

### Benchmark
```bash
./start_benchmark.sh --quick   # Rápido (~10 min)
./start_benchmark.sh --full    # Completo (~1 hora)
./analyze_results.sh           # Análise dos resultados
```

---

## 🏗️ Arquitetura em Camadas (O "Big Picture")

```
┌──────────────────────────────────────────────────────────────┐
│  INTERFACES (Entrada)                                        │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │ REST API   │  │    MCP     │  │  SDK (Py)  │             │
│  │ (FastAPI)  │  │ (FastMCP)  │  │ Decorators │             │
│  └──────┬─────┘  └──────┬─────┘  └──────┬─────┘             │
├─────────┴────────────────┴────────────────┴──────────────────┤
│  SERVICES (Lógica de Negócio)                                │
│  ┌────────────────────────────────────────────┐              │
│  │  MemoryService (Orquestrador Central)      │              │
│  │  - remember() / recall()                   │              │
│  │  - Namespace isolation                     │              │
│  │  - Threshold adaptativo                    │              │
│  └─────────────────┬──────────────────────────┘              │
├────────────────────┴──────────────────────────────────────────┤
│  CORE (Modelos Puros - SEM I/O)                               │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌────────────┐     │
│  │ Entity  │  │ Memory  │  │ Relation │  │ MemoryGraph│     │
│  │ (coisa) │  │ (W5H)   │  │ (conexão)│  │ (índices)  │     │
│  └─────────┘  └─────────┘  └──────────┘  └────────────┘     │
│                                                               │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │DecayManager  │  │SharedMemory    │  │DreamAgent       │  │
│  │(Ebbinghaus)  │  │(3 namespaces)  │  │(consolidation)  │  │
│  └──────────────┘  └────────────────┘  └─────────────────┘  │
├───────────────────────────────────────────────────────────────┤
│  STORAGE (Persistência)                                       │
│  ┌────────────────────────────────────┐                      │
│  │  JSON (atual) / SQLite (futuro)   │                      │
│  └────────────────────────────────────┘                      │
└───────────────────────────────────────────────────────────────┘
```

**Regra de Ouro:** Models (core) são **puros** (sem I/O). Services têm **lógica de negócio**. APIs fazem **I/O**.

---

## 🔬 Modelo W5H (Estrutura de Memória)

> 📖 Ver detalhes: [`docs/concepts/memory-model.md`](../docs/concepts/memory-model.md)

Memórias usam modelo **W5H** (Who, What, Why, When, Where, How) - NÃO texto livre:

```python
Memory(
    who=["João", "sistema_auth"],         # Participantes
    what="resolveu_bug_login",             # Ação
    why="timeout_conexao_db",              # Causa raiz
    how="adicionou_pool_conexoes",         # Solução
    where="projeto_x:backend",             # Namespace
    when=datetime.now(),                   # Timestamp
    importance=0.8,                        # 0.0 - 1.0
)
```

**Por quê W5H?**
- ✅ Busca estruturada O(1) (índices)
- ✅ ~36 tokens (5x mais compacto que texto livre)
- ✅ WHY explícito (não implícito)
- ✅ Agnóstico ao domínio

---

## 📉 Decaimento Cognitivo (Ebbinghaus)

> 📖 Ver detalhes: [`docs/concepts/cognitive-decay.md`](../docs/concepts/cognitive-decay.md)

Memórias **decaem** com o tempo (como cérebro humano):

```python
R = e^(-t/S)  # Retrievability = função do tempo e estabilidade

# Stability (S) aumenta com:
# - Acessos frequentes: 1 + log(access_count)
# - Consolidação: 2.0× (is_summary=True)
# - Hub centrality: 1.5× (5+ referências)
# - Importância alta: 1.3× (importance > 0.7)
```

**Implementação:**
```python
from cortex.core import DecayManager, DecayConfig

manager = DecayManager(DecayConfig(
    base_stability_days=7.0,      # Base
    consolidation_bonus=2.0,      # Memórias consolidadas
    hub_bonus=1.5,                # Hubs (muito referenciados)
    forgotten_threshold=0.1,      # < 0.1 = esquecida
))

# Memórias com R < 0.1 são marcadas como "forgotten"
```

---

## 🔄 Consolidação (DreamAgent)

> 📖 Ver detalhes: [`docs/concepts/consolidation.md`](../docs/concepts/consolidation.md)

**Problema:** 100 memórias sobre mesmo problema = ruído  
**Solução:** DreamAgent agrupa automaticamente (como sono humano)

```python
from cortex.workers import DreamAgent

agent = DreamAgent()
result = agent.dream(namespace="suporte_cliente")

# O que acontece:
# 1. Busca memórias similares (semântica + temporal)
# 2. Gera resumo usando LLM
# 3. Cria Memory com is_summary=True, occurrence_count=N
# 4. Marca originais com consolidated_into=<ID_RESUMO>
# 5. Originais decaem 3x mais rápido
```

**Estrutura hierárquica:**
```
CONSOLIDADA (aparece no recall):
  ├── is_summary: True
  ├── occurrence_count: 15
  └── consolidated_from: [id1, id2, ...]

GRANULARES (excluídas do recall normal):
  ├── consolidated_into: <ID_RESUMO>
  └── decaem 3x mais rápido
```

---

## 🔒 Shared Memory (Memória Coletiva)

> 📖 Ver detalhes: [`docs/concepts/shared-memory.md`](../docs/concepts/shared-memory.md)

**3 níveis de visibilidade** para isolamento LGPD/GDPR:

```python
from cortex.core.storage import SharedMemoryManager

manager = SharedMemoryManager()

# PERSONAL: user:123 → Dados isolados do usuário (PII/PCI)
personal_ns = manager.get_personal_namespace("user_123")
# → "user:user_123"

# SHARED: shared → Conhecimento institucional visível a todos
# LEARNED: learned → Padrões anonimizados extraídos de PERSONAL

# Recall combina os 3:
namespaces = manager.get_recall_namespaces("user_123")
# → ["user:user_123", "shared", "learned"]
```

**Exemplo de uso:**
```python
# Armazenar dados pessoais
service.remember(
    namespace="user:joao",  # Isolado
    who=["João"],
    what="pediu_produto_123",
    ...
)

# Armazenar conhecimento compartilhado
service.remember(
    namespace="shared",      # Visível a todos
    what="politica_devolucao_30_dias",
    ...
)
```

---

## 📊 SDK & Integrações

> 📖 Ver detalhes: [`docs/getting-started/integrations.md`](../docs/getting-started/integrations.md)

### MCP (Claude Desktop / Cursor)
```json
// ~/.config/claude/claude_desktop_config.json
{
  "mcpServers": {
    "cortex": {
      "command": "cortex-mcp",
      "env": {"CORTEX_DATA_DIR": "/path/to/data"}
    }
  }
}
```

**Tools disponíveis:**
- `cortex_recall` - ANTES de responder (busca contexto)
- `cortex_remember` - APÓS responder (armazena W5H)
- `cortex_stats`, `cortex_health`, `cortex_decay`

### SDK Python (Decorator-based)
```python
from cortex_memory_sdk import with_memory

@with_memory(namespace="meu_agente")
def agent(message: str, context: str = "") -> str:
    # context vem automaticamente do recall
    # retorno é automaticamente armazenado
    return f"Resposta baseada em: {context}"
```

### LangChain
```python
from cortex_memory_sdk.integrations import CortexLangChainMemory

memory = CortexLangChainMemory(namespace="lc_agent")
chain = ConversationChain(llm=llm, memory=memory)
```

### CrewAI
```python
from cortex_memory_sdk.integrations import CortexCrewAIMemory

crew = Crew(
    long_term_memory=CortexCrewAIMemory(namespace="crew_agents")
)
```

---

## 🏛️ Padrões de Código Específicos do Projeto

### 1. Separação de Responsabilidades (CRÍTICO)

```python
# ✅ CORRETO - Models puros (sem I/O)
@dataclass
class Memory:
    who: list[str]
    what: str
    # Só lógica pura, sem file I/O ou HTTP

# ✅ CORRETO - Services com lógica de negócio
class MemoryService:
    def remember(self, memory: Memory) -> str:
        # Orquestra: validação, índices, persistência
        ...

# ✅ CORRETO - APIs fazem I/O
@app.post("/memory/remember")
async def api_remember(request: RememberRequest):
    # Converte DTO → Model, chama Service
    ...
```

**NUNCA misture:**
- ❌ I/O direto em dataclasses (`src/cortex/core/primitives/`)
- ❌ Lógica de negócio em APIs (`src/cortex/api/`)
- ❌ HTTP calls em Services (use abstrações)

### 2. Pydantic vs Dataclass

```python
# API/Services: Pydantic (validação de entrada)
from pydantic import BaseModel, Field

class RememberRequest(BaseModel):
    who: list[str] = Field(..., description="Participants")
    what: str = Field(..., description="Action")

# Core: Dataclass (models puros, performance)
from dataclasses import dataclass

@dataclass
class Memory:
    who: list[str]
    what: str
```

### 3. Threshold Adaptativo (NÃO fixo!)

```python
# ❌ ERRADO - Threshold fixo
results = [r for r in results if r.score >= 0.75]

# ✅ CORRETO - Threshold adaptativo (gap analysis)
# Ver: src/cortex/services/memory_service.py::_recall_by_embedding
if top_score >= 0.75:
    return [top_result]  # Alta confiança
elif std_dev < 0.05:
    return []  # Uniformidade = ruído
elif gap > 0.10:
    threshold = top_score - gap  # Ajuste dinâmico
else:
    threshold = 0.60  # Fallback
```

### 4. Namespace Isolation

```python
# ✅ SEMPRE use namespace para isolamento
service = MemoryService(storage_path="data/user_123")

# ❌ NUNCA compartilhe instância entre namespaces
# Cada namespace = MemoryGraph isolado

# ✅ Use NamespacedMemoryService para multi-tenant
from cortex.services import NamespacedMemoryService

manager = NamespacedMemoryService(base_path="./data")
service_a = manager.get_service("user_123")  # Isolado
service_b = manager.get_service("user_456")  # Isolado
```

### 5. FastMCP (NÃO old MCP)

```python
# ✅ CORRETO - FastMCP (decorator-based)
from fastmcp import FastMCP

mcp = FastMCP("cortex")

@mcp.tool()
def cortex_recall(query: str, namespace: str = "default") -> dict:
    """Busca memórias relevantes."""
    ...

# ❌ ERRADO - Old MCP (manual JSON-RPC)
# NUNCA use implementação manual de JSON-RPC
```

---

## 🔍 Estratégia de Recall (Busca Adaptativa)

O Cortex usa **busca híbrida** com threshold adaptativo:

```python
# src/cortex/services/memory_service.py::recall()

# 1. Busca por índice O(1) (estruturada)
if query contains WHO/WHAT/WHERE:
    results = graph.recall_by_index(...)

# 2. Busca semântica (embeddings)
else:
    results = _recall_by_embedding(query)
    
    # Threshold adaptativo:
    # - Score muito alto (≥0.75) → retorna top 1
    # - Uniformidade (std < 0.05) → descarta (ruído)
    # - Gap grande (>0.10) → ajusta threshold dinamicamente
    # - Fallback: threshold base 0.60
```

**Por quê isso importa:**
- Similarity fixa (0.75) falha em queries genéricas
- Gap analysis detecta resultados únicos vs ruído
- Reduz falsos positivos em 35% (vs baseline)

---

## 🚨 O QUE NÃO FAZER

```python
# ❌ Duplicar explicações de conceitos
# ✅ Referenciar: Ver [Modelo W5H](docs/concepts/memory-model.md)

# ❌ Threshold fixo para embeddings (ex: 0.75)
# ✅ Threshold adaptativo com gap analysis

# ❌ Old MCP (manual JSON-RPC)
# ✅ FastMCP (decorator-based)

# ❌ Misturar camadas (I/O em models)
# ✅ Models puros, Services com lógica, APIs fazem I/O

# ❌ Compartilhar MemoryGraph entre namespaces
# ✅ Cada namespace = instância isolada

# ❌ Importar spaCy se não necessário
# ✅ Embeddings via Ollama (qwen3-embedding:0.6b)

# ❌ Criar arquivos em src/cortex/core/ com I/O
# ✅ I/O só em services/ e api/
```

---

## 📝 Commits

```
feat: nova funcionalidade
fix: correção de bug
docs: documentação
refactor: sem mudar comportamento
test: testes
bench: benchmark
```

---

*Última atualização: Janeiro 2026*
