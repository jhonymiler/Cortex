# Guia de Entidades (Entity)

## Estrutura

```python
Entity(
    id: str,                    # UUID gerado automaticamente
    type: str,                  # "person", "file", "system", "product", "character"
    name: str,                  # Nome legível
    identifiers: list[str],     # Aliases: email, path, apelido, username
    attributes: dict,           # Metadados livres
    namespace: str              # Isolamento por tenant
)
```

## Tipos de Entidade

| Tipo | Quando Usar | Exemplos de `identifiers` |
|------|-------------|---------------------------|
| `person` | Humanos, usuários | `["maria@email.com", "Maria Silva", "maria.silva"]` |
| `file` | Arquivos, documentos | `["/path/to/file.py", "file.py", "hash:abc123"]` |
| `system` | Sistemas, serviços | `["api_pagamento", "pagamento.service", "https://api.pay.com"]` |
| `product` | Produtos, features | `["produto_premium", "SKU-1234"]` |
| `character` | Personagens (roleplay) | `["Elena Stormborn", "Elena", "The Thief"]` |

## Criação e Resolução

### Criar Nova Entidade

```python
entity = Entity(
    type="person",
    name="João Silva",
    identifiers=["joao@empresa.com", "João", "joão.silva"],
    attributes={"cargo": "desenvolvedor", "time": "backend"},
    namespace="tenant_x/projeto_y"
)
```

### Resolver Entidade Existente

Buscar por qualquer `identifier`:

```python
# Busca retorna mesma Entity para qualquer identifier
get_entity("joao@empresa.com")  # → Entity(name="João Silva")
get_entity("João")              # → Entity(name="João Silva")
get_entity("joão.silva")        # → Entity(name="João Silva")
```

## Boas Práticas

1. **Normalizar identifiers**: Lowercase, remover acentos quando possível
2. **Adicionar múltiplos aliases**: Email, username, nome completo, apelido
3. **Usar `attributes` para metadados**: Cargo, departamento, tags relevantes
4. **Verificar existência antes de criar**: Evitar duplicação

## Referência de Código

- **Modelo**: `src/cortex/core/primitives/entity.py`
- **CRUD**: `src/cortex/core/graph/memory_graph.py::add_entity()`, `get_entity()`
