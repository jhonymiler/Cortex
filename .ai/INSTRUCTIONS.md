# Cortex - Sistema Cognitivo de Memória para Agentes de IA

**Cortex é um sistema de memória cognitiva que resolve a "amnésia crônica" de LLMs**, implementando 9 melhorias científicas validadas para armazenamento de alto valor informacional com menos tokens, raciocínio causal, e aprendizado coletivo. Score 93% em dimensões cognitivas vs 31% de alternativas como RAG ou Mem0.

**Motivação central**: Maximizar valor informacional por token + capturar relações causais/temporais + habilitar aprendizado coletivo entre agentes.

---

## Stack Tecnológica

| Componente | Tecnologia | Versão | Observação |
|------------|-----------|--------|------------|
| **Linguagem** | Python | 3.10+ (rec. 3.11+) | Type hints obrigatórios |
| **Web Framework** | FastAPI | ≥0.115.0 | API REST assíncrona |
| **Validação** | Pydantic | ≥2.0.0 | Modelos de dados |
| **Processamento NLP** | spaCy | ≥3.7.0 | Tokenização e análise |
| **Embedding** | Ollama + qwen3 | Local | Padrão alpha (custo), mas suporta OpenAI/Anthropic via LiteLLM |
| **Storage** | Neo4j | 5.15+ | **PRODUÇÃO** - JSON apenas para dev/testes |
| **Testing** | pytest + pytest-asyncio | ≥8.0.0 | Cobertura alvo: >90% |
| **Linting** | ruff | ≥0.8.0 | PEP8 + naming patterns |
| **Type Check** | mypy | ≥1.8.0 | Validação obrigatória |
| **UI (opcional)** | Streamlit | ≥1.40.0 | Interface visual |
| **MCP (opcional)** | FastMCP | ≥0.4.0 | Claude Desktop (apenas interface alternativa à REST API) |

---

## Arquitetura - Componentes e Responsabilidades

```
┌─────────────────────────────────────┐
│  INTERFACES                        │
│  ├─ MCP Server (Claude Desktop)    │  Protocolo alternativo, mesma funcionalidade da API
│  └─ REST API (FastAPI)             │  Interface principal
└─────────┬───────────────────────────┘
          │
┌─────────┴───────────────────────────┐
│  SERVICES                          │
│  └─ MemoryService                  │  Orquestração centralizada (remember/recall)
└─────────┬───────────────────────────┘
          │
┌─────────┴───────────────────────────┐
│  CORE DOMAIN (src/cortex/core/)    │
│  ├─ primitives/                    │  Entity, Memory (W5H), Relation, Namespace
│  ├─ graph/                         │  MemoryGraph (O(1)), GraphAlgorithms (BFS, PageRank, Louvain)
│  ├─ processing/                    │  Embedding, Tokenization, SemanticHash
│  ├─ recall/                        │  Ranking (RRF+MMR), HierarchicalRecall, ContextPacker
│  ├─ learning/                      │  DecayManager (Ebbinghaus), MemoryAttention, Contradiction
│  ├─ storage/                       │  Adapters (JSON/Neo4j), IdentityKernel (Memory Firewall)
│  └─ consolidation/                 │  DreamAgent (background worker)
└─────────┬───────────────────────────┘
          │
┌─────────┴───────────────────────────┐
│  STORAGE                           │
│  ├─ Neo4jAdapter (PRODUÇÃO)        │  Operações graph-native, performance otimizada
│  └─ JSONAdapter (dev/testes)       │  Dados descartáveis, não usar em produção
└─────────────────────────────────────┘
```

