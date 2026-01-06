"""
Scientific Metrics Module - Métricas padronizadas para avaliação científica

Implementa métricas usadas na literatura de AI Memory:
- Precision@K, Recall@K, MRR (Information Retrieval)
- F1-Memory (Harmônica de precisão e recall)
- Consistency Score (Coerência entre sessões)
- LLM-as-Judge (Avaliação qualitativa)

Baseado em:
- MemoryAgentBench (ICLR 2025)
- LongMemEval (OpenReview 2024)
- A-MEM (arXiv 2025)
"""

import json
import math
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import litellm
import yaml


@dataclass
class GroundTruth:
    """Ground truth para uma mensagem."""
    message: str
    expected_memories: list[str]  # Memórias que DEVEM ser recuperadas
    expected_facts: list[str]  # Fatos que a resposta DEVE mencionar
    should_not_recall: list[str] = field(default_factory=list)  # Memórias irrelevantes


@dataclass
class RetrievalMetrics:
    """Métricas de recuperação de informação."""
    precision_at_k: dict[int, float]  # {1: 0.8, 3: 0.6, 5: 0.5}
    recall_at_k: dict[int, float]  # {1: 0.2, 3: 0.5, 5: 0.8}
    mrr: float  # Mean Reciprocal Rank
    f1_at_k: dict[int, float]  # F1 para cada K
    
    def to_dict(self) -> dict:
        return {
            "precision_at_k": self.precision_at_k,
            "recall_at_k": self.recall_at_k,
            "mrr": self.mrr,
            "f1_at_k": self.f1_at_k,
        }


@dataclass
class ConsistencyMetrics:
    """Métricas de consistência entre sessões."""
    factual_consistency: float  # % de fatos consistentes
    entity_consistency: float  # % de entidades corretamente referenciadas
    temporal_consistency: float  # % de eventos em ordem correta
    contradiction_count: int  # Número de contradições detectadas
    
    def to_dict(self) -> dict:
        return {
            "factual_consistency": self.factual_consistency,
            "entity_consistency": self.entity_consistency,
            "temporal_consistency": self.temporal_consistency,
            "contradiction_count": self.contradiction_count,
            "overall_consistency": (
                self.factual_consistency + 
                self.entity_consistency + 
                self.temporal_consistency
            ) / 3,
        }


@dataclass
class LLMJudgeResult:
    """Resultado de avaliação LLM-as-Judge."""
    relevance_score: float  # 0-10: Resposta é relevante à pergunta?
    memory_usage_score: float  # 0-10: Usa memórias adequadamente?
    coherence_score: float  # 0-10: Resposta é coerente?
    personalization_score: float  # 0-10: Resposta é personalizada?
    reasoning: str  # Explicação do julgamento
    
    @property
    def overall_score(self) -> float:
        """Score médio ponderado."""
        weights = {
            "relevance": 0.3,
            "memory_usage": 0.3,
            "coherence": 0.2,
            "personalization": 0.2,
        }
        return (
            self.relevance_score * weights["relevance"] +
            self.memory_usage_score * weights["memory_usage"] +
            self.coherence_score * weights["coherence"] +
            self.personalization_score * weights["personalization"]
        )
    
    def to_dict(self) -> dict:
        return {
            "relevance_score": self.relevance_score,
            "memory_usage_score": self.memory_usage_score,
            "coherence_score": self.coherence_score,
            "personalization_score": self.personalization_score,
            "overall_score": self.overall_score,
            "reasoning": self.reasoning,
        }


