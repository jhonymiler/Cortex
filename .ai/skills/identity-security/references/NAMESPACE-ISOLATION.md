# Isolamento de Namespaces

Implementação de isolamento multi-tenant com segurança obrigatória.

## Regra Fundamental

**Tenant NÃO pode acessar memória de outro tenant** — isolamento obrigatório para segurança.

## Estrutura de Namespace

```
namespace: "tenant_id/contexto/sub_contexto"

Formato:
  [TENANT_ID obrigatório] / [contexto opcional] / [sub_contexto opcional]

Exemplos válidos:
  "empresa_x"                          # Tenant raiz
  "empresa_x/projeto_a"                # Contexto
  "empresa_x/projeto_a/backend"        # Sub-contexto
  "empresa_x/global"                   # Memória compartilhada do tenant
  "user_123/personal"                  # Usuário individual
```

## Validação de Acesso

### Código de Validação

```python
def validate_namespace_access(user_tenant: str, requested_namespace: str) -> None:
    """
    Valida que namespace pertence ao tenant do usuário.

    Raises:
        NamespaceViolationError: Se namespace não pertence ao tenant
    """
    if not requested_namespace.startswith(user_tenant + "/"):
        raise NamespaceViolationError(
            f"Cannot access namespace '{requested_namespace}' "
            f"from tenant '{user_tenant}'"
        )
```

### Exemplos

#### ✅ Acessos Permitidos

```python
user_tenant = "empresa_x"

# OK - acesso à raiz do tenant
validate("empresa_x", "empresa_x")

# OK - acesso a contextos do tenant
validate("empresa_x", "empresa_x/projeto_a")
validate("empresa_x", "empresa_x/projeto_a/backend")
validate("empresa_x", "empresa_x/global")
```

#### ❌ Acessos Bloqueados

```python
user_tenant = "empresa_x"

# ERRO - acesso a outro tenant
validate("empresa_x", "empresa_y")
# → NamespaceViolationError

# ERRO - acesso a sub-contexto de outro tenant
validate("empresa_x", "empresa_y/projeto_a")
# → NamespaceViolationError

# ERRO - tentativa de bypass
validate("empresa_x", "../empresa_y")
# → NamespaceViolationError (path traversal)
```

## Flexibilidade Interna

**Dentro do tenant**: Livre organização de sub-namespaces.

### Hierarquia Típica

```
empresa_x/                        # Raiz do tenant
├── global/                       # Memória compartilhada (todos do tenant)
├── projeto_a/
│   ├── backend/                  # Contexto específico
│   ├── frontend/
│   └── docs/
├── projeto_b/
│   └── api/
└── suporte/
    ├── tickets/
    └── knowledge_base/
```

**Regras de visibilidade** (configurável por tenant):
- `global/`: Visível para todos do tenant
- `projeto_a/`: Visível apenas para time do projeto A
- `projeto_a/backend/`: Visível apenas para devs backend

## Collective Memory (Memória Coletiva)

Memória compartilhada **dentro** de um tenant.

### Configuração

```bash
# .env
CORTEX_MEMORY_MODE=multi_client  # ou "team", "single_user"
```

### Modos de Operação

#### 1. `single_user`

**Uso**: Desenvolvimento individual, uso pessoal.

```python
namespace = f"{user_id}/personal"
# Ex: "user_123/personal"
```

- Sem compartilhamento
- Isolamento completo por usuário
- Mais simples, menos overhead

#### 2. `team`

**Uso**: Times pequenos (2-10 pessoas).

```python
namespace = f"{team_id}/shared"
# Ex: "team_backend/shared"
```

- Compartilhamento dentro do time
- Isolamento entre times
- Médio overhead

#### 3. `multi_client` (Produção)

**Uso**: SaaS, múltiplos tenants/clientes.

```python
namespace = f"{tenant_id}/{context}/{sub_context}"
# Ex: "empresa_x/projeto_a/backend"
```

- Isolamento obrigatório por tenant
- Hierarquia flexível dentro do tenant
- Máximo controle e segurança

## API Request - Validação

### Middleware de Validação

```python
@app.middleware("http")
async def validate_tenant_middleware(request: Request, call_next):
    """Valida tenant em todas as requests."""
    # Extrair tenant do token JWT ou header
    user_tenant = extract_tenant_from_auth(request)

    # Extrair namespace do body/query
    requested_namespace = extract_namespace_from_request(request)

    # Validar acesso
    try:
        validate_namespace_access(user_tenant, requested_namespace)
    except NamespaceViolationError as e:
        return JSONResponse(
            status_code=403,
            content={"error": "Namespace access denied", "detail": str(e)}
        )

    # Adicionar tenant ao contexto da request
    request.state.tenant = user_tenant

    return await call_next(request)
```

### Headers da Request

```http
POST /api/v1/remember HTTP/1.1
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "text": "...",
  "namespace": "empresa_x/projeto_a"
}
```

**Validação**:
1. Extrai `tenant_id` do JWT → `"empresa_x"`
2. Extrai `namespace` do body → `"empresa_x/projeto_a"`
3. Valida que namespace inicia com `tenant_id/` → ✅ OK
4. Processa request

## Logging de Violações

```json
{
  "timestamp": "2026-03-22T14:30:00Z",
  "event_type": "namespace_violation",
  "user_tenant": "empresa_x",
  "requested_namespace": "empresa_y/projeto_b",
  "user_id": "user_123",
  "ip": "192.168.1.10",
  "action": "denied"
}
```

**Alertas**: Violations > 10 em 1 hora → notificar admin (possível ataque).

## Migração de Namespaces

Se necessário mover memórias entre contextos (dentro do mesmo tenant):

```python
# Exemplo: projeto_a → projeto_b
old_namespace = "empresa_x/projeto_a"
new_namespace = "empresa_x/projeto_b"

# REGRA: Só permitir se mesmo tenant
if not (old_namespace.split("/")[0] == new_namespace.split("/")[0]):
    raise NamespaceViolationError("Cannot migrate across tenants")

# Atualizar no banco
adapter.update_memories_namespace(old_namespace, new_namespace)
```

## Referência de Código

- **Validação**: `src/cortex/services/memory_service.py::validate_namespace_access()`
- **Middleware**: `src/cortex/api/middleware.py::validate_tenant_middleware()`
- **Exceptions**: `src/cortex/core/primitives/namespace.py::NamespaceViolationError`
