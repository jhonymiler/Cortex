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
    # Procura por todos os tipos de resultado (ordem de prioridade)
    LATEST_RESULT=$(ls -t \
        $RESULTS_DIR/full_comparison_*.json \
        $RESULTS_DIR/lightweight_*.json \
        $RESULTS_DIR/lightweight_*.checkpoint.json \
        $RESULTS_DIR/benchmark_*.summary.json \
        2>/dev/null | head -1)
fi

if [ -z "$LATEST_RESULT" ] || [ ! -f "$LATEST_RESULT" ]; then
    echo "❌ Nenhum resultado de benchmark encontrado em $RESULTS_DIR"
    echo "   Procurando por: full_comparison_*.json, lightweight_*.json, *.checkpoint.json"
    echo ""
    echo "📁 Arquivos disponíveis:"
    ls -la $RESULTS_DIR/*.json 2>/dev/null || echo "   (nenhum)"
    exit 1
fi

echo "📊 Analisando: $(basename $LATEST_RESULT)"
echo ""

# Detecta tipo de resultado e executa análise apropriada
if [[ "$(basename $LATEST_RESULT)" == full_comparison_* ]]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "1️⃣  Análise de Comparação (Cortex vs RAG vs Mem0)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    python $SCRIPT_DIR/analyze_comparison.py
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "1️⃣  Análise Completa do Benchmark"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    python $SCRIPT_DIR/analyze_graph.py
fi

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