class ScientificMetricsEvaluator:
    """Avaliador de métricas científicas padronizadas."""
    
    def __init__(
        self,
        judge_model: str = "ollama_chat/ministral-3:3b",
        ollama_url: str = "http://localhost:11434",
    ):
        """
        Args:
            judge_model: Modelo para LLM-as-Judge (default: DeepSeek via Ollama)
            ollama_url: URL do Ollama
        """
        self.judge_model = judge_model
        self.ollama_url = ollama_url
        # Configure LiteLLM para Ollama
        import os
        os.environ["OLLAMA_API_BASE"] = ollama_url
    
    # ================== RETRIEVAL METRICS ==================
    
    def calculate_precision_at_k(
        self,
        retrieved: list[str],
        relevant: list[str],
        k: int,
    ) -> float:
        """
        Calcula Precision@K.
        
        Precision@K = |retrieved[:k] ∩ relevant| / k
        
        Args:
            retrieved: Lista de memórias recuperadas (ordenadas por relevância)
            relevant: Lista de memórias relevantes (ground truth)
            k: Número de itens a considerar
        """
        if k <= 0:
            return 0.0
        
        retrieved_k = retrieved[:k]
        relevant_set = set(self._normalize_memories(relevant))
        retrieved_set = set(self._normalize_memories(retrieved_k))
        
        intersection = len(relevant_set & retrieved_set)
        return intersection / k
    
    def calculate_recall_at_k(
        self,
        retrieved: list[str],
        relevant: list[str],
        k: int,
    ) -> float:
        """
        Calcula Recall@K.
        
        Recall@K = |retrieved[:k] ∩ relevant| / |relevant|
        
        Args:
            retrieved: Lista de memórias recuperadas (ordenadas por relevância)
            relevant: Lista de memórias relevantes (ground truth)
            k: Número de itens a considerar
        """
        if not relevant:
            return 1.0  # Se não há relevantes, recall é 100%
        
        retrieved_k = retrieved[:k]
        relevant_set = set(self._normalize_memories(relevant))
        retrieved_set = set(self._normalize_memories(retrieved_k))
        
        intersection = len(relevant_set & retrieved_set)
        return intersection / len(relevant_set)
    
    def calculate_mrr(
        self,
        retrieved: list[str],
        relevant: list[str],
    ) -> float:
        """
        Calcula Mean Reciprocal Rank.
        
        MRR = 1 / rank of first relevant item
        
        Args:
            retrieved: Lista de memórias recuperadas (ordenadas por relevância)
            relevant: Lista de memórias relevantes (ground truth)
        """
        if not relevant or not retrieved:
            return 0.0
        
        relevant_normalized = set(self._normalize_memories(relevant))
        
        for i, item in enumerate(retrieved):
            if self._normalize_memory(item) in relevant_normalized:
                return 1.0 / (i + 1)
        
        return 0.0
    
    def calculate_f1_at_k(
        self,
        retrieved: list[str],
        relevant: list[str],
        k: int,
    ) -> float:
        """Calcula F1@K = 2 * (P@K * R@K) / (P@K + R@K)."""
        precision = self.calculate_precision_at_k(retrieved, relevant, k)
        recall = self.calculate_recall_at_k(retrieved, relevant, k)
        
        if precision + recall == 0:
            return 0.0
        
        return 2 * (precision * recall) / (precision + recall)
    
    def calculate_retrieval_metrics(
        self,
        retrieved: list[str],
        relevant: list[str],
        k_values: list[int] = [1, 3, 5, 10],
    ) -> RetrievalMetrics:
        """Calcula todas as métricas de retrieval."""
        precision_at_k = {}
        recall_at_k = {}
        f1_at_k = {}
        
        for k in k_values:
            precision_at_k[k] = self.calculate_precision_at_k(retrieved, relevant, k)
            recall_at_k[k] = self.calculate_recall_at_k(retrieved, relevant, k)
            f1_at_k[k] = self.calculate_f1_at_k(retrieved, relevant, k)
        
        mrr = self.calculate_mrr(retrieved, relevant)
        
        return RetrievalMetrics(
            precision_at_k=precision_at_k,
            recall_at_k=recall_at_k,
            mrr=mrr,
            f1_at_k=f1_at_k,
        )
    
    # ================== CONSISTENCY METRICS ==================
    
    def calculate_consistency_metrics(
        self,
        sessions: list[dict],
        facts_per_session: dict[int, list[str]],
    ) -> ConsistencyMetrics:
        """
        Calcula métricas de consistência entre sessões.
        
        Args:
            sessions: Lista de sessões com suas respostas
            facts_per_session: Fatos introduzidos em cada sessão
        
        Returns:
            ConsistencyMetrics
        """
        factual_matches = 0
        factual_total = 0
        entity_matches = 0
        entity_total = 0
        temporal_matches = 0
        temporal_total = 0
        contradictions = 0
        
        # Acumula fatos conhecidos
        known_facts: set[str] = set()
        known_entities: set[str] = set()
        
        for session_idx, session in enumerate(sessions):
            # Adiciona fatos desta sessão
            session_facts = facts_per_session.get(session_idx, [])
            
            # Verifica se sessões posteriores lembram dos fatos
            for msg in session.get("messages", []):
                response = msg.get("cortex_response", "")
                
                # Verifica fatos anteriores mencionados
                for fact in known_facts:
                    factual_total += 1
                    if self._fact_mentioned(fact, response):
                        factual_matches += 1
                    elif self._fact_contradicted(fact, response):
                        contradictions += 1
                
                # Verifica entidades mencionadas
                for entity in known_entities:
                    entity_total += 1
                    if entity.lower() in response.lower():
                        entity_matches += 1
            
            # Atualiza conhecido
            known_facts.update(session_facts)
            known_entities.update(self._extract_entities(session_facts))
        
        return ConsistencyMetrics(
            factual_consistency=factual_matches / factual_total if factual_total else 1.0,
            entity_consistency=entity_matches / entity_total if entity_total else 1.0,
            temporal_consistency=temporal_matches / temporal_total if temporal_total else 1.0,
            contradiction_count=contradictions,
        )
    
    # ================== LLM-AS-JUDGE ==================
    
    def judge_response(
        self,
        user_message: str,
        response: str,
        memory_context: str,
        expected_facts: list[str],
        user_profile: dict,
    ) -> LLMJudgeResult:
        """
        Usa LLM para avaliar qualidade da resposta.
        
        Args:
            user_message: Mensagem do usuário
            response: Resposta do agente
            memory_context: Contexto de memória usado
            expected_facts: Fatos que deveriam ser mencionados
            user_profile: Perfil do usuário (para personalização)
        """
        # Usando YAML para economizar tokens (mais compacto que JSON)
        prompt = f"""Evaluate this AI response (0-10 each):

USER: {user_message}
RESPONSE: {response}
MEMORY: {memory_context}
EXPECTED: {', '.join(expected_facts) if expected_facts else 'none'}

Reply ONLY in YAML:
relevance: <0-10>
memory_usage: <0-10>
coherence: <0-10>
personalization: <0-10>
reasoning: <brief>"""

        try:
            
            result = litellm.completion(
                model=self.judge_model,
                messages=[{"role": "user", "content": prompt}],
                api_base=self.ollama_url,
            )
            
            content = result.choices[0].message.content
            # Strip markdown wrappers if present
            content = re.sub(r'```ya?ml\s*|\s*```', '', content).strip()
            parsed = yaml.safe_load(content)
            
            return LLMJudgeResult(
                relevance_score=float(parsed.get("relevance", 5)),
                memory_usage_score=float(parsed.get("memory_usage", 5)),
                coherence_score=float(parsed.get("coherence", 5)),
                personalization_score=float(parsed.get("personalization", 5)),
                reasoning=str(parsed.get("reasoning", "")),
            )
        except Exception as e:
            # Fallback em caso de erro
            return LLMJudgeResult(
                relevance_score=5.0,
                memory_usage_score=5.0,
                coherence_score=5.0,
                personalization_score=5.0,
                reasoning=f"Error during evaluation: {str(e)}",
            )
    
    def judge_batch(
        self,
        messages: list[dict],
        sample_size: int = 50,
    ) -> list[LLMJudgeResult]:
        """
        Avalia um lote de mensagens (amostragem para eficiência).
        
        Args:
            messages: Lista de mensagens para avaliar
            sample_size: Número de mensagens a amostrar
        """
        import random
        
        # Amostra se necessário
        if len(messages) > sample_size:
            messages = random.sample(messages, sample_size)
        
        results = []
        for msg in messages:
            result = self.judge_response(
                user_message=msg.get("message", ""),
                response=msg.get("cortex_response", ""),
                memory_context=msg.get("cortex_context_used", ""),
                expected_facts=msg.get("expected_recalls", []),
                user_profile=msg.get("user_profile", {}),
            )
            results.append(result)
        
        return results
    
    # ================== ABLATION SUPPORT ==================
    
    @staticmethod
    def compare_variants(
        results: dict[str, dict],
    ) -> dict:
        """
        Compara resultados de diferentes variantes para ablation study.
        
        Args:
            results: {variant_name: benchmark_result}
        
        Returns:
            Comparação estatística entre variantes
        """
        comparison = {}
        
        for variant, result in results.items():
            # Extrai métricas chave
            token_metrics = result.get("token_metrics", {})
            memory_metrics = result.get("memory_metrics", {})
            
            comparison[variant] = {
                "avg_tokens": token_metrics.get("cortex", {}).get("avg_tokens_per_message", 0),
                "memory_hit_rate": memory_metrics.get("memory_hit_rate", 0),
                "total_entities": memory_metrics.get("total_entities_recalled", 0),
                "total_episodes": memory_metrics.get("total_episodes_recalled", 0),
            }
        
        # Calcula diferenças relativas ao baseline (full)
        if "full" in comparison:
            baseline = comparison["full"]
            for variant, metrics in comparison.items():
                if variant != "full":
                    comparison[variant]["relative_performance"] = {
                        "hit_rate_diff": metrics["memory_hit_rate"] - baseline["memory_hit_rate"],
                        "token_diff_pct": (
                            (metrics["avg_tokens"] - baseline["avg_tokens"]) / baseline["avg_tokens"] * 100
                            if baseline["avg_tokens"] else 0
                        ),
                    }
        
        return comparison
    
    # ================== HELPERS ==================
    
    def _normalize_memory(self, memory: str) -> str:
        """Normaliza uma memória para comparação."""
        return memory.lower().strip()
    
    def _normalize_memories(self, memories: list[str]) -> list[str]:
        """Normaliza lista de memórias."""
        return [self._normalize_memory(m) for m in memories]
    
    def _fact_mentioned(self, fact: str, response: str) -> bool:
        """Verifica se um fato é mencionado na resposta."""
        # Versão simplificada - pode ser melhorada com NLI
        fact_words = set(fact.lower().split())
        response_lower = response.lower()
        
        # Pelo menos 50% das palavras do fato devem aparecer
        matches = sum(1 for word in fact_words if word in response_lower)
        return matches / len(fact_words) >= 0.5 if fact_words else False
    
    def _fact_contradicted(self, fact: str, response: str) -> bool:
        """Verifica se resposta contradiz um fato."""
        # Versão simplificada - detecta negações básicas
        negation_patterns = [
            r"not\s+",
            r"never\s+",
            r"don't\s+",
            r"doesn't\s+",
            r"didn't\s+",
            r"isn't\s+",
            r"aren't\s+",
            r"wasn't\s+",
            r"weren't\s+",
        ]
        
        fact_lower = fact.lower()
        response_lower = response.lower()
        
        for pattern in negation_patterns:
            if re.search(pattern + r".*" + re.escape(fact_lower[:20]), response_lower):
                return True
        
        return False
    
    def _extract_entities(self, texts: list[str]) -> list[str]:
        """Extrai entidades (simplificado - palavras capitalizadas)."""
        entities = []
        for text in texts:
            words = text.split()
            for word in words:
                if word[0].isupper() if word else False:
                    entities.append(word.strip(",.!?"))
        return entities


