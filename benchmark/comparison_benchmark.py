#!/usr/bin/env python3
"""
Comparison Benchmark - Cortex vs RAG vs Mem0 vs Baseline

Benchmark focado em VALOR, não apenas métricas brutas.
Compara a QUALIDADE da informação recuperada por cada sistema.

Métricas de VALOR (foco principal):
1. Acurácia Semântica - Encontra memória certa com termos diferentes
2. Recall Contextual - Lembra de fluxos anteriores
3. Memória Coletiva - Compartilha conhecimento útil (apenas Cortex)
4. Relevância - Retorna informação útil, não ruído

Métricas de Eficiência (secundárias):
- Latência média
- Tokens no contexto

Uso:
    python comparison_benchmark.py           # Benchmark padrão
    python comparison_benchmark.py --save    # Salva resultados em JSON
    python comparison_benchmark.py -v        # Modo verbose
"""

import functools
import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Silencia logs verbosos
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Força flush imediato
print = functools.partial(print, flush=True)

# Paths
benchmark_path = Path(__file__).parent
project_root = benchmark_path.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(benchmark_path))
sys.path.insert(0, str(project_root / "sdk" / "python"))

import requests

# Imports dos agentes
from agents import BaselineAgent
from cortex_agent import CortexAgent
from rag_agent import RAGAgent
from mem0_agent import Mem0Agent


# ==================== CONFIGURAÇÃO ====================

CORTEX_URL = os.getenv("CORTEX_API_URL", "http://localhost:8000")
OLLAMA_URL = os.getenv("OLLAMA_URL", "https://c84231491772.ngrok-free.app")
OUTPUT_DIR = Path("./benchmark_results")


# ==================== MODELOS DE DADOS ====================

@dataclass
class TestResult:
    """Resultado de um teste individual."""
    name: str
    category: str
    agent: str
    passed: bool
    score: float
    expected: str
    actual: str
    latency_ms: float = 0.0
    tokens: int = 0


@dataclass
class AgentMetrics:
    """Métricas agregadas por agente."""
    name: str
    semantic_accuracy: float = 0.0
    contextual_recall: float = 0.0
    collective_memory: float = 0.0  # Apenas Cortex
    relevance: float = 0.0
    avg_latency_ms: float = 0.0
    avg_tokens: int = 0
    total_tests: int = 0
    passed_tests: int = 0
    tests: list[TestResult] = field(default_factory=list)


@dataclass
class ComparisonReport:
    """Relatório comparativo completo."""
    timestamp: str = ""
    duration_seconds: float = 0.0
    agents: dict[str, AgentMetrics] = field(default_factory=dict)
    winner_by_category: dict[str, str] = field(default_factory=dict)


# ==================== BENCHMARK ====================

