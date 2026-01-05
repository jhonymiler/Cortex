# Cortex Python SDK

SDK Python para comunicação com a API REST do Cortex.

## Instalação

```bash
# Copiar para seu projeto
cp cortex_sdk.py seu_projeto/

# Ou adicionar ao PYTHONPATH
export PYTHONPATH=/path/to/cortex/sdk/python:$PYTHONPATH
```

## Uso Básico

```python
from cortex_sdk import CortexClient, make_participant

# Conectar ao Cortex
client = CortexClient("http://localhost:8000")

# Verificar conexão
if client.health_check():
    print("✅ Conectado!")

# Recall - Buscar memórias
memories = client.recall(
    query="Como fazer autenticação?",
    context={"source": "my_app"}
)

# Store - Armazenar episódio
result = client.store(
    action="implemented_auth",
    outcome="JWT authentication working",
    participants=[
        make_participant("user", "developer", ["dev@email.com"])
    ],
    context="new feature development"
)

# Stats - Estatísticas
stats = client.stats()
print(f"Entidades: {stats['total_entities']}")
```

## API Reference

### CortexClient

```python
client = CortexClient(base_url="http://localhost:8000")
```

**Métodos:**

- `recall(query: str, context: dict = None) -> dict`
- `store(action: str, outcome: str, participants: list = None, context: str = "", relations: list = None) -> dict`
- `stats() -> dict`
- `clear() -> dict` ⚠️ Perigoso!
- `health_check() -> bool`

### Helpers

```python
# Criar participante (entidade)
make_participant(
    type="user",
    name="João",
    identifiers=["joao@email.com"]
)

# Criar relação
make_relation(
    from_name="bug_123",
    relation_type="caused_by",
    to_name="null_pointer"
)
```

## Exemplos

Ver `../../teste-llm/agent.py` para exemplo completo de uso com Ollama.

## Documentação Completa

- [API Reference](../../docs/API.md)
- [Architecture](../../docs/ARCHITECTURE.md)
- [Vision](../../docs/VISION.md)
