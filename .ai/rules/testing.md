---
applyTo: "**/*.py"
paths:
  - "tests/**"
  - "src/**"
---

# Testes e Qualidade de Código

## Cobertura de Testes

**Meta**: >90% cobertura para novas features

**Cobertura mínima por módulo**:

| Módulo | Cobertura Alvo | Justificativa |
|--------|----------------|---------------|
| `core/primitives/` | >95% | Entidades fundamentais, validação crítica |
| `core/graph/` | >90% | Operações de grafo, busca, indexação |
| `core/recall/` | >90% | Algoritmos de ranking, token optimization |
| `core/learning/` | >85% | Background workers, menos crítico para testes síncronos |
| `core/storage/` | >90% | Persistência, integridade de dados |
| `services/` | >85% | Orquestração, cobertura via integration tests |
| `api/` | >80% | E2E tests cobrem fluxos principais |

## Estrutura de Testes

### Organização de Arquivos

```
tests/
├── core/
│   ├── test_memory_graph.py      # Testa MemoryGraph
│   ├── test_decay.py              # Testa DecayManager
│   ├── test_ranking.py            # Testa algoritmos de ranking
│   └── ...
├── integration/
│   ├── test_storage_adapters.py  # Testa JSON e Neo4j adapters
│   ├── test_recall_pipeline.py   # Testa pipeline completo de recall
│   └── ...
├── e2e/
│   ├── test_api_endpoints.py     # Testa API REST
│   └── ...
└── conftest.py                    # Fixtures compartilhadas
```

**Nomenclatura**:
- Arquivo: `test_<modulo>.py`
- Classe de teste: `Test<NomeDaClasse>` ou `Test<Funcionalidade>`
- Função de teste: `test_<comportamento_esperado>`

## Tipos de Testes

### 1. Unit Tests

**Quando usar**: Testar funções/classes isoladas sem dependências externas

**Características**:
- Rápidos (<10ms por teste)
- Mockam dependências externas (storage, embedding, LLM)
- Alta cobertura de branches

**Exemplo**:

```python
def test_ebbinghaus_decay_calculation():
    """Test retrievability calculation using Ebbinghaus curve."""
    memory = Memory(
        who=["test"],
        what="test event",
        when=datetime.now() - timedelta(days=7),
        where="test_namespace",
        stability=7.0
    )

    decay_manager = DecayManager(base_stability=7.0)
    retrievability = decay_manager.calculate_retrievability(memory)

    # R(7 days) = e^(-7/7) = e^(-1) ≈ 0.368
    assert 0.35 < retrievability < 0.40
```

### 2. Integration Tests

**Quando usar**: Testar interação entre múltiplos módulos ou com recursos externos (banco de dados)

**Características**:
- Mais lentos (100ms-1s por teste)
- Usam recursos reais quando possível (Neo4j test container)
- Validam contratos entre componentes

**Markers**:
- `@pytest.mark.integration` — testes de integração
- `@pytest.mark.slow` — testes lentos (>1s)
- `@pytest.mark.neo4j` — requerem Neo4j rodando

**Exemplo**:

```python
@pytest.mark.integration
@pytest.mark.neo4j
def test_neo4j_adapter_crud(neo4j_adapter):
    """Test complete CRUD cycle with Neo4j."""
    # Create
    entity = Entity(type="person", name="Test User")
    neo4j_adapter.add_entity(entity)

    # Read
    retrieved = neo4j_adapter.get_entity(entity.id)
    assert retrieved == entity

    # Update
    entity.name = "Updated Name"
    neo4j_adapter.update_entity(entity)
    assert neo4j_adapter.get_entity(entity.id).name == "Updated Name"

    # Delete
    neo4j_adapter.delete_entity(entity.id)
    assert neo4j_adapter.get_entity(entity.id) is None
```

### 3. E2E (End-to-End) Tests

**Quando usar**: Testar fluxos completos de usuário via API

**Características**:
- Mais lentos (1s-5s por teste)
- Usam ambiente completo (API + Storage + Workers)
- Validam comportamento do sistema como um todo

**Exemplo**:

```python
@pytest.mark.e2e
def test_recall_pipeline_complete(test_client):
    """Test complete recall pipeline from API request to response."""
    # Store memories
    response = test_client.post("/api/v1/remember", json={
        "text": "João debugou timeout porque conexão não fechava",
        "namespace": "test_tenant/project"
    })
    assert response.status_code == 200

    # Recall
    response = test_client.post("/api/v1/recall", json={
        "query": "problemas de timeout",
        "namespace": "test_tenant/project"
    })
    assert response.status_code == 200
    memories = response.json()["memories"]
    assert len(memories) > 0
    assert "timeout" in memories[0]["what"].lower()
```

## Fixtures e Mocks

### Fixtures Compartilhadas (`conftest.py`)

