---
applyTo: "**/*.{py,pyi}"
paths:
  - "src/**"
  - "tests/**"
---

# Code Style e Convenções Python

## Formatação e Linting

- **PEP8 obrigatório**: Seguir todas as convenções PEP8 sem exceção
- **Ruff como linter**: Executar `ruff check .` antes de commit — deve passar sem erros
- **Line length**: Máximo 100 caracteres (configurado em `pyproject.toml`)
  - Preferir quebra de linha legível sobre linha única comprimida

## Type Hints

- **Obrigatório em todas as funções**: Incluir type hints para parâmetros e retorno
  - Exceção: métodos `__init__` podem omitir `-> None` se óbvio
- **Validação mypy**: Executar `mypy src/cortex/` antes de commit — deve passar sem erros
- **Usar tipos específicos**: Preferir `list[str]` sobre `List`, `dict[str, Any]` over `Dict`
  - Python 3.10+ permite tipos built-in sem `from typing import`

### ✅ Bom
```python
def calculate_retrievability(memory: Memory, current_time: datetime) -> float:
    """Calculate memory retrievability using Ebbinghaus curve."""
    ...
```

### ❌ Ruim
```python
def calculate_retrievability(memory, current_time):  # Sem type hints
    ...
```

## Naming Conventions

- **Classes**: PascalCase — `MemoryGraph`, `DecayManager`, `Neo4jAdapter`
- **Funções e variáveis**: snake_case — `calculate_retrievability`, `memory_graph`
- **Constantes**: UPPER_SNAKE_CASE — `FORGOTTEN_THRESHOLD`, `BASE_STABILITY`
- **Privados**: Prefixo `_` — `_internal_method()`, `_cache`

### Padrões de Sufixo

| Sufixo | Quando Usar | Exemplo |
|--------|-------------|---------|
| `Adapter` | Implementações de storage adapter | `Neo4jAdapter`, `JSONAdapter` |
| `Service` | Camada de orquestração | `MemoryService` |
| `Manager` | Gerenciadores de estado | `DecayManager`, `ConsolidationManager` |
| `Result` | Tipos de retorno estruturados | `RecallResult`, `SearchResult` |

## Imports

- **Ordem**: stdlib → third-party → local (separados por linha em branco)
- **Alfabético**: Dentro de cada grupo, ordenar alfabeticamente
- **Absolutos sobre relativos**: Usar `from cortex.core.graph import MemoryGraph` ao invés de imports relativos

### ✅ Bom
```python
import asyncio
from datetime import datetime
from typing import Optional

import numpy as np
from pydantic import BaseModel

from cortex.core.primitives import Memory
from cortex.core.graph import MemoryGraph
```

### ❌ Ruim
```python
from cortex.core.graph import MemoryGraph
import asyncio
from datetime import datetime
import numpy as np  # Misturado com stdlib
```

## Docstrings

- **Google-style docstrings**: Usar formato Google (não NumPy ou reStructuredText)
- **Obrigatório para**: Classes públicas, funções públicas, módulos
- **Opcional para**: Métodos privados (prefixo `_`), funções internas simples

### Template

```python
def hybrid_ranking(
    memories: list[Memory],
    query: str,
    rrf_k: int = 60,
    mmr_lambda: float = 0.7
) -> list[Memory]:
    """
    Rank memories using hybrid approach (RRF + MMR).

    Combines Reciprocal Rank Fusion for multi-signal fusion with
    Maximal Marginal Relevance for diversity.

    Args:
        memories: Candidate memories to rank
        query: Search query string
        rrf_k: RRF smoothing constant (default 60)
        mmr_lambda: MMR relevance/diversity balance (default 0.7)

    Returns:
        Ranked list of memories (most relevant first)

    Raises:
        ValueError: If mmr_lambda not in [0, 1]
    """
    ...
```

## Estrutura de Código

- **Funções pequenas**: Máximo ~50 linhas — quebrar funções maiores em helpers privados
- **Single Responsibility**: Cada função deve ter uma responsabilidade clara
- **Early returns**: Preferir early returns para condições de erro

### ✅ Bom
```python
def get_entity(entity_id: str) -> Optional[Entity]:
    """Retrieve entity by ID."""
    if not entity_id:
        return None

    entity = self._cache.get(entity_id)
    if entity:
        return entity

    return self._load_from_storage(entity_id)
```

### ❌ Ruim
```python
def get_entity(entity_id: str) -> Optional[Entity]:
    """Retrieve entity by ID."""
    entity = None
    if entity_id:
        entity = self._cache.get(entity_id)
        if not entity:
            entity = self._load_from_storage(entity_id)
    return entity  # Nested ifs, late return
```

## Constantes e Enums

- **Constantes em UPPER_SNAKE_CASE**: No topo do módulo ou em `config.py`
- **Enums para valores fixos**: Usar `enum.Enum` para conjuntos fechados de valores

### ✅ Bom
```python
from enum import Enum

class MemoryMode(str, Enum):
    SINGLE_USER = "single_user"
    TEAM = "team"
    MULTI_CLIENT = "multi_client"

FORGOTTEN_THRESHOLD = 0.1
BASE_STABILITY = 7.0
```

### ❌ Ruim
```python
# String literals espalhados no código
if mode == "single_user":  # Usar enum
    ...

forgotten_threshold = 0.1  # Não é constante (minúsculo)
```

## Comentários

- **Comentar "por quê", não "o quê"**: Código deve ser auto-explicativo para "o quê"
- **Evitar comentários óbvios**: Se o código é claro, não comentar
- **Atualizar comentários**: Ao modificar código, atualizar comentários relacionados

### ✅ Bom
```python
# Hub protection: critical memories (hubs) get 2x stability bonus
# to prevent premature forgetting via Ebbinghaus decay
if is_hub(memory):
    memory.stability *= 2.0
```

### ❌ Ruim
```python
# Multiply stability by 2
memory.stability *= 2.0  # Óbvio
```

## Async/Await

- **Async quando I/O-bound**: Usar `async def` para operações de rede, banco de dados, arquivo
- **Sync quando CPU-bound**: Manter sync para cálculos, processamento em memória
- **Não misturar desnecessariamente**: Não transformar função sync em async sem necessidade

## Error Handling

- **Usar exceções específicas**: Não usar `Exception` genérico
- **Documentar raises**: Incluir `Raises:` em docstring para exceções esperadas
- **Fail fast**: Validar inputs no início da função

### ✅ Bom
```python
class NamespaceViolationError(PermissionError):
    """Raised when attempting to access namespace from different tenant."""
    pass

def validate_namespace(user_tenant: str, namespace: str) -> None:
    """
    Validate namespace belongs to user's tenant.

    Raises:
        NamespaceViolationError: If namespace not owned by tenant
    """
    if not namespace.startswith(f"{user_tenant}/"):
        raise NamespaceViolationError(
            f"Cannot access namespace '{namespace}' from tenant '{user_tenant}'"
        )
```

## Ferramentas de Validação

**Pipeline antes de commit** (ordem obrigatória):

```bash
ruff check .        # Linting
mypy src/cortex/    # Type checking
pytest tests/       # Testes (>90% cobertura esperada)
```

Todos devem passar sem erros antes de criar commit.
