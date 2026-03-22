#!/bin/bash
# scripts/run-tests-if-changed.sh
# Roda testes se arquivos relevantes foram modificados (Stop hook)

# Detecta arquivos alterados
CHANGED=$(git diff --name-only HEAD 2>/dev/null)
[ -z "$CHANGED" ] && exit 0

# Verifica se há mudanças em arquivos Python
if echo "$CHANGED" | grep -qE '\.(py|pyi)$'; then
    echo "📝 Arquivos Python modificados. Rodando testes..."

    # Rodar testes rápidos (excluindo testes lentos)
    pytest -m "not slow" --tb=short -q 2>&1 | tail -20

    # Capturar exit code
    TEST_EXIT=$?

    if [ $TEST_EXIT -eq 0 ]; then
        echo "✅ Testes passaram"
    else
        echo "❌ Alguns testes falharam. Revise os erros acima."
    fi
fi

# Nunca falha — testes falhando não devem bloquear o agente (apenas avisar)
exit 0
