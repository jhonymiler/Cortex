#!/bin/bash
# Script para executar benchmark leve facilmente

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 CORTEX LIGHTWEIGHT BENCHMARK"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Configura data dir
export CORTEX_DATA_DIR="$(pwd)/data"

# Carrega .env se existir
if [ -f .env ]; then
    echo "📂 Carregando variáveis de .env..."
    set -a
    source .env
    set +a
fi

# Detecta IP do Windows para WSL (se OLLAMA_URL não definida)
if [ -z "$OLLAMA_URL" ]; then
    # Tenta detectar se está no WSL
    if grep -qi microsoft /proc/version 2>/dev/null; then
        WINDOWS_IP=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2}')
        export OLLAMA_URL="http://${WINDOWS_IP}:11434"
        echo "🪟 WSL detectado - Usando IP do Windows: $OLLAMA_URL"
    else
        export OLLAMA_URL="http://localhost:11434"
    fi
fi

echo "📌 OLLAMA_URL=$OLLAMA_URL"

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
    echo "🧹 Limpando TODOS os dados de benchmark anteriores..."
    
    # Limpa grafos de memória de todos os namespaces
    rm -rf "$CORTEX_DATA_DIR"/benchmark*/memory_graph.json 2>/dev/null || true
    rm -rf "$CORTEX_DATA_DIR"/benchmark*/ 2>/dev/null || true
    rm -f "$CORTEX_DATA_DIR/default/memory_graph.json" 2>/dev/null || true
    
    # Limpa resultados anteriores (JSON, não os reports MD)
    rm -f benchmark/results/lightweight_*.json 2>/dev/null || true
    rm -f benchmark/results/*.checkpoint.json 2>/dev/null || true
    
    echo "   ✓ Dados resetados"
else
    echo "⏩ Modo RESUME - mantendo dados existentes"
fi

# Verifica se está no ambiente virtual
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Ativando ambiente virtual..."
    source venv/bin/activate
fi

# Verifica Ollama (timeout de 5 segundos)
echo "🔍 Verificando Ollama em $OLLAMA_URL..."
if ! curl -s --connect-timeout 5 --max-time 10 "${OLLAMA_URL}/api/version" > /dev/null 2>&1; then
    echo "❌ Ollama não está acessível em $OLLAMA_URL!"
    echo ""
    echo "   Possíveis causas:"
    echo "   1. Ollama não está rodando → No Windows: ollama serve"
    echo "   2. WSL não consegue acessar Windows → Configure OLLAMA_HOST=0.0.0.0 no Windows"
    echo "   3. Firewall bloqueando porta 11434"
    echo ""
    echo "   Para configurar Ollama no Windows (PowerShell Admin):"
    echo "   \$env:OLLAMA_HOST='0.0.0.0'; ollama serve"
    echo ""
    echo "   Ou defina OLLAMA_URL no .env com o IP correto"
        exit 1
    fi
echo "   ✓ Ollama OK"

# Modelo padrão
OLLAMA_MODEL="${OLLAMA_MODEL:-ministral-3:3b}"

# Verifica modelo
echo "🔍 Verificando modelo $OLLAMA_MODEL..."
if ! curl -s --connect-timeout 5 --max-time 10 "${OLLAMA_URL}/api/tags" | grep -q "$OLLAMA_MODEL"; then
    echo "⚠️  Modelo $OLLAMA_MODEL não encontrado."
    # No WSL, precisamos chamar ollama no Windows
    if grep -qi microsoft /proc/version 2>/dev/null; then
        echo "   Baixe o modelo no Windows: ollama pull $OLLAMA_MODEL"
        echo "   Pressione ENTER após baixar..."
        read -r
    else
        echo "   Baixando..."
        ollama pull "$OLLAMA_MODEL"
    fi
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
BENCHMARK_ARGS="--ollama-url $OLLAMA_URL --model $OLLAMA_MODEL -y"
BENCHMARK_SUCCESS=0

if [ "$1" == "--compare" ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🔬 BENCHMARK DE COMPARAÇÃO COMPLETA"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "   Agentes: Baseline, RAG, Mem0, Cortex"
    echo "   Inclui: Multi-sessão, volta de usuário, consolidação"
    echo ""
    
    if [ "$2" == "--full" ]; then
        echo "🚀 Executando comparação COMPLETA..."
        python benchmark/full_comparison_benchmark.py --full -y && BENCHMARK_SUCCESS=1
    else
        echo "🚀 Executando comparação RÁPIDA..."
        python benchmark/full_comparison_benchmark.py --quick -y && BENCHMARK_SUCCESS=1
    fi
    
elif [ "$1" == "--full" ]; then
    echo "🚀 Executando benchmark COMPLETO com CortexAgent..."
    python run_lightweight_benchmark.py --full $BENCHMARK_ARGS && BENCHMARK_SUCCESS=1
elif [ "$1" == "--quick" ]; then
    echo "🚀 Executando benchmark RÁPIDO com CortexAgent..."
    python run_lightweight_benchmark.py --quick $BENCHMARK_ARGS && BENCHMARK_SUCCESS=1
elif [ "$IS_RESUME" = true ]; then
    echo "🚀 Continuando benchmark..."
    python run_lightweight_benchmark.py "$@" $BENCHMARK_ARGS && BENCHMARK_SUCCESS=1
elif [ -n "$1" ]; then
    echo "🚀 Executando com domínio: $1"
    python run_lightweight_benchmark.py --domain "$1" --conversations 2 $BENCHMARK_ARGS && BENCHMARK_SUCCESS=1
else
    echo "🚀 Executando benchmark PADRÃO (1 conv/domínio, 3 sessões)..."
    python run_lightweight_benchmark.py $BENCHMARK_ARGS && BENCHMARK_SUCCESS=1
fi

# Executa análise se benchmark completou com sucesso
if [ "$BENCHMARK_SUCCESS" == "1" ]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 EXECUTANDO ANÁLISE AUTOMÁTICA"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    ./analyze_results.sh
fi

# Cleanup - para API se foi iniciada por este script
if [ "$CORTEX_API_STARTED" == "1" ]; then
    echo ""
    echo "🛑 Parando Cortex API..."
    # Encontra e mata o processo da API
    pkill -f "cortex-api" || true
    echo "   ✓ API encerrada"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 BENCHMARK CORTEX V2 CONCLUÍDO!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
