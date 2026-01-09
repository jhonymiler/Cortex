# Integração MCP

> *"Cortex, porque agentes inteligentes precisam de memória inteligente"*

O MCP (Model Context Protocol) é um projeto **separado** que se integra com a API do Cortex.

📁 **Localização**: [`/mcp`](../mcp/README.md)

---

## Hierarquia de Namespace

O MCP usa namespace hierárquico de 3 níveis:

```
{team}:{project}:{user}
  │        │        └── Memória pessoal
  │        └── Memória do projeto (detectado automaticamente)
  └── Memória do time (fixo)
```

### Níveis de Visibilidade

| Nível | Scope | Quem vê | Uso |
|-------|-------|---------|-----|
| **personal** | user | Só você | Preferências, notas |
| **shared** | project | Time do projeto | Decisões, padrões |
| **learned** | team | Toda organização | Aprendizados gerais |

### Detecção Automática

O projeto é detectado automaticamente (em ordem):
1. Variável `CORTEX_PROJECT`
2. Nome em `pyproject.toml`
3. Nome em `package.json`
4. Nome do repositório Git
5. Nome do diretório atual

---

## Instalação

```bash
# MCP é projeto separado
cd mcp
pip install -e .
```

---

## Configuração Claude Desktop

```json
{
  "mcpServers": {
    "cortex": {
      "command": "cortex-mcp",
      "env": {
        "CORTEX_API_URL": "http://localhost:8000",
        "CORTEX_TEAM": "meu_time",
        "CORTEX_USER": "meu_usuario"
      }
    }
  }
}
```

### Localização do arquivo

| OS | Caminho |
|----|---------|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

---

## Tools Principais

### Gerenciamento de Contexto

| Tool | Descrição |
|------|-----------|
| `get_current_context` | Mostra team/project/user atual |
| `switch_project` | Muda projeto sem mudar diretório |

### Operações de Memória

| Tool | Descrição |
|------|-----------|
| `store_memory` | Armazena memória pessoal |
| `recall_memory` | Busca com scope (personal/project/team) |
| `share_with_project` | Compartilha com o projeto |
| `share_with_team` | Compartilha com todo o time |

### Utilitários

| Tool | Descrição |
|------|-----------|
| `get_entity` | Recupera entidade |
| `list_entities` | Lista entidades |
| `consolidate_memories` | DreamAgent |
| `get_memory_stats` | Estatísticas |

---

## Exemplos de Uso

### IDE - Trabalhando em Projetos

```
# Abrindo o Claude no diretório do Cortex
# Detecta automaticamente: default_team:cortex_memory:jhony

Usuário: O que você sabe sobre este projeto?

Claude: [Usa recall_memory(scope="project")]
        Encontrei informações sobre o projeto Cortex...

# Mudando de projeto
Usuário: Preciso trabalhar no cliente_xyz

Claude: [Usa switch_project("cliente_xyz")]
        Contexto alterado para cliente_xyz.
```

### Suporte - Múltiplos Atendentes

```
# Config: CORTEX_TEAM=suporte, CORTEX_USER=maria
# Namespace: suporte:financeiro:maria

Usuário: Como resolver erro de boleto?

Claude: [Usa recall_memory(scope="team")]
        Encontrei um padrão aprendido pelo time...

# Após resolver
Claude: [Usa share_with_team("Boleto expirado: orientar a gerar novo")]
        Compartilhado com todo o time de suporte!
```

### Multi-Agentes - CrewAI

```
# Config: CORTEX_TEAM=agents, CORTEX_PROJECT=sales_crew
# Cada agente tem seu CORTEX_USER

# bot_researcher: agents:sales_crew:researcher
# bot_writer: agents:sales_crew:writer

# Agentes compartilham memória do projeto
# Mas têm memórias pessoais isoladas
```

---

## Variáveis de Ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `CORTEX_API_URL` | `http://localhost:8000` | URL da API |
| `CORTEX_TEAM` | `default_team` | Time (fixo) |
| `CORTEX_USER` | `$USER` | Usuário (fixo) |
| `CORTEX_PROJECT` | (auto) | Override do projeto |

---

## Documentação Completa

Veja [mcp/README.md](../mcp/README.md) para documentação completa.

---

## Modelo W5H

O Cortex extrai automaticamente:

| Campo | Significado | Exemplo |
|-------|-------------|---------|
| WHO | Participantes | `["maria", "sistema"]` |
| WHAT | O que aconteceu | `"resolveu erro de boleto"` |
| WHY | Por que | `"boleto expirado"` |
| WHEN | Quando | `timestamp` |
| WHERE | Namespace | `"suporte:financeiro:maria"` |
| HOW | Resultado | `"orientou a gerar novo"` |

---

## 4 Dimensões de Valor

| Dimensão | Score | Exclusivo? |
|----------|-------|------------|
| 🧠 Cognição Biológica | 50% | ✅ |
| 👥 Memória Coletiva | 75% | ✅ |
| 🎯 Valor Semântico | 100% | Empata |
| ⚡ Eficiência | 100% | ✅ |

**Score Total: 83%** (vs 40% das alternativas)

---

*Veja também: [Quickstart](./getting-started/quickstart.md) | [Integrações](./getting-started/integrations.md)*