```python
import pytest
from cortex.core.graph import MemoryGraph
from cortex.core.storage import JSONAdapter, Neo4jAdapter

@pytest.fixture
def memory_graph():
    """Fixture for MemoryGraph with in-memory storage."""
    adapter = JSONAdapter(data_dir=":memory:")
    graph = MemoryGraph(adapter)
    yield graph
    graph.clear()

@pytest.fixture
def sample_memory():
    """Fixture for sample Memory object."""
    return Memory(
        who=["Test User"],
        what="tested the system",
        why="validation",
        when=datetime.now(),
        where="test_namespace",
        how="successfully"
    )

@pytest.fixture(scope="session")
def neo4j_adapter():
    """Fixture for Neo4j adapter (requires Neo4j running)."""
    adapter = Neo4jAdapter(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="test_password"
    )
    yield adapter
    # Cleanup
    adapter.clear_test_data()
```

### Mocking Dependências Externas

**Mockar**: Embedding service, LLM calls, external APIs

**Não mockar**: Storage em integration tests, lógica de domínio

**Exemplo**:

```python
from unittest.mock import Mock, patch

def test_recall_with_mocked_embedding():
    """Test recall with mocked embedding service."""
    mock_embedding = Mock()
    mock_embedding.get_embedding.return_value = [0.1] * 1024

    with patch("cortex.services.memory_service.get_embedding_service", return_value=mock_embedding):
        service = MemoryService(...)
        result = service.recall("test query")

    assert mock_embedding.get_embedding.called
```

## Markers Pytest

Usar markers para categorizar e filtrar testes:

```python
# pytest.ini (já configurado)
[pytest]
markers =
    slow: marks tests as slow (>1s)
    integration: marks tests as integration tests
    e2e: marks tests as end-to-end tests
    neo4j: marks tests requiring Neo4j
```

**Executar subsets**:

```bash
pytest tests/                    # Todos os testes
pytest -m "not slow"            # Excluir testes lentos
pytest -m "integration"         # Apenas integration tests
pytest tests/core/              # Apenas tests de core/
```

## Testes Async

**Quando usar**: Testar funções `async def`

**Configuração**: `pytest-asyncio` (já instalado)

**Exemplo**:

```python
import pytest

@pytest.mark.asyncio
async def test_async_recall():
    """Test async recall method."""
    service = MemoryService(...)
    result = await service.recall_async("test query")
    assert result is not None
```

## Boas Práticas

### 1. Arrange-Act-Assert (AAA)

Estruturar testes em 3 seções claras:

```python
def test_memory_importance_calculation():
    # Arrange
    memory = Memory(who=["test"], what="test", when=datetime.now(), where="test")
    memory.access_count = 10

    # Act
    importance = calculate_importance(memory)

    # Assert
    assert importance > 0.5
```

### 2. Um Assert por Conceito

Preferir múltiplos asserts relacionados ao mesmo conceito:

```python
def test_recall_result_structure():
    result = service.recall("query")

    # All asserts validate RecallResult structure
    assert isinstance(result, RecallResult)
    assert isinstance(result.memories, list)
    assert all(isinstance(m, Memory) for m in result.memories)
```

### 3. Nomes Descritivos

```python
# ✅ Bom - descreve comportamento
def test_retrievability_drops_below_threshold_after_7_days():
    ...

# ❌ Ruim - genérico
def test_decay():
    ...
```

### 4. Testes Determinísticos

**Evitar**: `random`, `datetime.now()` sem seed/mock
**Usar**: Valores fixos, mocks controlados

```python
# ✅ Bom
def test_with_fixed_timestamp():
    fixed_time = datetime(2024, 3, 22, 12, 0, 0)
    memory = Memory(..., when=fixed_time)
    ...

# ❌ Ruim - pode falhar aleatoriamente
def test_with_current_time():
    memory = Memory(..., when=datetime.now())
    # Assume specific time...
```

### 5. Cleanup em Fixtures

Usar `yield` para cleanup automático:

```python
@pytest.fixture
def temp_storage():
    storage = JSONAdapter(data_dir="./test_data")
    yield storage
    # Cleanup após teste
    storage.clear()
    os.rmdir("./test_data")
```

## Execução de Testes (Pipeline)

**Antes de commit** (ordem obrigatória):

```bash
# 1. Linting
ruff check .

# 2. Type checking
mypy src/cortex/

# 3. Tests rápidos
pytest -m "not slow"

# 4. Tests completos (CI)
pytest tests/ --cov=src/cortex --cov-report=term-missing
```

## Troubleshooting

| Problema | Causa | Solução |
|----------|-------|---------|
| Teste falhando aleatoriamente | Não-determinístico (datetime, random) | Mockar datetime.now(), fixar seeds |
| Teste muito lento | I/O real, sem mock | Mockar operações externas (embedding, LLM) |
| Baixa cobertura | Branches não testados | Adicionar casos edge (empty, null, error) |
| Fixture não funciona | Escopo errado | Verificar scope (function/session/module) |

## Referências

- **Conftest**: `tests/conftest.py` — fixtures compartilhadas
- **Integration tests**: `tests/integration/` — exemplos de integration tests
- **Pytest docs**: https://docs.pytest.org