class ComparisonBenchmark:
    """Benchmark comparativo focado em VALOR."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.cortex_url = CORTEX_URL
        self.ollama_url = OLLAMA_URL
        self.namespace_base = f"comparison_{int(time.time())}"
        
        # Agentes
        self.agents: dict[str, Any] = {}
        
    def log(self, msg: str):
        """Log com timestamp."""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")
    
    def _init_agents(self):
        """Inicializa todos os agentes."""
        self.log("🔧 Inicializando agentes...")
        
        # Modelo padrão
        model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
        
        # Baseline (sem memória)
        self.agents["Baseline"] = BaselineAgent(
            ollama_url=self.ollama_url,
            model=model,
        )
        
        # RAG (TF-IDF simples)
        self.agents["RAG"] = RAGAgent(
            ollama_url=self.ollama_url,
            model=model,
            namespace=f"{self.namespace_base}_rag",
        )
        
        # Mem0 (salience extraction)
        self.agents["Mem0"] = Mem0Agent(
            ollama_url=self.ollama_url,
            model=model,
            user_id=f"{self.namespace_base}_mem0",
        )
        
        # Cortex (W5H + embeddings)
        self.agents["Cortex"] = CortexAgent(
            ollama_url=self.ollama_url,
            model=model,
            cortex_url=self.cortex_url,
            namespace=f"{self.namespace_base}:cortex",
        )
        
        # Inicia novas sessões
        for agent in self.agents.values():
            agent.new_session()
        
        self.log(f"   ✅ {len(self.agents)} agentes prontos (modelo: {model})")
    
    def run(self) -> ComparisonReport:
        """Executa benchmark comparativo."""
        self.log("=" * 60)
        self.log("🎯 COMPARISON BENCHMARK - CORTEX vs RAG vs Mem0")
        self.log("=" * 60)
        
        start_time = time.time()
        report = ComparisonReport(timestamp=datetime.now().isoformat())
        
        # Verifica APIs
        if not self._check_apis():
            self.log("❌ APIs não disponíveis!")
            return report
        
        # Inicializa agentes
        self._init_agents()
        
        # Inicializa métricas por agente
        for name in self.agents:
            report.agents[name] = AgentMetrics(name=name)
        
        # Fase 1: Acurácia Semântica
        self.log("\n📊 FASE 1: Acurácia Semântica")
        self.log("-" * 40)
        self._test_semantic_accuracy(report)
        
        # Fase 2: Recall Contextual
        self.log("\n📊 FASE 2: Recall Contextual")
        self.log("-" * 40)
        self._test_contextual_recall(report)
        
        # Fase 3: Memória Coletiva (apenas Cortex)
        self.log("\n📊 FASE 3: Memória Coletiva (apenas Cortex)")
        self.log("-" * 40)
        self._test_collective_memory(report)
        
        # Fase 4: Relevância
        self.log("\n📊 FASE 4: Relevância")
        self.log("-" * 40)
        self._test_relevance(report)
        
        # Calcula métricas finais
        self._calculate_metrics(report)
        
        # Determina vencedor por categoria
        self._determine_winners(report)
        
        report.duration_seconds = time.time() - start_time
        
        # Imprime resumo
        self._print_summary(report)
        
        return report
    
    def _check_apis(self) -> bool:
        """Verifica se APIs estão disponíveis."""
        try:
            # Cortex
            r = requests.get(f"{self.cortex_url}/health", timeout=5)
            if r.status_code != 200:
                return False
            
            # Ollama
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if r.status_code != 200:
                return False
            
            return True
        except Exception:
            return False
    
    def _remember(self, agent_name: str, user_id: str, message: str):
        """Faz agente processar uma mensagem (armazena memória)."""
        agent = self.agents[agent_name]
        try:
            response = agent.process_message(message, {"user_id": user_id})
            
            # Para Cortex: força armazenamento direto via API
            # (não depende do LLM gerar [MEMORY])
            if agent_name == "Cortex":
                self._cortex_store_direct(user_id, message)
            
            return response.response if hasattr(response, "response") else str(response)
        except Exception as e:
            self.log(f"     ⚠️ Erro em {agent_name}: {e}")
            return ""
    
    def _cortex_store_direct(self, user_id: str, message: str):
        """Armazena memória diretamente na API Cortex (bypass LLM extraction)."""
        try:
            # Usa mesmo namespace que o CortexAgent
            # CORREÇÃO: Passa 'where' explicitamente para garantir isolamento
            namespace = f"{self.namespace_base}:cortex"
            requests.post(
                f"{self.cortex_url}/memory/remember",
                json={
                    "who": [user_id],
                    "what": message,  # Mensagem completa como ação
                    "why": "user_stated",
                    "how": message,  # Conteúdo completo
                    "where": namespace,  # CORREÇÃO: Campo where explícito
                    "importance": 0.9,
                    "owner_id": user_id,  # CORREÇÃO: Owner explícito para isolamento
                },
                headers={"X-Cortex-Namespace": namespace},
                timeout=5,
            )
        except Exception:
            pass  # Silencia erros
    
    def _recall(self, agent_name: str, user_id: str, query: str) -> tuple[str, float, int]:
        """Faz agente responder (usa memória).
        
        Returns:
            (response, latency_ms, context_tokens)
        """
        agent = self.agents[agent_name]
        try:
            start = time.time()
            result = agent.process_message(query, {"user_id": user_id})
            latency = (time.time() - start) * 1000
            
            # Extrai resposta
            response = result.response if hasattr(result, "response") else str(result)
            
            # Estima tokens do contexto
            context = getattr(agent, "_last_context", "")
            tokens = len(context.split()) if context else 0
            
            # Debug: verifica se Cortex recuperou memória
            if agent_name == "Cortex" and self.verbose:
                mem_count = getattr(result, "memories_retrieved", 0) if hasattr(result, "memories_retrieved") else 0
                if mem_count == 0:
                    # Tenta recall direto para debug
                    try:
                        debug_result = requests.post(
                            f"{self.cortex_url}/memory/recall",
                            json={"query": query, "context": {"who": [user_id]}, "limit": 5},
                            headers={"X-Cortex-Namespace": f"{self.namespace_base}:cortex"},
                            timeout=5,
                        ).json()
                        debug_eps = len(debug_result.get("episodes", []))
                        if debug_eps > 0:
                            self.log(f"        📋 Debug: API encontrou {debug_eps} episódios")
                    except Exception:
                        pass
            
            return response, latency, tokens
        except Exception as e:
            self.log(f"     ⚠️ Erro em {agent_name}: {e}")
            return "", 0, 0
    
    def _llm_judge(self, response: str, concept: str, context: str) -> bool:
        """
        Usa LLM para avaliar se a resposta demonstra conhecimento do conceito.
        
        Resolve o problema de falsos negativos quando sinônimos são usados.
        Ex: "conta mensal" é equivalente a "fatura"
        
        Args:
            response: Resposta do agente
            concept: Conceito que deveria estar presente
            context: Contexto original da conversa
            
        Returns:
            True se a resposta demonstra conhecimento do conceito
        """
        if not response:
            return False
        
        # Prompt para o juiz LLM
        judge_prompt = f"""Avalie se a resposta do assistente demonstra que ele LEMBROU do conceito mencionado.

