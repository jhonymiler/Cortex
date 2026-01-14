#!/bin/bash
# Cortex Benchmark Suite
# "Porque agentes inteligentes precisam de memória inteligente"

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧠 CORTEX BENCHMARK SUITE"
echo "   \"Porque agentes inteligentes precisam de memória inteligente\""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Carrega .env
if [ -f .env ]; then
    set -a && source .env && set +a
fi

# Configuração
export CORTEX_DATA_DIR="${CORTEX_DATA_DIR:-./data}"
export OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
export CORTEX_LLM_MODEL="${CORTEX_LLM_MODEL:-llama3.2:3b}"

echo "⚙️  Configuração:"
echo "   OLLAMA_URL=$OLLAMA_URL"
echo "   CORTEX_LLM_MODEL=$CORTEX_LLM_MODEL"
echo ""

# Ativa venv
[ -d "venv" ] && source venv/bin/activate

# Executa benchmark realista
if [ "${1:-realistic}" = "realistic" ]; then
    python -m benchmark.realistic_benchmark ${2:+--$2}
elif [ "$1" = "v2" ]; then
    python benchmark/v2_validation.py
else
    echo "Uso: ./start_benchmark.sh [realistic|v2] [quick]"
    exit 1
fi
