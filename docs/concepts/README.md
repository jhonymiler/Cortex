# 📚 Conceitos

> Documentação canônica dos fundamentos do Cortex.

---

## Índice

| Conceito | Descrição |
|----------|-----------|
| [Modelo W5H](./memory-model.md) | Como memórias são estruturadas |
| [Decaimento Cognitivo](./cognitive-decay.md) | Curva de Ebbinghaus e spaced repetition |
| [Consolidação](./consolidation.md) | DreamAgent e hierarquia de memórias |
| [Memória Compartilhada](./shared-memory.md) | Multi-tenant com isolamento |

---

## Princípio D.R.Y.

Estes documentos são a **fonte única de verdade** para cada conceito. Outros documentos da documentação referenciam estes arquivos em vez de duplicar explicações.

Se você precisa atualizar um conceito, faça-o aqui. Todas as referências automaticamente refletirão a atualização.

---

## Relacionamentos

```
                    ┌──────────────┐
                    │  memory-     │
                    │  model.md    │
                    │    (W5H)     │
                    └──────┬───────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  cognitive-  │  │ consolidation│  │   shared-    │
│  decay.md    │  │     .md      │  │  memory.md   │
│ (Ebbinghaus) │  │ (DreamAgent) │  │ (Isolation)  │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## Próximos Passos

| Quer... | Vá para... |
|---------|------------|
| Começar a usar | [Quick Start](../getting-started/quickstart.md) |
| Ver arquitetura | [Overview](../architecture/overview.md) |
| Entender a ciência | [Base Científica](../research/scientific-basis.md) |

---

*Índice de Conceitos — Última atualização: Janeiro 2026*

