# Convenções da Estrutura de Documentação AI

Este documento descreve a organização da documentação para agentes de IA no projeto Cortex e as convenções para mantê-la.

---

## Princípio: Single Source of Truth

**Regra fundamental**: `.ai/` é a **única fonte de verdade** para toda documentação de agentes de IA. Todas as pastas específicas de IDEs (`.claude/`, `.cursor/`, `.agents/`, `.github/`) contêm apenas **symlinks** apontando para `.ai/` — nunca cópias.

**Por quê**: Elimina divergência. Alterar um arquivo em `.ai/` propaga instantaneamente para todas as IDEs. Impossível ter versões diferentes do mesmo conteúdo.

---

## Estrutura de Diretórios

```
cortex/
├── .ai/                          ← ÚNICA FONTE DE VERDADE
│   ├── INSTRUCTIONS.md           ← Contexto geral do projeto (100-180 linhas)
│   ├── CONVENTIONS.md            ← Este arquivo (regras de manutenção)
│   ├── skills/                   ← Conhecimento de domínio (Progressive Disclosure)
│   │   └── <nome-skill>/
│   │       ├── SKILL.md          ← Índice conciso (~40-60 linhas)
│   │       └── references/       ← Detalhes on-demand (tabelas, guias, troubleshooting)
│   ├── rules/                    ← Regras de código (Markdown com frontmatter)
│   │   ├── code-style.md
│   │   ├── architecture-patterns.md
│   │   └── testing.md
│   └── docs/                     ← Documentação técnica (referência)
│       ├── architecture.md
│       ├── database-schema.md
│       ├── w5h-model.md
│       ├── cognitive-principles.md
│       ├── api-contracts.md
│       ├── PROJECT-STATUS.md     ← Estado atual (atualizado frequentemente)
│       ├── RFC/                  ← Decisões arquiteturais
│       │   └── RFC-001-*.md
│       └── stories/              ← Tasks do backlog (contexto)
│
├── CLAUDE.md     → symlink → .ai/INSTRUCTIONS.md
├── AGENTS.md     → symlink → .ai/INSTRUCTIONS.md
│
├── .claude/
│   ├── CLAUDE.md → symlink → ../.ai/INSTRUCTIONS.md
│   ├── rules/    → symlink → ../.ai/rules/
│   └── skills/   → symlink → ../.ai/skills/
│
├── .cursor/
│   ├── rules/    → symlink → ../.ai/rules/
│   └── skills/   → symlink → ../.ai/skills/
│
├── .agents/
│   ├── rules/    → symlink → ../.ai/rules/
│   └── skills/   → symlink → ../.ai/skills/
│
└── .github/
    ├── copilot-instructions.md → symlink → ../.ai/INSTRUCTIONS.md
    ├── instructions/           → symlink → ../.ai/rules/
    └── skills/                 → symlink → ../.ai/skills/
```

---

## Mapa de Symlinks

### Symlinks Criados (Executar `./setup-ide-links.sh`)

| Localização | Target | IDE/Ferramenta |
|-------------|--------|----------------|
| `CLAUDE.md` | `.ai/INSTRUCTIONS.md` | Claude Code (raiz) |
| `AGENTS.md` | `.ai/INSTRUCTIONS.md` | Windsurf, outros agentes |
| `.claude/CLAUDE.md` | `../.ai/INSTRUCTIONS.md` | Claude Code |
| `.claude/rules/` | `../.ai/rules/` | Claude Code |
| `.claude/skills/` | `../.ai/skills/` | Claude Code |
| `.cursor/rules/` | `../.ai/rules/` | Cursor |
| `.cursor/skills/` | `../.ai/skills/` | Cursor |
| `.agents/rules/` | `../.ai/rules/` | Windsurf |
| `.agents/skills/` | `../.ai/skills/` | Windsurf |
| `.github/copilot-instructions.md` | `../.ai/INSTRUCTIONS.md` | GitHub Copilot |
| `.github/instructions/` | `../.ai/rules/` | GitHub Copilot |
| `.github/skills/` | `../.ai/skills/` | GitHub Copilot |

**IMPORTANTE**: Para adicionar suporte a uma nova IDE, criar apenas symlinks — nunca copiar conteúdo.

---

## Progressive Disclosure - 3 Camadas

Skills seguem modelo de **Progressive Disclosure** para economizar tokens:

