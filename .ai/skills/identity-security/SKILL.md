---
name: identity-security
description: Guide for IdentityKernel (Memory Firewall), jailbreak detection, namespace isolation,
  security patterns, and threat mitigation. Use when implementing security checks,
  detecting malicious input, configuring isolation by tenant, or understanding the 3 modes
  (Pattern/Semantic/Hybrid) of jailbreak detection. Mention when working with identity.py,
  namespace security, or handling suspicious memories.
---

# Identity Kernel & Segurança (Memory Firewall)

Sistema de segurança que protege o grafo de memórias contra jailbreak, injection attacks, e violação de isolamento entre tenants.

## Quando Usar

- Configurar IdentityKernel (Memory Firewall)
- Detectar jailbreak em memórias sendo criadas
- Debugar memórias bloqueadas por segurança
- Implementar isolamento de namespaces por tenant
- Entender os 3 modos (Pattern, Semantic, Hybrid)

## IdentityKernel - 3 Modos

| Modo | Latência | Detecção | Falsos + | Uso |
|------|----------|----------|----------|-----|
| **Pattern** | <0.01ms | 90% | 0% | **Produção (padrão)** |
| **Semantic** | ~50ms | 95% | <1% | Alta segurança + LLM |
| **Hybrid** | ~50ms | 97% | <0.5% | Máxima segurança (combina ambos) |

**PADRÃO CORTEX**: Pattern mode (90% detecção, 0% falsos positivos, <0.01ms).

## Configuração

```bash
# .env
CORTEX_IDENTITY_ENABLED=true
CORTEX_IDENTITY_MODE=pattern  # ou "semantic", "hybrid"
CORTEX_IDENTITY_LOG_PATH=./logs/security.log
```

## Comportamento ao Detectar Jailbreak

**Pipeline**: Input → IdentityKernel.check() → Se detectado:
1. **Log**: Registra tentativa (timestamp, namespace, conteúdo)
2. **Notifica**: Alerta admin (se configurado)
3. **Bloqueia**: Retorna 403, memória **NÃO é salva**

**Não salva, não sanitiza** — rejeita completamente.

## Pattern Mode - Categorias de Ataques

| Categoria | Exemplos | Detecta |
|-----------|----------|---------|
| **Prompt Injection** | "Ignore previous", "New instruction" | `ignore (previous\|above\|all)` |
| **Jailbreak** | "DAN mode", "Act as if" | `(DAN\|jailbreak\|act as)` |
| **System Override** | "System:", "<\|system\|>" | `(system:\|<\|system\|>)` |
| **Memory Poisoning** | Texto excessivo/repetitivo | Length >10k, repetition >70% |
| **Code Injection** | SQL, shell commands | `(DROP TABLE\|rm -rf\|exec\()` |

**Ver lista completa**: [JAILBREAK-PATTERNS.md](references/JAILBREAK-PATTERNS.md)

## Isolamento de Namespaces

**REGRA FUNDAMENTAL**: Tenant NÃO pode acessar memória de outro tenant (segurança obrigatória).

**Estrutura**: `tenant_id/contexto/sub_contexto`

Exemplos:
- `empresa_x/projeto_a/backend`
- `empresa_y/suporte/tickets`

**Validação**: Todo acesso valida que namespace inicia com `tenant_id/`.

**Flexibilidade interna**: Dentro do tenant, livre organização de sub-namespaces.

## Collective Memory (Memória Coletiva)

Memória compartilhada **dentro** de um tenant (não entre tenants).

**Modos**:
- `single_user`: Namespace único (uso pessoal)
- `team`: Compartilhado por time (2-10 pessoas)
- `multi_client`: **Produção** (isolamento por tenant + sub-namespaces)

## Troubleshooting

| Problema | Solução |
|----------|---------|
| Memórias legítimas bloqueadas | Mudar para Semantic ou Hybrid mode |
| Jailbreak passou | Adicionar padrão em `patterns.py` ou ativar Semantic |
| Alta latência | Mudar para Hybrid (Pattern primeiro, Semantic só se passar) |
| Namespace violation | Habilitar validação em `config.py` |

## Boas Práticas

1. **Sempre habilitar em produção** (`CORTEX_IDENTITY_ENABLED=true`)
2. **Usar Pattern mode por padrão** (90% detecção sem latência)
3. **Habilitar logging** para auditoria
4. **Revisar logs semanalmente** para novos padrões
5. **Nunca compartilhar namespaces entre tenants**
6. **Validar tenant em toda API request**

## Referências

- [JAILBREAK-PATTERNS.md](references/JAILBREAK-PATTERNS.md) — Lista completa de padrões detectados
- [NAMESPACE-ISOLATION.md](references/NAMESPACE-ISOLATION.md) — Implementação de isolamento
- [SECURITY-AUDIT.md](references/SECURITY-AUDIT.md) — Checklist de auditoria de segurança
