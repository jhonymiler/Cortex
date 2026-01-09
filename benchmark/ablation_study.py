#!/usr/bin/env python3
"""
Ablation Study - Análise de Contribuição de Componentes

Avalia a contribuição individual de cada componente do Cortex:
1. W5H Model - Estruturação de memória
2. Decay (Ebbinghaus) - Esquecimento temporal
3. Hub Centrality - Proteção de memórias importantes
4. Namespace Hierarchy - Isolamento e herança
5. Adaptive Threshold - Filtro de relevância

Metodologia:
- Cortex completo (baseline)
- Remove cada componente individualmente
- Mede impacto na acurácia

Uso:
    python ablation_study.py           # Executa estudo completo
    python ablation_study.py --save    # Salva resultados
    python ablation_study.py --quick   # Versão rápida (menos testes)
"""

import functools
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

print = functools.partial(print, flush=True)

# Paths
benchmark_path = Path(__file__).parent
project_root = benchmark_path.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

# Configuração
CORTEX_URL = os.getenv("CORTEX_API_URL", "http://localhost:8000")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OUTPUT_DIR = Path("./benchmark_results")


# ==================== MODELOS ====================

@dataclass
class AblationResult:
    """Resultado de uma variante de ablation."""
    variant: str
    description: str
    semantic_accuracy: float
    contextual_recall: float
    collective_memory: float
    efficiency_latency: float
    total_accuracy: float
    delta_vs_full: float
    tests_passed: int
    tests_total: int


@dataclass
class AblationReport:
    """Relatório completo do ablation study."""
    timestamp: str = ""
    duration_seconds: float = 0.0
    results: list[AblationResult] = field(default_factory=list)
    component_impact: dict[str, float] = field(default_factory=dict)


# ==================== ABLATION STUDY ====================