| Módulo | Responsabilidade | Arquivo-chave |
|--------|------------------|---------------|
| **primitives/** | Definição de entidades de domínio (Entity, Memory, Relation, Namespace) | `memory.py`, `entity.py`, `relation.py` |
| **graph/** | Grafo de memória (armazenamento O(1), busca, indexação) + algoritmos (BFS, PageRank, Louvain) | `memory_graph.py`, `graph_algorithms.py` |
| **processing/** | Embedding semântico (Ollama), tokenização (spaCy), hash semântico | `embedding.py`, `language.py` |
| **recall/** | Recuperação de memória (Hybrid Ranking RRF+MMR, 4 níveis hierárquicos, context packing 40-70% tokens) | `ranking.py`, `hierarchical_recall.py`, `context_packer.py` |
| **learning/** | Decaimento cognitivo (Ebbinghaus), multi-head attention, detecção de contradições | `decay.py`, `memory_attention.py`, `contradiction.py` |
| **storage/** | Persistência (Adapter pattern), IdentityKernel (Memory Firewall anti-jailbreak 90% detecção) | `adapters.py`, `neo4j_adapter.py`, `identity.py` |
| **consolidation/** | DreamAgent - consolidação background de memórias brutas → padrões → conhecimento coletivo | `episode.py` |

---

## Princípios de Design (Por Quê das Decisões)

1. **Modelo W5H (Who/What/Why/When/Where/How)**: Estruturação para recall preciso — decomposição em dimensões buscáveis melhora relevância vs formato livre
2. **Neo4j como storage padrão**: JSON apenas dev/testes (dados descartáveis) — Neo4j preparado para crescimento, operações graph-native essenciais
3. **Threshold adaptativo (0.25 padrão)**: Ajustável por domínio — sistemas técnicos usam maior precisão, roleplay usa menor para criatividade
4. **Namespace com isolamento obrigatório por tenant**: Segurança — empresa não pode invadir memória de outra, mas flexível internamente (sub-namespaces por contexto)
5. **Importância inferida + hub detection**: Memórias críticas identificadas automaticamente por frequência de acesso (PageRank) vs marcação manual
6. **Delete permanente ao atingir forgotten threshold (retrievability <0.1)**: Liberar recursos — memórias não recuperáveis são descartadas definitivamente
7. **Contradições reconciliadas via LLM + notificação**: Tentar merge inteligente mas avisar agente cliente para decisão final (preserva autonomia)
8. **DreamAgent configurável/sob demanda**: Background worker para consolidação — pode rodar agendado, por volume, ou continuamente conforme necessidade
9. **Ollama local (alpha) com suporte LiteLLM**: Custo zero para validação alpha, mas sistema preparado para trocar para OpenAI/Anthropic em produção

---

## Como Rodar o Projeto

### Instalação
```bash
# Clone e setup ambiente
git clone <repo>
cd cortex
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalação (escolha uma opção)
pip install -e "."           # Básico (API REST)
pip install -e ".[neo4j]"    # + Suporte Neo4j (RECOMENDADO para produção)
pip install -e ".[all]"      # Tudo (API, UI, Benchmarks, Dev tools)
```

### Configuração (`.env`)
```bash
# Storage (PRODUÇÃO = neo4j)
CORTEX_STORAGE_BACKEND=neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=<seu-password>

# LLM (alpha = Ollama, produção = configurável)
OLLAMA_URL=http://localhost:11434
CORTEX_EMBEDDING_MODEL=qwen3-embedding:0.6b

# Decay e thresholds
CORTEX_DECAY_BASE_STABILITY=7.0
CORTEX_DECAY_FORGOTTEN_THRESHOLD=0.1

# Namespace e modo
CORTEX_NAMESPACE=default
CORTEX_MEMORY_MODE=multi_client  # ou single_user/team
```

### Execução
```bash
# API REST
cortex-api                        # Produção
CORTEX_RELOAD=true cortex-api     # Dev (hot reload)

# UI (opcional)
./start_ui.sh

# Testes (SEMPRE antes de commit)
pytest tests/                     # Todos os testes (>90% cobertura esperada)
pytest -m "not slow"             # Excluir testes lentos
ruff check .                      # Linting
mypy src/cortex/                  # Type checking
```

---

## Convenções de Código (Resumo — detalhes em `.ai/rules/`)

- **PEP8 + Ruff**: Formatação padrão Python validada por ruff
- **Type hints obrigatórios**: Todo código deve ter type hints completos validados por mypy
- **Naming patterns**:
  - Adapters terminam em `Adapter` (ex: `Neo4jAdapter`, `JSONAdapter`)
  - Services terminam em `Service` (ex: `MemoryService`)
  - Algoritmos de grafo em `graph_algorithms.py` seguem nomes acadêmicos (BFS, PageRank, Louvain)
- **Organização modular**: Novos módulos devem alinhar com camadas existentes (primitives, graph, processing, recall, learning, storage)
- **Cobertura de testes >90%**: Toda feature nova precisa de testes unitários + integração para paths críticos

---

## Skills Disponíveis (Conhecimento de Domínio)

Use os skills abaixo quando trabalhar com domínios específicos do Cortex. Cada skill contém conhecimento detalhado que não está óbvio no código.

| Nome | Quando Usar | Conteúdo |
|------|-------------|----------|
| **[memory-model](skills/memory-model/SKILL.md)** | Implementar/entender modelo W5H (Who/What/Why/When/Where/How), criar memórias, entidades, relações | Especificação completa do modelo W5H, regras de validação, exemplos por domínio (suporte, dev, roleplay) |
| **[recall-system](skills/recall-system/SKILL.md)** | Implementar busca de memórias, otimizar relevância, entender ranking híbrido (RRF+MMR), context packing | Algoritmos de ranking, 4 níveis hierárquicos, BFS graph expansion, estratégias de otimização de tokens |
| **[decay-learning](skills/decay-learning/SKILL.md)** | Trabalhar com decaimento de memória (Ebbinghaus), spaced repetition, importância, consolidação | Curva de Ebbinghaus, SM-2 adaptativo, hub protection, DreamAgent, active forgetting |
| **[storage-adapters](skills/storage-adapters/SKILL.md)** | Escolher/configurar storage (JSON vs Neo4j), implementar migrations, troubleshooting de persistência | Diferenças entre adapters, quando usar cada um, configuração Neo4j, constraints e índices |
| **[identity-security](skills/identity-security/SKILL.md)** | Configurar IdentityKernel (Memory Firewall), detectar jailbreak, gerenciar namespaces seguros | 3 modos (Pattern/Semantic/Hybrid), padrões de ataque, isolamento de tenants, logging de segurança |

---

## Documentação Detalhada (`.ai/docs/`)

| Documento | Descrição |
|-----------|-----------|
| [architecture.md](docs/architecture.md) | Diagrama completo do sistema, decisões arquiteturais, trade-offs |
| [database-schema.md](docs/database-schema.md) | Schema Neo4j completo (nodes, relationships, constraints, índices) |
| [w5h-model.md](docs/w5h-model.md) | Especificação detalhada do modelo W5H com exemplos |
| [cognitive-principles.md](docs/cognitive-principles.md) | Base científica das 9 melhorias cognitivas implementadas |
| [api-contracts.md](docs/api-contracts.md) | Contratos REST API + MCP (endpoints, payloads, responses) |
| [PROJECT-STATUS.md](docs/PROJECT-STATUS.md) | Estado atual (v3.0.0 alpha), features implementadas, pendências |

---

## Fluxos de Trabalho Críticos

### 1. Store (Armazenar Memória)
```
Input → MemoryService.remember()
  → Parse W5H (extrair Who/What/Why/When/Where/How)
  → Extract/Create Entities
  → Create Memory + Relations (grafo)
  → IdentityKernel check (90% jailbreak detection) — Se detectar: Log + Notifica + Bloqueia
  → Save to MemoryGraph (O(1) insertion)
  → Update DecayManager (inicializar stability/retrievability)
  → Optional: Trigger DreamAgent (consolidação background se configurado)
```

### 2. Recall (Recuperar Memória)
```
Query → MemoryService.recall()
  → Embedding similarity search (cosine similarity)
  → Inverted index keyword search (fallback)
  → RRF fusion (Reciprocal Rank Fusion - múltiplos sinais)
  → Hierarchical ranking (4 níveis: Working/Recent/Patterns/Knowledge)
  → MMR diversity (Maximal Marginal Relevance - evita redundância +40%)
  → BFS graph expansion (contexto adicional +30%)
  → Context Packing (40-70% token reduction via priority scoring)
  → Return RecallResult (memories + metadata)
```

### 3. Learning (Aprendizado Contínuo)
```
Time passes...
  → DecayManager.calculate_retrievability() (Ebbinghaus: R = e^(-t/S))
  → Hub detection (PageRank) — Memórias críticas identificadas
  → Consolidation bonus (hubs ganham 2x stability)
  → Active forgetting (retrievability <0.1 → DELETE permanente)
  → DreamAgent background worker (se habilitado):
    → Refine raw memories (consolidação progressiva)
    → Extract patterns (identificar padrões recorrentes)
    → Promote to collective knowledge (memória compartilhada)
```

---

## Regras de Negócio Críticas (Não Óbvias no Código)

1. **Namespace isolation**: Tenant não pode acessar memória de outro tenant (segurança obrigatória), mas pode organizar sub-namespaces internamente
2. **Forgotten threshold = DELETE**: Memória com retrievability <0.1 é **deletada permanentemente** (não arquivada)
3. **Jailbreak detection = Log + Notifica + Bloqueia**: IdentityKernel não salva memória suspeita, registra tentativa, notifica admin
4. **Importância automática**: Não marcar manualmente — sistema infere via frequência de acesso (hub detection) e padrões de uso
5. **JSON é descartável**: Dados em JSON são apenas para dev/testes, produção **sempre Neo4j** (preparado para crescimento)
6. **MCP = REST API alternativa**: Mesma funcionalidade, apenas protocolo diferente (não tem features exclusivas)
7. **Threshold 0.25 ajustável por domínio**: Sistemas técnicos aumentam (precisão), roleplay diminui (criatividade)
8. **Cobertura >90% obrigatória**: Novas features precisam de testes — validar antes de commit (pytest + ruff + mypy)

---

## Validação Antes de Commit

**SEMPRE execute nesta ordem antes de criar commit:**

```bash
# 1. Linting
ruff check .

# 2. Type checking
mypy src/cortex/

# 3. Testes completos
pytest tests/

# 4. Review manual de diffs
git diff
```

**Pipeline esperado**: Linting + Type Check + Testes 100% passando + Review manual → Commit

---

## Próximos Passos (Quando Trabalhar em Features)

- Consultar skills relevantes em [.ai/skills/](skills/)
- Seguir rules de código em [.ai/rules/](rules/)
- Documentar decisões arquiteturais em [.ai/docs/RFC/](docs/RFC/) se não-óbvias
- Atualizar [PROJECT-STATUS.md](docs/PROJECT-STATUS.md) após mudanças significativas
- Sempre validar com pipeline completo antes de commit
