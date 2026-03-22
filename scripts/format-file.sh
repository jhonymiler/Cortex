#!/bin/bash
# scripts/format-file.sh
# Auto-formata arquivo após Edit ou Write

FILE="$1"
[ -z "$FILE" ] && exit 0

# Formatar baseado em extensão
case "$FILE" in
  *.py)
    # Usar ruff para formatação Python
    ruff format "$FILE" 2>/dev/null || true
    ;;
  *.json)
    # Formatação JSON (se jq estiver disponível)
    if command -v jq >/dev/null 2>&1; then
      tmp=$(mktemp)
      jq '.' "$FILE" > "$tmp" 2>/dev/null && mv "$tmp" "$FILE" || rm -f "$tmp"
    fi
    ;;
  *.md)
    # Markdown (prettier se disponível)
    if command -v prettier >/dev/null 2>&1; then
      prettier --write "$FILE" 2>/dev/null || true
    fi
    ;;
esac

# Nunca falha — formatter ausente não deve bloquear o agente
exit 0
