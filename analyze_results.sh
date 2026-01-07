#!/bin/bash
# Script para análise completa dos resultados do Cortex Benchmark
# Usage: ./analyze_results.sh [checkpoint_file]

set -e

RESULTS_DIR="benchmark/results"
SCRIPT_DIR="benchmark"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧠 CORTEX BENCHMARK - ANÁLISE DE RESULTADOS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Verifica se há resultados
if [ ! -d "$RESULTS_DIR" ]; then
    echo "❌ Diretório de resultados não encontrado: $RESULTS_DIR"
    exit 1
fi

# Ativa ambiente virtual
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Ativando ambiente virtual..."
    source venv/bin/activate
fi

# Encontra o resultado mais recente
if [ -n "$1" ]; then
    LATEST_RESULT="$1"
else
    # Procura por checkpoint ou summary
    LATEST_RESULT=$(ls -t $RESULTS_DIR/lightweight_*.checkpoint.json $RESULTS_DIR/lightweight_*.json $RESULTS_DIR/benchmark_*.summary.json 2>/dev/null | head -1)
fi

if [ -z "$LATEST_RESULT" ] || [ ! -f "$LATEST_RESULT" ]; then
    echo "❌ Nenhum resultado de benchmark encontrado em $RESULTS_DIR"
    echo "   Procurando por: lightweight_*.json, *.checkpoint.json ou benchmark_*.summary.json"
    exit 1
fi

echo "📊 Analisando: $(basename $LATEST_RESULT)"
echo ""

# Executa análise do grafo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  Análise Completa do Benchmark"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python $SCRIPT_DIR/analyze_graph.py

# Verifica se analyze_hubs.py existe
if [ -f "$SCRIPT_DIR/analyze_hubs.py" ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "2️⃣  Análise de Hubs (Entidades Centrais)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    python $SCRIPT_DIR/analyze_hubs.py 2>/dev/null || echo "   ⚠️  Análise de hubs não disponível"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Análise concluída!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📁 Arquivos disponíveis:"
ls -la $RESULTS_DIR/*.json 2>/dev/null | tail -5 || echo "   (nenhum arquivo JSON)"
echo ""
