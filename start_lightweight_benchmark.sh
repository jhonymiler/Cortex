#!/bin/bash
# Script para executar benchmark leve facilmente

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 CORTEX LIGHTWEIGHT BENCHMARK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Configura data dir
export CORTEX_DATA_DIR="$(pwd)/data"

# Verifica se é resume (se primeiro argumento começar com --resume ou tiver --resume)
IS_RESUME=false
for arg in "$@"; do
    if [[ "$arg" == --resume* ]] || [[ "$arg" == --checkpoint* ]]; then
        IS_RESUME=true
        break
    fi
done

# Limpa processos anteriores
echo "🧹 Limpando processos anteriores..."
pkill -f "cortex-api" 2>/dev/null || true
sleep 1
echo "   ✓ Processos limpos"

# Limpa dados APENAS se NÃO for resume
if [ "$IS_RESUME" = false ]; then
    echo "🧹 Limpando grafo de memória..."
    rm -f "$CORTEX_DATA_DIR/benchmark/memory_graph.json" 2>/dev/null || true
    echo "   ✓ Grafo resetado"
else
    echo "⏩ Modo RESUME - mantendo grafo existente"
fi

# Verifica se está no ambiente virtual
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Ativando ambiente virtual..."
    source venv/bin/activate
fi

# Verifica Ollama
echo "🔍 Verificando Ollama..."
if ! curl -s http://localhost:11434/api/version > /dev/null; then
    echo "❌ Ollama não está rodando!"
    echo "   Execute: ollama serve"
    exit 1
fi
echo "   ✓ Ollama OK"

# Verifica modelo
echo "🔍 Verificando modelo deepseek-v3.1:671b-cloud..."
if ! ollama list | grep -q "deepseek-v3.1:671b-cloud"; then
    echo "⚠️  Modelo não encontrado. Baixando..."
    ollama pull deepseek-v3.1:671b-cloud
fi
echo "   ✓ Modelo OK"

# Verifica/Inicia Cortex API
echo "🔍 Verificando Cortex API..."
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "⚠️  API não está rodando. Iniciando..."
    
    # Inicia API em background com data dir do projeto
    CORTEX_DATA_DIR="$(pwd)/data" nohup cortex-api > /tmp/cortex-api.log 2>&1 &
    API_PID=$!
    echo "   PID da API: $API_PID"
    
    # Aguarda API estar pronta (max 30s)
    echo -n "   Aguardando API iniciar"
    for i in {1..30}; do
        if curl -s http://localhost:8000/health > /dev/null; then
            echo " ✓"
            break
        fi
        echo -n "."
        sleep 1
    done
    
    # Verifica se conseguiu iniciar
    if ! curl -s http://localhost:8000/health > /dev/null; then
        echo ""
        echo "❌ Falha ao iniciar API. Verifique logs:"
        echo "   tail -f /tmp/cortex-api.log"
        exit 1
    fi
    
    echo "   ✓ API iniciada com sucesso!"
    CORTEX_API_STARTED=1
else
    echo "   ✓ Cortex API OK"
    CORTEX_API_STARTED=0
fi

echo ""
echo "✅ Todos os serviços estão prontos!"
echo ""

# Executa benchmark (passa todos os argumentos)
if [ "$1" == "--full" ]; then
    echo "🚀 Executando benchmark COMPLETO..."
    python run_lightweight_benchmark.py --full
elif [ "$1" == "--quick" ]; then
    echo "🚀 Executando benchmark RÁPIDO..."
    python run_lightweight_benchmark.py --quick
elif [ "$IS_RESUME" = true ]; then
    echo "🚀 Continuando benchmark..."
    python run_lightweight_benchmark.py "$@"
elif [ -n "$1" ]; then
    echo "🚀 Executando com domínio: $1"
    python run_lightweight_benchmark.py --domain "$1" --conversations 2
else
    echo "🚀 Executando benchmark PADRÃO (1 conv/domínio, 3 sessões)..."
    python run_lightweight_benchmark.py
fi

# Cleanup - para API se foi iniciada por este script
if [ "$CORTEX_API_STARTED" == "1" ]; then
    echo ""
    echo "🛑 Parando Cortex API..."
    # Encontra e mata o processo da API
    pkill -f "cortex-api" || true
    echo "   ✓ API encerrada"
fi
