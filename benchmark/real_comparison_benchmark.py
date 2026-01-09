#!/usr/bin/env python3
"""
Real Comparison Benchmark - Cortex vs RAG vs Mem0 vs Baseline

Benchmark com implementações REAIS (não mocks):
- RAG: Usa embeddings reais via Ollama (não TF-IDF)
- Mem0: Usa biblioteca mem0ai quando disponível
- Cortex: API completa com embeddings

Métricas medidas:
1. Acurácia Semântica - Encontra memória com termos diferentes
2. Recall Contextual - Lembra de conversas anteriores
3. Memória Coletiva - Compartilhamento hierárquico (apenas Cortex)
4. Eficiência - Latência e tokens

Uso:
    python real_comparison_benchmark.py           # Benchmark completo
    python real_comparison_benchmark.py --save    # Salva resultados
    python real_comparison_benchmark.py -v        # Modo verbose
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

import requests

# Silencia logs
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

print = functools.partial(print, flush=True)

# Paths
benchmark_path = Path(__file__).parent
project_root = benchmark_path.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(benchmark_path))
sys.path.insert(0, str(project_root / "src"))


# ==================== CONFIGURAÇÃO ====================

CORTEX_URL = os.getenv("CORTEX_API_URL", "http://localhost:8000")
# Usa OLLAMA_URL ou OLLAMA_BASE_URL
OLLAMA_URL = os.getenv("OLLAMA_URL") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.getenv("CORTEX_EMBEDDING_MODEL", "qwen3-embedding:latest")
LLM_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
OUTPUT_DIR = Path("./benchmark_results")


# ==================== EMBEDDING SERVICE ====================

class OllamaEmbedding:
    """Serviço de embedding usando Ollama diretamente."""
    
    def __init__(self, model: str | None = None, base_url: str | None = None):
        # Lê variáveis de ambiente em runtime
        self.model = model or os.getenv("CORTEX_EMBEDDING_MODEL", "qwen3-embedding:latest")
        self.base_url = base_url or os.getenv("OLLAMA_URL") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    def embed(self, text: str) -> list[float] | None:
        """Gera embedding para texto."""
        try:
            response = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": text},
                timeout=60,  # Aumentado para modelos grandes
            )
            if response.status_code == 200:
                data = response.json()
                embeddings = data.get("embeddings", [])
                if embeddings:
                    return embeddings[0]
            return None
        except Exception:
            return None
    
    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calcula similaridade de cosseno."""
        if not a or not b or len(a) != len(b):
            return 0.0
        
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)


# ==================== RAG COM EMBEDDINGS REAIS ====================

@dataclass
class RAGDocument:
    id: str
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