| Camada | Momento | Conteúdo | Custo de tokens |
|--------|---------|----------|----------------|
| **1 - Discovery** | Startup (sempre) | `name` + `description` do frontmatter | ~3 linhas por skill |
| **2 - Índice** | Quando relevante | `SKILL.md` completo | ~40-60 linhas |
| **3 - On-demand** | Quando necessário | Arquivos em `references/` | Sob demanda |

**Regra**: Um agente deve conseguir responder ~70% das perguntas sobre o domínio apenas com o índice (camada 2).

---

## Template: Criar Nova Skill

### 1. Criar estrutura de diretórios

```bash
mkdir -p .ai/skills/<nome-skill>/references
```

### 2. Criar `SKILL.md` (Camada 2 - Índice)

```markdown
---
name: nome-da-skill
description: Descrição em terceira pessoa para discovery (CRÍTICO para relevância).
  Use when implementando X, debugando Y, ou entendendo Z.
  Mention specific domain terms: term1, term2, term3.
---

# Título da Skill

Propósito em 1-2 frases.

## Quando Usar

- Trigger 1 — situação específica
- Trigger 2 — situação específica
- Trigger 3 — situação específica

## Resumo Rápido

| Item | Valor | Observação |
|------|-------|------------|
| ... | ... | ... |

## Conceitos-Chave

- **Conceito A**: Explicação concisa
- **Conceito B**: Explicação concisa

## Referências

- [GUIDE.md](references/GUIDE.md) — guia operacional passo a passo
- [REFERENCE.md](references/REFERENCE.md) — tabelas e dados de referência
- [TROUBLESHOOTING.md](references/TROUBLESHOOTING.md) — erros comuns e soluções (opcional)
```

**Tamanho alvo**: 40-60 linhas. Mais de 60 = mover para `references/`.

### 3. Criar arquivos em `references/` (Camada 3 - On-demand)

Criar apenas se necessário (>30 linhas ou informação raramente usada):

- **`GUIDE.md`**: Guia operacional (como fazer passo a passo)
- **`REFERENCE.md`**: Dados de referência (tabelas, payloads, mapeamentos)
- **`TROUBLESHOOTING.md`**: Erros comuns e soluções (opcional)

### 4. Atualizar `INSTRUCTIONS.md`

Adicionar linha na tabela de skills:

```markdown
| **[nome-skill](skills/nome-skill/SKILL.md)** | Quando usar | Resumo do conteúdo |
```

---

## Template: Criar Nova Rule

### 1. Criar arquivo em `.ai/rules/`

```bash
touch .ai/rules/nome-da-rule.md
```

### 2. Conteúdo com frontmatter

```markdown
---
applyTo: "**/*.py"   # Glob pattern - ex: **/*.{py,pyi}, src/**/*.py
paths:
  - "src/**"
  - "tests/**"
---

# Nome da Regra

## Seção 1: Tópico

- **Regra concisa**: [O que fazer] — [Por que fazer assim]
  - Exemplo: Preferir `Path` do `pathlib` sobre `os.path` — type-safe e orientado a objetos
- **Regra concisa**: [O que fazer] — [Por que fazer assim]

## Seção 2: Outro Tópico

- **Regra concisa**: [O que fazer] — [Por que fazer assim]

## Exemplos

### ✅ Bom
```python
# Código seguindo a regra
```

### ❌ Ruim
```python
# Código violando a regra
```
```

**Dica**: Rules eficazes têm três elementos: **o quê fazer**, **como fazer**, **por quê** (quando não é óbvio).

---

## Template: Criar RFC (Decisão Arquitetural)

```bash
touch .ai/docs/RFC/RFC-NNN-titulo-curto.md
```

```markdown
# RFC-NNN: Título da Decisão

**Status**: Aceito | Em discussão | Descontinuado
**Data**: YYYY-MM-DD
**Autor**: Nome

## Contexto

[Problema ou necessidade que motivou a decisão]

## Decisão

[O que foi decidido, em 1-3 frases claras]

## Consequências

- **Positivas**: [benefícios esperados]
- **Negativas**: [trade-offs aceitos]

## Alternativas Consideradas

- **Alternativa A**: [descrição] — rejeitada porque [motivo]
- **Alternativa B**: [descrição] — rejeitada porque [motivo]

## Referências

- Link para issue/PR
- Documentação relacionada
```

---

## Regras para Agentes de IA

Quando trabalhar neste projeto, o agente de IA deve:

### ✅ SEMPRE

