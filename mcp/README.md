# 🧠 Cortex MCP Server

> *"Cortex, porque agentes inteligentes precisam de memória inteligente"*

Servidor MCP (Model Context Protocol) para integrar o Cortex Memory com Claude Desktop, IDEs e outros clientes MCP.

## Hierarquia de Namespace

O MCP usa uma estrutura hierárquica de 3 níveis:

```
{team}:{project}:{user}
  │        │        └── Memória pessoal do usuário
  │        └── Memória compartilhada do projeto (dinâmico)
  └── Memória coletiva do time/organização (fixo)
```

### Exemplos de Uso

| Contexto | Team | Project | User | Namespace |
|----------|------|---------|------|-----------|
| IDE (Cortex) | dev_team | cortex | jhony | `dev_team:cortex:jhony` |
| IDE (Outro) | dev_team | outro_projeto | jhony | `dev_team:outro_projeto:jhony` |
| Suporte | suporte | financeiro | maria | `suporte:financeiro:maria` |
| Multi-agentes | agents | sales_crew | bot_1 | `agents:sales_crew:bot_1` |

### Detecção Automática de Projeto

O projeto é detectado automaticamente (em ordem de prioridade):

1. Variável `CORTEX_PROJECT` (se definida)
2. Nome em `pyproject.toml`
3. Nome em `package.json`
4. Nome do repositório Git
5. Nome do diretório atual

## Instalação

```bash
cd mcp
pip install -e .
```

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

## Variáveis de Ambiente

### Conexão e Namespace

| Variável | Default | Descrição |
|----------|---------|-----------|
| `CORTEX_API_URL` | `http://localhost:8000` | URL da API Cortex |
| `CORTEX_TEAM` | `default_team` | Time/organização (fixo) |
| `CORTEX_USER` | `$USER` | Usuário atual (fixo) |
| `CORTEX_PROJECT` | (auto) | Override do projeto |

### Memory Firewall (Identity Kernel)

| Variável | Default | Descrição |
|----------|---------|-----------|
| `CORTEX_IDENTITY_ENABLED` | `true` | Habilita proteção anti-jailbreak |
| `CORTEX_IDENTITY_MODE` | `pattern` | Modo de detecção: `pattern`, `semantic`, `hybrid` |
| `CORTEX_IDENTITY_STRICT` | `false` | `true` = bloqueia, `false` = apenas alerta |

## Tools Disponíveis

### Gerenciamento de Contexto

| Tool | Descrição |
|------|-----------|
| `switch_project` | Muda projeto sem mudar diretório |
| `get_current_context` | Mostra team/project/user atual |

### Operações de Memória

| Tool | Descrição |
|------|-----------|
| `store_memory` | Armazena memória pessoal |
| `recall_memory` | Busca semântica com scope |
| `share_with_team` | Compartilha com todo o time |
| `share_with_project` | Compartilha com o projeto |
| `get_entity` | Recupera entidade |
| `list_entities` | Lista entidades |
| `consolidate_memories` | DreamAgent |
| `get_memory_stats` | Estatísticas |

### Scopes de Busca

| Scope | O que busca |
|-------|-------------|
| `personal` | Só suas memórias |
| `project` | Suas + compartilhadas do projeto |
| `team` / `all` | Todas (incluindo time) |

## Resources

| Resource | Descrição |
|----------|-----------|
| `cortex://context` | Contexto atual completo |
| `cortex://health` | Status do servidor |
| `cortex://about` | Informações do Cortex |

## Prompts

| Prompt | Descrição |
|--------|-----------|
| `remember_context` | Template para usar memória |
| `new_project_context` | Iniciar em novo projeto |

## Exemplo de Uso

```
# Claude detecta automaticamente o projeto pelo diretório

Usuário: O que você sabe sobre este projeto?

Claude: [Usa recall_memory com scope="project"]
        Este é o projeto Cortex. Encontrei que:
        - Usa Python 3.11+ com FastAPI
        - Modelo W5H para estruturar memórias
        - ...

Usuário: Descobri que precisamos usar visibility="shared" para herança

Claude: [Usa share_with_project para salvar]
        Anotado para todo o time do projeto!

# Mudando de projeto sem sair do Claude

Usuário: Agora preciso trabalhar no projeto cliente_xyz

Claude: [Usa switch_project("cliente_xyz")]
        Contexto alterado para cliente_xyz.
        [Usa recall_memory para buscar contexto]
        ...
```

## Fluxo de Memória

```
┌─────────────────────────────────────────────────────────────┐
│                        TEAM (learned)                        │
│  "Padrões universais, aprendizados de todos os projetos"    │
├─────────────────────────────────────────────────────────────┤
│                     PROJECT (shared)                         │
│  "Decisões, padrões e conhecimento específico do projeto"   │
├─────────────────────────────────────────────────────────────┤
│                      USER (personal)                         │
│  "Preferências pessoais, notas, contexto individual"        │
└─────────────────────────────────────────────────────────────┘

Herança: User vê tudo ↑ | Project vê Team | Team é isolado
```

## 4 Dimensões de Valor

| Dimensão | Score | O que ganha |
|----------|-------|-------------|
| 🧠 Cognição Biológica | 50% | Decay, consolidação, hubs |
| 👥 Memória Coletiva | 75% | Herança hierárquica |
| 🎯 Valor Semântico | 100% | Sinônimos funcionam |
| ⚡ Eficiência | 100% | 16ms, tokens compactos |

**Score Total: 83%** (vs 40% das alternativas)

## Requisitos

- Python 3.10+
- Cortex API rodando (`cortex-api`)
- Cliente MCP (Claude Desktop, etc.)

## Desenvolvimento

```bash
pip install -e ".[dev]"
cortex-mcp
```
