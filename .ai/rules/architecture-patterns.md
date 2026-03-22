---
applyTo: "**/*.py"
paths:
  - "src/cortex/**"
---

# Padrões Arquiteturais e Organização de Módulos

## Organização em Camadas

O Cortex segue arquitetura em camadas. **Novos módulos devem alinhar com camadas existentes.**

### Camadas e Responsabilidades

| Camada | Localização | Responsabilidade | Dependências Permitidas |
|--------|-------------|------------------|-------------------------|
| **Interfaces** | `src/cortex/api/`, `mcp/` | Exposição externa (REST, MCP) | Services |
| **Services** | `src/cortex/services/` | Orquestração de domínio | Core (todos os módulos) |
| **Core Domain** | `src/cortex/core/` | Lógica de negócio | Apenas outros módulos Core |
| **Storage** | `src/cortex/core/storage/` | Persistência | Primitives apenas |
| **Utils** | `src/cortex/utils/` | Utilidades transversais | Nenhuma (zero dependências) |

### Regra de Dependência

**Fluxo unidirecional**: Interfaces → Services → Core → Storage/Utils

**Nunca**: Core não pode depender de Services, Services não podem depender de API, etc.

## Módulos Core

### `primitives/` - Entidades de Domínio

Contém definições fundamentais (Entity, Memory, Relation, Namespace).

**Regras**:
- **Modelos Pydantic**: Usar Pydantic BaseModel para validação
- **Imutabilidade quando possível**: Preferir frozen=True para read-only models
- **Zero lógica de negócio**: Apenas estruturas de dados + validação

### `graph/` - Grafo de Memória

Armazena e busca memórias (O(1) insertion, busca otimizada).

**Regras**:
- **MemoryGraph como singleton**: Uma instância por namespace
- **Índice invertido obrigatório**: Manter índice de keywords para fallback
- **Thread-safe**: Usar locks para operações concorrentes

### `processing/` - Processamento de Entrada

Embedding, tokenização, semantic hashing, normalização.

**Regras**:
- **Stateless quando possível**: Funções puras preferidas
- **Cache embedding**: Cachear últimos N embeddings (1000 padrão)
- **Fallback**: Sempre ter fallback quando embedding falha (inverted index)

### `recall/` - Recuperação de Memória

Ranking, hierarchical recall, context packing.

**Regras**:
- **Composição de algoritmos**: RRF → Hierarchical → MMR → BFS (pipeline)
- **Configurável**: Todos os parâmetros (rrf_k, mmr_lambda, threshold) via config
- **Métricas**: Logar recall@k, latency, token_count

### `learning/` - Aprendizado Contínuo

Decay, attention, contradiction, consolidação.

**Regras**:
- **Background workers**: DecayManager e DreamAgent rodam em background (não bloqueiam)
- **Idempotência**: Consolidação pode rodar múltiplas vezes sem efeito colateral
- **Hub protection**: Hubs nunca decaem abaixo de threshold

### `storage/` - Persistência

Adapters (JSON, Neo4j), IdentityKernel.

**Regras**:
- **Adapter Pattern**: Toda operação storage via adapter (facilita troca)
- **Transaction safety**: Neo4j usa transações ACID, JSON usa file locks
- **Constraints**: Validar constraints de unicidade (entity_id, memory_id) na camada adapter

## Padrões de Design Utilizados

### 1. Adapter Pattern (Storage)

**Por quê**: Permite trocar backend (JSON ↔ Neo4j) sem alterar código de domínio.

**Como implementar**:

```python
class StorageAdapter(ABC):
    @abstractmethod
    def add_memory(self, memory: Memory) -> None: ...

    @abstractmethod
    def get_memory(self, memory_id: str) -> Optional[Memory]: ...

class Neo4jAdapter(StorageAdapter):
    def add_memory(self, memory: Memory) -> None:
        # Implementação específica Neo4j
        ...

class JSONAdapter(StorageAdapter):
    def add_memory(self, memory: Memory) -> None:
        # Implementação específica JSON
        ...
```

**Regra**: Novos backends devem implementar `StorageAdapter` completo.

### 2. Strategy Pattern (Recall e Ranking)

**Por quê**: Permite trocar algoritmos de ranking/recall dinamicamente.

**Exemplo**:

```python
class RankingStrategy(ABC):
    @abstractmethod
    def rank(self, memories: list[Memory], query: str) -> list[Memory]: ...

class RRFRanking(RankingStrategy):
    def rank(self, memories: list[Memory], query: str) -> list[Memory]:
        # Implementação RRF
        ...

class MMRRanking(RankingStrategy):
    def rank(self, memories: list[Memory], query: str) -> list[Memory]:
        # Implementação MMR
        ...
```

