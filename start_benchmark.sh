#!/bin/bash
# Script para executar benchmark do Cortex
# "Porque agentes inteligentes precisam de memória inteligente"
#
# Mede o VALOR REAL do sistema em 4 dimensões:
# 1. Cognição Biológica (decay, consolidação, hubs)
# 2. Memória Coletiva (compartilhamento, isolamento)
# 3. Valor Semântico (acurácia, relevância)
# 4. Eficiência (latência, tokens)

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧠 CORTEX BENCHMARK"
echo "   \"Porque agentes inteligentes precisam de memória inteligente\""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

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
    fi
fi

# === FUNÇÕES ===

check_ollama() {
    echo "🔍 Verificando Ollama..."
    if curl -s "$OLLAMA_BASE_URL/api/tags" > /dev/null 2>&1; then
        echo "   ✅ Ollama disponível"
        return 0
    else
        echo "   ❌ Ollama não disponível em $OLLAMA_BASE_URL"
        return 1
    fi
}

check_embedding_model() {
    echo "🔍 Verificando modelo de embedding..."
    MODEL=${CORTEX_EMBEDDING_MODEL:-"qwen3-embedding:0.6b"}
    MODELS=$(curl -s "$OLLAMA_BASE_URL/api/tags" | python3 -c "import json,sys; print(' '.join(m['name'] for m in json.load(sys.stdin).get('models',[])))" 2>/dev/null)
    
    if echo "$MODELS" | grep -q "$MODEL"; then
        echo "   ✅ Modelo $MODEL disponível"
        return 0
    else
        echo "   ⚠️ Modelo $MODEL não encontrado. Instalando..."
        curl -s -X POST "$OLLAMA_BASE_URL/api/pull" -d "{\"name\":\"$MODEL\"}" > /dev/null
        return 0
    fi
}

start_api() {
    echo "🚀 Iniciando API Cortex..."
    
    # Para processos anteriores
    pkill -f "uvicorn cortex" 2>/dev/null || true
    sleep 2
    
    # Inicia em background (passa todas as variáveis de ambiente necessárias)
    CORTEX_DATA_DIR="$CORTEX_DATA_DIR" \
    OLLAMA_URL="$OLLAMA_BASE_URL" \
    OLLAMA_BASE_URL="$OLLAMA_BASE_URL" \
    python -m uvicorn cortex.api.app:app \
        --host 0.0.0.0 --port $CORTEX_PORT > /tmp/cortex_api.log 2>&1 &
    
    # Aguarda startup
    for i in {1..10}; do
        if curl -s "http://localhost:$CORTEX_PORT/health" | grep -q "healthy"; then
            echo "   ✅ API rodando em http://localhost:$CORTEX_PORT"
            return 0
        fi
        sleep 1
    done
    
    echo "   ❌ Falha ao iniciar API"
    cat /tmp/cortex_api.log
    return 1
}

stop_api() {
    echo "🛑 Parando API..."
    pkill -f "uvicorn cortex" 2>/dev/null || true
}

clean_benchmark_data() {
    echo "🧹 Limpando dados de benchmark anteriores..."
    rm -rf "$CORTEX_DATA_DIR/comparison_*" 2>/dev/null || true
    rm -rf "$CORTEX_DATA_DIR/paper_bench*" 2>/dev/null || true
}

run_unified_benchmark() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 BENCHMARK UNIFICADO (4 Dimensões de Valor)"
    echo "   Cortex vs Baseline vs RAG vs Mem0"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    python -m benchmark.unified_benchmark --save
}

run_paper_benchmark() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 BENCHMARK PAPER (Cortex isolado)"
    echo "   Métricas para publicação acadêmica"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    python -m benchmark.paper_benchmark --save
    
    # Executa análise automática
    if [ -f "./analyze_results.sh" ]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📊 ANÁLISE DE RESULTADOS"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        bash ./analyze_results.sh
    fi
}

run_locomo_benchmark() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 BENCHMARK LoCoMo (Long-term Conversational Memory)"
    echo "   Padrão da indústria para avaliação de memória LLM"
    echo "   Métricas: F1, BLEU-1, Exact Match, Recall@K"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    python -m benchmark.locomo_benchmark
}

run_real_comparison() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 COMPARATIVO REAL (Cortex vs RAG vs Mem0)"
    echo "   RAG com embeddings reais (não TF-IDF)"
    echo "   Mem0 real quando disponível"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    python -m benchmark.real_comparison_benchmark --save
}

run_ablation_study() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔬 ABLATION STUDY"
    echo "   Análise de contribuição de cada componente"
    echo "   W5H, Decay, Hub, Namespace, Threshold"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    python -m benchmark.ablation_study --save --chart
}

