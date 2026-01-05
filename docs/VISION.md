# 🧠 Cortex - Sistema de Memória Cognitiva

> **Memória semântica para agentes LLM**  
> Versão: 3.0 | Janeiro 2026

---

## 📋 O Que É o Cortex

Cortex é uma **infraestrutura de memória cognitiva** para agentes LLM que:

- **Armazena SIGNIFICADO**, não texto
- **Lembra experiências** (episódios), não logs
- **Conecta conhecimento** via grafo associativo
- **Consolida memórias** automaticamente (100 eventos → 1 padrão)
- **Funciona como MCP** (Model Context Protocol)
- **Agnóstico de domínio** (dev, roleplay, chatbot, assistentes)

---

## 🎯 Princípio Fundamental

```
APÓS cada interação:
├─ Agente responde ao usuário
├─ Agente extrai: O QUÊ fez, POR QUÊ, RESULTADO
└─ Cortex armazena episódio + entidades + relações

ANTES de cada interação:
├─ Agente consulta Cortex com contexto atual
├─ Cortex retorna memórias relevantes
└─ Agente usa contexto para responder melhor
```

**A resposta do assistente JÁ É o resumo.** Cortex memoriza significado, não texto bruto.

---

## 🏗️ Arquitetura

### Três Blocos Fundamentais

```
┌─────────────────────────────────────────────────────────────┐
│                        CORTEX                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ENTITY (Coisas)                                           │
│  ════════════════                                          │
│  Qualquer "coisa" mencionada:                              │
│  - Pessoas, objetos, lugares, conceitos                    │
│  - Identificadores flexíveis (nome, email, hash, etc)      │
│  - Atributos livres                                        │
│                                                             │
│  EPISODE (Acontecimentos)                                  │
│  ═════════════════════════                                 │
│  Qualquer "experiência":                                   │
│  - O que aconteceu (action)                                │
│  - Quem/o que participou (entities)                        │
│  - Contexto/situação                                       │
│  - Resultado/outcome                                       │
│  - Quando                                                  │
│                                                             │
│  RELATION (Conexões)                                       │
│  ════════════════════                                      │
│  Qualquer "ligação" entre coisas:                          │
│  - Tipo livre (caused_by, loves, resolved, requires...)    │
│  - Força da conexão (reforça com uso)                      │
│  - Contexto de quando foi criada                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Fluxo de Dados

```
┌──────────────────────────────────────────────────────┐
│                   AGENTE (qualquer)                  │
└──────────────────────────────────────────────────────┘
                    │                    ▲
                    │ store()            │ recall()
                    ▼                    │
┌──────────────────────────────────────────────────────┐
│                    MCP SERVER                        │
│              (cortex_store, cortex_recall)           │
└──────────────────────────────────────────────────────┘
                    │                    ▲
                    ▼                    │
┌──────────────────────────────────────────────────────┐
│                   MEMORY GRAPH                       │
│         Entity ←→ Episode ←→ Relation               │
└──────────────────────────────────────────────────────┘
                    │                    ▲
                    ▼                    │
┌──────────────────────────────────────────────────────┐
│                    STORAGE                           │
│            (JSON/SQLite/PostgreSQL)                  │
└──────────────────────────────────────────────────────┘
```

---

## 📦 Estruturas de Dados

### Entity

```python
@dataclass
class Entity:
    id: str                    # UUID
    type: str                  # Livre: "person", "object", "concept"...
    name: str                  # Nome legível
    identifiers: list[str]     # Formas de reconhecer
    attributes: dict           # Metadados livres
    created_at: datetime
    access_count: int          # Quantas vezes referenciado
```

### Episode

```python
@dataclass
class Episode:
    id: str                    # UUID
    timestamp: datetime
    
    # O que aconteceu
    action: str                # Verbo: "analyzed", "resolved", "discussed"
    participants: list[str]    # Entity IDs envolvidos
    
    # Contexto
    context: str               # Situação, cenário
    
    # Resultado
    outcome: str               # O que resultou
    
    # Consolidação
    occurrence_count: int      # Quantas vezes similar
    consolidated_from: list[str]  # IDs de episódios consolidados
```

### Relation

```python
@dataclass
class Relation:
    id: str
    from_id: str               # Entity ou Episode
    relation_type: str         # Livre: "caused_by", "loves", "resolved"
    to_id: str                 # Entity ou Episode
    strength: float            # 0.0 - 1.0 (reforça com uso)
    context: dict              # Quando/como foi criada
    created_at: datetime
