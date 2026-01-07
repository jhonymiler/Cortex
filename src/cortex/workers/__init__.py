"""
Cortex Workers - Processos em background.

Workers disponíveis:
- SleepRefiner: Consolida e refina memórias periodicamente

Uso:
    from cortex.workers import SleepRefiner
    
    # Usa variáveis de ambiente: CORTEX_API_URL, OLLAMA_URL, OLLAMA_MODEL
    refiner = SleepRefiner()
    refiner.refine(namespace="meu_agente")
"""

from .sleep_refiner import SleepRefiner, RefineResult

__all__ = [
    "SleepRefiner",
    "RefineResult",
]

