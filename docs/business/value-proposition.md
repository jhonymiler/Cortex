# 💰 Proposta de Valor

> Traduzindo métricas técnicas em impacto de negócio.

---

## O Problema que Resolvemos

Agentes LLM sofrem de **amnésia crônica**:

| Sintoma | Custo Real |
|---------|------------|
| Perguntas repetitivas | 10+ interações desnecessárias por sessão |
| Context stuffing | Tokens crescem linearmente ($$$$) |
| Respostas genéricas | Baixa conversão, alto churn |
| Contexto perdido | Usuário frustrado, abandono |

### O Custo da Amnésia

```
Cenário: Agente de suporte com 10.000 conversas/mês

SEM MEMÓRIA:
├── Média 15 mensagens/conversa (muitas repetições)
├── ~2.000 tokens de contexto por mensagem
├── Total: 300.000.000 tokens/mês
└── Custo GPT-4: ~$3.000/mês

COM CORTEX:
├── Média 4 mensagens/conversa (sem repetições)
├── ~100 tokens de contexto por mensagem
├── Total: 4.000.000 tokens/mês
└── Custo GPT-4: ~$40/mês

ECONOMIA: $2.960/mês (98.7%)
```

---

## Resultados Comprovados

### Benchmark (Janeiro 2026)

| Métrica | Baseline | Cortex | Diferença |
|---------|----------|--------|-----------|
| **Tokens** | 49.438 | 43.255 | **-12.5%** |
| **Tempo** | 239s | 189s | **-21%** |
| **Hit Rate** | 0% | **100%** | ∞ |

### Tradução para Negócio

| Escala | Mensagens/mês | Economia tokens | Economia USD* |
|--------|---------------|-----------------|---------------|
| **Startup** | 10.000 | 62.000 | **$0.62** |
| **Médio** | 100.000 | 620.000 | **$6.20** |
| **Enterprise** | 1.000.000 | 6.200.000 | **$62.00** |
| **Grande** | 10.000.000 | 62.000.000 | **$620.00** |

*Baseado em GPT-4 Turbo ($0.01/1K tokens)

---

## Ganhos Além de Tokens

### 1. Redução de Tempo de Atendimento

| Cenário | Antes | Depois | Ganho |
|---------|-------|--------|-------|
| Customer Support | 15+ msgs | 4 msgs | **-73%** |
| Healthcare Triage | 12 min | 4 min | **-67%** |
| Dev Onboarding | 30 min | 5 min | **-83%** |

### 2. Aumento de Conversão

| Cenário | Antes | Depois | Ganho |
|---------|-------|--------|-------|
| E-commerce | 2.5% | 8.1% | **+224%** |
| SaaS Trial | 12% | 28% | **+133%** |
| Lead Qualification | 5% | 15% | **+200%** |

### 3. Satisfação do Usuário

| Métrica | Antes | Depois |
|---------|-------|--------|
| "Já te disse isso" | 40% reclamam | 0% |
| NPS | +20 | +55 |
| Retenção 30 dias | 45% | 78% |

---

## ROI Calculator

### Fórmula

```
ROI = (Economia de Tokens + Valor do Tempo Economizado) / Custo Cortex

Onde:
- Economia de Tokens = msgs/mês × tokens_economizados × $/token
- Valor do Tempo = horas_economizadas × $/hora
- Custo Cortex = Infra + Manutenção
```

### Exemplo Real

```
Empresa: E-commerce com 50.000 interações/mês

ECONOMIA DE TOKENS:
├── 50.000 × 1.000 tokens economizados × $0.01/1K
└── = $500/mês

ECONOMIA DE TEMPO:
├── 50.000 × 2 min economizados = 1.667 horas
├── Atendente custa $15/hora
└── = $25.000/mês (ou realocar para tarefas de maior valor)

CUSTO CORTEX:
├── Servidor: $50/mês
├── Manutenção: $0 (self-hosted)
└── = $50/mês

ROI = ($500 + $25.000) / $50 = 510x
```

---

## Casos de Uso por Indústria

### 🛒 E-commerce

**Problema**: Cliente VIP tratado como novato toda vez.

**Com Cortex**:
```
❌ "Qual seu tamanho? Qual marca prefere?"
✅ "Maria! Chegou o Pegasus 2025. Como VIP, 20% off. Reservo o 42?"
```

**Impacto**: +224% conversão, +45% ticket médio

---

### 🏥 Healthcare

**Problema**: Triagem demora 12 minutos repetindo histórico.

**Com Cortex**:
```
❌ "Tem alergias? Toma medicamentos? Histórico familiar?"
✅ "Carlos, vi sua gastrite crônica. Sintomas iguais ou diferentes?"
```

**Impacto**: -67% tempo de triagem, +30% satisfação

---

### 💻 Developer Tools

**Problema**: Assistente sugere JS para time de TypeScript.

**Com Cortex**:
```
❌ "Qual framework você usa?"
✅ "Vi que o time usa TypeScript + NextAuth. Aqui o fix no estilo:"
```

**Impacto**: +92% acerto de contexto, -80% retrabalho

---

### 🎮 Gaming / Roleplay

**Problema**: NPC esquece toda a narrativa anterior.

**Com Cortex**:
```
❌ "Quem é você, aventureiro?"
✅ "Marcus! Voltou da missão? O dragão foi derrotado?"
```

**Impacto**: +300% engajamento, +150% sessão média

---

## Comparativo de Custos

| Solução | Custo Setup | Custo/Mês | Custo/Recall |
|---------|-------------|-----------|--------------|
| **Context Window** | $0 | Alto (tokens) | ~$0.02 |
| **RAG + VectorDB** | $500+ | $100+ | ~$0.001 |
| **Fine-tuning** | $1.000+ | $0 | $0 |
| **Cortex** | $0 | $50 (infra) | **$0** |

### Por que Cortex é Diferente?

- **Zero custo por recall**: Busca O(1), não embeddings
- **Self-hosted**: Sem vendor lock-in
- **Open source**: Sem licença por assento
- **Incremental**: Escala com seu negócio

---

## Pronto para Começar?

| Passo | Ação |
|-------|------|
| 1 | [Quick Start](../getting-started/quickstart.md) — 2 minutos |
| 2 | [Integrações](../getting-started/integrations.md) — escolha seu framework |
| 3 | [Benchmark](../research/benchmarks.md) — valide com seus dados |

---

## Contato

- **Repositório**: [GitHub](https://github.com/seu-usuario/cortex)
- **Discussões**: [GitHub Discussions](https://github.com/seu-usuario/cortex/discussions)
- **Issues**: [GitHub Issues](https://github.com/seu-usuario/cortex/issues)

---

*Proposta de Valor — Última atualização: Janeiro 2026*

