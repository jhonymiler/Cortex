#!/bin/bash
# Script para análise completa dos resultados do Cortex Benchmark
# Usage: ./analyze_results.sh

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

# Encontra o resultado mais recente
LATEST_SUMMARY=$(ls -t $RESULTS_DIR/benchmark_*.summary.json 2>/dev/null | head -1)

if [ -z "$LATEST_SUMMARY" ]; then
    echo "❌ Nenhum resultado de benchmark encontrado em $RESULTS_DIR"
    exit 1
fi

echo "📊 Resultado mais recente: $(basename $LATEST_SUMMARY)"
echo ""

# Executa análises
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  Análise Geral do Grafo"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python $SCRIPT_DIR/analyze_graph.py

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  Análise de Hubs (Nós Centrais)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python $SCRIPT_DIR/analyze_hubs.py

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Análise concluída!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📁 Relatórios disponíveis:"
echo "   - $RESULTS_DIR/PRELIMINARY_REPORT.md (análise detalhada)"
echo "   - $RESULTS_DIR/VISUAL_SUMMARY.md (resumo visual)"
echo ""
echo "💡 Próximos passos:"
echo "   1. Aguardar rate limit resetar"
echo "   2. Executar: ./start_benchmark.sh --resume"
echo "   3. Completar os 7 domínios restantes"
echo ""
