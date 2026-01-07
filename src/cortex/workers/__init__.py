"""
Cortex Workers - Processos em background.

Workers disponíveis:
- SleepRefiner: Consolida e refina memórias periodicamente

Uso:
    from cortex.workers import SleepRefiner
    
    refiner = SleepRefiner(cortex_url="http://localhost:8000")
    refiner.refine(namespace="meu_agente")
"""

from .sleep_refiner import SleepRefiner, RefineResult

__all__ = [
    "SleepRefiner",
    "RefineResult",
]

