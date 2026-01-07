# 🗺️ Roadmap: A Jornada do Cortex

> Uma narrativa estratégica, não uma lista de features.

---

## Visão de Longo Prazo

> **"Agentes que lembram, aprendem e evoluem — como humanos."**

O Cortex não é apenas um sistema de memória. É a fundação para a próxima geração de agentes verdadeiramente inteligentes, que mantêm contexto, personalizam interações e melhoram continuamente.

---

## Era 1: Fundação Científica ✅

**Período**: Q4 2025 — Concluído

**Propósito**: Provar que memória cognitiva funciona melhor que abordagens tradicionais.

| Entrega | Por que importa | Status |
|---------|-----------------|--------|
| Modelo W5H | Estrutura agnóstica de domínio | ✅ |
| Decaimento Ebbinghaus | Memória que esquece como humanos | ✅ |
| Hub Centrality | Importância emergente, não declarada | ✅ |
| Consolidação Hierárquica | 100 eventos → 1 padrão | ✅ |
| DreamAgent | Consolidação em background | ✅ |
| Benchmark científico | Validação rigorosa vs RAG, Mem0 | ✅ |

### Marco Atingido
✅ Sistema funcional com fundamentos científicos sólidos.
✅ -12.5% tokens, -21% latência vs baseline.

---

## Era 2: Integração Universal 🚧

**Período**: Q1 2026 — Em Andamento

**Propósito**: Tornar Cortex acessível para qualquer framework, sem fricção.

| Entrega | Por que importa | Status |
|---------|-----------------|--------|
| SDK Core genérico | Base para todos os adaptadores | ✅ |
| LangChain adapter | Maior ecossistema de agentes | ✅ |
| CrewAI adapter | Multi-agente com memória compartilhada | ✅ |
| MCP Server | Claude Desktop, Cursor, etc. | ✅ |
| Google ADK adapter | Ecossistema Google AI | 🔜 |
| FastAgent adapter | Agentes rápidos | 🔜 |
| Documentação modular | Onboarding em 2 minutos | 🚧 |

### Marco Esperado
🎯 1.000 desenvolvedores usando em produção.
🎯 pip install cortex-memory funcionando.

---

## Era 3: Escala de Produção 🔮

**Período**: Q2-Q3 2026

**Propósito**: Suportar workloads enterprise com SLAs rigorosos.

| Entrega | Por que importa |
|---------|-----------------|
| PostgreSQL backend | Durabilidade enterprise |
| Neo4j opcional | Grafos em escala |
| Redis cache | Latência sub-millisecond |
| Dashboard de observability | Monitoramento em tempo real |
| Multi-tenant SaaS | Deploy gerenciado |
| SDK TypeScript | Frontend-first developers |
| Docker + Kubernetes | Deploy em qualquer infra |

### Marco Esperado
🎯 Cliente enterprise com >1M interações/mês.
🎯 SLA 99.9% uptime.

---

## Era 4: Agência Autônoma 🌟

**Período**: 2027+

**Propósito**: Memória que não apenas armazena, mas **raciocina**.

| Entrega | Por que importa |
|---------|-----------------|
| ProceduralMemory | Agentes que lembram "como fazer" |
| SemanticMemory | Fatos vs experiências separados |
| IdentityKernel | Personalidade persistente + anti-jailbreak |
| Metacognição | Agente que sabe o que não sabe |
| Goal Memory | Persistência de objetivos de longo prazo |
| Counterfactual Reasoning | "E se eu tivesse feito diferente?" |

### Marco Esperado
🎯 Agentes verdadeiramente autônomos com memória de longo prazo.
🎯 Paper aceito em conferência tier-1 (NeurIPS, ICML, ACL).

---

## Timeline Visual

```
2025                    2026                    2027+
──────────────────────────────────────────────────────────►

 ┌─────────────┐
 │  ERA 1:     │
 │  FUNDAÇÃO   │ ✅ Concluído
 │  CIENTÍFICA │
 └─────────────┘
        │
        ▼
        ┌─────────────┐
        │  ERA 2:     │
        │  INTEGRAÇÃO │ 🚧 Em andamento
        │  UNIVERSAL  │
        └─────────────┘
                │
                ▼
                ┌─────────────┐
                │  ERA 3:     │
                │  ESCALA DE  │ 🔮 Planejado
                │  PRODUÇÃO   │
                └─────────────┘
                        │
                        ▼
                        ┌─────────────┐
                        │  ERA 4:     │
                        │  AGÊNCIA    │ 🌟 Visão
                        │  AUTÔNOMA   │
                        └─────────────┘
```

---

## Como Contribuir

Cada era tem oportunidades diferentes:

| Era | Tag GitHub | Skills Necessárias |
|-----|------------|-------------------|
| **Fundação** | `research` | ML, ciência cognitiva, papers |
| **Integração** | `integration` | Python, TypeScript, frameworks |
| **Escala** | `infra` | Databases, DevOps, Kubernetes |
| **Agência** | `experimental` | Arquitetura de agentes, reasoning |

### Primeiros Passos para Contribuidores

1. **Fork** o repositório
2. **Escolha uma era** que combine com suas skills
3. **Veja issues abertas** com a tag correspondente
4. **Proponha** ou **claim** uma issue
5. **Submeta PR** com testes

### Áreas de Alto Impacto Agora

| Área | Impacto | Dificuldade |
|------|---------|-------------|
| Google ADK adapter | 🔥🔥🔥 | ⭐⭐ |
| Dashboard de visualização | 🔥🔥 | ⭐⭐ |
| Documentação de exemplos | 🔥🔥🔥 | ⭐ |
| Testes de integração | 🔥🔥 | ⭐⭐ |
| PostgreSQL backend | 🔥🔥🔥 | ⭐⭐⭐ |

---

## FAQ do Roadmap

### "Por que não priorizar X?"

O roadmap é guiado por três princípios:
1. **Fundação antes de features**: Sem base científica sólida, features são frágeis.
2. **Adoção antes de escala**: Sem usuários, escala é irrelevante.
3. **Comunidade antes de comercialização**: Open source primeiro.

### "Quando teremos feature Y?"

Veja a era correspondente. Se não está listada, abra uma issue com o label `feature-request`.

### "Posso acelerar uma feature?"

Sim! Contribuições movem features para cima na prioridade. PRs de qualidade são a moeda do open source.

### "E se eu precisar de algo para produção agora?"

Entre em contato via [GitHub Discussions](https://github.com/seu-usuario/cortex/discussions). Podemos ajudar a adaptar para seu caso de uso.

---

## Princípios de Design

Estes guiam todas as decisões de roadmap:

1. **Zero tokens por recall**: Nunca comprometer busca O(1)
2. **Estrutura sobre texto**: W5H sempre, texto livre nunca
3. **Cognição sobre storage**: Memória que pensa, não arquivo
4. **Self-hosted primeiro**: Controle total para o usuário
5. **Ciência sobre hype**: Validação empírica, não marketing

---

## Próximos Passos

| Interessado em... | Ação |
|-------------------|------|
| Usar agora | [Quick Start](../getting-started/quickstart.md) |
| Contribuir | [Contributing Guide](../../CONTRIBUTING.md) |
| Entender a ciência | [Base Científica](../research/scientific-basis.md) |
| Acompanhar progresso | [GitHub Project Board](https://github.com/seu-usuario/cortex/projects) |

---

*Roadmap — Última atualização: Janeiro 2026*