class BenchmarkAnnotator:
    """Cria anotações de ground truth para o benchmark."""
    
    @staticmethod
    def create_ground_truth_template(
        conversation: dict,
    ) -> dict:
        """
        Cria template de ground truth para uma conversa.
        
        Deve ser preenchido manualmente ou via LLM.
        """
        template = {
            "conversation_id": conversation.get("conversation_id"),
            "domain": conversation.get("domain"),
            "sessions": [],
        }
        
        for session in conversation.get("sessions", []):
            session_gt = {
                "session_index": session.get("session_index"),
                "key_facts": session.get("key_facts", []),
                "messages": [],
            }
            
            for msg in session.get("messages", []):
                msg_gt = {
                    "message": msg.get("message"),
                    "expected_memories": [],  # TO FILL
                    "expected_facts_in_response": [],  # TO FILL
                    "should_not_recall": [],  # TO FILL
                }
                session_gt["messages"].append(msg_gt)
            
            template["sessions"].append(session_gt)
        
        return template
    
    @staticmethod
    def generate_ground_truth_with_llm(
        conversation: dict,
        model: str = "ollama_chat/ministral-3:3b",
        ollama_url: str = "http://localhost:11434",
    ) -> dict:
        """
        Usa LLM para gerar ground truth automaticamente.
        
        Útil para bootstrap, mas deve ser revisado manualmente.
        """
        prompt = f"""Analyze this conversation and generate ground truth annotations.

CONVERSATION:
{json.dumps(conversation, indent=2)}

For each message, determine:
- expected_memories: What should the agent remember from previous sessions?
- expected_facts_in_response: What facts should the response include?
- should_not_recall: What memories would be irrelevant/wrong to recall?

Respond in YAML format."""

        try:
            os.environ["OLLAMA_API_BASE"] = ollama_url
            result = litellm.completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                api_base=ollama_url,
            )
            
            content = result.choices[0].message.content
            # Parse YAML from response (may have markdown wrappers)
            content = re.sub(r'```ya?ml\s*|\s*```', '', content).strip()
            return yaml.safe_load(content)
        except Exception as e:
            return {"error": str(e)}


