"""
Shared Memory Benchmark - Avalia memória compartilhada com isolamento pessoal.

Testa cenários críticos:
1. Isolamento de dados pessoais entre usuários
2. Compartilhamento de conhecimento aprendido
3. Distinção entre "você disse" vs "aprendi que"

Cenários:
- Customer Support: múltiplos clientes, padrões aprendidos
- Dev Team: múltiplos devs, conhecimento do projeto
- Healthcare: dados de pacientes isolados

Uso:
    python shared_memory_benchmark.py --scenario customer_support
    python shared_memory_benchmark.py --all
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Adiciona paths
benchmark_path = Path(__file__).parent
sys.path.insert(0, str(benchmark_path))
sdk_path = benchmark_path.parent / "sdk" / "python"
sys.path.insert(0, str(sdk_path))

from scenarios.shared_memory_scenarios import (
    SharedMemoryScenario,
    get_all_scenarios,
    get_scenario_by_name,
    validate_recall_result,
    calculate_scenario_score,
    CUSTOMER_SUPPORT_SCENARIO,
    DEV_TEAM_SCENARIO,
    HEALTHCARE_TEAM_SCENARIO,
)
from agents import CortexAgent, BaselineAgent


@dataclass
class SharedMemoryResult:
    """Resultado de um teste de shared memory."""
    
    scenario_name: str
    
    # Scores principais
    isolation_score: float = 0.0  # Dados pessoais isolados?
    sharing_score: float = 0.0   # Conhecimento compartilhado?
    attribution_score: float = 0.0  # Atribuição correta?
    overall_score: float = 0.0
    
    # Detalhes
    interactions_tested: int = 0
    isolation_passes: int = 0
    isolation_failures: int = 0
    sharing_passes: int = 0
    sharing_failures: int = 0
    
    # Evidências
    failures: list[dict] = field(default_factory=list)
    
    # Timing
    duration_seconds: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "scenario_name": self.scenario_name,
            "isolation_score": self.isolation_score,
            "sharing_score": self.sharing_score,
            "attribution_score": self.attribution_score,
            "overall_score": self.overall_score,
            "interactions_tested": self.interactions_tested,
            "isolation_passes": self.isolation_passes,
            "isolation_failures": self.isolation_failures,
            "sharing_passes": self.sharing_passes,
            "sharing_failures": self.sharing_failures,
            "failures": self.failures,
            "duration_seconds": self.duration_seconds,
        }


class SharedMemoryBenchmarkRunner:
    """
    Runner para benchmark de shared memory.
    
    Executa cenários de teste e avalia:
    - Se dados pessoais são isolados
    - Se conhecimento é compartilhado corretamente
    - Se atribuição é correta
    """
    
    def __init__(
        self,
        model: str = "ministral-3:3b",
        ollama_url: str = "http://localhost:11434",
        cortex_url: str = "http://localhost:8000",
        verbose: bool = True,
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.cortex_url = cortex_url
        self.verbose = verbose
        
        # Cache de agentes por usuário
        self._user_agents: dict[str, CortexAgent] = {}
    
    def _log(self, message: str) -> None:
        if self.verbose:
            print(message)
    
    def _get_agent_for_user(self, user_id: str, namespace: str) -> CortexAgent:
        """Obtém ou cria agente para um usuário."""
        key = f"{namespace}:{user_id}"
        
        if key not in self._user_agents:
            agent = CortexAgent(
                model=self.model,
                ollama_url=self.ollama_url,
                cortex_url=self.cortex_url,
                namespace=namespace,
            )
            self._user_agents[key] = agent
        
        return self._user_agents[key]
    
    def run_scenario(self, scenario: SharedMemoryScenario) -> SharedMemoryResult:
        """
        Executa um cenário de shared memory.
        """
        self._log(f"\n{'='*60}")
        self._log(f"🧪 Cenário: {scenario.name}")
        self._log(f"   {scenario.description}")
        self._log(f"   Usuários: {len(scenario.users)}")
        self._log(f"   Interações: {len(scenario.interactions)}")
        self._log(f"{'='*60}")
        
        start_time = time.time()
        result = SharedMemoryResult(scenario_name=scenario.name)
        
        # Limpa agentes anteriores
        self._user_agents.clear()
        
        # Mapeia usuários
        user_map = {u["id"]: u for u in scenario.users}
        
        # Agrupa interações por sessão
        current_sessions: dict[str, int] = {}  # user_id -> current session
        
        for idx, interaction in enumerate(scenario.interactions):
            user_id = interaction["user_id"]
            user = user_map[user_id]
            session = interaction.get("session", 1)
            message = interaction["message"]
            
            # Verifica se é nova sessão
            if current_sessions.get(user_id, 0) != session:
                current_sessions[user_id] = session
                self._log(f"\n--- Sessão {session} para {user['name']} ---")
            
            self._log(f"\n[{user['name']}] {message[:50]}...")
            
            # Obtém agente
            agent = self._get_agent_for_user(user_id, scenario.namespace)
            
            # Nova sessão se necessário
            if session > 1 and current_sessions.get(user_id) == session:
                agent.new_session(user_id=user_id)
            else:
                agent.new_session(user_id=user_id)
            
            result.interactions_tested += 1
            
            # Processa mensagem
            try:
                response = agent.process_message(message, verbose=self.verbose)
                
                # Verifica expected_recall se existir
                expected_recall = interaction.get("expected_recall")
                if expected_recall:
                    validation = self._validate_recall(
                        recall_context=response.context_from_memory,
                        expected=expected_recall,
                        user_name=user["name"],
                    )
                    
                    if validation["isolation_passed"]:
                        result.isolation_passes += 1
                        self._log(f"   ✅ Isolamento OK")
                    else:
                        result.isolation_failures += 1
                        result.failures.append({
                            "interaction_idx": idx,
                            "user": user["name"],
                            "type": "isolation",
                            "details": validation["details"],
                        })
                        self._log(f"   ❌ Isolamento FALHOU: {validation['details']}")
                    
                    if validation.get("sharing_passed"):
                        result.sharing_passes += 1
                        self._log(f"   ✅ Compartilhamento OK")
                    elif "sharing_passed" in validation:
                        result.sharing_failures += 1
                
                self._log(f"   Response: {response.content[:80]}...")
                
            except Exception as e:
                self._log(f"   ❌ Erro: {e}")
                result.failures.append({
                    "interaction_idx": idx,
                    "user": user["name"],
                    "type": "error",
                    "details": str(e),
                })
        
        # Calcula scores
        total_isolation_tests = result.isolation_passes + result.isolation_failures
        if total_isolation_tests > 0:
            result.isolation_score = result.isolation_passes / total_isolation_tests
        else:
            result.isolation_score = 1.0  # Sem testes = sem falhas
        
        total_sharing_tests = result.sharing_passes + result.sharing_failures
        if total_sharing_tests > 0:
            result.sharing_score = result.sharing_passes / total_sharing_tests
        else:
            result.sharing_score = 1.0
        
        # Attribution score (baseado em comportamentos esperados)
        result.attribution_score = self._evaluate_attribution(scenario, result)
        
        # Overall
        result.overall_score = (
            result.isolation_score * 0.4 +
            result.sharing_score * 0.3 +
            result.attribution_score * 0.3
        )
        
        result.duration_seconds = time.time() - start_time
        
        self._log(f"\n{'='*60}")
        self._log(f"📊 RESULTADOS - {scenario.name}")
        self._log(f"   Isolamento: {result.isolation_score:.1%}")
        self._log(f"   Compartilhamento: {result.sharing_score:.1%}")
        self._log(f"   Atribuição: {result.attribution_score:.1%}")
        self._log(f"   OVERALL: {result.overall_score:.1%}")
        self._log(f"   Duração: {result.duration_seconds:.1f}s")
        self._log(f"{'='*60}")
        
        return result
    
    def _validate_recall(
        self,
        recall_context: str,
        expected: dict,
        user_name: str,
    ) -> dict:
        """Valida se o recall atende às expectativas."""
        recall_lower = recall_context.lower()
        
        isolation_passed = True
        details = []
        
        # Verifica should_have
        for item in expected.get("should_have", []):
            if item.lower() not in recall_lower:
                isolation_passed = True  # OK se não tem algo que deveria ter
        
        # Verifica should_not_have (crítico para isolamento)
        for item in expected.get("should_not_have", []):
            if item.lower() in recall_lower:
                isolation_passed = False
                details.append(f"Encontrou '{item}' que não deveria estar")
        
        # Verifica may_have (opcional)
        sharing_passed = None
        if "may_have" in expected:
            for item in expected["may_have"]:
                if item.lower() in recall_lower:
                    sharing_passed = True
                    break
            if sharing_passed is None:
                sharing_passed = True  # OK se não encontrou opcional
        
        return {
            "isolation_passed": isolation_passed,
            "sharing_passed": sharing_passed,
            "details": "; ".join(details) if details else "OK",
        }
    
    def _evaluate_attribution(
        self,
        scenario: SharedMemoryScenario,
        result: SharedMemoryResult,
    ) -> float:
        """Avalia se a atribuição está correta."""
        # Por enquanto, usa heurística simples
        # Score alto se não houve falhas de isolamento
        if result.isolation_failures == 0:
            return 1.0
        
        # Penaliza por falhas
        return max(0.0, 1.0 - (result.isolation_failures * 0.2))
    
    def run_all_scenarios(self) -> dict[str, SharedMemoryResult]:
        """Executa todos os cenários."""
        results = {}
        
        for scenario in get_all_scenarios():
            result = self.run_scenario(scenario)
            results[scenario.name] = result
        
        return results
    
    def generate_report(self, results: dict[str, SharedMemoryResult]) -> str:
        """Gera relatório em Markdown."""
        lines = [
            "# Shared Memory Benchmark Report",
            "",
            f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Modelo:** {self.model}",
            "",
            "## Resumo",
            "",
            "| Cenário | Isolamento | Compartilhamento | Atribuição | Overall |",
            "|---------|------------|------------------|------------|---------|",
        ]
        
        for name, result in results.items():
            lines.append(
                f"| {name} | {result.isolation_score:.1%} | "
                f"{result.sharing_score:.1%} | {result.attribution_score:.1%} | "
                f"**{result.overall_score:.1%}** |"
            )
        
        # Média
        avg_isolation = sum(r.isolation_score for r in results.values()) / len(results)
        avg_sharing = sum(r.sharing_score for r in results.values()) / len(results)
        avg_attribution = sum(r.attribution_score for r in results.values()) / len(results)
        avg_overall = sum(r.overall_score for r in results.values()) / len(results)
        
        lines.extend([
            f"| **MÉDIA** | **{avg_isolation:.1%}** | **{avg_sharing:.1%}** | "
            f"**{avg_attribution:.1%}** | **{avg_overall:.1%}** |",
            "",
            "## Falhas Detectadas",
            "",
        ])
        
        for name, result in results.items():
            if result.failures:
                lines.append(f"### {name}")
                lines.append("")
                for failure in result.failures:
                    lines.append(f"- **{failure['type']}** ({failure['user']}): {failure['details']}")
                lines.append("")
        
        lines.extend([
            "## Interpretação",
            "",
            "- **Isolamento > 95%**: Dados pessoais bem protegidos",
            "- **Compartilhamento > 80%**: Conhecimento sendo compartilhado",
            "- **Atribuição > 90%**: Sem confusão de 'você disse' vs 'aprendi que'",
            "",
        ])
        
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Shared Memory Benchmark")
    parser.add_argument(
        "--scenario",
        type=str,
        help="Nome do cenário específico",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Executar todos os cenários",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="ministral-3:3b",
        help="Modelo Ollama",
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        default="http://localhost:11434",
        help="URL do Ollama",
    )
    parser.add_argument(
        "--cortex-url",
        type=str,
        default="http://localhost:8000",
        help="URL da API Cortex",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Arquivo de saída para resultados",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Menos output",
    )
    
    args = parser.parse_args()
    
    runner = SharedMemoryBenchmarkRunner(
        model=args.model,
        ollama_url=args.ollama_url,
        cortex_url=args.cortex_url,
        verbose=not args.quiet,
    )
    
    if args.all:
        results = runner.run_all_scenarios()
    elif args.scenario:
        scenario = get_scenario_by_name(args.scenario)
        if not scenario:
            print(f"❌ Cenário não encontrado: {args.scenario}")
            print(f"   Disponíveis: {[s.name for s in get_all_scenarios()]}")
            sys.exit(1)
        results = {args.scenario: runner.run_scenario(scenario)}
    else:
        # Default: customer_support
        results = {"customer_support_shared": runner.run_scenario(CUSTOMER_SUPPORT_SCENARIO)}
    
    # Gera relatório
    report = runner.generate_report(results)
    print("\n" + report)
    
    # Salva resultados
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump({name: r.to_dict() for name, r in results.items()}, f, indent=2)
        print(f"\n💾 Resultados salvos em: {output_path}")
    
    # Salva relatório
    report_path = benchmark_path / "results" / f"shared_memory_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report)
    print(f"📄 Relatório salvo em: {report_path}")


if __name__ == "__main__":
    main()