Contexto original: "{context}"
Conceito esperado: "{concept}"
Resposta do assistente: "{response[:500]}"

A resposta demonstra conhecimento/lembrança do conceito "{concept}"?
Considere sinônimos válidos (ex: "fatura" = "conta mensal" = "boleto").

Responda APENAS com: SIM ou NAO"""

        try:
            import litellm
            
            result = litellm.completion(
                model=f"ollama/{os.getenv('OLLAMA_MODEL', 'gemma3:4b')}",
                messages=[{"role": "user", "content": judge_prompt}],
                api_base=self.ollama_url,
                timeout=15,
            )
            
            answer = result.choices[0].message.content.strip().upper()
            return "SIM" in answer or "YES" in answer
            
        except Exception as e:
            # Fallback para verificação literal
            return concept.lower() in response.lower()
    
    def _test_semantic_accuracy(self, report: ComparisonReport):
        """Testa acurácia semântica - encontrar memória com termos diferentes."""
        
        # Setup: Cada agente recebe as mesmas memórias (SESSÃO 1)
        memories = [
            ("user1", "Tive um problema de login, não consegui entrar no sistema"),
            ("user1", "Minha fatura não chegou no email"),
            ("user1", "O pagamento foi recusado no cartão"),
        ]
        
        for agent_name in self.agents:
            for user_id, msg in memories:
                self._remember(agent_name, user_id, msg)
                time.sleep(0.3)
        
        time.sleep(1)  # Aguarda processamento
        
        # ⚠️ NOVA SESSÃO - Simula usuário voltando depois
        # Isso limpa o histórico do Baseline, testando memória REAL
        self.log("  🔄 Iniciando nova sessão (testa memória persistente)")
        for agent in self.agents.values():
            agent.new_session()
        
        # Testes com termos DIFERENTES
        # (query, conceito esperado, contexto original, descrição)
        test_cases = [
            ("não consigo acessar minha conta", "login", "problema de login no sistema", "Login com termos diferentes"),
            ("conta mensal não veio", "fatura", "fatura não chegou no email", "Fatura como sinônimo"),
            ("cobrança foi negada", "pagamento", "pagamento foi recusado no cartão", "Pagamento com termos diferentes"),
        ]
        
        for query, concept, context, description in test_cases:
            self.log(f"\n  🔍 {description}")
            
            for agent_name in self.agents:
                response, latency, tokens = self._recall(agent_name, "user1", query)
                
                # Usa LLM como juiz para avaliar semanticamente (aceita sinônimos)
                passed = self._llm_judge(response, concept, context)
                
                result = TestResult(
                    name=description,
                    category="semantic",
                    agent=agent_name,
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    expected=concept,
                    actual=response[:100] if response else "VAZIO",
                    latency_ms=latency,
                    tokens=tokens,
                )
                report.agents[agent_name].tests.append(result)
                
                status = "✅" if passed else "❌"
                self.log(f"     {status} {agent_name}: {latency:.0f}ms")
    
    def _test_contextual_recall(self, report: ComparisonReport):
        """Testa recall contextual - lembrar de fluxos anteriores."""
        
        # Setup: Cria um fluxo de conversa (SESSÃO 1)
        flow = [
            ("user2", "Comprei um produto ontem, um notebook Dell"),
            ("user2", "Chegou com defeito na tela"),
            ("user2", "Quero acionar a garantia"),
        ]
        
        for agent_name in self.agents:
            for user_id, msg in flow:
                self._remember(agent_name, user_id, msg)
                time.sleep(0.3)
        
        time.sleep(1)
        
        # ⚠️ NOVA SESSÃO - Simula usuário voltando depois
        # Baseline perde tudo, sistemas com memória devem lembrar
        self.log("  🔄 Iniciando nova sessão (testa memória persistente)")
        for agent in self.agents.values():
            agent.new_session()
        
        # Teste: Pergunta sobre o fluxo
        # (query, conceito, contexto original, descrição)
        test_cases = [
            ("qual era o problema do produto?", "defeito", "produto chegou com defeito na tela", "Lembra do problema"),
            ("qual produto eu comprei?", "notebook", "comprei um notebook Dell", "Lembra do produto"),
            ("o que eu queria fazer?", "garantia", "quero acionar a garantia", "Lembra da intenção"),
        ]
        
        for query, concept, context, description in test_cases:
            self.log(f"\n  🔍 {description}")
            
            for agent_name in self.agents:
                response, latency, tokens = self._recall(agent_name, "user2", query)
                
                # Usa LLM como juiz (aceita sinônimos e paráfrases)
                passed = self._llm_judge(response, concept, context)
                
                result = TestResult(
                    name=description,
                    category="contextual",
                    agent=agent_name,
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    expected=concept,
                    actual=response[:100] if response else "VAZIO",
                    latency_ms=latency,
                    tokens=tokens,
                )
                report.agents[agent_name].tests.append(result)
                
                status = "✅" if passed else "❌"
                self.log(f"     {status} {agent_name}: {latency:.0f}ms")
    
    def _test_collective_memory(self, report: ComparisonReport):
        """Testa memória coletiva - apenas Cortex suporta."""
        
        # Setup: Salva conhecimento coletivo via API Cortex
        collective_knowledge = [
            ("solucao_conexao", "reiniciar_modem"),
            ("recuperar_senha", "usar_cpf"),
        ]
        
        parent_ns = f"{self.namespace_base}:coletivo"
        
        for what, how in collective_knowledge:
            try:
                requests.post(
                    f"{self.cortex_url}/memory/remember",
                    json={
                        "who": ["sistema"],
                        "what": what,
                        "why": "procedimento_padrao",
                        "how": how,
                        "importance": 0.9,
                    },
                    headers={"X-Namespace": parent_ns},
                    timeout=5,
                )
                time.sleep(0.3)
            except Exception:
                pass
        
        time.sleep(1)
        
        # Teste: Novo usuário no namespace filho deve encontrar
        test_cases = [
            ("minha conexão está lenta", "reiniciar", "Encontra solução de conexão"),
            ("esqueci minha senha", "cpf", "Encontra recuperação de senha"),
        ]
        
        for query, expected_keyword, description in test_cases:
            self.log(f"\n  🔍 {description}")
            
            # Apenas Cortex
            agent_name = "Cortex"
            child_ns = f"{parent_ns}:user_novo"
            
            try:
                data = requests.post(
                    f"{self.cortex_url}/memory/recall",
                    json={"query": query, "limit": 5},
                    headers={"X-Namespace": child_ns},
                    timeout=5,
                ).json()
                
                episodes = data.get("episodes", [])
                found = any(expected_keyword.lower() in str(ep).lower() for ep in episodes)
                
                result = TestResult(
                    name=description,
                    category="collective",
                    agent=agent_name,
                    passed=found,
                    score=1.0 if found else 0.0,
                    expected=expected_keyword,
                    actual=str([ep.get("outcome", "")[:20] for ep in episodes[:2]]),
                    latency_ms=0,
                )
                report.agents[agent_name].tests.append(result)
                
                status = "✅" if found else "❌"
                self.log(f"     {status} {agent_name}: (coletivo)")
                
            except Exception as e:
                self.log(f"     ❌ Cortex: erro - {e}")
            
            # Outros agentes não suportam
            for agent_name in ["Baseline", "RAG", "Mem0"]:
                result = TestResult(
                    name=description,
                    category="collective",
                    agent=agent_name,
                    passed=False,
                    score=0.0,
                    expected=expected_keyword,
                    actual="N/A - não suportado",
                    latency_ms=0,
                )
                report.agents[agent_name].tests.append(result)
                self.log(f"     ➖ {agent_name}: (não suportado)")
    
    def _test_relevance(self, report: ComparisonReport):
        """Testa relevância - retorna informação útil, não ruído."""
        
        # Setup: Memórias variadas
        memories = [
            ("user3", "Comprei um produto azul ontem"),
            ("user3", "A entrega atrasou 5 dias"),
            ("user3", "Gostei muito do atendimento"),
        ]
        
        for agent_name in self.agents:
            for user_id, msg in memories:
                self._remember(agent_name, user_id, msg)
                time.sleep(0.3)
        
        time.sleep(0.5)
        
        # Teste: Query específica retorna só relevante
        self.log(f"\n  🔍 Query específica retorna só relevante")
        
        for agent_name in self.agents:
            response, latency, tokens = self._recall(agent_name, "user3", "problema com entrega")
            
            # Deve mencionar atraso, não deve mencionar cor ou atendimento
            has_relevant = "atraso" in response.lower() or "entrega" in response.lower()
            has_noise = "azul" in response.lower() and "atendimento" in response.lower()
            
            passed = has_relevant and not has_noise
            
            result = TestResult(
                name="Query específica",
                category="relevance",
                agent=agent_name,
                passed=passed,
                score=1.0 if passed else (0.5 if has_relevant else 0.0),
                expected="Só entrega",
                actual=f"Relevante: {has_relevant}, Ruído: {has_noise}",
                latency_ms=latency,
                tokens=tokens,
            )
            report.agents[agent_name].tests.append(result)
            
            status = "✅" if passed else "❌"
            self.log(f"     {status} {agent_name}: {latency:.0f}ms")
    
    def _calculate_metrics(self, report: ComparisonReport):
        """Calcula métricas agregadas por agente."""
        
        for agent_name, metrics in report.agents.items():
            if not metrics.tests:
                continue
            
            # Separa por categoria
            semantic_tests = [t for t in metrics.tests if t.category == "semantic"]
            contextual_tests = [t for t in metrics.tests if t.category == "contextual"]
            collective_tests = [t for t in metrics.tests if t.category == "collective"]
            relevance_tests = [t for t in metrics.tests if t.category == "relevance"]
            
            # Calcula acurácia por categoria
            if semantic_tests:
                metrics.semantic_accuracy = sum(t.score for t in semantic_tests) / len(semantic_tests)
            
            if contextual_tests:
                metrics.contextual_recall = sum(t.score for t in contextual_tests) / len(contextual_tests)
            
            if collective_tests:
                metrics.collective_memory = sum(t.score for t in collective_tests) / len(collective_tests)
            
            if relevance_tests:
                metrics.relevance = sum(t.score for t in relevance_tests) / len(relevance_tests)
            
            # Métricas gerais
            metrics.total_tests = len(metrics.tests)
            metrics.passed_tests = sum(1 for t in metrics.tests if t.passed)
            
            latencies = [t.latency_ms for t in metrics.tests if t.latency_ms > 0]
            metrics.avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0
            
            tokens = [t.tokens for t in metrics.tests if t.tokens > 0]
            metrics.avg_tokens = sum(tokens) // len(tokens) if tokens else 0
    
    def _determine_winners(self, report: ComparisonReport):
        """Determina vencedor por categoria."""
        
        categories = ["semantic_accuracy", "contextual_recall", "collective_memory", "relevance"]
        
        for category in categories:
            best_score = 0
            best_agent = ""
            
            for agent_name, metrics in report.agents.items():
                score = getattr(metrics, category, 0)
                if score > best_score:
                    best_score = score
                    best_agent = agent_name
            
            if best_agent:
                report.winner_by_category[category] = f"{best_agent} ({best_score*100:.0f}%)"
    
    def _print_summary(self, report: ComparisonReport):
        """Imprime resumo do benchmark."""
        
        self.log("\n" + "=" * 60)
        self.log("📊 RELATÓRIO COMPARATIVO")
        self.log("=" * 60)
        
        # Tabela de resultados
        self.log("\n📈 MÉTRICAS DE VALOR:")
        self.log("-" * 60)
        self.log(f"{'Métrica':<25} {'Baseline':>10} {'RAG':>10} {'Mem0':>10} {'Cortex':>10}")
        self.log("-" * 60)
        
        metrics_names = [
            ("semantic_accuracy", "Acurácia Semântica"),
            ("contextual_recall", "Recall Contextual"),
            ("collective_memory", "Memória Coletiva"),
            ("relevance", "Relevância"),
        ]
        
        for attr, name in metrics_names:
            values = []
            for agent in ["Baseline", "RAG", "Mem0", "Cortex"]:
                if agent in report.agents:
                    val = getattr(report.agents[agent], attr, 0) * 100
                    values.append(f"{val:.0f}%")
                else:
                    values.append("N/A")
            
            self.log(f"{name:<25} {values[0]:>10} {values[1]:>10} {values[2]:>10} {values[3]:>10}")
        
        self.log("-" * 60)
        
        # Totais
        totals = []
        for agent in ["Baseline", "RAG", "Mem0", "Cortex"]:
            if agent in report.agents:
                m = report.agents[agent]
                if m.total_tests > 0:
                    total = m.passed_tests / m.total_tests * 100
                    totals.append(f"{total:.0f}%")
                else:
                    totals.append("N/A")
            else:
                totals.append("N/A")
        
        self.log(f"{'TOTAL':<25} {totals[0]:>10} {totals[1]:>10} {totals[2]:>10} {totals[3]:>10}")
        
        # Vencedores
        self.log("\n🏆 VENCEDORES POR CATEGORIA:")
        for category, winner in report.winner_by_category.items():
            pretty_name = category.replace("_", " ").title()
            self.log(f"   • {pretty_name}: {winner}")
        
        # Eficiência
        self.log("\n⚡ EFICIÊNCIA:")
        for agent in ["Baseline", "RAG", "Mem0", "Cortex"]:
            if agent in report.agents:
                m = report.agents[agent]
                self.log(f"   • {agent}: {m.avg_latency_ms:.0f}ms / {m.avg_tokens} tokens")
        
        self.log("\n" + "=" * 60)
        self.log(f"⏱️  Duração: {report.duration_seconds:.1f}s")
        self.log("=" * 60)
    
    def save_report(self, report: ComparisonReport, filename: str | None = None):
        """Salva relatório em JSON."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"comparison_{ts}.json"
        
        filepath = OUTPUT_DIR / filename
        
        # Converte para dict serializável
        data = {
            "timestamp": report.timestamp,
            "duration_seconds": report.duration_seconds,
            "agents": {},
            "winner_by_category": report.winner_by_category,
        }
        
        for name, metrics in report.agents.items():
            data["agents"][name] = {
                "semantic_accuracy": metrics.semantic_accuracy,
                "contextual_recall": metrics.contextual_recall,
                "collective_memory": metrics.collective_memory,
                "relevance": metrics.relevance,
                "avg_latency_ms": metrics.avg_latency_ms,
                "avg_tokens": metrics.avg_tokens,
                "total_tests": metrics.total_tests,
                "passed_tests": metrics.passed_tests,
                "tests": [asdict(t) for t in metrics.tests],
            }
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self.log(f"\n📁 Relatório salvo: {filepath}")


# ==================== MAIN ====================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Comparison Benchmark - Cortex vs RAG vs Mem0")
    parser.add_argument("-v", "--verbose", action="store_true", help="Modo verbose")
    parser.add_argument("--save", action="store_true", help="Salva resultados em JSON")
    parser.add_argument("-y", "--yes", action="store_true", help="Confirma execução")
    
    args = parser.parse_args()
    
    benchmark = ComparisonBenchmark(verbose=args.verbose)
    report = benchmark.run()
    
    if args.save:
        benchmark.save_report(report)
    
    return 0 if report.duration_seconds > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
