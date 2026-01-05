"""
Benchmark Package - Comparação Cortex vs Baseline com LLM Real
"""

from .agents import BaselineAgent, CortexAgent, AgentResponse
from .benchmark import BenchmarkRunner, MetricsEvaluator, BenchmarkResult
from .conversation_generator import ConversationGenerator, Conversation, Session, Message

__all__ = [
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
]