# ================== INTEGRATION ==================


def evaluate_benchmark_scientifically(
    benchmark_result: dict,
    ground_truth: dict | None = None,
    use_llm_judge: bool = False,
    judge_model: str = "ollama_chat/ministral-3:3b",
    ollama_url: str = "http://localhost:11434",
) -> dict:
    """
    Avalia um resultado de benchmark com métricas científicas.
    
    Args:
        benchmark_result: Resultado do BenchmarkRunner
        ground_truth: Anotações de ground truth (opcional)
        use_llm_judge: Se deve usar LLM-as-Judge (requer API key)
        judge_model: Modelo para LLM-as-Judge
    
    Returns:
        Avaliação científica completa
    """
    evaluator = ScientificMetricsEvaluator(judge_model=judge_model, ollama_url=ollama_url)
    
    evaluation = {
        "timestamp": datetime.now().isoformat(),
        "benchmark_model": benchmark_result.get("model"),
        "retrieval_metrics": {},
        "consistency_metrics": {},
        "llm_judge_metrics": {},
    }
    
    # Coleta todas as mensagens
    all_messages = []
    for conv in benchmark_result.get("conversations", []):
        for session in conv.get("sessions", []):
            for msg in session.get("messages", []):
                msg["user_profile"] = conv.get("user_profile", {})
                all_messages.append(msg)
    
    # Métricas de retrieval (se ground truth disponível)
    if ground_truth:
        retrieval_results = []
        for conv in benchmark_result.get("conversations", []):
            conv_gt = next(
                (g for g in ground_truth.get("conversations", [])
                 if g.get("conversation_id") == conv.get("conversation_id")),
                None
            )
            if conv_gt:
                for session, session_gt in zip(
                    conv.get("sessions", []),
                    conv_gt.get("sessions", []),
                ):
                    for msg, msg_gt in zip(
                        session.get("messages", []),
                        session_gt.get("messages", []),
                    ):
                        # Extrai memórias recuperadas
                        retrieved = msg.get("cortex_context_used", "").split("\n")
                        expected = msg_gt.get("expected_memories", [])
                        
                        if expected:
                            metrics = evaluator.calculate_retrieval_metrics(
                                retrieved, expected
                            )
                            retrieval_results.append(metrics)
        
        # Agrega métricas de retrieval
        if retrieval_results:
            k_values = [1, 3, 5, 10]
            for k in k_values:
                evaluation["retrieval_metrics"][f"avg_precision@{k}"] = sum(
                    r.precision_at_k.get(k, 0) for r in retrieval_results
                ) / len(retrieval_results)
                evaluation["retrieval_metrics"][f"avg_recall@{k}"] = sum(
                    r.recall_at_k.get(k, 0) for r in retrieval_results
                ) / len(retrieval_results)
                evaluation["retrieval_metrics"][f"avg_f1@{k}"] = sum(
                    r.f1_at_k.get(k, 0) for r in retrieval_results
                ) / len(retrieval_results)
            
            evaluation["retrieval_metrics"]["avg_mrr"] = sum(
                r.mrr for r in retrieval_results
            ) / len(retrieval_results)
    
    # LLM-as-Judge
    if use_llm_judge:
        judge_results = evaluator.judge_batch(all_messages[:50])  # Amostra 50
        
        evaluation["llm_judge_metrics"] = {
            "sample_size": len(judge_results),
            "avg_relevance": sum(r.relevance_score for r in judge_results) / len(judge_results),
            "avg_memory_usage": sum(r.memory_usage_score for r in judge_results) / len(judge_results),
            "avg_coherence": sum(r.coherence_score for r in judge_results) / len(judge_results),
            "avg_personalization": sum(r.personalization_score for r in judge_results) / len(judge_results),
            "avg_overall": sum(r.overall_score for r in judge_results) / len(judge_results),
        }
    
    return evaluation


