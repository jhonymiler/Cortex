# 🏗️ Arquitetura

> *"Cortex, porque agentes inteligentes precisam de memória inteligente"*

---

## Onde Cortex se Encaixa

Cortex não substitui seu LLM ou RAG — ele **complementa** como camada de memória cognitiva:

```
┌─────────────────────────────────────────────────────────────────┐
│                       SUA APLICAÇÃO                             │
│                   (Chat, Agente, Assistente)                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
    ┌───────────┐     ┌───────────┐     ┌───────────┐
    │    LLM    │     │   CORTEX  │     │    RAG    │
    │           │     │           │     │           │
    │ Raciocina │     │ Lembra    │     │ Busca em  │
    │ e gera    │◄───►│ evolui    │     │ documentos│
    │ respostas │     │ aprende   │     │ estáticos │
    └───────────┘     └───────────┘     └───────────┘
          │                 │                 │
          │     ┌───────────┘                 │
          │     │                             │
          ▼     ▼                             ▼
    ┌───────────────────────────────────────────────────┐
    │            PROMPT ENRIQUECIDO                     │
    │  "Contexto: João gosta de café sem açúcar.       │
    │   Documento: Manual de devoluções página 12.     │
    │   Pergunta: Posso devolver o café?"              │
    └───────────────────────────────────────────────────┘
```

**Cada peça faz o que faz melhor:**
- **LLM:** Raciocina, gera respostas
- **Cortex:** Lembra experiências, evolui, esquece ruído
- **RAG:** Busca em documentação estática

---

## Propósito e Visão

O Cortex entrega **5 dimensões de valor** para agentes LLM:

| Dimensão | Implementação | Score |
|----------|---------------|-------|
| 🧠 **Cognição Biológica** | DecayManager, DreamAgent, Hub Detection | 100% |
| 👥 **Memória Coletiva** | SharedMemory, Namespace Hierarchy | 75% |
| 🎯 **Valor Semântico** | Embedding semântico, Threshold adaptativo | 100% |
| ⚡ **Eficiência** | MemoryGraph O(1), Índice invertido | 100% |
| 🔒 **Segurança** | IdentityKernel anti-jailbreak | 100% |

**Score Total: 93%** (vs 31% das alternativas)

---

## Diagrama de Camadas

```
┌─────────────────────────────────────────────────────────────┐
│                        INTERFACES                           │
│              ┌───────────┐  ┌───────────┐                  │
│              │    MCP    │  │  REST API │                  │
│              │  Server   │  │  FastAPI  │                  │
│              └─────┬─────┘  └─────┬─────┘                  │
├────────────────────┴──────────────┴─────────────────────────┤
│                        SDK                                   │
│     ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│     │ Core Genérico│  │  LangChain   │  │   CrewAI     │   │
│     │ before/after │  │   Adapter    │  │   Adapter    │   │
│     └──────────────┘  └──────────────┘  └──────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                        SERVICES                             │
│              ┌───────────────────────┐                     │
│              │    MemoryService      │                     │
│              │  (Lógica de Negócio)  │                     │
│              └───────────┬───────────┘                     │
├──────────────────────────┴──────────────────────────────────┤
│                        CORE                                  │
│     ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│     │  Entity  │  │  Memory  │  │ Relation │               │
│     └────┬─────┘  └────┬─────┘  └────┬─────┘               │
│          └─────────────┴─────────────┘                      │
│                        │                                    │
│     ┌──────────────────┴──────────────────┐                │
│     │            MemoryGraph              │                │
│     │        (Grafo + Índices O(1))       │                │
│     └──────────────────┬──────────────────┘                │
│                        │                                    │
│     ┌─────────┐  ┌─────┴─────┐  ┌──────────────┐          │
│     │ Decay   │  │  Shared   │  │ Consolidation│          │
│     │ Manager │  │  Memory   │  │   (Dream)    │          │
│     └─────────┘  └───────────┘  └──────────────┘          │
├─────────────────────────────────────────────────────────────┤
│                        STORAGE                              │
│              ┌───────────────────────┐                     │
│              │    JSON / SQLite      │                     │
│              │    (Neo4j futuro)     │                     │
│              └───────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Componentes Core

### Entity

Representa qualquer "coisa" no universo de discurso:

```python
@dataclass
class Entity:
    id: str                    # UUID
    type: str                  # "person", "object", "concept"
    name: str                  # Nome legível
    identifiers: list[str]     # Formas de reconhecer
    attributes: dict           # Metadados flexíveis
    centrality_score: float    # Hub detection