generate_charts() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 GERAÇÃO DE GRÁFICOS PARA PAPER"
    echo "   Comparativo, Radar, Latência, Ebbinghaus, Arquitetura"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Verifica se matplotlib está instalado
    if ! python -c "import matplotlib" 2>/dev/null; then
        echo "⚠️ matplotlib não instalado. Instalando..."
        pip install matplotlib numpy
    fi
    
    python -m benchmark.generate_paper_charts
}

run_full_paper_suite() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📚 SUITE COMPLETA PARA PAPER ACADÊMICO"
    echo "   1. Paper Benchmark (métricas Cortex)"
    echo "   2. Comparativo Real (vs RAG/Mem0)"
    echo "   3. Ablation Study"
    echo "   4. Geração de Gráficos"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # 1. Paper Benchmark
    run_paper_benchmark
    
    # 2. Comparativo Real
    run_real_comparison
    
    # 3. Ablation Study
    run_ablation_study
    
    # 4. Gráficos
    generate_charts
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "✅ SUITE COMPLETA FINALIZADA!"
    echo "   Resultados em: ./benchmark_results/"
    echo "   Gráficos em: ./benchmark_results/charts/"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

show_help() {
    echo "Uso: ./start_benchmark.sh [COMANDO]"
    echo ""
    echo "🧠 Cortex Benchmark - Mede o valor real do sistema de memória cognitiva"
    echo ""
    echo "Comandos principais:"
    echo "  (sem args)       Benchmark unificado (padrão) - 4 dimensões de valor"
    echo "  --paper          Benchmark para paper acadêmico (Cortex isolado)"
    echo "  --full-paper     Suite completa para paper (benchmark + comparativo + ablation + gráficos)"
    echo ""
    echo "Comandos avançados:"
    echo "  --unified        Benchmark unificado (Cortex vs RAG vs Mem0 vs Baseline)"
    echo "  --real-compare   Comparativo real (RAG com embeddings, Mem0 real)"
    echo "  --ablation       Ablation Study (contribuição de cada componente)"
    echo "  --charts         Gera gráficos para publicação"
    echo "  --locomo         Benchmark LoCoMo (padrão da indústria)"
    echo ""
    echo "Utilitários:"
    echo "  --api-only       Apenas inicia a API"
    echo "  --stop           Para a API"
    echo ""
    echo "Dimensões de Valor medidas:"
    echo "  1. Cognição Biológica  - Decay, consolidação, hubs"
    echo "  2. Memória Coletiva    - Compartilhamento, isolamento"
    echo "  3. Valor Semântico     - Acurácia, relevância"
    echo "  4. Eficiência          - Latência, tokens"
    echo ""
    echo "Exemplos:"
    echo "  ./start_benchmark.sh              # Benchmark unificado completo"
    echo "  ./start_benchmark.sh --paper      # Métricas para paper (Cortex)"
    echo "  ./start_benchmark.sh --full-paper # Suite completa para publicação"
    echo "  ./start_benchmark.sh --charts     # Gera gráficos PNG/PDF"
}

# === MAIN ===

# Ativa venv
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Processa argumentos
case "${1:-}" in
    --help|-h)
        show_help
        exit 0
        ;;
    --stop)
        stop_api
        exit 0
        ;;
    --api-only)
        check_ollama || exit 1
        check_embedding_model
        start_api
        echo ""
        echo "API rodando. Use './start_benchmark.sh --stop' para parar."
        exit 0
        ;;
    --compare|--unified)
        check_ollama || exit 1
        check_embedding_model
        start_api || exit 1
        clean_benchmark_data
        run_unified_benchmark
        stop_api
        ;;
    --paper)
        check_ollama || exit 1
        check_embedding_model
        start_api || exit 1
        clean_benchmark_data
        run_paper_benchmark
        stop_api
        ;;
    --locomo)
        check_ollama || exit 1
        check_embedding_model
        clean_benchmark_data
        run_locomo_benchmark
        ;;
    --real-compare|--real-comparison)
        check_ollama || exit 1
        check_embedding_model
        start_api || exit 1
        clean_benchmark_data
        run_real_comparison
        stop_api
        ;;
    --ablation)
        check_ollama || exit 1
        check_embedding_model
        start_api || exit 1
        clean_benchmark_data
        run_ablation_study
        stop_api
        ;;
    --charts)
        generate_charts
        ;;
    --full-paper)
        check_ollama || exit 1
        check_embedding_model
        start_api || exit 1
        clean_benchmark_data
        run_full_paper_suite
        stop_api
        ;;
    "")
        check_ollama || exit 1
        check_embedding_model
        start_api || exit 1
        clean_benchmark_data
        run_unified_benchmark
        stop_api
        ;;
    *)
        echo "Comando desconhecido: $1"
        show_help
        exit 1
        ;;
esac

echo ""
echo "✅ Benchmark concluído!"