**Regra**: Novos algoritmos devem implementar interface comum.

### 3. Service Locator (Config e Singletons)

**Por quê**: Centraliza acesso a configuração e serviços compartilhados.

**Uso**:

```python
from cortex.config import get_config
from cortex.core.processing.embedding import get_embedding_service

config = get_config()
embedding_service = get_embedding_service()
```

**Regra**: Não instanciar `Config()` ou `EmbeddingService()` diretamente — usar getters.

### 4. Dependency Injection (Services)

**Por quê**: Facilita testes (mock de dependências).

**Exemplo**:

```python
class MemoryService:
    def __init__(
        self,
        storage: StorageAdapter,
        embedding: EmbeddingService,
        decay_manager: DecayManager
    ):
        self.storage = storage
        self.embedding = embedding
        self.decay_manager = decay_manager
```

**Regra**: Injetar dependências via `__init__`, não criar dentro do construtor.

## Criação de Novos Módulos

### Quando criar novo módulo em `src/cortex/core/`?

**Sim** — criar novo módulo quando:
- Responsabilidade distinta das existentes (ex: `validation/` para validações complexas)
- >3 arquivos relacionados agrupados logicamente
- Alinha com camadas arquiteturais (primitives, processing, recall, learning, storage)

**Não** — expandir módulo existente quando:
- Responsabilidade já coberta (ex: novo algoritmo de ranking → `recall/ranking.py`)
- <3 arquivos (não justifica módulo separado)
- Lógica auxiliar de módulo existente

### Template para Novo Módulo

```
src/cortex/core/<novo_modulo>/
├── __init__.py          # Exports públicos
├── <nome_principal>.py  # Classe/função principal
├── types.py             # Tipos compartilhados (opcional)
└── utils.py             # Helpers internos (opcional)
```

## Convenções de Serviço (Services Layer)

**Regras para `MemoryService` e futuros services**:

1. **Orquestração apenas**: Services coordenam Core modules, não implementam lógica de domínio
2. **Transações**: Services gerenciam transações (commit/rollback)
3. **Error handling**: Services traduzem exceções técnicas para erros de domínio
4. **Logging**: Services logam operações críticas (store, recall, delete)

### ✅ Bom (Service)
```python
class MemoryService:
    def remember(self, input_text: str, namespace: str) -> Memory:
        """Store new memory from natural language input."""
        # Orquestração
        parsed = self.parser.parse_w5h(input_text)
        entities = self.entity_extractor.extract(parsed)
        memory = Memory.from_w5h(parsed)

        # Security check
        self.identity_kernel.validate(memory)

        # Storage
        self.storage.add_memory(memory)
        self.storage.commit()

        # Background processing
        self.decay_manager.schedule_decay_update(memory)

        return memory
```

### ❌ Ruim (Service com lógica de domínio)
```python
class MemoryService:
    def remember(self, input_text: str) -> Memory:
        # Service não deve implementar parsing (responsabilidade de processing/)
        who = input_text.split("who:")[1].split(",")
        what = input_text.split("what:")[1]
        # ...
```

## Testes por Camada

| Camada | Tipo de Teste | Cobertura Alvo |
|--------|---------------|----------------|
| Primitives | Unit | >95% |
| Processing | Unit + Integration | >90% |
| Recall | Unit + Integration | >90% |
| Learning | Unit + Integration | >85% |
| Storage | Integration | >90% |
| Services | Integration + E2E | >85% |
| API | E2E | >80% |

**Regra**: Camadas core (primitives, graph) exigem cobertura >90%.

## Logs e Observabilidade

**Níveis de log por camada**:

- **ERROR**: Storage failures, security violations, crashes
- **WARNING**: Threshold violations, performance degradation, fallbacks
- **INFO**: Operações críticas (store, recall, delete, consolidation)
- **DEBUG**: Detalhes de algoritmos (scores, rankings, traversals)

**Formato estruturado** (JSON):

```python
logger.info(
    "Memory stored",
    extra={
        "memory_id": memory.id,
        "namespace": memory.where,
        "importance": memory.importance,
        "duration_ms": duration
    }
)
```

## Referências de Código

- **Adapter Pattern**: `src/cortex/core/storage/adapters.py`
- **Service Layer**: `src/cortex/services/memory_service.py`
- **Config Singleton**: `src/cortex/config.py`