```

**Responsabilidades**:
- Identificar entidades únicas
- Armazenar atributos conhecidos
- Calcular centralidade (quantas memórias referenciam)

Ver detalhes em [Modelo de Memória](../concepts/memory-model.md).

---

### Memory (W5H)

Representa qualquer "acontecimento":

```python
@dataclass
class Memory:
    id: str
    
    # W5H
    who: list[str]     # Participantes
    what: str          # Ação
    why: str           # Causa
    when: datetime     # Timestamp
    where: str         # Namespace
    how: str           # Resultado
    
    # Metadados
    importance: float
    access_count: int
    stability: float
    
    # Consolidação
    consolidated_from: list[str]
    consolidated_into: str | None
    is_summary: bool
```

**Responsabilidades**:
- Armazenar experiências estruturadas
- Calcular retrievability (decaimento)
- Suportar consolidação hierárquica

Ver detalhes em [Consolidação](../concepts/consolidation.md).

---

### Relation

Representa qualquer "conexão":

```python
@dataclass
class Relation:
    id: str
    from_id: str           # Entity ou Memory
    relation_type: str     # Tipo livre
    to_id: str             # Entity ou Memory
    strength: float        # 0.0 - 1.0
```

**Responsabilidades**:
- Conectar entidades e memórias
- Suportar tipos de relação flexíveis
- Reforçar com uso repetido

---

### MemoryGraph

Grafo de memória com índices O(1):

```python
class MemoryGraph:
    entities: dict[str, Entity]
    memories: dict[str, Memory]
    relations: dict[str, Relation]
    
    # Índices para busca O(1)
    entity_by_name: dict[str, list[str]]
    entity_by_type: dict[str, list[str]]
    memories_by_entity: dict[str, list[str]]
    relations_by_source: dict[str, list[str]]
    relations_by_target: dict[str, list[str]]
```

**Responsabilidades**:
- Armazenar grafo em memória
- Manter índices atualizados
- Executar buscas O(1)
- Persistir para storage

---

## Fluxos de Dados

### Store (Armazenar)

```
1. Request chega (API ou MCP)
   ↓
2. Validação (Pydantic)
   ↓
3. EntityResolver
   ├─ Entidade existe? → Atualiza
   └─ Não existe? → Cria nova
   ↓
4. Criar Memory (W5H)
   ↓
5. Criar Relations
   ├─ Memory → Entity (participants)
   └─ Memory → Memory (se relacionada)
   ↓
6. Verificar Consolidação
   └─ 5+ similares? → Marcar para DreamAgent
   ↓
7. Atualizar Índices
   ↓
8. Aplicar Decay (opcional)
   ↓
9. Persistir
   ↓
10. Response
```

### Recall (Recuperar)

```
1. Query chega (API ou MCP)
   ↓
2. Extrair Conceitos
   └─ "login do João" → ["login", "João"]
   ↓
3. Buscar por Embedding (Semântico)
   └─ Threshold adaptativo:
      ├─ Base: 0.55
      ├─ Gap analysis: melhor - 2º > 0.10?
      ├─ Uniformidade: std < 0.05 = ruído
      └─ Ajusta threshold dinamicamente
   ↓
4. Buscar Entidades (O(1))
   └─ entity_by_name["joão"] → [entity_id]
   ↓
5. Buscar Memórias por Entidade (O(1))
   └─ memories_by_entity[entity_id] → [memory_ids]
   ↓
6. Filtrar por Namespace
   └─ Excluir outros namespaces
   ↓
7. Filtrar por Retrievability
   └─ Excluir forgotten (R < 0.1)
   ↓
8. Filtrar Consolidadas
   └─ Excluir filhas (consolidated_into != null)
   ↓
9. Rankear por Relevância
   └─ Score = recency × importance × access_count
   ↓
10. Formatar Response (YAML)
    ↓
