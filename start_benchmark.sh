#!/bin/bash
# Cortex Professional Benchmark
# "Porque agentes inteligentes precisam de memória inteligente"
#
# Este script executa o benchmark profissional unificado que demonstra:
# - Excelência Técnica (Accuracy, Performance, Scalability)
# - Inteligência Cognitiva (Decay, Consolidation, Learning)
# - Valor Comercial (ROI, Cost Reduction, Developer Experience)
# - Segurança & Compliance (Jailbreak Detection, Data Isolation)
# - Vantagem Competitiva (vs. RAG, Mem0, Baseline)

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧠 CORTEX PROFESSIONAL BENCHMARK"
echo "   \"Porque agentes inteligentes precisam de memória inteligente\""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# === CONFIGURAÇÃO ===
export CORTEX_DATA_DIR="$(pwd)/data"
export CORTEX_PORT=8000

# Carrega .env se existir
if [ -f .env ]; then
    echo "📂 Carregando .env..."
    set -a && source .env && set +a
fi

# Usa OLLAMA_URL do .env ou detecta automaticamente
if [ -n "$OLLAMA_URL" ]; then
    export OLLAMA_BASE_URL="$OLLAMA_URL"
    echo "📌 OLLAMA_BASE_URL=$OLLAMA_BASE_URL (do .env)"
elif [ -z "$OLLAMA_BASE_URL" ]; then
    if grep -qi microsoft /proc/version 2>/dev/null; then
        WINDOWS_IP=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}')
        export OLLAMA_BASE_URL="http://${WINDOWS_IP}:11434"
        echo "🪟 WSL: OLLAMA_BASE_URL=$OLLAMA_BASE_URL"
    else
        export OLLAMA_BASE_URL="http://localhost:11434"
        echo "🖥️  Native: OLLAMA_BASE_URL=$OLLAMA_BASE_URL"
    fi
fi

# === FUNÇÕES ===

check_ollama() {
    echo "🔍 Verificando Ollama..."
    if curl -s "$OLLAMA_BASE_URL/api/tags" > /dev/null 2>&1; then
        echo "   ✅ Ollama disponível"
        return 0
    else
        echo "   ⚠️  Ollama não disponível (benchmarks sem embedding)"
        return 1
    fi
}

show_help() {
    cat << EOF
Uso: ./start_benchmark.sh [MODO]

Modos de Execução:
  full         Benchmark completo (padrão) - Todas as 5 dimensões
  quick        Testes essenciais - Execução rápida (~30s)
  paper        Métricas para papers acadêmicos
  commercial   Métricas de valor comercial (ROI, cost reduction)

  --help, -h   Mostra esta ajuda

Dimensões Avaliadas:
  1. 📊 Excelência Técnica    - Accuracy, performance, scalability
  2. 🧠 Inteligência Cognitiva - Decay, consolidation, learning
  3. 💰 Valor Comercial        - Cost reduction, ROI, developer experience
  4. 🔒 Segurança & Compliance - Jailbreak detection, data isolation
  5. 🏆 Vantagem Competitiva   - Feature matrix vs. competitors

Saídas Geradas:
  - JSON: benchmark_results/professional_benchmark_<timestamp>.json
  - Markdown: benchmark_results/professional_report_<timestamp>.md
  - Gráficos: benchmark_results/charts/*.png (se matplotlib disponível)

Exemplos:
  ./start_benchmark.sh              # Benchmark completo
  ./start_benchmark.sh quick        # Testes essenciais (rápido)
  ./start_benchmark.sh paper        # Para publicação acadêmica
  ./start_benchmark.sh commercial   # Para business case

EOF
}

run_benchmark() {
    MODE=${1:-full}

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🚀 EXECUTANDO BENCHMARK: modo=$MODE"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Executa benchmark profissional
    python -m benchmark.professional_benchmark --mode "$MODE"

    RESULT=$?

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if [ $RESULT -eq 0 ]; then
        echo "✅ BENCHMARK CONCLUÍDO COM SUCESSO"
        echo "   Pass rate >= 80%"
    else
        echo "⚠️  BENCHMARK CONCLUÍDO COM AVISOS"
        echo "   Pass rate < 80% - Revisar resultados"
    fi
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "📊 Resultados salvos em: ./benchmark_results/"
    echo "   - JSON: professional_benchmark_*.json"
    echo "   - Markdown: professional_report_*.md"
    echo "   - Gráficos: charts/*.png"
    echo ""

    return $RESULT
}

run_v2_validation() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔬 VALIDAÇÃO V2.0 (6 Melhorias Científicas)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    python experiments/07_test_improvements.py

    echo ""
}

# === MAIN ===

# Ativa venv se existir
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Processa argumentos
case "${1:-}" in
    --help|-h|help)
        show_help
        exit 0
        ;;
    full|quick|paper|commercial)
        check_ollama  # Continua mesmo se falhar
        run_benchmark "$1"
        exit $?
        ;;
    v2|--v2)
        run_v2_validation
        exit 0
        ;;
    "")
        check_ollama  # Continua mesmo se falhar
        run_benchmark "full"
        exit $?
        ;;
    *)
        echo "❌ Modo desconhecido: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
