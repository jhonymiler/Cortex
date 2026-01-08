#!/bin/bash
# Script para executar benchmark do Cortex
# Foco em VALOR (qualidade) não apenas velocidade/tokens

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎯 CORTEX BENCHMARK"
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
    
    # Inicia em background
    CORTEX_DATA_DIR="$CORTEX_DATA_DIR" python -m uvicorn cortex.api.app:app \
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

run_paper_benchmark() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 BENCHMARK PARA PAPER (Cortex isolado)"
    echo "   Métricas completas para publicação acadêmica"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    python benchmark/paper_benchmark.py --save
    
    # Executa análise automática
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 ANÁLISE DE RESULTADOS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    bash ./analyze_results.sh
}

run_comparison_benchmark() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 BENCHMARK COMPARATIVO"
    echo "   Cortex vs Baseline vs RAG vs Mem0"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    python benchmark/comparison_benchmark.py --save
}

show_help() {
    echo "Uso: ./start_benchmark.sh [COMANDO]"
    echo ""
    echo "Comandos:"
    echo "  (sem args)       Benchmark para paper (padrão)"
    echo "  --paper          Benchmark completo para paper acadêmico"
    echo "  --compare        Benchmark comparativo (Cortex vs RAG vs Mem0)"
    echo "  --api-only       Apenas inicia a API"
    echo "  --stop           Para a API"
    echo ""
    echo "Exemplos:"
    echo "  ./start_benchmark.sh              # Benchmark para paper"
    echo "  ./start_benchmark.sh --compare    # Compara com RAG/Mem0"
    echo "  ./start_benchmark.sh --api-only   # Só inicia API"
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
    --compare)
        check_ollama || exit 1
        check_embedding_model
        start_api || exit 1
        clean_benchmark_data
        run_comparison_benchmark
        stop_api
        ;;
    --paper|"")
        check_ollama || exit 1
        check_embedding_model
        start_api || exit 1
        clean_benchmark_data
        run_paper_benchmark
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