```

---

## 🔌 API (MCP Tools)

### cortex_recall

Chamado **ANTES** de responder ao usuário.

```python
# Input
{
    "query": "texto da mensagem do usuário",
    "context": {
        "entities": ["nomes ou ids conhecidos"],
        "recent_topics": ["tópicos recentes"]
    }
}

# Output
{
    "entities_found": [...],
    "relevant_episodes": [...],
    "relations": [...],
    "context_summary": "Resumo textual para injetar no prompt"
}
```

### cortex_store

Chamado **APÓS** responder ao usuário.

```python
# Input
{
    "action": "o que foi feito",
    "participants": [
        {"type": "...", "name": "...", "identifiers": [...]}
    ],
    "context": "situação/cenário",
    "outcome": "resultado",
    "relations": [
        {"from": "...", "type": "...", "to": "..."}
    ]
}

# Output
{
    "episode_id": "...",
    "entities_created": [...],
    "entities_updated": [...],
    "consolidated": true/false
}
```

---

## 🔄 Consolidação Automática

Quando um padrão se repete:

```
Análise 1: "analisou log, encontrou erro 404"
Análise 2: "analisou log, encontrou erro 404"
...
Análise 10: "analisou log, encontrou erro 404"

CORTEX CONSOLIDA:
├─ Arquiva episódios 1-10
├─ Cria episódio consolidado:
│   "Padrão recorrente (10x): análise de log revela erro 404"
└─ Próxima busca retorna O PADRÃO, não os 10 eventos
```

---

## 🎭 Exemplos por Domínio

### Desenvolvimento

```python
cortex_store({
    "action": "debugged",
    "participants": [{"type": "bug", "name": "memory leak"}],
    "context": "production server",
    "outcome": "fixed by closing connections properly",
    "relations": [
        {"from": "memory_leak", "type": "caused_by", "to": "unclosed_connections"}
    ]
})
```

### Roleplay

```python
cortex_store({
    "action": "confessed_feelings",
    "participants": [
        {"type": "character", "name": "Elena"},
        {"type": "character", "name": "Marcus"}
    ],
    "context": "moonlit rooftop",
    "outcome": "mutual feelings revealed",
    "relations": [
        {"from": "elena", "type": "loves", "to": "marcus"}
    ]
})
```

### Atendimento

```python
cortex_store({
    "action": "resolved_complaint",
    "participants": [
        {"type": "customer", "name": "Maria", "identifiers": ["maria@email.com"]},
        {"type": "product", "name": "Laptop X"}
    ],
    "context": "delivery delay",
    "outcome": "refund processed, customer satisfied",
    "relations": [
        {"from": "complaint", "type": "resolved_by", "to": "refund"}
    ]
})
```

---

## 🚀 Uso como MCP

### Configuração (claude_desktop_config.json)

```json
{
  "mcpServers": {
    "cortex": {
      "command": "python",
      "args": ["-m", "cortex.mcp.server"],
      "env": {
        "CORTEX_DATA_DIR": "/path/to/data"
      }
    }
  }
}
```

### System Prompt Recomendado

```
WORKFLOW OBRIGATÓRIO:

1. ANTES de responder: SEMPRE chame cortex_recall para buscar memórias relevantes
2. Use o contexto retornado para personalizar sua resposta
3. APÓS responder: SEMPRE chame cortex_store para memorizar a interação

Memória NÃO é opcional. Ela permite continuidade entre sessões.
```

---

## 📊 Métricas de Sucesso

| Métrica | Alvo |
|---------|------|
| Latência recall | < 50ms |
| Latência store | < 100ms |
| Consolidação | Automática após 5+ episódios similares |
| Relevância | > 80% memórias retornadas são úteis |
| Economia | Contexto comprimido vs histórico completo |

---

## 🗺️ Roadmap

### Fase 1: Core ← ATUAL
- [x] Estrutura do projeto
- [ ] Entity, Episode, Relation
- [ ] MemoryGraph
- [ ] Storage (JSON local)

### Fase 2: MCP
- [ ] MCP Server
- [ ] cortex_recall
- [ ] cortex_store
- [ ] Testes com Claude Desktop

### Fase 3: Inteligência
- [ ] EntityResolver (identificar entidades ambíguas)
- [ ] Consolidator (compactar episódios repetidos)
- [ ] RecallEngine (busca por relevância)

### Fase 4: Produção
- [ ] PostgreSQL storage
- [ ] API REST (além de MCP)
- [ ] SDKs (Python, TypeScript)
- [ ] Docker

---

*Última atualização: 05 de Janeiro de 2026*
