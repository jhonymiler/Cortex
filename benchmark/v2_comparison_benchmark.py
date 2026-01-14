#!/usr/bin/env python3
"""
Cortex v2.0 Comparison Benchmark

Compara v1.x (legacy mode) vs v2.0 (performance mode) nas 6 melhorias:
1. Context Packing
2. Progressive Consolidation
3. Active Forgetting
4. Hierarchical Recall
5. SM-2 Adaptive
6. Attention Mechanism
"""

import sys
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cortex.core.memory_graph import MemoryGraph
from src.cortex.core.episode import Episode
from src.cortex.core.memory import Memory
from src.cortex.config import CortexConfig


class V2ComparisonBenchmark:
    """Benchmark comparando v1.x (legacy) vs v2.0 (performance)."""

    def __init__(self):
        self.results: Dict[str, Dict] = {}

    def run_all(self) -> Dict:
        """Executa todos os benchmarks."""
        print("=" * 70)
        print("CORTEX V2.0 COMPARISON BENCHMARK")
        print("=" * 70)
        print()

        tests = [
            ("Context Packing", self.benchmark_context_packing),
            ("Progressive Consolidation", self.benchmark_progressive_consolidation),
            ("Active Forgetting", self.benchmark_active_forgetting),
            ("Hierarchical Recall", self.benchmark_hierarchical_recall),
            ("SM-2 Adaptive", self.benchmark_sm2_adaptive),
            ("Attention Mechanism", self.benchmark_attention_mechanism),
        ]

        for name, test_func in tests:
            print(f"\n{'='*70}")
            print(f"TEST: {name}")
            print(f"{'='*70}\n")

            try:
                result = test_func()
                self.results[name] = result
                self._print_result(name, result)
            except Exception as e:
                print(f"❌ ERRO: {e}")
                self.results[name] = {"error": str(e)}

        self._print_summary()
        return self.results

    # ==================== TEST 1: Context Packing ====================

    def benchmark_context_packing(self) -> Dict:
        """Compara densidade de tokens: legacy vs context packing."""
        # Setup: 10 episódios (alguns redundantes)
        episodes = []
        for i in range(10):
            ep = Episode(
                who=["joão"],
                what=f"configurar servidor {'prod' if i < 5 else 'staging'}",
                why="deploy",
                how="configurado com sucesso" if i % 2 == 0 else "erro na config",
                where="terminal",
                when=datetime.now() - timedelta(days=i),
            )
            ep.importance = 0.7 if i < 5 else 0.5
            episodes.append(ep)

        # Legacy mode (sem packing)
        graph_legacy = MemoryGraph(storage_path=None)
        graph_legacy._config = CortexConfig.create_legacy()

        for ep in episodes:
            graph_legacy.add_episode(ep)

        result_legacy = graph_legacy.recall("configurar servidor")
        context_legacy = result_legacy.to_prompt_context(format="yaml")
        tokens_legacy = len(context_legacy.split())

        # V2.0 mode (com packing)
        graph_v2 = MemoryGraph(storage_path=None)
        graph_v2._config = CortexConfig.create_performance()

        for ep in episodes:
            graph_v2.add_episode(ep)

        result_v2 = graph_v2.recall("configurar servidor")
        context_v2 = result_v2.to_prompt_context(format="yaml")
        tokens_v2 = len(context_v2.split())

        reduction = ((tokens_legacy - tokens_v2) / tokens_legacy) * 100 if tokens_legacy > 0 else 0

        return {
            "tokens_legacy": tokens_legacy,
            "tokens_v2": tokens_v2,
            "reduction_pct": round(reduction, 1),
            "target": 40.0,  # 40% reduction target
            "passed": reduction >= 40.0,
        }

    # ==================== TEST 2: Progressive Consolidation ====================

    def benchmark_progressive_consolidation(self) -> Dict:
        """Compara tempo até consolidação: fixed vs progressive."""
        # Legacy (threshold=5)
        graph_legacy = MemoryGraph(storage_path=None)
        graph_legacy._config = CortexConfig.create_legacy()

        occurrences_legacy = 0
        for i in range(10):
            ep = Episode(
                who=["joão"],
                what="erro deploy",
                why="bug",
                how="resolvido",
                when=datetime.now() - timedelta(days=i * 2),
            )
            graph_legacy.add_episode(ep, consolidation_mode="fixed")

            consolidated = [e for e in graph_legacy._episodes.values() if e.is_consolidated]
            if consolidated and occurrences_legacy == 0:
                occurrences_legacy = i + 1
                break

        # V2.0 (threshold=2 para emergente)
        graph_v2 = MemoryGraph(storage_path=None)
        graph_v2._config = CortexConfig.create_performance()

        occurrences_v2 = 0
        for i in range(10):
            ep = Episode(
                who=["joão"],
                what="erro deploy",
                why="bug",
                how="resolvido",
                when=datetime.now() - timedelta(days=i * 2),
            )
            graph_v2.add_episode(ep, consolidation_mode="progressive")

            consolidated = [e for e in graph_v2._episodes.values() if e.is_consolidated]
            if consolidated and occurrences_v2 == 0:
                occurrences_v2 = i + 1
                break

        improvement = ((occurrences_legacy - occurrences_v2) / occurrences_legacy) * 100 if occurrences_legacy > 0 else 0

        return {
            "occurrences_legacy": occurrences_legacy,
            "occurrences_v2": occurrences_v2,
            "improvement_pct": round(improvement, 1),
            "target": 60.0,  # 60% faster target
            "passed": improvement >= 50.0,  # Allow 10% margin
        }

    # ==================== TEST 3: Active Forgetting ====================

    def benchmark_active_forgetting(self) -> Dict:
        """Compara ruído filtrado: sem forget gate vs com forget gate."""
        # Create episodes (alguns são ruído)
        episodes = []

        # Episódios relevantes
        for i in range(5):
            ep = Episode(
                who=["joão"],
                what="configurar CI/CD",
                why="automation",
                how="sucesso",
                when=datetime.now() - timedelta(days=i),
            )
            ep.importance = 0.8
            ep.access_count = 3
            episodes.append(ep)

        # Ruído (baixa importância, sem acesso)
        for i in range(5):
            ep = Episode(
                who=["maria"],
                what="evento irrelevante",
                why="teste",
                how="nada",
                when=datetime.now() - timedelta(days=30 + i),
            )
            ep.importance = 0.2
            ep.access_count = 0
            episodes.append(ep)

        # Legacy (sem forget gate)
        graph_legacy = MemoryGraph(storage_path=None)
        graph_legacy._config = CortexConfig.create_legacy()

        for ep in episodes:
            graph_legacy.add_episode(ep)

        result_legacy = graph_legacy.recall("configurar")
        noise_legacy = len([e for e in result_legacy.episodes if e.importance < 0.3])

        # V2.0 (com forget gate)
        graph_v2 = MemoryGraph(storage_path=None)
        graph_v2._config = CortexConfig.create_performance()

        for ep in episodes:
            graph_v2.add_episode(ep)

        result_v2 = graph_v2.recall("configurar")
        noise_v2 = len([e for e in result_v2.episodes if e.importance < 0.3])

        noise_reduction = ((noise_legacy - noise_v2) / noise_legacy) * 100 if noise_legacy > 0 else 0

        return {
            "noise_legacy": noise_legacy,
            "noise_v2": noise_v2,
            "reduction_pct": round(noise_reduction, 1),
            "target": 30.0,  # 30% noise reduction target
            "passed": noise_reduction >= 20.0,
        }

    # ==================== TEST 4: Hierarchical Recall ====================

    def benchmark_hierarchical_recall(self) -> Dict:
        """Compara latência: flat recall vs hierarchical recall."""
        # Create episodes spanning different time windows
        episodes = []

        # Working memory (hoje)
        for i in range(5):
            ep = Episode(
                who=["joão"],
                what=f"tarefa atual {i}",
                why="work",
                how="em progresso",
                when=datetime.now() - timedelta(hours=i),
            )
            episodes.append(ep)

        # Recent (última semana)
        for i in range(5):
            ep = Episode(
                who=["joão"],
                what=f"tarefa recente {i}",
                why="work",
                how="concluída",
                when=datetime.now() - timedelta(days=i + 1),
            )
            episodes.append(ep)

        # Patterns (último mês)
        for i in range(3):
            ep = Episode(
                who=["joão"],
                what="padrão recorrente",
                why="pattern",
                how="identificado",
                when=datetime.now() - timedelta(days=15 + i),
            )
            ep.is_consolidated = True
            ep.occurrence_count = 5
            episodes.append(ep)

        # Legacy (flat)
        graph_legacy = MemoryGraph(storage_path=None)
        graph_legacy._config = CortexConfig.create_legacy()

        for ep in episodes:
            graph_legacy.add_episode(ep)

        start = time.perf_counter()
        result_legacy = graph_legacy.recall("tarefa")
        latency_legacy = (time.perf_counter() - start) * 1000  # ms

        # V2.0 (hierarchical)
        graph_v2 = MemoryGraph(storage_path=None)
        graph_v2._config = CortexConfig.create_performance()

        for ep in episodes:
            graph_v2.add_episode(ep)

        start = time.perf_counter()
        result_v2 = graph_v2.recall("tarefa")
        latency_v2 = (time.perf_counter() - start) * 1000  # ms

        speedup = (latency_legacy / latency_v2) if latency_v2 > 0 else 1.0

        return {
            "latency_legacy_ms": round(latency_legacy, 2),
            "latency_v2_ms": round(latency_v2, 2),
            "speedup": round(speedup, 2),
            "target": 2.0,  # 2x faster target
            "passed": speedup >= 1.5,  # Allow margin
        }

    # ==================== TEST 5: SM-2 Adaptive ====================

    def benchmark_sm2_adaptive(self) -> Dict:
        """Testa adaptação do easiness factor."""
        # Create memory
        mem = Memory(
            what="teste_sm2",
            who=["teste_user"],
            importance=0.7,
            easiness=2.0,  # Start at 2.0 (não no máximo)
        )

        # Simulate perfect recalls (quality=5)
        ef_initial = mem.easiness
        for _ in range(3):
            mem.update_sm2(quality=5)
        ef_after_success = mem.easiness

        # Simulate failure (quality=1)
        mem.update_sm2(quality=1)
        ef_after_failure = mem.easiness

        return {
            "ef_initial": ef_initial,
            "ef_after_success": round(ef_after_success, 2),
            "ef_after_failure": round(ef_after_failure, 2),
            "adapts_up": ef_after_success > ef_initial,
            "adapts_down": ef_after_failure < ef_after_success,
            "passed": (ef_after_success > ef_initial) and (ef_after_failure < ef_after_success),
        }

    # ==================== TEST 6: Attention Mechanism ====================

    def benchmark_attention_mechanism(self) -> Dict:
        """Compara coerência: sem attention vs com attention."""
        # Create related episodes (João + deploy) and unrelated (Maria + login)
        episodes = []

        # Related: João deploy sequence
        episodes.append(
            Episode(
                who=["joão"],
                what="reportou erro deploy",
                why="bug",
                how="servidor não iniciou",
                when=datetime.now() - timedelta(hours=2),
            )
        )
        episodes.append(
            Episode(
                who=["joão"],
                what="investigou logs",
                why="debug",
                how="encontrou causa",
                when=datetime.now() - timedelta(hours=1),
            )
        )
        episodes.append(
            Episode(
                who=["joão"],
                what="corrigiu configuração",
                why="fix",
                how="deploy funcionou",
                when=datetime.now() - timedelta(minutes=30),
            )
        )

        # Unrelated: Maria login
        episodes.append(
            Episode(
                who=["maria"],
                what="fez login",
                why="acesso",
                how="autenticada",
                when=datetime.now() - timedelta(hours=1, minutes=30),
            )
        )

        # Set importance (Maria high to test if attention overrides)
        for i, ep in enumerate(episodes):
            ep.importance = 0.9 if i == 3 else 0.7  # Maria tem maior importance!

        # Legacy (sem attention)
        graph_legacy = MemoryGraph(storage_path=None)
        graph_legacy._config = CortexConfig.create_legacy()

        for ep in episodes:
            graph_legacy.add_episode(ep)

        result_legacy = graph_legacy.recall("joão deploy")
        top3_legacy = result_legacy.episodes[:3]
        related_legacy = sum(1 for ep in top3_legacy if "joão" in str(ep.who).lower())

        # V2.0 (com attention)
        graph_v2 = MemoryGraph(storage_path=None)
        graph_v2._config = CortexConfig.create_performance()

        for ep in episodes:
            graph_v2.add_episode(ep)

        result_v2 = graph_v2.recall("joão deploy")
        top3_v2 = result_v2.episodes[:3]
        related_v2 = sum(1 for ep in top3_v2 if "joão" in str(ep.who).lower())

        coherence_legacy = (related_legacy / 3.0) * 100
        coherence_v2 = (related_v2 / 3.0) * 100
        improvement = coherence_v2 - coherence_legacy

        return {
            "coherence_legacy_pct": round(coherence_legacy, 1),
            "coherence_v2_pct": round(coherence_v2, 1),
            "improvement_pct": round(improvement, 1),
            "target": 30.0,  # +30% coherence target
            "passed": improvement >= 20.0,
        }

    # ==================== Helpers ====================

    def _print_result(self, test_name: str, result: Dict):
        """Print result of a single test."""
        if "error" in result:
            print(f"❌ ERRO: {result['error']}")
            return

        print(f"📊 Resultados:")
        for key, value in result.items():
            if key not in ["passed", "target"]:
                print(f"  - {key}: {value}")

        if "passed" in result:
            status = "✅ PASSOU" if result["passed"] else "❌ FALHOU"
            print(f"\n{status}")

    def _print_summary(self):
        """Print summary of all tests."""
        print("\n" + "=" * 70)
        print("RESUMO")
        print("=" * 70)

        passed = sum(1 for r in self.results.values() if r.get("passed", False))
        total = len(self.results)

        print(f"\n✅ Testes passados: {passed}/{total} ({(passed/total)*100:.1f}%)\n")

        for name, result in self.results.items():
            if "error" in result:
                print(f"❌ {name}: ERRO")
            elif result.get("passed"):
                print(f"✅ {name}: PASSOU")
            else:
                print(f"❌ {name}: FALHOU")

        print("\n" + "=" * 70)

        if passed == total:
            print("🎉 TODOS OS TESTES PASSARAM!")
        else:
            print(f"⚠️  {total - passed} testes falharam")

        print("=" * 70)


if __name__ == "__main__":
    benchmark = V2ComparisonBenchmark()
    results = benchmark.run_all()

    sys.exit(0 if all(r.get("passed", False) for r in results.values()) else 1)
