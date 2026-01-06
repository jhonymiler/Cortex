"""
Ablation Study Runner - Comparação de variantes do Cortex

Executa benchmark com diferentes configurações para ablation study:
1. Full - Cortex completo (W5H + Decay + Centrality + Consolidation)
2. NoDecay - Sem decaimento Ebbinghaus
3. NoCentrality - Sem hub detection
4. NoConsolidation - Sem consolidação de episódios
5. SimpleEpisodic - Apenas action/outcome (sem W5H completo)
6. Baseline - Sem memória (controle)

Uso:
    python ablation_runner.py --quick        # Teste rápido
    python ablation_runner.py --full         # Todos os experimentos
    python ablation_runner.py --variant full no_decay  # Variantes específicas
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Adiciona paths
benchmark_path = Path(__file__).parent
sys.path.insert(0, str(benchmark_path))
sdk_path = benchmark_path.parent / "sdk" / "python"
sys.path.insert(0, str(sdk_path))

from agents import BaselineAgent, CortexAgent, AgentResponse
from benchmark import BenchmarkRunner, BenchmarkResult, MetricsEvaluator
from conversation_generator import ConversationGenerator
from scientific_metrics import (
    ScientificMetricsEvaluator,
    evaluate_benchmark_scientifically,
)


@dataclass
class AblationVariant:
    """Configuração de uma variante para ablation study."""
    name: str
    description: str
    config: dict[str, Any]


# Definição das variantes
ABLATION_VARIANTS = {
    "full": AblationVariant(
        name="full",
        description="Cortex completo (W5H + Decay + Centrality + Consolidation)",
        config={
            "use_decay": True,
            "use_centrality": True,
            "use_consolidation": True,
            "use_w5h": True,
        },
    ),
    "no_decay": AblationVariant(
        name="no_decay",
        description="Sem decaimento Ebbinghaus",
        config={
            "use_decay": False,
            "use_centrality": True,
            "use_consolidation": True,
            "use_w5h": True,
        },
    ),
    "no_centrality": AblationVariant(
        name="no_centrality",
        description="Sem hub detection/centralidade",
        config={
            "use_decay": True,
            "use_centrality": False,
            "use_consolidation": True,
            "use_w5h": True,
        },
    ),
    "no_consolidation": AblationVariant(
        name="no_consolidation",
        description="Sem consolidação de episódios",
        config={
            "use_decay": True,
            "use_centrality": True,
            "use_consolidation": False,
            "use_w5h": True,
        },
    ),
    "simple_episodic": AblationVariant(
        name="simple_episodic",
        description="Apenas action/outcome (sem W5H completo)",
        config={
            "use_decay": True,
            "use_centrality": True,
            "use_consolidation": True,
            "use_w5h": False,
        },
    ),
    "baseline": AblationVariant(
        name="baseline",
        description="Sem memória (controle)",
        config={
            "is_baseline": True,
        },
    ),
}


class AblationRunner:
    """Executor de ablation study."""
    
    def __init__(
        self,
        model: str = "deepseek-v3.1:671b-cloud",
        ollama_url: str = "http://localhost:11434",
        cortex_url: str = "http://localhost:8000",
        output_dir: Path | str = None,
        verbose: bool = True,
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.cortex_url = cortex_url
        self.output_dir = Path(output_dir or (benchmark_path / "results" / "ablation"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        
        self.results: dict[str, dict] = {}
        self.scientific_evaluations: dict[str, dict] = {}
    
    def _log(self, msg: str, end: str = "\n") -> None:
        if self.verbose:
            print(msg, end=end, flush=True)
    
    def run_variant(
        self,
        variant: AblationVariant,
        conversations: list,
        namespace_suffix: str = "",
    ) -> dict:
        """Executa benchmark para uma variante específica."""
        self._log(f"\n{'='*60}")
        self._log(f"🧪 Variante: {variant.name}")
        self._log(f"   {variant.description}")
        self._log(f"{'='*60}")
        
        namespace = f"ablation_{variant.name}{namespace_suffix}"
        
        if variant.config.get("is_baseline"):
            # Para baseline, usamos BenchmarkRunner normal
            # mas só coletamos métricas do baseline
            runner = BenchmarkRunner(
                model=self.model,
                ollama_url=self.ollama_url,
                cortex_url=self.cortex_url,
                namespace=namespace,
                verbose=self.verbose,
            )
            
            # Verifica serviços
            if not runner.verify_services():
                self._log("❌ Serviços não disponíveis")
                return {"error": "services_unavailable"}
            
            result = runner.run_benchmark(
                conversations,
                clear_memory_before=True,
            )
            
            return result.to_dict()
        
        else:
            # Para variantes do Cortex, precisamos passar configuração
            # TODO: Implementar flags no CortexAgent para cada componente
            # Por enquanto, usamos o CortexAgent padrão
            
            runner = BenchmarkRunner(
                model=self.model,
                ollama_url=self.ollama_url,
                cortex_url=self.cortex_url,
                namespace=namespace,
                verbose=self.verbose,
            )
            
            # Verifica serviços
            if not runner.verify_services():
                self._log("❌ Serviços não disponíveis")
                return {"error": "services_unavailable"}
            
            # Define configuração da variante como variáveis de ambiente
            # (será lido pelo CortexAgent)
            os.environ["CORTEX_USE_DECAY"] = str(variant.config.get("use_decay", True))
            os.environ["CORTEX_USE_CENTRALITY"] = str(variant.config.get("use_centrality", True))
            os.environ["CORTEX_USE_CONSOLIDATION"] = str(variant.config.get("use_consolidation", True))
            os.environ["CORTEX_USE_W5H"] = str(variant.config.get("use_w5h", True))
            
            result = runner.run_benchmark(
                conversations,
                clear_memory_before=True,
            )
            
            return result.to_dict()
    
    def run_ablation_study(
        self,
        variants: list[str] | None = None,
        conversations_per_domain: int = 1,
        sessions_per_conversation: int = 3,
    ) -> dict:
        """
        Executa ablation study completo.
        
        Args:
            variants: Lista de nomes de variantes (ou None para todas)
            conversations_per_domain: Conversas por domínio
            sessions_per_conversation: Sessões por conversa
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self._log("=" * 70)
        self._log("🔬 INICIANDO ABLATION STUDY")
        self._log("=" * 70)
        
        # Seleciona variantes
        if variants:
            selected = {k: v for k, v in ABLATION_VARIANTS.items() if k in variants}
        else:
            selected = ABLATION_VARIANTS
        
        self._log(f"\n📋 Variantes: {list(selected.keys())}")
        
        # Gera conversas (mesmas para todas as variantes)
        self._log("\n🔄 Gerando conversas de teste...")
        generator = ConversationGenerator()
        conversations = generator.generate_all(
            conversations_per_domain=conversations_per_domain,
            sessions_per_conversation=sessions_per_conversation,
        )
        self._log(f"   ✅ {len(conversations)} conversas geradas")
        
        # Executa cada variante
        for name, variant in selected.items():
            try:
                result = self.run_variant(
                    variant,
                    conversations,
                    namespace_suffix=f"_{timestamp}",
                )
                
                if "error" not in result:
                    self.results[name] = result
                    
                    # Avalia cientificamente (usando DeepSeek para LLM-as-Judge)
                    self._log(f"\n📊 Avaliando métricas científicas para {name}...")
                    sci_eval = evaluate_benchmark_scientifically(
                        result,
                        use_llm_judge=True,  # Sempre usa DeepSeek via Ollama
                    )
                    self.scientific_evaluations[name] = sci_eval
                    
            except Exception as e:
                self._log(f"❌ Erro na variante {name}: {e}")
                self.results[name] = {"error": str(e)}
        
        # Gera comparação
        comparison = self._generate_comparison()
        
        # Salva resultados
        output_file = self.output_dir / f"ablation_{timestamp}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": timestamp,
                "config": {
                    "model": self.model,
                    "conversations_per_domain": conversations_per_domain,
                    "sessions_per_conversation": sessions_per_conversation,
                    "total_conversations": len(conversations),
                },
                "variants": {k: v.config for k, v in selected.items()},
                "results": self.results,
                "scientific_evaluations": self.scientific_evaluations,
                "comparison": comparison,
            }, f, ensure_ascii=False, indent=2)
        
        self._log(f"\n💾 Resultados salvos em: {output_file}")
        
        # Imprime comparação
        self._print_comparison(comparison)
        
        return comparison
    
    def _generate_comparison(self) -> dict:
        """Gera comparação entre variantes."""
        comparison = {
            "variants": {},
            "rankings": {},
        }
        
        for name, result in self.results.items():
            if "error" in result:
                continue
            
            # Extrai métricas para comparação
            evaluator = MetricsEvaluator(result)
            summary = evaluator.generate_summary()
            
            comparison["variants"][name] = {
                "avg_tokens": summary["token_metrics"]["cortex"]["avg_tokens_per_message"],
                "avg_response_time_ms": summary["time_metrics"]["cortex"]["avg_time_ms"],
                "memory_hit_rate": summary["memory_metrics"]["memory_hit_rate"],
                "total_entities": summary["memory_metrics"]["total_entities_recalled"],
                "total_episodes": summary["memory_metrics"]["total_episodes_recalled"],
            }
            
            # Adiciona métricas científicas se disponíveis
            if name in self.scientific_evaluations:
                sci = self.scientific_evaluations[name]
                if "retrieval_metrics" in sci:
                    comparison["variants"][name]["avg_precision@3"] = sci["retrieval_metrics"].get("avg_precision@3", 0)
                    comparison["variants"][name]["avg_mrr"] = sci["retrieval_metrics"].get("avg_mrr", 0)
                if "llm_judge_metrics" in sci:
                    comparison["variants"][name]["llm_judge_overall"] = sci["llm_judge_metrics"].get("avg_overall", 0)
        
        # Calcula rankings
        metrics_to_rank = [
            ("memory_hit_rate", True),  # Maior é melhor
            ("avg_response_time_ms", False),  # Menor é melhor
            ("avg_tokens", False),  # Menor é melhor
        ]
        
        for metric, higher_is_better in metrics_to_rank:
            values = [
                (name, data.get(metric, 0))
                for name, data in comparison["variants"].items()
            ]
            if values:
                sorted_values = sorted(values, key=lambda x: x[1], reverse=higher_is_better)
                comparison["rankings"][metric] = [v[0] for v in sorted_values]
        
        return comparison
    
    def _print_comparison(self, comparison: dict) -> None:
        """Imprime comparação formatada."""
        print("\n" + "=" * 70)
        print("📊 COMPARAÇÃO DE VARIANTES (ABLATION STUDY)")
        print("=" * 70)
        
        # Tabela de métricas
        print("\n┌" + "─" * 18 + "┬" + "─" * 12 + "┬" + "─" * 14 + "┬" + "─" * 12 + "┐")
        print(f"│ {'Variante':<16} │ {'Hit Rate':<10} │ {'Tempo (ms)':<12} │ {'Tokens':<10} │")
        print("├" + "─" * 18 + "┼" + "─" * 12 + "┼" + "─" * 14 + "┼" + "─" * 12 + "┤")
        
        for name, data in comparison.get("variants", {}).items():
            hit_rate = data.get("memory_hit_rate", 0)
            time_ms = data.get("avg_response_time_ms", 0)
            tokens = data.get("avg_tokens", 0)
            print(f"│ {name:<16} │ {hit_rate:>9.1f}% │ {time_ms:>11.0f} │ {tokens:>10.0f} │")
        
        print("└" + "─" * 18 + "┴" + "─" * 12 + "┴" + "─" * 14 + "┴" + "─" * 12 + "┘")
        
        # Rankings
        print("\n🏆 Rankings:")
        for metric, ranking in comparison.get("rankings", {}).items():
            print(f"   {metric}: {' > '.join(ranking[:3])}")
        
        print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Ablation Study Runner")
    
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=list(ABLATION_VARIANTS.keys()),
        help="Variantes específicas para testar",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Teste rápido (1 conv/domínio, 2 sessões)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Teste completo (3 conv/domínio, 5 sessões)",
    )
    parser.add_argument(
        "--conversations",
        type=int,
        default=1,
        help="Conversas por domínio",
    )
    parser.add_argument(
        "--sessions",
        type=int,
        default=3,
        help="Sessões por conversa",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OLLAMA_MODEL", "deepseek-v3.1:671b-cloud"),
        help="Modelo Ollama",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Diretório de saída",
    )
    
    args = parser.parse_args()
    
    # Configura baseado em presets
    if args.quick:
        conversations = 1
        sessions = 2
    elif args.full:
        conversations = 3
        sessions = 5
    else:
        conversations = args.conversations
        sessions = args.sessions
    
    # Cria runner
    runner = AblationRunner(
        model=args.model,
        output_dir=args.output,
    )
    
    # Executa
    runner.run_ablation_study(
        variants=args.variants,
        conversations_per_domain=conversations,
        sessions_per_conversation=sessions,
    )


if __name__ == "__main__":
    main()