class RealRAGMemory:
    """RAG com embeddings reais via Ollama."""
    
    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        self._documents: list[RAGDocument] = []
        self._embedder = OllamaEmbedding()
    
    def add(self, content: str, metadata: dict | None = None) -> str:
        """Adiciona documento com embedding real."""
        doc_id = f"doc_{len(self._documents)}_{self.namespace}"
        embedding = self._embedder.embed(content)
        
        if embedding:
            doc = RAGDocument(
                id=doc_id,
                content=content,
                embedding=embedding,
                metadata=metadata or {},
            )
            self._documents.append(doc)
            return doc_id
        return ""
    
    def search(self, query: str, limit: int = 5, min_score: float = 0.4) -> list[tuple[RAGDocument, float]]:
        """Busca por similaridade vetorial real."""
        if not self._documents:
            return []
        
        query_embedding = self._embedder.embed(query)
        if not query_embedding:
            return []
        
        scored = []
        for doc in self._documents:
            score = self._embedder.cosine_similarity(query_embedding, doc.embedding)
            if score >= min_score:
                scored.append((doc, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]
    
    def clear(self):
        self._documents.clear()


# ==================== MEM0 REAL (quando disponível) ====================

try:
    from mem0 import Memory as Mem0Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    Mem0Memory = None


class RealMem0:
    """Wrapper para Mem0 real ou fallback para mock com embeddings."""
    
    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self._use_real = MEM0_AVAILABLE
        self._embedder = OllamaEmbedding()
        
        if self._use_real:
            try:
                config = {
                    "llm": {
                        "provider": "ollama",
                        "config": {
                            "model": LLM_MODEL,
                            "ollama_base_url": OLLAMA_URL,
                            "temperature": 0.1,
                        },
                    },
                    "embedder": {
                        "provider": "ollama",
                        "config": {
                            "model": EMBEDDING_MODEL,
                            "ollama_base_url": OLLAMA_URL,
                        },
                    },
                }
                self._memory = Mem0Memory.from_config(config)
            except Exception as e:
                print(f"  ⚠️ Mem0 falhou: {e}, usando fallback")
                self._use_real = False
                self._memories: list[dict] = []
        else:
            self._memories: list[dict] = []
    
    def add(self, messages: list[dict], user_id: str | None = None) -> dict:
        """Adiciona memória."""
        user_id = user_id or self.user_id
        
        if self._use_real:
            return self._memory.add(messages, user_id=user_id)
        
        # Fallback com embeddings
        content = " ".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}"
            for m in messages
        )
        embedding = self._embedder.embed(content)
        
        mem = {
            "id": f"mem_{len(self._memories)}",
            "memory": content,
            "embedding": embedding,
            "user_id": user_id,
        }
        self._memories.append(mem)
        return {"results": [mem]}
    
    def search(self, query: str, user_id: str | None = None, limit: int = 5) -> dict:
        """Busca memórias."""
        user_id = user_id or self.user_id
        
        if self._use_real:
            return self._memory.search(query, user_id=user_id, limit=limit)
        
        # Fallback com embeddings
        query_emb = self._embedder.embed(query)
        if not query_emb:
            return {"results": []}
        
        scored = []
        for mem in self._memories:
            if mem["user_id"] != user_id:
                continue
            if mem.get("embedding"):
                score = self._embedder.cosine_similarity(query_emb, mem["embedding"])
                if score >= 0.4:
                    scored.append((mem, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return {"results": [m for m, _ in scored[:limit]]}
    
    def clear(self, user_id: str | None = None):
        """Limpa memórias."""
        user_id = user_id or self.user_id
        if self._use_real:
            try:
                self._memory.delete_all(user_id=user_id)
            except Exception:
                pass
        else:
            self._memories = [m for m in self._memories if m["user_id"] != user_id]


# ==================== MODELOS DE DADOS ====================

@dataclass
class TestResult:
    name: str
    category: str
    agent: str
    passed: bool
    score: float
    expected: str
    actual: str
    latency_ms: float = 0.0
    details: str = ""
    context_richness: int = 0  # Quantidade de campos/informações retornadas


@dataclass
class AgentMetrics:
    name: str
    semantic_accuracy: float = 0.0
    contextual_recall: float = 0.0
    collective_memory: float = 0.0
    efficiency_latency: float = 0.0
    context_richness_avg: float = 0.0  # Média de riqueza de contexto
    total_tests: int = 0
    passed_tests: int = 0
    tests: list[TestResult] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    timestamp: str = ""
    duration_seconds: float = 0.0
    embedding_model: str = ""
    llm_model: str = ""
    mem0_real: bool = False
    agents: dict[str, AgentMetrics] = field(default_factory=dict)


# ==================== BENCHMARK ====================

class RealComparisonBenchmark:
    """Benchmark comparativo com implementações reais."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.namespace_base = f"real_bench_{int(time.time())}"
        
        # Sistemas de memória
        self.rag: RealRAGMemory | None = None
        self.mem0: RealMem0 | None = None
        self._embedder = OllamaEmbedding()
    
    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")
    
    def _check_apis(self) -> bool:
        """Verifica disponibilidade das APIs."""
        try:
            # Cortex
            r = requests.get(f"{CORTEX_URL}/health", timeout=5)
            if r.status_code != 200:
                self.log("❌ Cortex API não disponível")
                return False
            
            # Ollama
            r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            if r.status_code != 200:
                self.log("❌ Ollama não disponível")
                return False
            
            # Teste de embedding
            test_emb = self._embedder.embed("teste")
            if not test_emb:
                self.log("❌ Embedding não funciona")
                return False
            
            self.log(f"   ✅ Embedding: {len(test_emb)} dims ({EMBEDDING_MODEL})")
            return True
            
        except Exception as e:
            self.log(f"❌ Erro: {e}")
            return False
    
    def run(self) -> BenchmarkReport:
        """Executa benchmark completo."""
        self.log("=" * 60)
        self.log("🎯 REAL COMPARISON BENCHMARK")
        self.log("   Cortex vs RAG (embeddings) vs Mem0")
        self.log("=" * 60)
        
        start_time = time.time()
        report = BenchmarkReport(
            timestamp=datetime.now().isoformat(),
            embedding_model=EMBEDDING_MODEL,
            llm_model=LLM_MODEL,
        )
        
        # Verifica APIs
        self.log("\n🔍 Verificando APIs...")
        if not self._check_apis():
            return report
        
        # Inicializa sistemas
        self.log("\n🔧 Inicializando sistemas de memória...")
        self.rag = RealRAGMemory(f"{self.namespace_base}_rag")
        self.mem0 = RealMem0(f"{self.namespace_base}_mem0")
        report.mem0_real = self.mem0._use_real
        
        self.log(f"   ✅ RAG: embeddings reais")
        self.log(f"   {'✅' if report.mem0_real else '⚠️'} Mem0: {'real' if report.mem0_real else 'fallback com embeddings'}")
        self.log(f"   ✅ Cortex: API completa")
        
        # Inicializa métricas
        for name in ["Baseline", "RAG", "Mem0", "Cortex"]:
            report.agents[name] = AgentMetrics(name=name)
        
        # Fase 1: Acurácia Semântica
        self.log("\n" + "=" * 60)
        self.log("📊 FASE 1: Acurácia Semântica")
        self.log("-" * 40)
        self._test_semantic_accuracy(report)
        
        # Fase 2: Recall Contextual
        self.log("\n" + "=" * 60)
        self.log("📊 FASE 2: Recall Contextual")
        self.log("-" * 40)
        self._test_contextual_recall(report)
        
        # Fase 3: Memória Coletiva
        self.log("\n" + "=" * 60)
        self.log("📊 FASE 3: Memória Coletiva (apenas Cortex)")
        self.log("-" * 40)
        self._test_collective_memory(report)
        
        # Fase 4: Eficiência
        self.log("\n" + "=" * 60)
        self.log("📊 FASE 4: Eficiência")
        self.log("-" * 40)
        self._test_efficiency(report)
        
        # Calcula métricas finais
        self._calculate_metrics(report)
        
        report.duration_seconds = time.time() - start_time
        
        # Imprime resumo
        self._print_summary(report)
        
        return report
    
    def _calculate_context_richness(self, agent: str, result: Any) -> tuple[int, int]:
        """
        Calcula riqueza de contexto.
        
        Retorna: (raw_words, structured_fields)
        - raw_words: Quantidade de palavras brutas
        - structured_fields: Quantidade de campos estruturados (W5H)
        
        Cortex tem vantagem em structured_fields (dados organizados, prontos para uso).
        RAG/Mem0 têm mais raw_words (texto bruto que precisa ser parseado).
        """
        if not result:
            return 0, 0
        
        if agent == "Baseline":
            return 0, 0
        
        if agent == "RAG":
            # RAG retorna texto simples - precisa ser parseado
            if isinstance(result, list) and result:
                content = result[0][0].content if hasattr(result[0][0], 'content') else str(result[0])
                return len(content.split()), 1  # 1 campo (texto)
            return 0, 0
        
        if agent == "Mem0":
            # Mem0 retorna dict com memory - texto semi-estruturado
            if isinstance(result, dict) and result.get("results"):
                mem = result["results"][0]
                content = mem.get("memory", str(mem)) if isinstance(mem, dict) else str(mem)
                return len(content.split()), 1  # 1 campo (memory)
            return 0, 0
        
        if agent == "Cortex":
            # Cortex retorna episódio com campos W5H estruturados
            # Vantagem: dados já organizados, prontos para uso no prompt
            if isinstance(result, list) and result:
                ep = result[0]
                words = 0
                fields = 0
                for key in ["action", "outcome", "reason", "participants", "context"]:
                    val = ep.get(key)
                    if val and str(val).strip():
                        fields += 1
                        if isinstance(val, str):
                            words += len(val.split())
                        elif isinstance(val, list):
                            words += len(val)
                return words, fields
            return 0, 0
        
        return 0, 0
    
    def _store_cortex(self, who: list[str], what: str, why: str, how: str, ns: str, visibility: str = "personal"):
        """Armazena memória no Cortex."""
        try:
            requests.post(
                f"{CORTEX_URL}/memory/remember",
                json={
                    "who": who,
                    "what": what,
                    "why": why,
                    "how": how,
                    "visibility": visibility,  # personal, shared ou learned
                },
                headers={"X-Cortex-Namespace": ns},
                timeout=10,
            )
        except Exception:
            pass
    
    def _recall_cortex(self, query: str, ns: str) -> tuple[list[dict], float]:
        """Busca memória no Cortex."""
        try:
            start = time.time()
            r = requests.post(
                f"{CORTEX_URL}/memory/recall",
                json={"query": query, "context": {}},
                headers={"X-Cortex-Namespace": ns},
                timeout=10,
            )
            latency = (time.time() - start) * 1000
            return r.json().get("episodes", []), latency
        except Exception:
            return [], 0
    
    def _test_semantic_accuracy(self, report: BenchmarkReport):
        """Testa busca semântica com termos diferentes."""
        
        # Memórias a salvar (formato estruturado)
        memories = [
            (["Ana"], "problema_login_sistema", "senha_expirada", "reset_por_email"),
            (["Bruno"], "fatura_nao_recebida", "email_incorreto", "reenviou_fatura"),
            (["Carla"], "erro_pagamento_cartao", "cartao_bloqueado", "atualizou_dados"),
            (["Daniel"], "cancelamento_assinatura", "insatisfacao_servico", "ofereceu_desconto"),
        ]
        
        ns_cortex = f"{self.namespace_base}:semantic"
        
        # Salva em todos os sistemas
        self.log("  Salvando memórias...")
        
        for who, what, why, how in memories:
            # Cortex
            self._store_cortex(who, what, why, how, ns_cortex)
            
            # RAG
            content = f"{what} {why} {how} {' '.join(who)}"
            self.rag.add(content.replace("_", " "), {"who": who})
            
            # Mem0
            self.mem0.add([{"role": "user", "content": content.replace("_", " ")}])
            
            time.sleep(0.3)
        
        time.sleep(1)
        
        # Testes de busca com sinônimos
        test_cases = [
            ("não consigo entrar no sistema", "login", "Login com termos diferentes"),
            ("esqueci minha senha", "login", "Senha esquecida"),
            ("minha conta mensal não chegou", "fatura", "Fatura com termos diferentes"),
            ("boleto não veio", "fatura", "Boleto como sinônimo"),
            ("cobrança foi negada", "pagamento", "Pagamento com termos diferentes"),
            ("quero cancelar minha conta", "cancelamento", "Cancelamento"),
        ]
        
        for query, expected, description in test_cases:
            self.log(f"\n  🔍 {description}: \"{query}\"")
            
            # Baseline: sempre falha (sem memória)
            result_baseline = TestResult(
                name=description,
                category="semantic",
                agent="Baseline",
                passed=False,
                score=0.0,
                expected=expected,
                actual="sem memória",
            )
            report.agents["Baseline"].tests.append(result_baseline)
            self.log(f"     ❌ Baseline: sem memória")
            
            # RAG
            start = time.time()
            rag_results = self.rag.search(query, limit=1)
            rag_latency = (time.time() - start) * 1000
            
            rag_found = ""
            rag_passed = False
            rag_words, rag_fields = self._calculate_context_richness("RAG", rag_results)
            if rag_results:
                rag_found = rag_results[0][0].content[:50]
                rag_passed = expected in rag_found.lower()
            
            result_rag = TestResult(
                name=description,
                category="semantic",
                agent="RAG",
                passed=rag_passed,
                score=1.0 if rag_passed else 0.0,
                expected=expected,
                actual=rag_found or "NENHUM",
                latency_ms=rag_latency,
                context_richness=rag_fields,  # Campos estruturados
                details=f"words:{rag_words}",
            )
            report.agents["RAG"].tests.append(result_rag)
            self.log(f"     {'✅' if rag_passed else '❌'} RAG: {rag_found[:30] if rag_found else 'NENHUM'} ({rag_words}w/{rag_fields}f)")
            
            # Mem0
            start = time.time()
            mem0_results = self.mem0.search(query, limit=1)
            mem0_latency = (time.time() - start) * 1000
            
            mem0_found = ""
            mem0_passed = False
            mem0_words, mem0_fields = self._calculate_context_richness("Mem0", mem0_results)
            if mem0_results.get("results"):
                mem0_found = str(mem0_results["results"][0])[:50]
                mem0_passed = expected in mem0_found.lower()
            
            result_mem0 = TestResult(
                name=description,
                category="semantic",
                agent="Mem0",
                passed=mem0_passed,
                score=1.0 if mem0_passed else 0.0,
                expected=expected,
                actual=mem0_found or "NENHUM",
                latency_ms=mem0_latency,
                context_richness=mem0_fields,
                details=f"words:{mem0_words}",
            )
            report.agents["Mem0"].tests.append(result_mem0)
            self.log(f"     {'✅' if mem0_passed else '❌'} Mem0: {mem0_found[:30] if mem0_found else 'NENHUM'} ({mem0_words}w/{mem0_fields}f)")
            
            # Cortex
            cortex_results, cortex_latency = self._recall_cortex(query, ns_cortex)
            
            cortex_found = ""
            cortex_passed = False
            cortex_words, cortex_fields = self._calculate_context_richness("Cortex", cortex_results)
            if cortex_results:
                cortex_found = cortex_results[0].get("action", "")
                cortex_passed = expected in cortex_found.lower()
            
            result_cortex = TestResult(
                name=description,
                category="semantic",
                agent="Cortex",
                passed=cortex_passed,
                score=1.0 if cortex_passed else 0.0,
                expected=expected,
                actual=cortex_found or "NENHUM",
                latency_ms=cortex_latency,
                context_richness=cortex_fields,  # Campos W5H estruturados
                details=f"words:{cortex_words}",
            )
            report.agents["Cortex"].tests.append(result_cortex)
            self.log(f"     {'✅' if cortex_passed else '❌'} Cortex: {cortex_found or 'NENHUM'}")
    
    def _test_contextual_recall(self, report: BenchmarkReport):
        """Testa recall de contexto de conversa."""
        
        # Fluxo de conversa
        flow = [
            (["Cliente1"], "produto_com_defeito", "aparelho_nao_liga", "verificar_garantia"),
            (["Cliente1"], "garantia_confirmada", "compra_recente", "aprovar_troca"),
            (["Cliente1"], "troca_agendada", "envio_novo_produto", "cliente_satisfeito"),
        ]
        
        ns_cortex = f"{self.namespace_base}:contextual"
        
        self.log("  Salvando fluxo de conversa...")
        
        for who, what, why, how in flow:
            self._store_cortex(who, what, why, how, ns_cortex)
            
            content = f"{what} {why} {how}".replace("_", " ")
            self.rag.add(content)
            self.mem0.add([{"role": "user", "content": content}])
            
            time.sleep(0.3)
        
        time.sleep(1)
        
        # Testes
        test_cases = [
            ("produto defeituoso", "defeito", "Recall de defeito"),
            ("sobre a garantia", "garantia", "Recall de garantia"),
            ("troca do produto", "troca", "Recall de troca"),
        ]
        
        for query, expected, description in test_cases:
            self.log(f"\n  🔍 {description}: \"{query}\"")
            
            # Baseline
            report.agents["Baseline"].tests.append(TestResult(
                name=description, category="contextual", agent="Baseline",
                passed=False, score=0.0, expected=expected, actual="sem memória",
            ))
            self.log(f"     ❌ Baseline: sem memória")
            
            # RAG
            rag_results = self.rag.search(query, limit=1)
            rag_passed = any(expected in r[0].content.lower() for r in rag_results) if rag_results else False
            report.agents["RAG"].tests.append(TestResult(
                name=description, category="contextual", agent="RAG",
                passed=rag_passed, score=1.0 if rag_passed else 0.0,
                expected=expected, actual=str(rag_results[0][0].content[:30]) if rag_results else "NENHUM",
            ))
            self.log(f"     {'✅' if rag_passed else '❌'} RAG")
            
            # Mem0
            mem0_results = self.mem0.search(query, limit=1)
            mem0_passed = expected in str(mem0_results).lower()
            report.agents["Mem0"].tests.append(TestResult(
                name=description, category="contextual", agent="Mem0",
                passed=mem0_passed, score=1.0 if mem0_passed else 0.0,
                expected=expected, actual=str(mem0_results)[:50],
            ))
            self.log(f"     {'✅' if mem0_passed else '❌'} Mem0")
            
            # Cortex
            cortex_results, _ = self._recall_cortex(query, ns_cortex)
            cortex_passed = any(expected in str(ep).lower() for ep in cortex_results) if cortex_results else False
            report.agents["Cortex"].tests.append(TestResult(
                name=description, category="contextual", agent="Cortex",
                passed=cortex_passed, score=1.0 if cortex_passed else 0.0,
                expected=expected, actual=str(cortex_results[0].get("action", ""))[:30] if cortex_results else "NENHUM",
            ))
            self.log(f"     {'✅' if cortex_passed else '❌'} Cortex")
    
    def _test_collective_memory(self, report: BenchmarkReport):
        """Testa memória coletiva (apenas Cortex suporta)."""
        
        parent_ns = f"{self.namespace_base}:coletivo"
        
        # Salva conhecimento coletivo no namespace pai com visibility="shared"
        collective = [
            (["sistema"], "solucao_conexao", "procedimento_padrao", "reiniciar_modem"),
            (["sistema"], "recuperar_senha", "procedimento_padrao", "usar_cpf"),
        ]
        
        self.log("  Salvando conhecimento coletivo (visibility=shared)...")
        
        for who, what, why, how in collective:
            self._store_cortex(who, what, why, how, parent_ns, visibility="shared")
            time.sleep(0.3)
        
        time.sleep(1)
        
        # Testa se namespace filho herda
        test_cases = [
            ("minha conexão está lenta", "reiniciar", "Herança: conexão"),
            ("esqueci minha senha", "cpf", "Herança: senha"),
        ]
        
        child_ns = f"{parent_ns}:user_novo"
        
        for query, expected, description in test_cases:
            self.log(f"\n  🔍 {description}")
            
            # Outros sistemas não suportam
            for agent in ["Baseline", "RAG", "Mem0"]:
                report.agents[agent].tests.append(TestResult(
                    name=description, category="collective", agent=agent,
                    passed=False, score=0.0, expected=expected, actual="não suportado",
                ))
                self.log(f"     ➖ {agent}: não suportado")
            
            # Cortex
            cortex_results, _ = self._recall_cortex(query, child_ns)
            cortex_passed = any(expected in str(ep).lower() for ep in cortex_results) if cortex_results else False
            
            report.agents["Cortex"].tests.append(TestResult(
                name=description, category="collective", agent="Cortex",
                passed=cortex_passed, score=1.0 if cortex_passed else 0.0,
                expected=expected, actual=str(cortex_results)[:50] if cortex_results else "NENHUM",
            ))
            self.log(f"     {'✅' if cortex_passed else '❌'} Cortex")
    
    def _test_efficiency(self, report: BenchmarkReport):
        """Testa eficiência (latência)."""
        
        ns_cortex = f"{self.namespace_base}:efficiency"
        
        # Salva algumas memórias
        for i in range(5):
            self._store_cortex(["user"], f"memoria_{i}", "teste", "resultado", ns_cortex)
            self.rag.add(f"memoria {i} teste resultado")
            self.mem0.add([{"role": "user", "content": f"memoria {i}"}])
        
        time.sleep(1)
        
        # Mede latência de múltiplas queries
        queries = ["primeira memória", "segunda memória", "terceira memória"]
        
        latencies = {"Baseline": [], "RAG": [], "Mem0": [], "Cortex": []}
        
        self.log("  Medindo latências...")
        
        for query in queries:
            # RAG
            start = time.time()
            self.rag.search(query)
            latencies["RAG"].append((time.time() - start) * 1000)
            
            # Mem0
            start = time.time()
            self.mem0.search(query)
            latencies["Mem0"].append((time.time() - start) * 1000)
            
            # Cortex
            _, lat = self._recall_cortex(query, ns_cortex)
            latencies["Cortex"].append(lat)
        
        # Registra resultados
        for agent, lats in latencies.items():
            if agent == "Baseline":
                avg_lat = 0
                passed = True  # Baseline é "eficiente" por não fazer nada
            else:
                avg_lat = sum(lats) / len(lats) if lats else 0
                passed = avg_lat < 500  # Threshold de 500ms
            
            report.agents[agent].tests.append(TestResult(
                name="Latência média",
                category="efficiency",
                agent=agent,
                passed=passed,
                score=1.0 if passed else 0.0,
                expected="<500ms",
                actual=f"{avg_lat:.0f}ms",
                latency_ms=avg_lat,
            ))
            
            self.log(f"     {'✅' if passed else '❌'} {agent}: {avg_lat:.0f}ms")
    
    def _calculate_metrics(self, report: BenchmarkReport):
        """Calcula métricas agregadas."""
        
        for agent_name, metrics in report.agents.items():
            if not metrics.tests:
                continue
            
            # Por categoria
            semantic = [t for t in metrics.tests if t.category == "semantic"]
            contextual = [t for t in metrics.tests if t.category == "contextual"]
            collective = [t for t in metrics.tests if t.category == "collective"]
            efficiency = [t for t in metrics.tests if t.category == "efficiency"]
            
            if semantic:
                metrics.semantic_accuracy = sum(t.score for t in semantic) / len(semantic)
            if contextual:
                metrics.contextual_recall = sum(t.score for t in contextual) / len(contextual)
            if collective:
                metrics.collective_memory = sum(t.score for t in collective) / len(collective)
            if efficiency:
                lats = [t.latency_ms for t in efficiency if t.latency_ms > 0]
                metrics.efficiency_latency = sum(lats) / len(lats) if lats else 0
            
            # Calcula riqueza de contexto média
            richness = [t.context_richness for t in metrics.tests if t.context_richness > 0]
            metrics.context_richness_avg = sum(richness) / len(richness) if richness else 0
            
            metrics.total_tests = len(metrics.tests)
            metrics.passed_tests = sum(1 for t in metrics.tests if t.passed)
    
    def _print_summary(self, report: BenchmarkReport):
        """Imprime resumo final."""
        
        self.log("\n" + "=" * 60)
        self.log("📊 RELATÓRIO FINAL - REAL COMPARISON BENCHMARK")
        self.log("=" * 60)
        
        self.log(f"\n🔧 Configuração:")
        self.log(f"   • Embedding: {report.embedding_model}")
        self.log(f"   • LLM: {report.llm_model}")
        self.log(f"   • Mem0: {'real' if report.mem0_real else 'fallback'}")
        
        self.log("\n📈 RESULTADOS:")
        self.log("-" * 60)
        self.log(f"{'Métrica':<25} {'Baseline':>10} {'RAG':>10} {'Mem0':>10} {'Cortex':>10}")
        self.log("-" * 60)
        
        metrics = [
            ("semantic_accuracy", "Acurácia Semântica"),
            ("contextual_recall", "Recall Contextual"),
            ("collective_memory", "Memória Coletiva"),
            ("context_richness_avg", "Campos Estrut. (W5H)"),
        ]
        
        for attr, name in metrics:
            values = []
            for agent in ["Baseline", "RAG", "Mem0", "Cortex"]:
                val = getattr(report.agents[agent], attr, 0)
                if attr == "context_richness_avg":
                    values.append(f"{val:.0f}")
                else:
                    val = val * 100
                    values.append(f"{val:.0f}%")
            self.log(f"{name:<25} {values[0]:>10} {values[1]:>10} {values[2]:>10} {values[3]:>10}")
        
        # Latência
        lats = []
        for agent in ["Baseline", "RAG", "Mem0", "Cortex"]:
            lat = report.agents[agent].efficiency_latency
            lats.append(f"{lat:.0f}ms" if lat > 0 else "N/A")
        self.log(f"{'Latência Média':<25} {lats[0]:>10} {lats[1]:>10} {lats[2]:>10} {lats[3]:>10}")
        
        self.log("-" * 60)
        
        # Total
        totals = []
        for agent in ["Baseline", "RAG", "Mem0", "Cortex"]:
            m = report.agents[agent]
            if m.total_tests > 0:
                total = m.passed_tests / m.total_tests * 100
                totals.append(f"{total:.0f}%")
            else:
                totals.append("N/A")
        
        self.log(f"{'TOTAL':<25} {totals[0]:>10} {totals[1]:>10} {totals[2]:>10} {totals[3]:>10}")
        
        self.log("\n" + "=" * 60)
        self.log(f"⏱️  Duração: {report.duration_seconds:.1f}s")
        self.log("=" * 60)
    
    def save_report(self, report: BenchmarkReport, filename: str | None = None):
        """Salva relatório em JSON."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"real_comparison_{ts}.json"
        
        filepath = OUTPUT_DIR / filename
        
        data = {
            "timestamp": report.timestamp,
            "duration_seconds": report.duration_seconds,
            "embedding_model": report.embedding_model,
            "llm_model": report.llm_model,
            "mem0_real": report.mem0_real,
            "agents": {},
        }
        
        for name, metrics in report.agents.items():
            data["agents"][name] = {
                "semantic_accuracy": metrics.semantic_accuracy,
                "contextual_recall": metrics.contextual_recall,
                "collective_memory": metrics.collective_memory,
                "efficiency_latency": metrics.efficiency_latency,
                "total_tests": metrics.total_tests,
                "passed_tests": metrics.passed_tests,
                "tests": [asdict(t) for t in metrics.tests],
            }
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self.log(f"\n📁 Relatório salvo: {filepath}")
        return filepath


# ==================== MAIN ====================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Real Comparison Benchmark")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--save", action="store_true")
    
    args = parser.parse_args()
    
    benchmark = RealComparisonBenchmark(verbose=args.verbose)
    report = benchmark.run()
    
    if args.save:
        benchmark.save_report(report)
    
    return 0 if report.duration_seconds > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
