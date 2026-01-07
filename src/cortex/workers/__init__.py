"""
Cortex Workers - Processos em background.

Workers disponíveis:
- DreamAgent: Consolida e refina memórias periodicamente (como sonhos)

Uso:
    from cortex.workers import DreamAgent
    
    # Usa variáveis de ambiente: CORTEX_API_URL, OLLAMA_URL, OLLAMA_MODEL
    agent = DreamAgent()
    agent.dream(namespace="meu_agente")
"""

from .dream_agent import DreamAgent, DreamResult

__all__ = [
    "DreamAgent",
    "DreamResult",
]
