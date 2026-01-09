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
4. Nome do diretório atual

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

## Tools Disponíveis (Contrato W5H)

O MCP expõe **3 ferramentas** com parâmetros W5H explícitos. O modelo W5H estrutura memórias de forma compacta (~36 tokens vs 200+ texto livre).

---

### `store_memory` — Armazena memória estruturada

| Parâmetro | Obrigatório | Descrição | Formato/Exemplos |
|-----------|-------------|-----------|------------------|
| `what` | ✅ | O QUE aconteceu? | `verbo_objeto`: `"solicitou_reembolso"`, `"corrigiu_bug_timeout"` |
| `why` | ✅ | POR QUE aconteceu? | Causa/razão: `"produto_com_defeito"`, `"conexao_nao_fechada"` |
| `how` | ❌ | COMO foi resolvido? | Resultado: `"aprovado_credito_loja"`, `"adicionou_connection_pool"` |
| `who` | ❌ | QUEM participou? | Vírgula-separado: `"cliente_vip, atendente_maria"` |
| `where` | ❌ | ONDE aconteceu? | Contexto: `"suporte:ticket_123"`, `"src/auth/login.py"` |
| `visibility` | ❌ | Quem vê? | `personal` (só você), `shared` (projeto), `learned` (time) |
| `importance` | ❌ | Prioridade | `0.1-0.3` baixa, `0.4-0.6` normal, `0.7-1.0` alta |

**Exemplos por domínio:**

```python
# Suporte ao cliente
store_memory(
    what="solicitou_reembolso",
    why="produto_com_defeito",
    how="aprovado_credito_loja",
    who="cliente_vip, atendente_maria",
    where="atendimento:ticket_123",
    visibility="shared"
)

# Desenvolvimento
store_memory(
    what="corrigiu_bug_timeout",
    why="conexao_nao_fechada",
    how="adicionou_connection_pool",
    who="dev_joao, modulo_auth",
    where="projeto_x:sprint_15",
    visibility="shared",
    importance=0.8
)

# Preferência pessoal
store_memory(
    what="prefere_contato_email",
    why="responde_mais_rapido",
    who="cliente_carlos"
)
```

---

### `recall_memory` — Busca semântica com filtros

Sinônimos funcionam! "erro de login" encontra "problema de autenticação".

| Parâmetro | Obrigatório | Descrição | Exemplos |
|-----------|-------------|-----------|----------|
| `query` | ✅ | O QUE buscar? | `"preferências do cliente"`, `"bugs no módulo auth"` |
| `limit` | ❌ | Máximo resultados | `1-3` rápido, `10+` análise completa |
| `who` | ❌ | Filtrar por QUEM | `"cliente_joao"`, `"dev_maria, tech_lead"` |
| `where` | ❌ | Filtrar por ONDE | `"src/auth/"`, `"suporte_cliente"` |

**Exemplos:**

```python
# Busca simples
recall_memory(query="preferências do cliente")

# Filtrar por arquivo/módulo
recall_memory(query="bugs de timeout", where="src/db/", limit=10)

# Filtrar por pessoa
recall_memory(query="decisões técnicas", who="tech_lead")

# Contexto de conversa anterior
recall_memory(query="última solicitação", who="cliente_joao", limit=3)
```

---

### `get_current_context` — Contexto atual

Retorna o namespace ativo (determina quem vê as memórias).

```python
get_current_context()
# {
#   "team": "dev_team",
#   "project": "cortex",
#   "user": "jhony",
#   "namespace": "dev_team:cortex:jhony"
# }
```

---

### Níveis de Visibilidade

| Visibility | Quem vê | Quando usar |
|------------|---------|-------------|
| `personal` | Só você | Preferências, notas pessoais |
| `shared` | Time do projeto | Decisões, padrões, bugs resolvidos |
| `learned` | Toda organização | Aprendizados universais, boas práticas |

## Exemplo de Uso

```
# Claude detecta automaticamente o projeto pelo diretório

Usuário: O que você sabe sobre este projeto?

Claude: [Usa recall_memory(query="visão geral do projeto")]
        Este é o projeto Cortex. Encontrei que:
        - Usa Python 3.11+ com FastAPI
        - Modelo W5H para estruturar memórias
        - ...

Usuário: Resolvemos o bug de conexões que não fechavam

Claude: [Usa store_memory(
          what="Bug de conexões resolvido",
          why="Pool não fechava conexões após timeout",
          how="Context manager implementado",
          where="db/pool.py",
          visibility="shared"
        )]
        Anotado para todo o time do projeto!

Usuário: O que sabemos sobre problemas no pool?

Claude: [Usa recall_memory(query="problemas conexão", where="db/")]
        Encontrei que o bug de conexões foi resolvido com context manager...
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
