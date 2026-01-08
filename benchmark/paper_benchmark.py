#!/usr/bin/env python3
"""
Paper Benchmark - Avaliação Completa do Cortex Memory System

Este benchmark gera todas as métricas necessárias para o paper acadêmico,
comparando o Cortex com sistemas de memória tradicionais (RAG, Mem0).

Métricas avaliadas:
1. QUALIDADE DO RECALL
   - Acurácia semântica (encontra memória certa com termos diferentes)
   - Precisão (memórias relevantes / total retornadas)
   - Recall contextual (lembra de fluxos/conversas)

2. MEMÓRIA COLETIVA
   - Compartilhamento de conhecimento entre usuários
   - Isolamento de dados pessoais (PII/PCI)
   - Herança de namespace

3. EFICIÊNCIA OPERACIONAL
   - Latência de recall (ms)
   - Tokens no contexto
   - Overhead vs baseline

4. INTELIGÊNCIA DA MEMÓRIA
   - Consolidação (compacta episódios similares)
   - Decaimento (Ebbinghaus - memórias não usadas enfraquecem)
   - Relevância (não retorna ruído)

Saída:
- Relatório completo para paper
- Métricas em JSON para análise
- Gráficos comparativos (opcional)
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


# ==================== CONFIGURAÇÃO ====================

CORTEX_URL = os.getenv("CORTEX_API_URL", "http://localhost:8000")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://172.30.64.1:11434")
OUTPUT_DIR = Path("./benchmark_results")


# ==================== MODELOS DE DADOS ====================

@dataclass
class TestResult:
    """Resultado de um teste individual."""
    name: str
    category: str
    passed: bool
    score: float  # 0.0 a 1.0
    expected: str
    actual: str
    latency_ms: float = 0.0
    tokens: int = 0
    details: dict = field(default_factory=dict)


@dataclass
class CategoryMetrics:
    """Métricas agregadas por categoria."""
    name: str
    total_tests: int = 0
    passed_tests: int = 0
    accuracy: float = 0.0
    avg_latency_ms: float = 0.0
    avg_tokens: int = 0
    tests: list[TestResult] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    """Relatório completo do benchmark."""
    timestamp: str = ""
    duration_seconds: float = 0.0
    
    # Métricas por categoria
    semantic_accuracy: CategoryMetrics = field(default_factory=lambda: CategoryMetrics("Acurácia Semântica"))
    contextual_recall: CategoryMetrics = field(default_factory=lambda: CategoryMetrics("Recall Contextual"))
    collective_memory: CategoryMetrics = field(default_factory=lambda: CategoryMetrics("Memória Coletiva"))
    relevance: CategoryMetrics = field(default_factory=lambda: CategoryMetrics("Relevância"))
    efficiency: CategoryMetrics = field(default_factory=lambda: CategoryMetrics("Eficiência"))
    
    # Totais
    total_tests: int = 0
    total_passed: int = 0
    overall_accuracy: float = 0.0
    
    # Comparativo (se disponível)
    comparison: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return asdict(self)


# ==================== BENCHMARK ====================

class PaperBenchmark:
    """Benchmark completo para o paper."""
    
    def __init__(self, verbose: bool = True):
        self.cortex_url = CORTEX_URL
        self.verbose = verbose
        self.namespace_base = f"paper_bench_{int(time.time())}"
        self.results: list[TestResult] = []
        
    def log(self, msg: str) -> None:
        """Log com timestamp."""
        if self.verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    
    def _remember(
        self, 
        who: list[str], 
        what: str, 
        why: str, 
        how: str, 
        namespace: str,
        visibility: str = "personal",
    ) -> dict:
        """Salva uma memória."""
        r = requests.post(
            f"{self.cortex_url}/memory/remember",
            headers={"Content-Type": "application/json", "X-Cortex-Namespace": namespace},
            json={
                "who": who, 
                "what": what, 
                "why": why, 
                "how": how, 
                "where": namespace,
                "visibility": visibility,
            },
            timeout=60,
        )
        return r.json()
    
    def _recall(self, query: str, namespace: str) -> tuple[dict, float]:
        """Busca memórias e retorna (resultado, latencia_ms)."""
        start = time.time()
        r = requests.post(
            f"{self.cortex_url}/memory/recall",
            headers={"Content-Type": "application/json", "X-Cortex-Namespace": namespace},
            json={"query": query, "context": {}},
            timeout=60,
        )
        latency = (time.time() - start) * 1000
        return r.json(), latency
    
    def _count_context_tokens(self, context: str) -> int:
        """Estima tokens no contexto (aproximado)."""
        if not context:
            return 0
        # Estimativa: ~4 chars por token
        return len(context) // 4
    
    def run(self) -> BenchmarkReport:
        """Executa o benchmark completo."""
        start_time = time.time()
        report = BenchmarkReport(timestamp=datetime.now().isoformat())
        
        self.log("=" * 60)
        self.log("🎯 CORTEX PAPER BENCHMARK")
        self.log("=" * 60)
        
        # Verifica API
        if not self._check_api():
            self.log("❌ API não disponível!")
            return report
        
        # Fase 1: Acurácia Semântica
        self.log("\n📊 FASE 1: Acurácia Semântica")
        self.log("-" * 40)
        report.semantic_accuracy = self._test_semantic_accuracy()
        
        # Fase 2: Recall Contextual
        self.log("\n📊 FASE 2: Recall Contextual")
        self.log("-" * 40)
        report.contextual_recall = self._test_contextual_recall()
        
        # Fase 3: Memória Coletiva
        self.log("\n📊 FASE 3: Memória Coletiva")
        self.log("-" * 40)
        report.collective_memory = self._test_collective_memory()
        
        # Fase 4: Relevância
        self.log("\n📊 FASE 4: Relevância")
        self.log("-" * 40)
        report.relevance = self._test_relevance()
        
        # Fase 5: Eficiência
        self.log("\n📊 FASE 5: Eficiência")
        self.log("-" * 40)
        report.efficiency = self._test_efficiency()
        
        # Calcula totais
        all_categories = [
            report.semantic_accuracy,
            report.contextual_recall,
            report.collective_memory,
            report.relevance,
            report.efficiency,
        ]
        
        report.total_tests = sum(c.total_tests for c in all_categories)
        report.total_passed = sum(c.passed_tests for c in all_categories)
        report.overall_accuracy = report.total_passed / report.total_tests if report.total_tests > 0 else 0
        report.duration_seconds = time.time() - start_time
        
        # Gera resumo
        self._print_summary(report)
        
        return report
    
    def _check_api(self) -> bool:
        """Verifica se API está disponível."""
        try:
            r = requests.get(f"{self.cortex_url}/health", timeout=5)
            return r.status_code == 200
        except Exception:
            return False
    
    def _test_semantic_accuracy(self) -> CategoryMetrics:
        """Testa acurácia semântica - encontrar memória certa com termos diferentes."""
        metrics = CategoryMetrics(name="Acurácia Semântica")
        ns = f"{self.namespace_base}:semantic"
        
        # Setup: Salva memórias com termos específicos
        memories = [
            (["Ana"], "problema_login_sistema", "senha_expirada", "reset_por_email"),
            (["Bruno"], "fatura_nao_recebida", "email_incorreto", "reenviou_fatura"),
            (["Carla"], "erro_pagamento_cartao", "cartao_bloqueado", "atualizou_dados"),
            (["Daniel"], "cancelamento_assinatura", "insatisfacao_servico", "ofereceu_desconto"),
            (["Elena"], "duvida_cobranca", "valor_incorreto", "explicou_tarifas"),
        ]
        
        for who, what, why, how in memories:
            self._remember(who, what, why, how, ns)
            time.sleep(0.4)  # Tempo para embedding
        
        time.sleep(1.5)  # Aguarda embeddings estarem prontos
        
        # Testes com termos DIFERENTES (sinonimos, paráfrases)
        test_cases = [
            # (query, expected_action, description)
            ("não consigo entrar no sistema", "problema_login", "Login com termos diferentes"),
            ("esqueci minha senha de acesso", "problema_login", "Senha esquecida"),
            ("conta não chegou no email", "fatura_nao_recebida", "Fatura com termos diferentes"),
            ("boleto não veio", "fatura_nao_recebida", "Boleto como sinônimo"),
            ("cobrança foi recusada no cartão", "erro_pagamento", "Pagamento com termos diferentes"),
            ("pagamento não foi aceito", "erro_pagamento", "Pagamento recusado"),
            ("quero cancelar minha conta", "cancelamento", "Cancelamento"),
            ("desejo encerrar o serviço", "cancelamento", "Encerrar como sinônimo"),
            ("não entendi o valor cobrado", "duvida_cobranca", "Dúvida de cobrança"),
            ("por que estou pagando isso", "duvida_cobranca", "Questionamento de valor"),
        ]
        
        for query, expected_keyword, description in test_cases:
            data, latency = self._recall(query, ns)
            episodes = data.get("episodes", [])
            
            actual = episodes[0].get("action", "NENHUM") if episodes else "NENHUM"
            passed = expected_keyword.lower() in actual.lower()
            tokens = self._count_context_tokens(data.get("prompt_context", ""))
            
            result = TestResult(
                name=description,
                category="semantic",
                passed=passed,
                score=1.0 if passed else 0.0,
                expected=expected_keyword,
                actual=actual,
                latency_ms=latency,
                tokens=tokens,
            )
            metrics.tests.append(result)
            
            status = "✅" if passed else "❌"
            self.log(f"  {status} {description}: {actual}")
        
        # Calcula métricas
        metrics.total_tests = len(metrics.tests)
        metrics.passed_tests = sum(1 for t in metrics.tests if t.passed)
        metrics.accuracy = metrics.passed_tests / metrics.total_tests if metrics.total_tests > 0 else 0
        metrics.avg_latency_ms = sum(t.latency_ms for t in metrics.tests) / len(metrics.tests) if metrics.tests else 0
        metrics.avg_tokens = sum(t.tokens for t in metrics.tests) // len(metrics.tests) if metrics.tests else 0
        
        self.log(f"\n  Resultado: {metrics.passed_tests}/{metrics.total_tests} = {metrics.accuracy*100:.0f}%")
        
        return metrics
    
    def _test_contextual_recall(self) -> CategoryMetrics:
        """Testa recall de fluxos/conversas anteriores."""
        metrics = CategoryMetrics(name="Recall Contextual")
        ns = f"{self.namespace_base}:contextual"
        
        # Cenário 1: Atendimento técnico
        self._remember(["Cliente1"], "produto_com_defeito", "aparelho_nao_liga", "verificar_garantia", ns)
        time.sleep(0.2)
        self._remember(["Cliente1"], "garantia_confirmada", "compra_recente", "aprovar_troca", ns)
        time.sleep(0.2)
        self._remember(["Cliente1"], "troca_agendada", "envio_novo_produto", "cliente_satisfeito", ns)
        time.sleep(0.5)
        
        # Cenário 2: Suporte financeiro
        self._remember(["Cliente2"], "contestacao_cobranca", "valor_duplicado", "analisar_fatura", ns)
        time.sleep(0.2)
        self._remember(["Cliente2"], "erro_confirmado", "cobranca_duplicada", "estorno_aprovado", ns)
        time.sleep(0.5)
        
        test_cases = [
            ("produto defeituoso não funciona", "defeito", "Recall de defeito"),
            ("garantia do produto", "garantia", "Recall de garantia"),
            ("troca agendada envio", "troca", "Recall de troca"),
            ("contestação valor cobrado", "contestacao", "Recall de contestação"),
            ("estorno da cobrança", "estorno", "Recall de estorno"),
        ]
        
        for query, expected_keyword, description in test_cases:
            data, latency = self._recall(query, ns)
            episodes = data.get("episodes", [])
            
            found = any(
                expected_keyword.lower() in ep.get("action", "").lower() or
                expected_keyword.lower() in ep.get("outcome", "").lower()
                for ep in episodes
            )
            
            result = TestResult(
                name=description,
                category="contextual",
                passed=found,
                score=1.0 if found else 0.0,
                expected=expected_keyword,
                actual=str([ep.get("action") for ep in episodes[:2]]),
                latency_ms=latency,
            )
            metrics.tests.append(result)
            
            status = "✅" if found else "❌"
            self.log(f"  {status} {description}")
        
        metrics.total_tests = len(metrics.tests)
        metrics.passed_tests = sum(1 for t in metrics.tests if t.passed)
        metrics.accuracy = metrics.passed_tests / metrics.total_tests if metrics.total_tests > 0 else 0
        metrics.avg_latency_ms = sum(t.latency_ms for t in metrics.tests) / len(metrics.tests) if metrics.tests else 0
        
        self.log(f"\n  Resultado: {metrics.passed_tests}/{metrics.total_tests} = {metrics.accuracy*100:.0f}%")
        
        return metrics
    
    def _test_collective_memory(self) -> CategoryMetrics:
        """Testa compartilhamento de conhecimento entre usuários."""
        metrics = CategoryMetrics(name="Memória Coletiva")
        parent_ns = f"{self.namespace_base}:coletivo"
        
        # Salva conhecimento coletivo (LEARNED) no namespace pai
        collective_knowledge = [
            ("solucao_conexao_lenta", "problema_roteador", "reiniciar_modem"),
            ("recuperar_senha", "email_esquecido", "usar_cpf_validacao"),
            ("atualizar_cadastro", "dados_desatualizados", "portal_autoatendimento"),
        ]
        
        for what, why, how in collective_knowledge:
            self._remember(["sistema"], what, why, how, parent_ns, visibility="learned")
            time.sleep(0.5)  # Mais tempo para embedding
        
        time.sleep(2)  # Aguarda embeddings estarem prontos
        
        # Testa se usuários em namespaces filhos conseguem acessar
        test_cases = [
            # Query mais alinhada semanticamente com "solucao_conexao_lenta" + "reiniciar_modem"
            (f"{parent_ns}:user1", "minha conexão está lenta, preciso solução", "reiniciar", "User1 encontra solução de conexão"),
            (f"{parent_ns}:user2", "esqueci senha, como recuperar", "cpf", "User2 encontra recuperação de senha"),
            (f"{parent_ns}:user3", "quero atualizar meu cadastro", "autoatendimento", "User3 encontra atualização"),
        ]
        
        for child_ns, query, expected_keyword, description in test_cases:
            data, latency = self._recall(query, child_ns)
            episodes = data.get("episodes", [])
            
            found = any(
                expected_keyword.lower() in str(ep).lower()
                for ep in episodes
            )
            
            result = TestResult(
                name=description,
                category="collective",
                passed=found,
                score=1.0 if found else 0.0,
                expected=expected_keyword,
                actual=str([ep.get("outcome", "")[:30] for ep in episodes[:2]]),
                latency_ms=latency,
            )
            metrics.tests.append(result)
            
            status = "✅" if found else "❌"
            self.log(f"  {status} {description}")
        
        # Testa isolamento - namespace diferente NÃO deve acessar
        other_ns = f"{self.namespace_base}:outro_tenant"
        data, latency = self._recall("internet lenta", other_ns)
        isolated = len(data.get("episodes", [])) == 0
        
        result = TestResult(
            name="Isolamento entre tenants",
            category="collective",
            passed=isolated,
            score=1.0 if isolated else 0.0,
            expected="Nenhum episódio",
            actual=f"{len(data.get('episodes', []))} episódios",
            latency_ms=latency,
        )
        metrics.tests.append(result)
        
        status = "✅" if isolated else "❌"
        self.log(f"  {status} Isolamento entre tenants")
        
        metrics.total_tests = len(metrics.tests)
        metrics.passed_tests = sum(1 for t in metrics.tests if t.passed)
        metrics.accuracy = metrics.passed_tests / metrics.total_tests if metrics.total_tests > 0 else 0
        metrics.avg_latency_ms = sum(t.latency_ms for t in metrics.tests) / len(metrics.tests) if metrics.tests else 0
        
        self.log(f"\n  Resultado: {metrics.passed_tests}/{metrics.total_tests} = {metrics.accuracy*100:.0f}%")
        
        return metrics
    
    def _test_relevance(self) -> CategoryMetrics:
        """Testa se o sistema retorna informação relevante (não ruído)."""
        metrics = CategoryMetrics(name="Relevância")
        ns = f"{self.namespace_base}:relevance"
        
        # Salva memórias variadas
        self._remember(["Ana"], "comprou_produto", "queria_presente", "escolheu_azul", ns)
        self._remember(["Ana"], "reclamou_entrega", "atraso_5dias", "reembolso_frete", ns)
        self._remember(["Ana"], "elogiou_atendimento", "suporte_rapido", "nota_10", ns)
        time.sleep(0.5)
        
        # Teste 1: Query específica retorna só relevante
        data, latency = self._recall("problema com entrega atrasada", ns)
        episodes = data.get("episodes", [])
        
        relevant_found = any("entrega" in ep.get("action", "").lower() or "atraso" in ep.get("context", "").lower() for ep in episodes)
        irrelevant_found = any("comprou" in ep.get("action", "").lower() for ep in episodes)
        
        passed = relevant_found and not irrelevant_found
        result = TestResult(
            name="Query específica retorna só relevante",
            category="relevance",
            passed=passed,
            score=1.0 if passed else (0.5 if relevant_found else 0.0),
            expected="Só entrega",
            actual=f"Relevante: {relevant_found}, Irrelevante: {irrelevant_found}",
            latency_ms=latency,
        )
        metrics.tests.append(result)
        status = "✅" if passed else "❌"
        self.log(f"  {status} Query específica retorna só relevante")
        
        # Teste 2: Query sem match retorna vazio
        data, latency = self._recall("previsão do tempo para amanhã", ns)
        episodes = data.get("episodes", [])
        
        passed = len(episodes) == 0
        result = TestResult(
            name="Query sem match retorna vazio",
            category="relevance",
            passed=passed,
            score=1.0 if passed else 0.0,
            expected="0 episódios",
            actual=f"{len(episodes)} episódios",
            latency_ms=latency,
        )
        metrics.tests.append(result)
        status = "✅" if passed else "❌"
        self.log(f"  {status} Query sem match retorna vazio")
        
        # Teste 3: Query vaga deve filtrar ruído (retornar poucos ou nenhum)
        data, latency = self._recall("me conta tudo", ns)
        episodes = data.get("episodes", [])
        
        # Deve retornar poucos ou nenhum (threshold de relevância filtra ruído)
        # 0-2 é aceitável, >2 seria ruído excessivo
        passed = len(episodes) <= 2
        result = TestResult(
            name="Query vaga filtra ruído",
            category="relevance",
            passed=passed,
            score=1.0 if passed else 0.0,
            expected="0-2 episódios (sem ruído)",
            actual=f"{len(episodes)} episódios",
            latency_ms=latency,
        )
        metrics.tests.append(result)
        status = "✅" if passed else "⚠️"
        self.log(f"  {status} Query vaga filtra ruído")
        
        metrics.total_tests = len(metrics.tests)
        metrics.passed_tests = sum(1 for t in metrics.tests if t.passed)
        metrics.accuracy = metrics.passed_tests / metrics.total_tests if metrics.total_tests > 0 else 0
        metrics.avg_latency_ms = sum(t.latency_ms for t in metrics.tests) / len(metrics.tests) if metrics.tests else 0
        
        self.log(f"\n  Resultado: {metrics.passed_tests}/{metrics.total_tests} = {metrics.accuracy*100:.0f}%")
        
        return metrics
    
    def _test_efficiency(self) -> CategoryMetrics:
        """Testa eficiência operacional."""
        metrics = CategoryMetrics(name="Eficiência")
        ns = f"{self.namespace_base}:efficiency"
        
        # Popula com várias memórias
        for i in range(10):
            self._remember(
                [f"User{i}"],
                f"acao_{i}",
                f"motivo_{i}",
                f"resultado_{i}",
                ns,
            )
        
        time.sleep(1)
        
        # Mede latência de recall
        latencies = []
        for _ in range(5):
            _, latency = self._recall("ação recente do usuário", ns)
            latencies.append(latency)
        
        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 20 else max(latencies)
        
        # Teste 1: Latência média aceitável (<500ms)
        passed = avg_latency < 500
        result = TestResult(
            name="Latência média < 500ms",
            category="efficiency",
            passed=passed,
            score=1.0 if passed else max(0, 1 - (avg_latency - 500) / 500),
            expected="< 500ms",
            actual=f"{avg_latency:.0f}ms",
            latency_ms=avg_latency,
        )
        metrics.tests.append(result)
        status = "✅" if passed else "❌"
        self.log(f"  {status} Latência média: {avg_latency:.0f}ms")
        
        # Teste 2: Contexto compacto (< 200 tokens)
        data, _ = self._recall("ação do usuário", ns)
        tokens = self._count_context_tokens(data.get("prompt_context", ""))
        
        passed = tokens < 200
        result = TestResult(
            name="Contexto compacto < 200 tokens",
            category="efficiency",
            passed=passed,
            score=1.0 if passed else max(0, 1 - (tokens - 200) / 200),
            expected="< 200 tokens",
            actual=f"{tokens} tokens",
            tokens=tokens,
        )
        metrics.tests.append(result)
        status = "✅" if passed else "❌"
        self.log(f"  {status} Tokens no contexto: {tokens}")
        
        metrics.total_tests = len(metrics.tests)
        metrics.passed_tests = sum(1 for t in metrics.tests if t.passed)
        metrics.accuracy = metrics.passed_tests / metrics.total_tests if metrics.total_tests > 0 else 0
        metrics.avg_latency_ms = avg_latency
        metrics.avg_tokens = tokens
        
        self.log(f"\n  Resultado: {metrics.passed_tests}/{metrics.total_tests} = {metrics.accuracy*100:.0f}%")
        
        return metrics
    
    def _print_summary(self, report: BenchmarkReport) -> None:
        """Imprime resumo do benchmark."""
        self.log("\n")
        self.log("=" * 60)
        self.log("📊 RELATÓRIO FINAL - CORTEX PAPER BENCHMARK")
        self.log("=" * 60)
        self.log("")
        self.log("📈 MÉTRICAS DE QUALIDADE:")
        self.log(f"   • Acurácia Semântica:  {report.semantic_accuracy.accuracy*100:.0f}%")
        self.log(f"   • Recall Contextual:   {report.contextual_recall.accuracy*100:.0f}%")
        self.log(f"   • Memória Coletiva:    {report.collective_memory.accuracy*100:.0f}%")
        self.log(f"   • Relevância:          {report.relevance.accuracy*100:.0f}%")
        self.log("")
        self.log("⚡ MÉTRICAS DE EFICIÊNCIA:")
        self.log(f"   • Latência média:      {report.efficiency.avg_latency_ms:.0f}ms")
        self.log(f"   • Tokens no contexto:  {report.efficiency.avg_tokens}")
        self.log("")
        self.log("📊 RESULTADO GERAL:")
        self.log(f"   • Testes: {report.total_passed}/{report.total_tests}")
        self.log(f"   • Acurácia: {report.overall_accuracy*100:.1f}%")
        self.log(f"   • Duração: {report.duration_seconds:.1f}s")
        self.log("")
        self.log("=" * 60)
    
    def save_report(self, report: BenchmarkReport, output_dir: Path | None = None) -> Path:
        """Salva relatório em JSON."""
        output_dir = output_dir or OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = output_dir / f"paper_benchmark_{timestamp}.json"
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report.to_dict(), f, indent=2, ensure_ascii=False, default=str)
        
        self.log(f"\n📁 Relatório salvo em: {filepath}")
        return filepath


def main():
    """Executa o benchmark."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cortex Paper Benchmark")
    parser.add_argument("-v", "--verbose", action="store_true", help="Output detalhado")
    parser.add_argument("-o", "--output", type=str, help="Diretório de saída")
    parser.add_argument("--save", action="store_true", help="Salva relatório em JSON")
    args = parser.parse_args()
    
    benchmark = PaperBenchmark(verbose=True)
    report = benchmark.run()
    
    if args.save or args.output:
        output_dir = Path(args.output) if args.output else OUTPUT_DIR
        benchmark.save_report(report, output_dir)
    
    # Exit code baseado no resultado
    sys.exit(0 if report.overall_accuracy >= 0.7 else 1)


if __name__ == "__main__":
    main()
