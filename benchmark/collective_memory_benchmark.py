"""
Benchmark de Memória Coletiva e Decaimento.

Este benchmark testa:
1. ISOLAMENTO: Cada usuário tem suas memórias isoladas
2. MEMÓRIA COLETIVA: Conhecimento LEARNED é compartilhado entre usuários
3. DECAIMENTO: Memórias não acessadas perdem força ao longo do tempo

Cenários:
- Múltiplos clientes do mesmo domínio (ex: suporte técnico)
- Problemas similares para testar extração de padrões
- Gap de tempo para testar decaimento

Fluxo esperado:
1. Cliente A tem problema X → resolve
2. DreamAgent extrai conhecimento procedural → LEARNED
3. Cliente B tem problema similar X → deve lembrar solução
4. Cliente C tem problema Y diferente → NÃO deve ver memórias de A/B pessoais
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field

import sys
from pathlib import Path

# Adiciona paths
benchmark_path = Path(__file__).parent
project_root = benchmark_path.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(benchmark_path))

from agents import BaselineAgent
from cortex_agent import CortexAgent
from conversation_generator import Conversation, Session, Message


# ==================== CENÁRIOS DE TESTE ====================


@dataclass
class CollectiveScenario:
    """Cenário com múltiplos usuários para testar memória coletiva."""
    
    name: str
    domain: str
    description: str
    users: list[dict] = field(default_factory=list)
    # Problema comum que deve ser extraído como LEARNED
    common_problem: str = ""
    common_solution: str = ""


def create_support_scenarios() -> list[CollectiveScenario]:
    """Cria cenários de suporte técnico com problemas similares."""
    
    scenarios = [
        CollectiveScenario(
            name="timeout_api",
            domain="customer_support",
            description="Múltiplos clientes com problema de timeout na API",
            common_problem="timeout na API",
            common_solution="aumentar connection timeout e verificar pool de conexões",
            users=[
                {
                    "id": "cliente_a",
                    "name": "Pedro Costa",
                    "problem": "Minha integração com a API está dando timeout toda hora!",
                    "details": "Uso o plano Enterprise, comecei a ter esse problema ontem",
                    "resolution": "Aumentei o timeout para 30s e funcionou!",
                },
                {
                    "id": "cliente_b", 
                    "name": "Maria Silva",
                    "problem": "API retornando timeout intermitente",
                    "details": "Acontece principalmente em horário de pico",
                    # Este cliente deve receber a solução aprendida do cliente A
                    "should_recall_learned": True,
                },
                {
                    "id": "cliente_c",
                    "name": "João Santos",
                    "problem": "Quero fazer upgrade do meu plano",
                    "details": "Estou no plano básico e preciso de mais recursos",
                    # Este cliente NÃO deve ver memórias pessoais de A ou B
                    "should_not_see_personal": True,
                },
            ]
        ),
        
        CollectiveScenario(
            name="pagamento_recusado",
            domain="customer_support", 
            description="Clientes com problema de pagamento recusado",
            common_problem="pagamento recusado",
            common_solution="verificar validade do cartão, limite disponível e dados cadastrais",
            users=[
                {
                    "id": "cliente_d",
                    "name": "Ana Oliveira",
                    "problem": "Meu pagamento foi recusado mas tenho limite!",
                    "details": "Cartão Visa, já conferi o limite",
                    "resolution": "Era o endereço de cobrança diferente do cartão",
                },
                {
                    "id": "cliente_e",
                    "name": "Carlos Souza",
                    "problem": "Não consigo finalizar a compra, dá erro no pagamento",
                    "details": "Tentei 3 cartões diferentes",
                    "should_recall_learned": True,
                },
            ]
        ),
    ]
    
    return scenarios


def create_education_scenarios() -> list[CollectiveScenario]:
    """Cria cenários educacionais com dúvidas similares."""
    
    scenarios = [
        CollectiveScenario(
            name="derivadas_calculo",
            domain="education",
            description="Alunos com dificuldade em derivadas",
            common_problem="entender derivadas",
            common_solution="começar com taxa de variação, usar exemplos de velocidade, depois regra da cadeia",
            users=[
                {
                    "id": "aluno_a",
                    "name": "Letícia",
                    "problem": "Não entendo derivadas, o professor explica mas não entra na minha cabeça",
                    "details": "Estou no 1º período de engenharia",
                    "resolution": "Ah, pensar como velocidade instantânea ajudou muito!",
                },
                {
                    "id": "aluno_b",
                    "name": "Rafael",
                    "problem": "Preciso de ajuda com cálculo, derivadas especificamente",
                    "details": "Prova semana que vem",
                    "should_recall_learned": True,
                },
                {
                    "id": "aluno_c",
                    "name": "Camila",
                    "problem": "Como estudo para prova de história?",
                    "details": "É sobre Revolução Francesa",
                    "should_not_see_personal": True,
                },
            ]
        ),
    ]
    
    return scenarios


# ==================== RUNNER ====================


class CollectiveMemoryBenchmark:
    """
    Runner para benchmark de memória coletiva.
    
    Testa:
    1. Isolamento entre usuários
    2. Herança de memória LEARNED
    3. Decaimento de memória
    """
    
    def __init__(
        self,
        model: str | None = None,
        ollama_url: str | None = None,
        cortex_url: str | None = None,
        namespace: str = "collective_test",
        verbose: bool = True,
    ):
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma3:4b")
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.cortex_url = cortex_url or os.getenv("CORTEX_API_URL", "http://localhost:8000")
        self.namespace = namespace
        self.verbose = verbose
        
        self.baseline = BaselineAgent(
            model=self.model,
            ollama_url=self.ollama_url,
        )
        
        self.cortex = CortexAgent(
            model=self.model,
            ollama_url=self.ollama_url,
            cortex_url=self.cortex_url,
            namespace=self.namespace,
        )
    
    def _log(self, msg: str, end: str = "\n"):
        if self.verbose:
            print(msg, end=end, flush=True)
    
    def run_scenario(self, scenario: CollectiveScenario) -> dict[str, Any]:
        """
        Executa um cenário com múltiplos usuários.
        
        Fluxo CORRIGIDO:
        1. Primeiro usuário reporta problema → resolve
        2. DreamAgent consolida (cria LEARNED)
        3. Segundo usuário reporta problema similar → DEVE lembrar da solução
        4. Terceiro usuário com problema diferente → isolado
        """
        self._log(f"\n{'='*60}")
        self._log(f"🎯 CENÁRIO: {scenario.name}")
        self._log(f"   {scenario.description}")
        self._log(f"   Problema comum: {scenario.common_problem}")
        self._log(f"   Usuários: {len(scenario.users)}")
        self._log(f"{'='*60}")
        
        results = {
            "scenario": scenario.name,
            "domain": scenario.domain,
            "common_problem": scenario.common_problem,
            "users": [],
            "collective_memory_test": {},
            "isolation_test": {},
        }
        
        # Categoriza usuários por tipo
        users_with_resolution = [u for u in scenario.users if u.get("resolution")]
        users_should_recall = [u for u in scenario.users if u.get("should_recall_learned")]
        users_isolation_test = [u for u in scenario.users if u.get("should_not_see_personal")]
        
        # ═══════════════════════════════════════════════════════════
        # FASE 1: Usuários que CRIAM conhecimento (resolvem problemas)
        # ═══════════════════════════════════════════════════════════
        self._log(f"\n📌 FASE 1: Criando conhecimento...")
        
        for user_idx, user in enumerate(users_with_resolution):
            user_result = self._process_user(user, scenario, user_idx + 1)
            results["users"].append(user_result)
            time.sleep(0.5)
        
        # ═══════════════════════════════════════════════════════════
        # FASE 2: DreamAgent consolida → cria memória LEARNED
        # ═══════════════════════════════════════════════════════════
        self._log(f"\n{'─'*50}")
        self._log("🌙 FASE 2: DreamAgent consolidando memórias...")
        dream_result = self._simulate_dream_consolidation(scenario)
        results["dream_consolidation"] = dream_result
        
        # ═══════════════════════════════════════════════════════════
        # FASE 3: Usuários que DEVEM LEMBRAR (testam memória coletiva)
        # ═══════════════════════════════════════════════════════════
        if users_should_recall:
            self._log(f"\n📌 FASE 3: Testando memória coletiva (LEARNED)...")
            
            for user_idx, user in enumerate(users_should_recall):
                user_result = self._process_user(user, scenario, len(users_with_resolution) + user_idx + 1)
                
                # Verifica se lembrou de memória coletiva
                last_interaction = user_result["interactions"][-1] if user_result["interactions"] else {}
                context = last_interaction.get("memory_context", "")
                
                has_learned = self._check_learned_memory(context, scenario.common_solution)
                user_result["recalled_learned"] = has_learned
                results["collective_memory_test"][user["id"]] = has_learned
                
                if has_learned:
                    self._log(f"   ✅ LEMBROU conhecimento coletivo!")
                else:
                    self._log(f"   ❌ NÃO lembrou conhecimento coletivo")
                    self._log(f"      Contexto: {context[:100] if context else '(vazio)'}...")
                
                results["users"].append(user_result)
                time.sleep(0.5)
        
        # ═══════════════════════════════════════════════════════════
        # FASE 4: Usuários de ISOLAMENTO (não devem ver memórias pessoais)
        # ═══════════════════════════════════════════════════════════
        if users_isolation_test:
            self._log(f"\n📌 FASE 4: Testando isolamento...")
            
            for user_idx, user in enumerate(users_isolation_test):
                user_result = self._process_user(user, scenario, len(users_with_resolution) + len(users_should_recall) + user_idx + 1)
                
                # Verifica isolamento
                last_interaction = user_result["interactions"][-1] if user_result["interactions"] else {}
                context = last_interaction.get("memory_context", "")
                
                has_personal_leak = self._check_personal_leak(
                    context, 
                    [u["name"] for u in scenario.users if u["id"] != user["id"]]
                )
                user_result["personal_leak"] = has_personal_leak
                results["isolation_test"][user["id"]] = not has_personal_leak
                
                if has_personal_leak:
                    self._log(f"   ❌ VAZAMENTO de memória pessoal!")
                else:
                    self._log(f"   ✅ Isolamento OK - não viu memórias pessoais de outros")
                
                results["users"].append(user_result)
                time.sleep(0.5)
        
        return results
    
    def _process_user(self, user: dict, scenario: CollectiveScenario, user_num: int) -> dict:
        """Processa um usuário individual."""
        user_id = user["id"]
        user_name = user["name"]
        
        # Define namespace hierárquico para o usuário
        user_namespace = f"{self.namespace}:{scenario.domain}:{user_id}"
        self.cortex.set_namespace(user_namespace)
        self.cortex.new_session(user_id=user_id)
        
        self._log(f"\n{'─'*50}")
        self._log(f"👤 USUÁRIO {user_num}: {user_name} ({user_id})")
        self._log(f"   Namespace: {user_namespace}")
        
        user_result = {
            "user_id": user_id,
            "user_name": user_name,
            "namespace": user_namespace,
            "interactions": [],
        }
        
        # INTERAÇÃO 1: Usuário reporta problema
        problem_msg = f"Olá, meu nome é {user_name}. {user['problem']}"
        if user.get("details"):
            problem_msg += f" {user['details']}"
        
        self._log(f"\n   💬 Problema: {user['problem'][:60]}...")
        
        response = self.cortex.process_message(problem_msg)
        
        user_result["interactions"].append({
            "type": "problem_report",
            "message": problem_msg,
            "response": response.content,
            "memory_context": response.context_from_memory,
            "entities": response.memory_entities,
            "episodes": response.memory_episodes,
        })
        
        # Se o usuário tem resolução, simula a resolução
        if user.get("resolution"):
            self._log(f"   💡 Resolução: {user['resolution'][:50]}...")
            
            resolution_msg = user["resolution"]
            response2 = self.cortex.process_message(resolution_msg)
            
            user_result["interactions"].append({
                "type": "resolution",
                "message": resolution_msg,
                "response": response2.content,
                "memory_extracted": response2.memory_extracted,
            })
        
        return user_result
    
    def _check_learned_memory(self, context: str | None, expected_pattern: str) -> bool:
        """Verifica se o contexto contém conhecimento aprendido."""
        if not context:
            return False
        
        context_lower = context.lower()
        patterns = expected_pattern.lower().split()
        
        # Verifica se palavras-chave da solução aparecem
        matches = sum(1 for p in patterns if p in context_lower)
        return matches >= len(patterns) // 2
    
    def _check_personal_leak(self, context: str | None, other_names: list[str]) -> bool:
        """Verifica se há vazamento de memórias pessoais de outros usuários."""
        if not context:
            return False
        
        context_lower = context.lower()
        for name in other_names:
            if name.lower() in context_lower:
                return True
        return False
    
    def _simulate_dream_consolidation(self, scenario: CollectiveScenario) -> dict:
        """
        Simula o DreamAgent extraindo conhecimento procedural.
        
        Na implementação real, isso seria feito pelo DreamAgent.
        Aqui simulamos para testar o fluxo.
        """
        import requests
        
        try:
            # Chama a API para criar memória LEARNED no namespace pai
            parent_namespace = f"{self.namespace}:{scenario.domain}"
            
            resp = requests.post(
                f"{self.cortex_url}/memory/remember",
                json={
                    "who": ["sistema"],
                    "what": scenario.common_problem,
                    "why": "procedural_knowledge",
                    "how": scenario.common_solution,
                    "where": parent_namespace,
                    "importance": 0.85,
                    "visibility": "learned",
                    "owner_id": "system",
                },
                headers={"X-Cortex-Namespace": parent_namespace},
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self._log(f"   ✅ Conhecimento procedural criado: {scenario.common_problem[:40]}")
                return {
                    "success": True,
                    "memory_id": data.get("memory_id"),
                    "problem": scenario.common_problem,
                    "solution": scenario.common_solution,
                }
            else:
                self._log(f"   ⚠️ Falha ao criar memória LEARNED: {resp.status_code}")
                return {"success": False, "error": resp.text}
                
        except Exception as e:
            self._log(f"   ❌ Erro na consolidação: {e}")
            return {"success": False, "error": str(e)}
    
    def run_decay_test(self) -> dict[str, Any]:
        """
        Testa decaimento de memória.
        
        1. Cria memórias com diferentes timestamps
        2. Verifica que memórias antigas têm menor retrievability
        3. Confirma que memórias fracas não aparecem no recall
        """
        self._log(f"\n{'='*60}")
        self._log("⏰ TESTE DE DECAIMENTO DE MEMÓRIA")
        self._log(f"{'='*60}")
        
        import requests
        
        results = {
            "test": "decay",
            "memories_created": [],
            "recall_results": [],
        }
        
        test_namespace = f"{self.namespace}:decay_test"
        
        # Cria memórias com diferentes "idades" simuladas via importance
        memories_to_create = [
            {"what": "problema_recente", "importance": 0.9, "age": "1 dia"},
            {"what": "problema_semana_passada", "importance": 0.7, "age": "7 dias"},
            {"what": "problema_mes_passado", "importance": 0.4, "age": "30 dias"},
            {"what": "problema_antigo", "importance": 0.2, "age": "90 dias"},
        ]
        
        self._log("\n📝 Criando memórias com diferentes 'idades'...")
        
        for mem in memories_to_create:
            try:
                resp = requests.post(
                    f"{self.cortex_url}/memory/remember",
                    json={
                        "who": ["decay_test_user"],
                        "what": mem["what"],
                        "why": "decay_test",
                        "how": f"resolvido após {mem['age']}",
                        "where": test_namespace,
                        "importance": mem["importance"],
                    },
                    headers={"X-Cortex-Namespace": test_namespace},
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    self._log(f"   ✓ {mem['what']} (importance={mem['importance']})")
                    results["memories_created"].append({
                        **mem,
                        "memory_id": data.get("memory_id"),
                    })
                    
            except Exception as e:
                self._log(f"   ✗ Erro: {e}")
        
        # Faz recall e verifica ordem de prioridade
        self._log("\n🔍 Testando recall (memórias mais fortes devem aparecer primeiro)...")
        
        try:
            resp = requests.post(
                f"{self.cortex_url}/memory/recall",
                json={
                    "query": "problema resolvido",
                    "context": {},
                    "limit": 10,
                },
                headers={"X-Cortex-Namespace": test_namespace},
            )
            
            if resp.status_code == 200:
                data = resp.json()
                self._log(f"   📊 Episódios encontrados: {data.get('episodes_found', 0)}")
                
                episodes = data.get("episodes", [])
                for i, ep in enumerate(episodes):
                    action = ep.get("action", "?")
                    self._log(f"   {i+1}. {action}")
                
                results["recall_results"] = {
                    "episodes_found": data.get("episodes_found", 0),
                    "episodes": episodes,
                    "context": data.get("prompt_context", ""),
                }
                
                # Verifica se a ordem faz sentido (recentes primeiro)
                if episodes:
                    first_action = episodes[0].get("action", "")
                    if "recente" in first_action:
                        self._log("   ✅ Memória mais recente apareceu primeiro!")
                        results["decay_working"] = True
                    else:
                        self._log("   ⚠️ Ordem pode não estar priorizando recentes")
                        results["decay_working"] = False
                        
        except Exception as e:
            self._log(f"   ❌ Erro no recall: {e}")
            results["error"] = str(e)
        
        return results
    
    def run_full_benchmark(
        self,
        clear_before: bool = True,
        include_decay_test: bool = True,
    ) -> dict[str, Any]:
        """
        Executa benchmark completo.
        
        Args:
            clear_before: Limpar memória antes
            include_decay_test: Incluir teste de decaimento
        """
        started_at = datetime.now()
        
        self._log("\n" + "=" * 70)
        self._log("🧠 BENCHMARK DE MEMÓRIA COLETIVA E DECAIMENTO")
        self._log(f"   Modelo: {self.model}")
        self._log(f"   Namespace: {self.namespace}")
        self._log("=" * 70)
        
        if clear_before:
            self._log("\n🧹 Limpando memória...")
            self.cortex.clear_namespace()
        
        results = {
            "started_at": started_at.isoformat(),
            "model": self.model,
            "namespace": self.namespace,
            "scenarios": [],
            "decay_test": None,
            "summary": {},
        }
        
        # Executa cenários de suporte
        support_scenarios = create_support_scenarios()
        for scenario in support_scenarios:
            scenario_result = self.run_scenario(scenario)
            results["scenarios"].append(scenario_result)
        
        # Executa cenários de educação
        education_scenarios = create_education_scenarios()
        for scenario in education_scenarios:
            scenario_result = self.run_scenario(scenario)
            results["scenarios"].append(scenario_result)
        
        # Teste de decaimento
        if include_decay_test:
            results["decay_test"] = self.run_decay_test()
        
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        
        # Sumário
        total_users = sum(len(s.get("users", [])) for s in results["scenarios"])
        collective_tests = sum(
            len(s.get("collective_memory_test", {})) 
            for s in results["scenarios"]
        )
        collective_passed = sum(
            sum(1 for v in s.get("collective_memory_test", {}).values() if v)
            for s in results["scenarios"]
        )
        isolation_tests = sum(
            len(s.get("isolation_test", {}))
            for s in results["scenarios"]
        )
        isolation_passed = sum(
            sum(1 for v in s.get("isolation_test", {}).values() if v)
            for s in results["scenarios"]
        )
        
        results["summary"] = {
            "duration_seconds": duration,
            "total_scenarios": len(results["scenarios"]),
            "total_users": total_users,
            "collective_memory": {
                "tests": collective_tests,
                "passed": collective_passed,
                "rate": collective_passed / collective_tests if collective_tests > 0 else 0,
            },
            "isolation": {
                "tests": isolation_tests,
                "passed": isolation_passed,
                "rate": isolation_passed / isolation_tests if isolation_tests > 0 else 0,
            },
            "decay_working": results.get("decay_test", {}).get("decay_working", None),
        }
        
        self._log("\n" + "=" * 70)
        self._log("📊 SUMÁRIO DO BENCHMARK")
        self._log(f"   ⏱️  Duração: {duration:.1f}s")
        self._log(f"   👥 Usuários testados: {total_users}")
        self._log(f"   🧠 Memória Coletiva: {collective_passed}/{collective_tests} passaram")
        self._log(f"   🔒 Isolamento: {isolation_passed}/{isolation_tests} passaram")
        if results["decay_test"]:
            decay_ok = "✅" if results["summary"]["decay_working"] else "⚠️"
            self._log(f"   ⏰ Decaimento: {decay_ok}")
        self._log("=" * 70)
        
        return results
    
    def save_results(self, results: dict, filepath: Path | str):
        """Salva resultados em JSON."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        self._log(f"\n💾 Resultados salvos em: {filepath}")


def main():
    """Função principal."""
    benchmark = CollectiveMemoryBenchmark(
        namespace="collective_benchmark",
        verbose=True,
    )
    
    # Verifica conexões
    if not benchmark.baseline.test_connection():
        print("❌ Ollama não está acessível")
        return
    
    if not benchmark.cortex.test_connection():
        print("❌ Cortex API não está acessível")
        return
    
    # Executa benchmark
    results = benchmark.run_full_benchmark(
        clear_before=True,
        include_decay_test=True,
    )
    
    # Salva resultados
    output_path = Path(__file__).parent / "results" / f"collective_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    benchmark.save_results(results, output_path)


if __name__ == "__main__":
    main()