if __name__ == "__main__":
    # Exemplo de uso
    print("Scientific Metrics Module")
    print("=" * 40)
    
    # Teste de métricas de retrieval
    evaluator = ScientificMetricsEvaluator()
    
    retrieved = [
        "João é gerente de projetos",
        "Maria trabalha com João",
        "O projeto está atrasado",
        "João prefere café",
        "A reunião foi ontem",
    ]
    
    relevant = [
        "João é gerente de projetos",
        "João prefere café",
        "João mora em São Paulo",  # Não recuperado
    ]
    
    metrics = evaluator.calculate_retrieval_metrics(retrieved, relevant)
    
    print("\n📊 Retrieval Metrics:")
    print(f"   Precision@1: {metrics.precision_at_k[1]:.2f}")
    print(f"   Precision@3: {metrics.precision_at_k[3]:.2f}")
    print(f"   Precision@5: {metrics.precision_at_k[5]:.2f}")
    print(f"   Recall@1: {metrics.recall_at_k[1]:.2f}")
    print(f"   Recall@3: {metrics.recall_at_k[3]:.2f}")
    print(f"   Recall@5: {metrics.recall_at_k[5]:.2f}")
    print(f"   MRR: {metrics.mrr:.2f}")
    print(f"   F1@3: {metrics.f1_at_k[3]:.2f}")
