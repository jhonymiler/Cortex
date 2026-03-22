# 🧠 Modelo de Memória W5H

> **A dor:** Agentes de IA perdem contexto entre sessões, forçando usuários a repetir informações.
> **A solução:** Estrutura W5H captura contexto completo em ~36 tokens — 5x mais compacto que texto livre.
> **O resultado:** Respostas personalizadas desde a primeira mensagem.

*Documento Canônico — fonte única de verdade sobre o modelo W5H.*

---

## O Que é W5H?

O Cortex estrutura memórias usando o modelo **W5H** (Who, What, Why, When, Where, How) — uma extensão do modelo jornalístico clássico adaptada para sistemas de memória cognitiva.

```
┌─────────────────────────────────────────────────────────────┐
│                         MEMORY                              │
├─────────────────────────────────────────────────────────────┤
│  WHO    │ Quem está envolvido (entidades)                   │
│  WHAT   │ O que aconteceu (ação/fato)                       │
│  WHY    │ Por quê (causa, motivação, razão)                 │
│  WHEN   │ Quando (timestamp + contexto temporal)            │
│  WHERE  │ Onde (namespace + contexto espacial)              │
│  HOW    │ Como (resultado, consequência, método)            │
└─────────────────────────────────────────────────────────────┘
```

---

## Campos e Exemplos

| Campo | Pergunta | Tipo | Exemplo |
|-------|----------|------|---------|
| **WHO** | Quem participou? | `list[str]` | `["maria@email.com", "sistema_auth"]` |
| **WHAT** | O que aconteceu? | `str` | `"reportou_erro_login"` |
| **WHY** | Por que aconteceu? | `str` | `"vpn_bloqueando_conexao"` |
| **WHEN** | Quando? | `datetime` | `"2026-01-07T10:30:00"` |
| **WHERE** | Em que contexto? | `str` | `"suporte_cliente:user_123"` |
| **HOW** | Qual foi o resultado? | `str` | `"orientada_desconectar_vpn"` |

---

## Por Que W5H?

### Problema com Modelos Tradicionais

| Modelo | Limitação |
|--------|-----------|
| **semantic/episodic/procedural** | Fronteiras confusas, difícil classificar |
| **Entity/Relation** | Não captura temporalidade nem causalidade |
| **action/outcome** | Falta contexto de "por quê" |
| **Texto livre** | Não permite busca estruturada |

### Vantagens do W5H

1. **Unificação**: Um modelo cobre todos os tipos de memória
2. **Explicitação**: WHY como campo obrigatório, não implícito
3. **Organização**: WHERE permite namespacing natural
4. **Agnóstico**: Funciona para dev, chatbot, roleplay, healthcare
5. **Busca O(1)**: Campos indexados, não embeddings

---

## Implementação

### Dataclass Python

```python
@dataclass
class Memory:
    id: str
    
    # W5H Fields
    who: list[str]              # Participantes
    what: str                   # Ação/fato principal
    why: str = ""               # Causa/motivação
    when: datetime = field(default_factory=datetime.now)
    where: str = ""             # Namespace/contexto
    how: str = ""               # Resultado/método
    
    # Metadados
    importance: float = 0.5     # 0.0 - 1.0
    access_count: int = 0
    last_accessed: datetime | None = None
    
    # Consolidação
    occurrence_count: int = 1
    consolidated_from: list[str] = field(default_factory=list)
    consolidated_into: str | None = None
    is_summary: bool = False
```

### API REST

```bash
POST /memory/remember
{
    "who": ["João", "sistema_pagamentos"],
    "what": "reportou_erro_pagamento",
    "why": "cartao_expirado",
    "how": "orientado_atualizar_dados"
}
```

### MCP Tool

```python
cortex_remember(
    who=["João", "sistema_pagamentos"],
    what="reportou_erro_pagamento",
    why="cartao_expirado",
    how="orientado_atualizar_dados",
    where="suporte_cliente"
)
```

---

## Mapeamento de Domínios

### Customer Support

```python
Memory(
    who=["cliente_vip", "atendente_maria"],
    what="solicitou_reembolso",
    why="produto_com_defeito",
    how="aprovado_credito_loja",
    where="atendimento:ticket_123"
)
```

### Desenvolvimento

```python
Memory(
    who=["dev_joao", "modulo_auth"],
    what="corrigiu_bug_timeout",
    why="conexao_nao_fechada",
    how="adicionou_connection_pool",
    where="projeto_x:sprint_15"
)
```

### Roleplay/Games

```python
Memory(
    who=["elena", "marcus"],
    what="confessou_sentimentos",
    why="medo_perder_chance",
    how="reciprocidade_confirmada",
    where="fantasia:capitulo_5"
)
```

### Healthcare

```python
Memory(
    who=["paciente_carlos", "dr_silva"],
    what="relatou_sintomas_gastrite",
    why="estresse_trabalho",
    how="prescrito_omeprazol",
    where="clinica:consulta_2026_01"
)
```

---

## 🧭 Próximos Passos

Escolha seu caminho baseado no que você quer fazer agora:

> **🚀 Quer usar o W5H na prática?**
> 
> Você já entendeu a estrutura. Agora veja como armazenar sua primeira memória:
> ```bash
> curl -X POST http://localhost:8000/memory/remember \
>   -H "Content-Type: application/json" \
>   -H "X-Cortex-Namespace: meu_agente" \
>   -d '{"who": ["João"], "what": "testou_cortex", "how": "sucesso"}'
> ```
> → [Quick Start completo](../getting-started/quickstart.md)

> **🔬 Quer entender como memórias são "esquecidas"?**
> 
> O W5H define a estrutura. O **decaimento de Ebbinghaus** define quanto tempo cada memória permanece ativa.
> → [Decaimento Cognitivo](./cognitive-decay.md)

> **💡 Quer ver quanto o W5H economiza vs texto livre?**
> 
> No ablation study, W5H completo economiza **7.4% mais tokens** que modelos simples (só action/outcome).
> → [Benchmarks: Ablation Study](../research/benchmarks.md#ablation-study)

> **🏗️ Quer ver a implementação completa?**
> 
> O dataclass `Memory` está em `src/cortex/core/memory.py` com todos os campos e propriedades.
> → [Arquitetura: Overview](../architecture/overview.md)

---

## Referências Científicas

- Modelo W5H deriva de jornalismo investigativo (Kipling, 1902)
- Adaptado para memória episódica baseado em Tulving (1972)
- Estrutura inspirada em CoALA (arXiv:2309.02427)
- Validado contra Generative Agents (arXiv:2304.03442)

---

*Documento canônico do modelo W5H — Última atualização: Janeiro 2026*

