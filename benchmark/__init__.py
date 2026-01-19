"""
Benchmark Package - Avaliação do Cortex Memory System

"Cortex, porque agentes inteligentes precisam de memória inteligente"

Componentes principais:
- realistic_benchmark: Benchmarks com LLM real e cenários realistas (RECOMENDADO)
- professional_benchmark: Testes técnicos isolados de componentes
- validation: Validação das melhorias científicas

Dimensões de Valor medidas:
1. Contexto Real - Conversas e casos de uso reais com LLM
2. Cognição Biológica - Decay, consolidação, aprendizado
3. Valor Semântico - Retenção de contexto, qualidade de resposta
4. Eficiência - Latência, tokens, performance

Uso:
    ./start_benchmark.sh realistic         # Benchmark realista com LLM (padrão)
    ./start_benchmark.sh realistic quick   # Versão rápida
    ./start_benchmark.sh validation        # Validação das melhorias

    # Ou diretamente:
    python -m benchmark.realistic_benchmark
    python benchmark/validation.py
    python -m benchmark.professional_benchmark
"""

# Importações dos benchmarks disponíveis
try:
    from .realistic_benchmark import RealisticBenchmark
except ImportError:
    RealisticBenchmark = None

try:
    from .professional_benchmark import ProfessionalBenchmark
except ImportError:
    ProfessionalBenchmark = None

__all__ = [
    "RealisticBenchmark",
    "ProfessionalBenchmark",
]
