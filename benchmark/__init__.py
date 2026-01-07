"""
Benchmark Package - Comparação Cortex vs Baseline com LLM Real

Componentes:
- agents: Agentes baseline, Cortex, RAG, Mem0
- benchmark: Runner principal
- scientific_metrics: Precision, Recall, MRR
- consistency_metrics: Coerência entre sessões
- ablation_runner: Ablation study
- shared_memory_benchmark: Testes de memória compartilhada
"""

from .agents import BaselineAgent, CortexAgent, AgentResponse
from .benchmark import BenchmarkRunner, MetricsEvaluator, BenchmarkResult
from .conversation_generator import ConversationGenerator, Conversation, Session, Message

# Importações opcionais (podem falhar se dependências não instaladas)
try:
    from .rag_agent import RAGAgent
except ImportError:
    RAGAgent = None

try:
    from .mem0_agent import Mem0Agent
except ImportError:
    Mem0Agent = None

try:
    from .consistency_metrics import ConsistencyEvaluator, calculate_consistency_score
except ImportError:
    ConsistencyEvaluator = None
    calculate_consistency_score = None

try:
    from .shared_memory_benchmark import SharedMemoryBenchmarkRunner
except ImportError:
    SharedMemoryBenchmarkRunner = None

__all__ = [
    # Core
    "BaselineAgent",
    "CortexAgent",
    "AgentResponse",
    "BenchmarkRunner",
    "MetricsEvaluator",
    "BenchmarkResult",
    "ConversationGenerator",
    "Conversation",
    "Session",
    "Message",
    # Baselines alternativos
    "RAGAgent",
    "Mem0Agent",
    # Métricas
    "ConsistencyEvaluator",
    "calculate_consistency_score",
    # Benchmarks especializados
    "SharedMemoryBenchmarkRunner",
]
