#!/bin/bash
# setup-ide-links.sh
# Automatiza criação de symlinks para IDEs (Single Source of Truth)

set -e

echo "🔗 Criando symlinks para estrutura .ai/ (Single Source of Truth)"

# Raiz do projeto
echo "📝 Criando symlinks na raiz..."
ln -sf .ai/INSTRUCTIONS.md CLAUDE.md
ln -sf .ai/INSTRUCTIONS.md AGENTS.md

# Claude Code
echo "📝 Criando symlinks para Claude Code (.claude/)..."
mkdir -p .claude
ln -sf ../.ai/INSTRUCTIONS.md .claude/CLAUDE.md
ln -sf ../.ai/rules .claude/rules
ln -sf ../.ai/skills .claude/skills

# Cursor
echo "📝 Criando symlinks para Cursor (.cursor/)..."
mkdir -p .cursor
ln -sf ../.ai/rules .cursor/rules
ln -sf ../.ai/skills .cursor/skills

# Windsurf / Outros agentes
echo "📝 Criando symlinks para Windsurf (.agents/)..."
mkdir -p .agents
ln -sf ../.ai/rules .agents/rules
ln -sf ../.ai/skills .agents/skills

# GitHub Copilot
echo "📝 Criando symlinks para GitHub Copilot (.github/)..."
mkdir -p .github
ln -sf ../.ai/INSTRUCTIONS.md .github/copilot-instructions.md
ln -sf ../.ai/rules .github/instructions
ln -sf ../.ai/skills .github/skills

echo "✅ Symlinks criados com sucesso!"
echo ""
echo "Estrutura criada:"
echo "  - CLAUDE.md → .ai/INSTRUCTIONS.md"
echo "  - AGENTS.md → .ai/INSTRUCTIONS.md"
echo "  - .claude/CLAUDE.md, rules/, skills/"
echo "  - .cursor/rules/, skills/"
echo "  - .agents/rules/, skills/"
echo "  - .github/copilot-instructions.md, instructions/, skills/"
echo ""
echo "⚠️  Lembre-se: Edite apenas arquivos em .ai/ — symlinks propagam automaticamente"
