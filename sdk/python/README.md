# Cortex Python SDK

SDK Python para comunicação com a API REST do Cortex.
Usa modelo W5H (Who, What, Why, When, Where, How).

## Instalação

```bash
# Copiar para seu projeto
cp cortex_sdk.py seu_projeto/

# Ou adicionar ao PYTHONPATH
export PYTHONPATH=/path/to/cortex/sdk/python:$PYTHONPATH
```

## Uso Básico

```python
from cortex_sdk import CortexClient

# Conectar ao Cortex com namespace
client = CortexClient(
    base_url="http://localhost:8000",
    namespace="meu_agente:usuario_123"
)

# Verificar conexão
if client.health_check():
    print("✅ Conectado!")

# ANTES de responder - Recall
memories = client.recall(
    query="problema com pagamento",
    who=["usuario_123"],  # Filtrar por participantes
    limit=5
)

print(f"Encontradas {memories['episodes_found']} memórias")
print(memories['prompt_context'])  # Injetar no prompt

# APÓS responder - Remember (W5H)
result = client.remember(
    who=["usuario_123", "sistema_pagamentos"],
    what="reportou erro de pagamento",
    why="cartão expirado",
    how="orientado a atualizar dados do cartão",
    importance=0.7
)

print(f"Memória {result['memory_id']} criada")
print(f"Retrievability: {result['retrievability']}")

# Para esquecer
client.forget(
    memory_id=result['memory_id'],
    reason="informação incorreta"
)

# Estatísticas
stats = client.stats()
print(f"Entidades: {stats['total_entities']}")
print(f"Memórias: {stats['total_episodes']}")
```

## API Reference

### CortexClient

```python
client = CortexClient(
    base_url="http://localhost:8000",
    namespace="default"
)
```

**Métodos W5H (Core):**

- `remember(who, what, why="", how="", where="default", importance=0.5) -> dict`
- `recall(query, who=None, where=None, min_importance=0.0, limit=10) -> dict`
- `forget(memory_id, reason="") -> dict`

**Métodos Admin:**

- `stats() -> dict` - Estatísticas do grafo
- `health() -> dict` - Métricas de saúde
- `clear() -> dict` ⚠️ Limpa namespace!
- `health_check() -> bool` - Verifica se API está online

## Modelo W5H

O Cortex usa o modelo W5H para memória semântica:

| Campo | Descrição | Obrigatório |
|-------|-----------|-------------|
| **WHO** | Quem participou (nomes, emails, sistemas) | ✅ |
| **WHAT** | O que aconteceu (ação/fato) | ✅ |
| **WHY** | Por quê aconteceu (causa/razão) | ❌ |
| **WHEN** | Quando (automático) | - |
| **WHERE** | Namespace/contexto | ❌ |
| **HOW** | Como foi resolvido (resultado) | ❌ |

## Workflow Típico

```python
# 1. ANTES de responder ao usuário
context = client.recall(user_message)

# 2. Usar context['prompt_context'] para informar resposta

# 3. APÓS responder
client.remember(
    who=[user_id, ...entities],
    what="ação realizada",
    why="causa/razão",
    how="resultado obtido"
)
```

## Namespaces

Use namespaces para isolar memórias:

```python
# Atendimento ao cliente
client = CortexClient(namespace=f"suporte:{user_email}")

# Multi-agente
client = CortexClient(namespace=f"agent:{agent_id}:user:{user_id}")

# Projetos diferentes
client = CortexClient(namespace=f"projeto:{project_name}")
```

## Documentação Completa

- [API Reference](../../docs/API.md)
- [W5H Design](../../docs/W5H_DESIGN.md)
- [Architecture](../../docs/ARCHITECTURE.md)
- [MCP Integration](../../docs/MCP.md)