1. **Criar/editar arquivos apenas em `.ai/`** — nunca em pastas de IDEs (`.claude/`, `.cursor/`, etc)
2. **Usar templates acima** ao criar skills, rules ou RFCs
3. **Manter `SKILL.md` entre 40-60 linhas** — mover excesso para `references/`
4. **Escrever `description` no frontmatter focada em gatilhos** — mencionar termos de domínio específicos
5. **Documentar decisões não-óbvias** — criar RFC quando decisão arquitetural não é evidente no código
6. **Atualizar `PROJECT-STATUS.md`** após mudanças significativas de comportamento

### ❌ NUNCA

1. **Criar cópias de conteúdo** em pastas de IDEs — apenas symlinks
2. **Editar symlinks** — symlinks são apenas ponteiros, editar o target em `.ai/`
3. **Duplicar informação** entre skills e docs — referenciar docs existentes
4. **Criar skills com >80 linhas** — usar progressive disclosure (mover detalhes para `references/`)
5. **Deletar `.ai/CONVENTIONS.md`** — este arquivo é crítico para auto-manutenção

### Quando Adicionar Nova IDE

Executar comandos de symlink manualmente ou adicionar no script `setup-ide-links.sh`:

```bash
# Exemplo: adicionar suporte para IDE "NovaIDE"
mkdir -p .nova-ide
ln -sf ../.ai/INSTRUCTIONS.md .nova-ide/INSTRUCTIONS.md
ln -sf ../.ai/skills .nova-ide/skills
ln -sf ../.ai/rules .nova-ide/rules
```

---

## Manutenção Contínua

### Gatilhos para Atualização de Documentação

| Evento no código | Ação esperada do agente |
|------------------|-------------------------|
| Código implementado que muda fluxo de uma skill | Propor atualização da skill antes de encerrar |
| Decisão arquitetural tomada durante conversa | Propor criação de RFC ou atualização de `architecture.md` |
| Regra de negócio mencionada que não está documentada | Perguntar se deve ser adicionada à skill ou docs |
| Bug corrigido que revela comportamento não documentado | Propor documentar o comportamento correto |
| Nova integração, API ou dependência adicionada | Verificar se precisa de skill própria ou atualizar existente |

### Protocolo de Encerramento de Sessão

Ao final de qualquer sessão onde houve mudanças relevantes, o agente deve:

1. Listar as mudanças de comportamento feitas no código
2. Identificar quais skills e docs são afetados
3. Perguntar ao usuário: *"As seguintes documentações precisam ser atualizadas: [lista]. Deseja que eu atualize agora?"*

### Guardião da Documentação

O agente deve identificar ativamente quando código contradiz documentação existente e reportar, mesmo sem pedido:

**Exemplo**:
> "Percebo que o código implementado agora envia um campo adicional na requisição, mas a skill 'api-integration' documenta apenas os campos originais. Deseja que eu atualize a skill com o novo campo e sua regra de derivação?"

---

## Métricas de Qualidade

| Métrica | Alvo |
|---------|------|
| Linhas em `INSTRUCTIONS.md` | 100-180 |
| Linhas médias por `SKILL.md` | 40-60 |
| Arquivos em `references/` por skill | 1-3 |
| Skills totais | 5-10 |
| Rules totais | 3-7 |
| % de perguntas resolvidas sem consulta ao dev | >70% |
| Tempo para agente novo começar a contribuir | <10 min |

---

## Troubleshooting

### Problema: Symlink quebrado

```bash
# Verificar symlinks
ls -l CLAUDE.md
ls -l .claude/

# Recriar todos os symlinks
./setup-ide-links.sh
```

### Problema: IDE não reconhece symlinks

**Causa**: Windows sem permissões ou modo desenvolvedor desativado

**Solução**:
1. Ativar Developer Mode no Windows
2. Ou executar terminal como Administrador
3. Ou configurar Git: `git config core.symlinks true`

### Problema: Skill muito grande (>80 linhas)

**Solução**: Aplicar Progressive Disclosure
1. Manter índice (conceitos-chave, resumo) em `SKILL.md`
2. Mover detalhes (tabelas grandes, guias passo a passo) para `references/GUIDE.md` ou `REFERENCE.md`
3. Linkar de `SKILL.md` para `references/`

---

## Referências Externas

- **Artigo original**: Este sistema é baseado no guia "Documentação AI Multi-IDE: Single Source of Truth com Progressive Disclosure"
- **Claude Code docs**: https://docs.anthropic.com/claude-code
- **Skills pattern**: https://docs.anthropic.com/claude-code/guides/skills
