#!/bin/bash

# Script para iniciar todos os serviços do Cortex Benchmark
# Uso: ./start_benchmark.sh [--quick|--full]

set -e

echo "======================================================================="
echo "🚀 INICIANDO CORTEX BENCHMARK STACK"
echo "======================================================================="

# Diretório do projeto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Ativar venv
echo "📦 Ativando ambiente virtual..."
source venv/bin/activate

# Parar processos existentes
echo "🛑 Parando processos existentes..."
pkill -9 -f "cortex-api" 2>/dev/null || true
pkill -9 -f "streamlit" 2>/dev/null || true
pkill -9 -f "uvicorn.*cortex" 2>/dev/null || true
sleep 2

# Definir diretório de dados
export CORTEX_DATA_DIR="./data"
echo "📂 Diretório de dados: $CORTEX_DATA_DIR"

# Iniciar Cortex API
echo "🔧 Iniciando Cortex API (porta 8000)..."
python -m uvicorn cortex.api.app:app --host 0.0.0.0 --port 8000 > /tmp/cortex-api.log 2>&1 &
API_PID=$!
echo "   PID: $API_PID"

# Aguardar API estar pronta
echo "⏳ Aguardando Cortex API..."
for i in {1..10}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "   ✅ Cortex API funcionando"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "   ❌ Cortex API não iniciou!"
        cat /tmp/cortex-api.log
        exit 1
    fi
    sleep 1
done

# Iniciar Streamlit
echo "📊 Iniciando Streamlit Dashboard (porta 8501)..."
streamlit run src/cortex/ui/app.py --server.headless=true --server.port=8501 > /tmp/streamlit.log 2>&1 &
STREAMLIT_PID=$!
echo "   PID: $STREAMLIT_PID"

# Aguardar Streamlit estar pronto
echo "⏳ Aguardando Streamlit..."
sleep 3
echo "   ✅ Streamlit funcionando"

echo ""
echo "======================================================================="
echo "✅ SERVIÇOS INICIADOS COM SUCESSO"
echo "======================================================================="
echo ""
echo "🔗 URLs:"
echo "   • Cortex API:  http://localhost:8000"
echo "   • Dashboard:   http://localhost:8501"
echo ""
echo "📁 Dados salvos em: $CORTEX_DATA_DIR"
echo ""
echo "📋 Processos:"
echo "   • Cortex API:  $API_PID (log: /tmp/cortex-api.log)"
echo "   • Streamlit:   $STREAMLIT_PID (log: /tmp/streamlit.log)"
echo ""
echo "======================================================================="

# Se argumento foi passado, executar benchmark
if [ -n "$1" ]; then
    echo ""
    echo "🚀 Iniciando benchmark com opção: $1"
    echo "======================================================================="
    python benchmark/run_benchmark.py "$1"
else
    echo ""
    echo "💡 Para executar benchmark:"
    echo "   python benchmark/run_benchmark.py --quick    (1 conv/domain, 3 sessions)"
    echo "   python benchmark/run_benchmark.py --full     (3 conv/domain, 5 sessions)"
    echo ""
    echo "🛑 Para parar os serviços:"
    echo "   kill $API_PID $STREAMLIT_PID"
    echo "   ou: pkill -f 'cortex-api|streamlit'"
    echo ""
fi