11. Touch (aumentar stability das acessadas)
```

---

## Camada Services

### MemoryService

Orquestrador principal:

```python
class MemoryService:
    def __init__(self, graph: MemoryGraph):
        self.graph = graph
        self.decay_manager = DecayManager()
        self.shared_manager = SharedMemoryManager()
    
    async def store(self, request: StoreRequest) -> StoreResponse:
        """Armazena memória com resolução de entidades."""
        ...
    
    async def recall(self, request: RecallRequest) -> RecallResponse:
        """Recupera memórias relevantes."""
        ...
    
    async def consolidate(self, namespace: str) -> ConsolidateResponse:
        """Dispara consolidação manual."""
        ...
```

---

## Camada Interfaces

### REST API (FastAPI)

```python
# Endpoints principais
POST /memory/recall      # Buscar memórias
POST /memory/remember    # Armazenar (W5H)
POST /memory/interact    # Recall + Store
GET  /memory/stats       # Estatísticas
POST /memory/forget/{id} # Esquecer
DELETE /memory/clear     # Limpar namespace
```

Ver detalhes em [API Reference](./api-reference.md).

### MCP Server (FastMCP)

```python
# Tools disponíveis
cortex_recall    # Buscar memórias
cortex_remember  # Armazenar (W5H)
cortex_stats     # Estatísticas
cortex_health    # Saúde
cortex_decay     # Aplicar decay
cortex_forget    # Esquecer memória
```

---

## Workers (Background)

### DreamAgent

Consolidação em background:

```python
class DreamAgent:
    """Consolida memórias como o sono consolida no cérebro."""
    
    def dream(self, namespace: str) -> DreamResult:
        # 1. Buscar memórias brutas
        raw = self.recall_raw(namespace)
        
        # 2. Agrupar por similaridade
        clusters = self.cluster(raw)
        
        # 3. Para cada cluster
        for cluster in clusters:
            # 3.1 Gerar resumo (LLM)
            summary = self.summarize(cluster)
            
            # 3.2 Criar memória consolidada
            consolidated = self.create_summary(summary)
            
            # 3.3 Marcar originais
            for m in cluster:
                m.consolidated_into = consolidated.id
        
        # 4. Persistir
        self.save()
        
        return result
```

Ver detalhes em [Consolidação](../concepts/consolidation.md).

---

## SDK

### Arquitetura Core + Adaptadores

```
┌─────────────────────────────────────────────────────────────┐
│                      SEU AGENTE LLM                         │
└─────────────────────────────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Core Genérico  │  │   LangChain     │  │    CrewAI       │
│  before/after   │  │   BaseMemory    │  │  LongTermMemory │
└────────┬────────┘  └────────┬────────┘  └────────┬────────┘
         │                    │                    │
         └────────────────────┴────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   Cortex API    │
                    │   /memory/*     │
                    └─────────────────┘
```

### CortexMemory (Core)

```python
class CortexMemory:
    """Core genérico com hooks before/after."""
    
    def before(self, user_message: str) -> str:
        """Busca memória relevante antes de processar."""
        return self.recall(user_message)
    
    def after(self, user_message: str, response: str) -> None:
        """Armazena memória após processar."""
        self.store_with_extraction(user_message, response)
```

Ver detalhes em [Integrações](../getting-started/integrations.md).

---

## Persistência

### JSON (Default)

```
~/.cortex/
├── {namespace}/
│   ├── entities.json
│   ├── episodes.json
│   ├── relations.json
│   └── indices.json
```

### SQLite (Em desenvolvimento)

```sql
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    type TEXT,
    name TEXT,
    ...
);

CREATE INDEX idx_entity_name ON entities(name);
```

### Neo4j (Futuro)

```cypher
// Entidades como nós
CREATE (e:Entity {id: $id, name: $name, type: $type})

// Memórias como nós
CREATE (m:Memory {id: $id, what: $what, ...})

// Relações como edges
CREATE (m)-[:INVOLVES]->(e)
```

---

## Próximos Passos

| Quer... | Vá para... |
|---------|------------|
| Entender o modelo de memória | [Modelo W5H](../concepts/memory-model.md) |
| Ver endpoints da API | [API Reference](./api-reference.md) |
| Entender consolidação | [Consolidação](../concepts/consolidation.md) |
| Usar em seu projeto | [Quick Start](../getting-started/quickstart.md) |

---

*Arquitetura — Última atualização: Janeiro 2026*