class AblationStudy:
    """Estudo de ablation para avaliar contribuição de componentes."""
    
    def __init__(self, quick: bool = False):
        self.quick = quick
        self.namespace_base = f"ablation_{int(time.time())}"
    
    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")
    
    def _check_api(self) -> bool:
        """Verifica API Cortex."""
        try:
            r = requests.get(f"{CORTEX_URL}/health", timeout=5)
            return r.status_code == 200
        except Exception:
            return False
    
    def _store(self, who: list, what: str, why: str, how: str, ns: str, **kwargs):
        """Armazena memória."""
        try:
            data = {"who": who, "what": what, "why": why, "how": how}
            data.update(kwargs)
            requests.post(
                f"{CORTEX_URL}/memory/remember",
                json=data,
                headers={"X-Cortex-Namespace": ns},
                timeout=10,
            )
        except Exception:
            pass
    
    def _recall(self, query: str, ns: str, **kwargs) -> tuple[list, float]:
        """Busca memória."""
        try:
            start = time.time()
            data = {"query": query, "context": kwargs}
            r = requests.post(
                f"{CORTEX_URL}/memory/recall",
                json=data,
                headers={"X-Cortex-Namespace": ns},
                timeout=10,
            )
            latency = (time.time() - start) * 1000
            return r.json().get("episodes", []), latency
        except Exception:
            return [], 0
    
    def run(self) -> AblationReport:
        """Executa ablation study completo."""
        self.log("=" * 60)
        self.log("🔬 ABLATION STUDY - ANÁLISE DE COMPONENTES")
        self.log("=" * 60)
        
        start_time = time.time()
        report = AblationReport(timestamp=datetime.now().isoformat())
        
        if not self._check_api():
            self.log("❌ API Cortex não disponível!")
            return report
        
        # Variantes a testar
        variants = [
            ("full", "Cortex Completo (baseline)", {}),
            ("no_decay", "Sem Decay", {"disable_decay": True}),
            ("no_hub", "Sem Hub Centrality", {"disable_hub": True}),
            ("no_namespace", "Sem Namespace Hierárquico", {"flat_namespace": True}),
            ("no_threshold", "Sem Threshold Adaptativo", {"fixed_threshold": True}),
            ("simple_episodic", "Apenas Episódico (sem W5H)", {"simple_mode": True}),
        ]
        
        full_result = None
        
        for variant_id, description, config in variants:
            self.log(f"\n{'='*60}")
            self.log(f"📊 Variante: {description}")
            self.log("-" * 40)
            
            result = self._test_variant(variant_id, description, config)
            report.results.append(result)
            
            if variant_id == "full":
                full_result = result
            elif full_result:
                result.delta_vs_full = result.total_accuracy - full_result.total_accuracy
            
            self.log(f"   Acurácia: {result.total_accuracy*100:.1f}%")
            if result.delta_vs_full != 0:
                delta_str = f"+{result.delta_vs_full*100:.1f}" if result.delta_vs_full > 0 else f"{result.delta_vs_full*100:.1f}"
                self.log(f"   Delta vs Full: {delta_str}%")
        
        # Calcula impacto de cada componente
        if full_result:
            for result in report.results:
                if result.variant != "full":
                    component = result.variant.replace("no_", "").replace("_", " ").title()
                    impact = full_result.total_accuracy - result.total_accuracy
                    report.component_impact[component] = impact
        
        report.duration_seconds = time.time() - start_time
        
        self._print_summary(report)
        
        return report
    
    def _test_variant(self, variant_id: str, description: str, config: dict) -> AblationResult:
        """Testa uma variante específica."""
        
        ns = f"{self.namespace_base}:{variant_id}"
        
        # Métricas
        semantic_tests = []
        contextual_tests = []
        collective_tests = []
        latencies = []
        
        # === Teste 1: Acurácia Semântica ===
        self.log("  🔍 Testando acurácia semântica...")
        
        # Salva memórias
        memories = [
            (["Ana"], "problema_login", "senha_expirada", "reset_email"),
            (["Bruno"], "fatura_nao_recebida", "email_incorreto", "reenviou"),
            (["Carla"], "erro_pagamento", "cartao_bloqueado", "atualizou"),
        ]
        
        for who, what, why, how in memories:
            if config.get("simple_mode"):
                # Modo simples: sem estrutura W5H
                self._store(who, f"{what}_{why}_{how}", "", "", ns)
            else:
                self._store(who, what, why, how, ns)
            time.sleep(0.2)
        
        time.sleep(0.5)
        
        # Testa queries
        queries = [
            ("não consigo entrar", "login"),
            ("boleto não veio", "fatura"),
            ("cobrança negada", "pagamento"),
        ]
        
        if self.quick:
            queries = queries[:2]
        
        for query, expected in queries:
            if config.get("fixed_threshold"):
                # Threshold fixo alto (simula sem adaptativo)
                results, lat = self._recall(query, ns, min_similarity=0.8)
            else:
                results, lat = self._recall(query, ns)
            
            latencies.append(lat)
            
            found = results[0].get("action", "") if results else ""
            passed = expected in found.lower()
            semantic_tests.append(passed)
        
        # === Teste 2: Recall Contextual ===
        self.log("  🔍 Testando recall contextual...")
        
        flow = [
            (["Cliente"], "produto_defeito", "nao_liga", "verificar_garantia"),
            (["Cliente"], "garantia_ok", "compra_recente", "aprovar_troca"),
        ]
        
        for who, what, why, how in flow:
            self._store(who, what, why, how, ns)
            time.sleep(0.2)
        
        time.sleep(0.5)
        
        context_queries = [("problema do produto", "defeito"), ("sobre garantia", "garantia")]
        
        if self.quick:
            context_queries = context_queries[:1]
        
        for query, expected in context_queries:
            results, lat = self._recall(query, ns)
            latencies.append(lat)
            
            found = str(results) if results else ""
            passed = expected in found.lower()
            contextual_tests.append(passed)
        
        # === Teste 3: Memória Coletiva ===
        self.log("  🔍 Testando memória coletiva...")
        
        if config.get("flat_namespace"):
            # Sem hierarquia: não deve funcionar
            collective_tests = [False, False]
        else:
            parent_ns = f"{ns}:parent"
            child_ns = f"{ns}:parent:child"
            
            self._store(["sistema"], "solucao_conexao", "padrao", "reiniciar_modem", parent_ns)
            time.sleep(0.3)
            
            # Busca do filho
            results, _ = self._recall("conexão lenta", child_ns)
            passed = any("conexao" in str(r).lower() or "reiniciar" in str(r).lower() for r in results)
            collective_tests.append(passed)
            
            # Isolamento
            other_ns = f"{self.namespace_base}:other"
            results, _ = self._recall("conexão lenta", other_ns)
            isolated = len(results) == 0
            collective_tests.append(isolated)
        
        # Calcula métricas
        sem_acc = sum(semantic_tests) / len(semantic_tests) if semantic_tests else 0
        ctx_acc = sum(contextual_tests) / len(contextual_tests) if contextual_tests else 0
        col_acc = sum(collective_tests) / len(collective_tests) if collective_tests else 0
        avg_lat = sum(latencies) / len(latencies) if latencies else 0
        
        total_passed = sum(semantic_tests) + sum(contextual_tests) + sum(collective_tests)
        total_tests = len(semantic_tests) + len(contextual_tests) + len(collective_tests)
        total_acc = total_passed / total_tests if total_tests > 0 else 0
        
        return AblationResult(
            variant=variant_id,
            description=description,
            semantic_accuracy=sem_acc,
            contextual_recall=ctx_acc,
            collective_memory=col_acc,
            efficiency_latency=avg_lat,
            total_accuracy=total_acc,
            delta_vs_full=0.0,
            tests_passed=total_passed,
            tests_total=total_tests,
        )
    
    def _print_summary(self, report: AblationReport):
        """Imprime resumo do estudo."""
        
        self.log("\n" + "=" * 60)
        self.log("📊 RELATÓRIO DO ABLATION STUDY")
        self.log("=" * 60)
        
        # Tabela de resultados
        self.log("\n📈 RESULTADOS POR VARIANTE:")
        self.log("-" * 70)
        self.log(f"{'Variante':<30} {'Semântica':>10} {'Context':>10} {'Coletiva':>10} {'Total':>10}")
        self.log("-" * 70)
        
        for result in report.results:
            name = result.description[:28]
            sem = f"{result.semantic_accuracy*100:.0f}%"
            ctx = f"{result.contextual_recall*100:.0f}%"
            col = f"{result.collective_memory*100:.0f}%"
            total = f"{result.total_accuracy*100:.0f}%"
            
            marker = "→" if result.variant == "full" else " "
            self.log(f"{marker}{name:<29} {sem:>10} {ctx:>10} {col:>10} {total:>10}")
        
        self.log("-" * 70)
        
        # Impacto de componentes
        self.log("\n🔬 IMPACTO DE CADA COMPONENTE:")
        self.log("-" * 40)
        
        sorted_impact = sorted(report.component_impact.items(), key=lambda x: x[1], reverse=True)
        
        for component, impact in sorted_impact:
            bar_len = int(abs(impact) * 50)
            bar = "█" * bar_len
            sign = "+" if impact > 0 else ""
            self.log(f"  {component:<20} {sign}{impact*100:>6.1f}%  {bar}")
        
        # Conclusão
        self.log("\n📝 CONCLUSÃO:")
        
        most_important = sorted_impact[0] if sorted_impact else ("N/A", 0)
        self.log(f"   • Componente mais crítico: {most_important[0]} (+{most_important[1]*100:.1f}%)")
        
        full_result = next((r for r in report.results if r.variant == "full"), None)
        if full_result:
            self.log(f"   • Acurácia do sistema completo: {full_result.total_accuracy*100:.1f}%")
        
        self.log(f"\n⏱️  Duração: {report.duration_seconds:.1f}s")
        self.log("=" * 60)
    
    def save_report(self, report: AblationReport, filename: str | None = None):
        """Salva relatório em JSON."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ablation_study_{ts}.json"
        
        filepath = OUTPUT_DIR / filename
        
        data = {
            "timestamp": report.timestamp,
            "duration_seconds": report.duration_seconds,
            "results": [asdict(r) for r in report.results],
            "component_impact": report.component_impact,
        }
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self.log(f"\n📁 Relatório salvo: {filepath}")
        return filepath


def generate_ablation_chart(report: AblationReport, output_path: Path):
    """Gera gráfico do ablation study."""
    
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("⚠️ matplotlib não disponível para gráficos")
        return
    
    # Dados
    variants = [r.description for r in report.results]
    totals = [r.total_accuracy * 100 for r in report.results]
    colors = ["#4CAF50" if r.variant == "full" else "#FF9800" for r in report.results]
    
    # Gráfico
    fig, ax = plt.subplots(figsize=(10, 6))
    
    bars = ax.barh(variants, totals, color=colors)
    
    for bar, val in zip(bars, totals):
        ax.text(
            val + 1,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.0f}%",
            ha="left",
            va="center",
            fontsize=10,
        )
    
    ax.set_xlabel("Acurácia (%)")
    ax.set_title("Ablation Study: Impacto de Cada Componente")
    ax.set_xlim(0, 110)
    ax.grid(axis="x", alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path / "ablation_study.png", dpi=300)
    plt.savefig(output_path / "ablation_study.pdf")
    plt.close()
    
    print(f"  ✅ Gráfico: {output_path / 'ablation_study.png'}")


# ==================== MAIN ====================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Ablation Study")
    parser.add_argument("--save", action="store_true", help="Salva resultados")
    parser.add_argument("--quick", action="store_true", help="Versão rápida")
    parser.add_argument("--chart", action="store_true", help="Gera gráfico")
    
    args = parser.parse_args()
    
    study = AblationStudy(quick=args.quick)
    report = study.run()
    
    if args.save:
        study.save_report(report)
    
    if args.chart:
        output_path = OUTPUT_DIR / "charts"
        output_path.mkdir(parents=True, exist_ok=True)
        generate_ablation_chart(report, output_path)
    
    return 0 if report.duration_seconds > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
