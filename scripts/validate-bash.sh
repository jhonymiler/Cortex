#!/bin/bash
# scripts/validate-bash.sh
# Valida comandos Bash antes de execução (PreToolUse hook)

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# Padrões nunca permitidos sem confirmação explícita
if echo "$CMD" | grep -qE '(rm -rf /|DROP TABLE|TRUNCATE |DELETE FROM [^W]|git push --force|git reset --hard)'; then
  echo '{"action": "deny", "reason": "Comando potencialmente destrutivo. Execute manualmente se intencional."}'
  exit 0
fi

# Padrões que requerem confirmação do usuário
if echo "$CMD" | grep -qE '(rm -rf|DROP DATABASE|git push.*main|git push.*master)'; then
  echo '{"action": "request_permission", "reason": "Comando perigoso - confirmar antes de executar."}'
  exit 0
fi

# Permitir comando
echo '{"action": "allow"}'
exit 0
