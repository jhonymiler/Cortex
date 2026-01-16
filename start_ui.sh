#!/bin/bash
# Script para iniciar o Cortex Control Panel (Streamlit)

echo "🧠 Iniciando Cortex Control Panel..."
echo ""

# Ativa o ambiente virtual se existir
if [ -d "venv" ]; then
    echo "✅ Ativando ambiente virtual..."
    source venv/bin/activate
fi

# Verifica se streamlit está instalado
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit não encontrado. Instalando..."
    pip install -e ".[ui]"
fi

# Inicia o Streamlit
echo "🚀 Abrindo painel em http://localhost:8501"
echo ""
streamlit run src/cortex/ui/app.py
