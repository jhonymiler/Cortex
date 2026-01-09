"""
Benchmark Package - Avaliação do Cortex Memory System

"Cortex, porque agentes inteligentes precisam de memória inteligente"

Componentes principais:
- unified_benchmark: Benchmark completo com 4 dimensões de valor (RECOMENDADO)
- paper_benchmark: Benchmark isolado do Cortex para métricas acadêmicas
- agents: Agentes de comparação (Baseline, RAG, Mem0, Cortex)

Dimensões de Valor medidas:
1. Cognição Biológica - Decay, consolidação, hubs
2. Memória Coletiva   - Compartilhamento, isolamento
3. Valor Semântico    - Acurácia, relevância
4. Eficiência         - Latência, tokens

Uso:
    ./start_benchmark.sh              # Benchmark unificado (padrão)
    ./start_benchmark.sh --paper      # Apenas Cortex
    
    # Ou diretamente:
    python -m benchmark.unified_benchmark
    python -m benchmark.paper_benchmark
"""

from .agents import BaselineAgent, CortexAgent, AgentResponse
from .conversation_generator import ConversationGenerator, Conversation, Session, Message

# Importações opcionais
try:
    from .rag_agent import RAGAgent
except ImportError:
    RAGAgent = None

try:
    from .mem0_agent import Mem0Agent
except ImportError:
    Mem0Agent = None

__all__ = [
    # Core
    "BaselineAgent",
    "CortexAgent",
    "AgentResponse",
    "ConversationGenerator",
    "Conversation",
    "Session",
    "Message",
    # Baselines alternativos
    "RAGAgent",
    "Mem0Agent",
]
