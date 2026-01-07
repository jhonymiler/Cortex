# Arquitetura do Cortex

> **Nota**: Este documento foi simplificado.  
> Para documentação completa, veja [architecture/overview.md](./architecture/overview.md).

---

## Redirecionamento

| Conteúdo | Novo Local |
|----------|------------|
| Diagrama de camadas | [architecture/overview.md](./architecture/overview.md) |
| Componentes Core | [architecture/overview.md](./architecture/overview.md#componentes-core) |
| Fluxos de dados | [architecture/overview.md](./architecture/overview.md#fluxos-de-dados) |
| API REST | [architecture/api-reference.md](./architecture/api-reference.md) |
| Modelo W5H | [concepts/memory-model.md](./concepts/memory-model.md) |
| Decaimento | [concepts/cognitive-decay.md](./concepts/cognitive-decay.md) |
| Consolidação | [concepts/consolidation.md](./concepts/consolidation.md) |
| Shared Memory | [concepts/shared-memory.md](./concepts/shared-memory.md) |
| SDK | [getting-started/integrations.md](./getting-started/integrations.md) |

---

## Visão Geral

```
┌─────────────────────────────────────────────────────────────┐
│                        INTERFACES                           │
│              ┌───────────┐  ┌───────────┐                  │
│              │    MCP    │  │  REST API │                  │
│              └─────┬─────┘  └─────┬─────┘                  │
├────────────────────┴──────────────┴─────────────────────────┤
│                        CORE                                  │
│     ┌──────────┐  ┌──────────┐  ┌──────────┐               │
│     │  Entity  │  │  Memory  │  │ Relation │               │
│     └──────────┘  └──────────┘  └──────────┘               │
│                        │                                    │
│              ┌─────────┴─────────┐                         │
│              │    MemoryGraph    │                         │
│              └───────────────────┘                         │
├─────────────────────────────────────────────────────────────┤
│                        STORAGE                              │
│              ┌───────────────────────┐                     │
│              │    JSON / SQLite      │                     │
│              └───────────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

Para detalhes completos, veja [architecture/overview.md](./architecture/overview.md).

---

*Documento legado — Veja documentação modular para informações atualizadas.*
