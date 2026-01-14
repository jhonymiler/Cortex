"""
LoCoMo Benchmark - Long-term Conversational Memory Evaluation

Implementa avaliação compatível com o benchmark LoCoMo (Stanford/Snap Research):
- Question Answering (QA) sobre histórico de conversas
- Métricas: F1 Score, BLEU-1, Exact Match, LLM-as-Judge
- Suporte a múltiplas sessões e eventos temporais

Referência: https://snap-research.github.io/locomo/

"Cortex, porque agentes inteligentes precisam de memória inteligente"
"""

import json
import time
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from collections import Counter
from pathlib import Path

# Importa Cortex
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cortex.core.graph import MemoryGraph
from cortex.core.primitives import Episode
from cortex.core.primitives import Entity


@dataclass
class QAExample:
    """Um exemplo de Question-Answering."""
    question: str
    expected_answer: str
    session_id: int = 0
    category: str = "factual"  # factual, temporal, preference, event
    difficulty: str = "easy"  # easy, medium, hard


@dataclass
class ConversationSession:
    """Uma sessão de conversa com múltiplos turnos."""
    session_id: int
    turns: list[dict[str, str]] = field(default_factory=list)  # [{"role": "user/assistant", "content": "..."}]
    timestamp: datetime = field(default_factory=datetime.now)
    events: list[str] = field(default_factory=list)  # Eventos que ocorreram na sessão


@dataclass
class LoCoMoTestCase:
    """Caso de teste LoCoMo completo."""
    persona_id: str
    persona_description: str
    sessions: list[ConversationSession] = field(default_factory=list)
    qa_pairs: list[QAExample] = field(default_factory=list)
    facts: dict[str, str] = field(default_factory=dict)  # Fatos importantes
    preferences: dict[str, str] = field(default_factory=dict)  # Preferências


@dataclass
class LoCoMoResult:
    """Resultado de avaliação LoCoMo."""
    # Métricas principais
    f1_score: float = 0.0
    exact_match: float = 0.0
    bleu_1: float = 0.0
    recall_at_1: float = 0.0
    recall_at_5: float = 0.0
    
    # Por categoria
    factual_f1: float = 0.0
    temporal_f1: float = 0.0
    preference_f1: float = 0.0
    event_f1: float = 0.0
    
    # Latência
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    
    # Detalhes
    total_questions: int = 0
    correct_answers: int = 0
    partial_answers: int = 0
    
    # Raw results
    qa_results: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "f1_score": round(self.f1_score, 4),
            "exact_match": round(self.exact_match, 4),
            "bleu_1": round(self.bleu_1, 4),
            "recall_at_1": round(self.recall_at_1, 4),
            "recall_at_5": round(self.recall_at_5, 4),
            "factual_f1": round(self.factual_f1, 4),
            "temporal_f1": round(self.temporal_f1, 4),
            "preference_f1": round(self.preference_f1, 4),
            "event_f1": round(self.event_f1, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "total_questions": self.total_questions,
            "correct_answers": self.correct_answers,
            "partial_answers": self.partial_answers,
        }


class LoCoMoMetrics:
    """Calculadora de métricas LoCoMo."""
    
    @staticmethod
    def tokenize(text: str) -> list[str]:
        """Tokeniza texto para cálculo de métricas."""
        # Normaliza
        text = text.lower().strip()
        # Remove pontuação
        text = re.sub(r'[^\w\s]', ' ', text)
        # Tokeniza
        tokens = text.split()
        return [t for t in tokens if t]
    
    @staticmethod
    def f1_score(prediction: str, reference: str) -> float:
        """
        Calcula F1 score entre predição e referência.
        
        F1 = 2 * (precision * recall) / (precision + recall)
        """
        pred_tokens = LoCoMoMetrics.tokenize(prediction)
        ref_tokens = LoCoMoMetrics.tokenize(reference)
        
        if not pred_tokens or not ref_tokens:
            return 0.0
        
        pred_counter = Counter(pred_tokens)
        ref_counter = Counter(ref_tokens)
        
        # Tokens em comum
        common = sum((pred_counter & ref_counter).values())
        
        if common == 0:
            return 0.0
        
        precision = common / len(pred_tokens)
        recall = common / len(ref_tokens)
        
        f1 = 2 * (precision * recall) / (precision + recall)
        return f1
    
    @staticmethod
    def exact_match(prediction: str, reference: str) -> float:
        """Verifica se predição é exatamente igual à referência."""
        pred_normalized = " ".join(LoCoMoMetrics.tokenize(prediction))
        ref_normalized = " ".join(LoCoMoMetrics.tokenize(reference))
        return 1.0 if pred_normalized == ref_normalized else 0.0
    
    @staticmethod
    def bleu_1(prediction: str, reference: str) -> float:
        """
        Calcula BLEU-1 (unigram precision).
        """
        pred_tokens = LoCoMoMetrics.tokenize(prediction)
        ref_tokens = LoCoMoMetrics.tokenize(reference)
        
        if not pred_tokens:
            return 0.0
        
        pred_counter = Counter(pred_tokens)
        ref_counter = Counter(ref_tokens)
        
        # Clipped count
        clipped = sum(min(pred_counter[t], ref_counter.get(t, 0)) for t in pred_counter)
        
        return clipped / len(pred_tokens)
    
    @staticmethod
    def contains_answer(prediction: str, reference: str) -> bool:
        """Verifica se a predição contém a resposta esperada."""
        pred_lower = prediction.lower()
        ref_lower = reference.lower()
        
        # Verifica substring
        if ref_lower in pred_lower:
            return True
        
        # Verifica tokens principais
        ref_tokens = set(LoCoMoMetrics.tokenize(reference))
        pred_tokens = set(LoCoMoMetrics.tokenize(prediction))
        
        # Se pelo menos 70% dos tokens da referência estão na predição
        if len(ref_tokens) > 0:
            overlap = len(ref_tokens & pred_tokens) / len(ref_tokens)
            return overlap >= 0.7
        
        return False


class LoCoMoBenchmark:
    """
    Benchmark LoCoMo para avaliação de memória de longo prazo.
    
    Baseado no paper:
    "LoCoMo: Long-term Conversational Memory for LLM-based Agents"
    """
    
    def __init__(self, graph: MemoryGraph | None = None):
        self.graph = graph or MemoryGraph()
        self.metrics = LoCoMoMetrics()
    
    def generate_test_cases(self) -> list[LoCoMoTestCase]:
        """
        Gera casos de teste sintéticos no formato LoCoMo.
        
        Categorias:
        - factual: Fatos sobre o usuário
        - temporal: Eventos com contexto temporal
        - preference: Preferências do usuário
        - event: Eventos específicos
        """
        cases = []
        
        # Caso 1: Suporte ao Cliente
        case1 = LoCoMoTestCase(
            persona_id="customer_support_1",
            persona_description="Cliente de e-commerce com histórico de compras",
            facts={
                "nome": "Carlos Silva",
                "email": "carlos@email.com",
                "tamanho_sapato": "42",
                "cor_preferida": "preto",
                "endereco": "São Paulo, SP",
            },
            preferences={
                "categoria_favorita": "calçados",
                "marca_preferida": "Nike",
                "forma_pagamento": "cartão de crédito",
                "horario_entrega": "manhã",
            },
        )
        
        # Sessão 1: Primeira compra
        session1 = ConversationSession(
            session_id=1,
            timestamp=datetime.now() - timedelta(days=30),
            turns=[
                {"role": "user", "content": "Olá, meu nome é Carlos Silva"},
                {"role": "assistant", "content": "Olá Carlos! Como posso ajudar?"},
                {"role": "user", "content": "Estou procurando sapatos pretos, tamanho 42"},
                {"role": "assistant", "content": "Temos várias opções no tamanho 42!"},
                {"role": "user", "content": "Prefiro da marca Nike"},
                {"role": "assistant", "content": "Encontrei 3 modelos Nike preto no 42"},
            ],
            events=["cliente_se_apresentou", "buscou_sapato", "indicou_preferencia_nike"],
        )
        
        # Sessão 2: Segunda visita
        session2 = ConversationSession(
            session_id=2,
            timestamp=datetime.now() - timedelta(days=15),
            turns=[
                {"role": "user", "content": "Voltei para finalizar aquela compra"},
                {"role": "assistant", "content": "Oi de novo! O sapato Nike preto 42?"},
                {"role": "user", "content": "Isso! Vou pagar com cartão de crédito"},
                {"role": "assistant", "content": "Perfeito, compra finalizada!"},
                {"role": "user", "content": "Entreguem pela manhã, por favor"},
                {"role": "assistant", "content": "Anotado: entrega pela manhã"},
            ],
            events=["retornou_para_compra", "pagou_cartao", "preferencia_entrega_manha"],
        )
        
        # Sessão 3: Problema com produto
        session3 = ConversationSession(
            session_id=3,
            timestamp=datetime.now() - timedelta(days=5),
            turns=[
                {"role": "user", "content": "O sapato que comprei está com defeito"},
                {"role": "assistant", "content": "Que pena Carlos! Qual o problema?"},
                {"role": "user", "content": "A sola está descolando"},
                {"role": "assistant", "content": "Vamos providenciar a troca imediatamente"},
                {"role": "user", "content": "Ok, obrigado pelo suporte rápido"},
            ],
            events=["reportou_defeito", "sola_descolando", "solicitou_troca"],
        )
        
        case1.sessions = [session1, session2, session3]
        
        # Perguntas QA
        case1.qa_pairs = [
            # Factual - Easy
            QAExample(
                question="Qual o nome do cliente?",
                expected_answer="Carlos Silva",
                category="factual",
                difficulty="easy",
            ),
            QAExample(
                question="Qual o tamanho de sapato do cliente?",
                expected_answer="42",
                category="factual",
                difficulty="easy",
            ),
            QAExample(
                question="Qual a cor preferida do cliente?",
                expected_answer="preto",
                category="factual",
                difficulty="easy",
            ),
            
            # Preference - Medium
            QAExample(
                question="Qual a marca preferida do cliente?",
                expected_answer="Nike",
                category="preference",
                difficulty="medium",
            ),
            QAExample(
                question="Como o cliente prefere receber entregas?",
                expected_answer="manhã",
                category="preference",
                difficulty="medium",
            ),
            QAExample(
                question="Qual a forma de pagamento preferida?",
                expected_answer="cartão de crédito",
                category="preference",
                difficulty="medium",
            ),
            
            # Event - Medium
            QAExample(
                question="O cliente teve algum problema com o produto?",
                expected_answer="sim, sola descolando",
                category="event",
                difficulty="medium",
            ),
            QAExample(
                question="O cliente finalizou a compra?",
                expected_answer="sim",
                category="event",
                difficulty="medium",
            ),
            
            # Temporal - Hard
            QAExample(
                question="Quantas vezes o cliente entrou em contato?",
                expected_answer="3",
                category="temporal",
                difficulty="hard",
            ),
            QAExample(
                question="O problema com o produto foi na primeira visita?",
                expected_answer="não, foi na terceira",
                category="temporal",
                difficulty="hard",
            ),
        ]
        
        cases.append(case1)
        
        # Caso 2: Assistente de Desenvolvimento
        case2 = LoCoMoTestCase(
            persona_id="dev_assistant_1",
            persona_description="Desenvolvedor trabalhando em projeto",
            facts={
                "nome": "Maria Santos",
                "linguagem_principal": "Python",
                "framework": "FastAPI",
                "banco_de_dados": "PostgreSQL",
                "ide": "VS Code",
            },
            preferences={
                "estilo_codigo": "type hints",
                "testes": "pytest",
                "formato_docstring": "Google style",
            },
        )
        
        session_dev1 = ConversationSession(
            session_id=1,
            timestamp=datetime.now() - timedelta(days=7),
            turns=[
                {"role": "user", "content": "Estou desenvolvendo uma API REST em Python"},
                {"role": "assistant", "content": "Qual framework você está usando?"},
                {"role": "user", "content": "FastAPI, é meu favorito"},
                {"role": "assistant", "content": "Excelente escolha! Banco de dados?"},
                {"role": "user", "content": "PostgreSQL"},
            ],
            events=["iniciou_projeto", "escolheu_fastapi", "escolheu_postgres"],
        )
        
        session_dev2 = ConversationSession(
            session_id=2,
            timestamp=datetime.now() - timedelta(days=3),
            turns=[
                {"role": "user", "content": "Preciso de ajuda com autenticação JWT"},
                {"role": "assistant", "content": "Vou criar com type hints como você prefere"},
                {"role": "user", "content": "Perfeito, sempre uso type hints"},
                {"role": "assistant", "content": "E os testes serão com pytest?"},
                {"role": "user", "content": "Sim, pytest com fixtures"},
            ],
            events=["implementou_jwt", "confirmou_type_hints", "usa_pytest"],
        )
        
        case2.sessions = [session_dev1, session_dev2]
        
        case2.qa_pairs = [
            QAExample(
                question="Qual framework o desenvolvedor usa?",
                expected_answer="FastAPI",
                category="factual",
                difficulty="easy",
            ),
            QAExample(
                question="Qual banco de dados foi escolhido?",
                expected_answer="PostgreSQL",
                category="factual",
                difficulty="easy",
            ),
            QAExample(
                question="O desenvolvedor usa type hints?",
                expected_answer="sim",
                category="preference",
                difficulty="medium",
            ),
            QAExample(
                question="Qual framework de testes é utilizado?",
                expected_answer="pytest",
                category="preference",
                difficulty="medium",
            ),
            QAExample(
                question="Qual feature foi implementada na segunda sessão?",
                expected_answer="autenticação JWT",
                category="event",
                difficulty="hard",
            ),
        ]
        
        cases.append(case2)
        
        return cases
    
    def ingest_test_case(self, test_case: LoCoMoTestCase) -> None:
        """
        Ingere um caso de teste no grafo de memória.
        """
        namespace = f"locomo:{test_case.persona_id}"
        
        # Cria entidade do persona
        persona_entity = Entity(
            name=test_case.facts.get("nome", test_case.persona_id),
            type="person",
            attributes={**test_case.facts, **test_case.preferences},
        )
        self.graph.add_entity(persona_entity)
        
        # Ingere cada sessão
        for session in test_case.sessions:
            for i, turn in enumerate(session.turns):
                if turn["role"] == "user":
                    # Cria episódio para cada mensagem do usuário
                    episode = Episode(
                        action=f"disse",
                        participants=[persona_entity.id],
                        context=turn["content"],
                        outcome=session.turns[i+1]["content"] if i+1 < len(session.turns) else "",
                        timestamp=session.timestamp,
                    )
                    episode.metadata["w5h"] = {
                        "who": [test_case.facts.get("nome", test_case.persona_id)],
                        "what": turn["content"][:50],
                        "where": namespace,
                    }
                    episode.metadata["namespace"] = namespace
                    episode.metadata["session_id"] = session.session_id
                    self.graph.add_episode(episode)
            
            # Adiciona eventos como episódios
            for event in session.events:
                episode = Episode(
                    action=event,
                    participants=[persona_entity.id],
                    timestamp=session.timestamp,
                )
                episode.metadata["namespace"] = namespace
                episode.metadata["event"] = True
                self.graph.add_episode(episode)
        
        # Adiciona fatos como episódios
        for key, value in test_case.facts.items():
            episode = Episode(
                action=f"informou_{key}",
                participants=[persona_entity.id],
                outcome=value,
            )
            episode.metadata["w5h"] = {
                "what": f"{key}={value}",
                "who": [test_case.facts.get("nome", test_case.persona_id)],
            }
            episode.metadata["namespace"] = namespace
            episode.metadata["fact"] = True
            self.graph.add_episode(episode)
        
        # Adiciona preferências como episódios
        for key, value in test_case.preferences.items():
            episode = Episode(
                action=f"preferencia_{key}",
                participants=[persona_entity.id],
                outcome=value,
            )
            episode.metadata["w5h"] = {
                "what": f"{key}={value}",
                "who": [test_case.facts.get("nome", test_case.persona_id)],
            }
            episode.metadata["namespace"] = namespace
            episode.metadata["preference"] = True
            self.graph.add_episode(episode)
    
    def answer_question(self, question: str, namespace: str) -> tuple[str, float]:
        """
        Responde uma pergunta usando o grafo de memória.
        
        Returns:
            Tupla (resposta, latência_ms)
        """
        start_time = time.time()
        
        # Recall do Cortex
        result = self.graph.recall(
            query=question,
            context={"namespace": namespace},
            limit=10,
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Gera resposta a partir do contexto
        if not result.episodes and not result.entities:
            return "Não encontrei informações sobre isso", latency_ms
        
        # Extrai informações relevantes
        answer_parts = []
        
        # De entidades
        for entity in result.entities[:3]:
            if entity.attributes:
                for key, value in entity.attributes.items():
                    if self._is_relevant(key, question):
                        answer_parts.append(str(value))
        
        # De episódios
        for episode in result.episodes[:5]:
            w5h = episode.metadata.get("w5h", {})
            
            # Verifica se é relevante para a pergunta
            what = w5h.get("what", episode.action)
            how = w5h.get("how", episode.outcome)
            
            if what:
                answer_parts.append(str(what))
            if how:
                answer_parts.append(str(how))
        
        # Combina partes únicas
        unique_parts = []
        seen = set()
        for part in answer_parts:
            part_lower = part.lower()
            if part_lower not in seen and len(part) > 1:
                seen.add(part_lower)
                unique_parts.append(part)
        
        answer = " ".join(unique_parts[:3]) if unique_parts else "Não encontrei informações"
        
        return answer, latency_ms
    
    def _is_relevant(self, key: str, question: str) -> bool:
        """Verifica se uma chave é relevante para a pergunta."""
        question_lower = question.lower()
        key_lower = key.lower().replace("_", " ")
        
        # Mapeamento de termos
        mappings = {
            "nome": ["nome", "name", "chama", "quem"],
            "tamanho": ["tamanho", "size", "número", "numero"],
            "cor": ["cor", "color", "preferida"],
            "marca": ["marca", "brand", "preferida"],
            "framework": ["framework", "usa", "utiliza"],
            "banco": ["banco", "database", "dados"],
            "linguagem": ["linguagem", "language", "programa"],
        }
        
        for term, keywords in mappings.items():
            if term in key_lower:
                if any(kw in question_lower for kw in keywords):
                    return True
        
        return key_lower in question_lower
    
    def run(self, test_cases: list[LoCoMoTestCase] | None = None) -> LoCoMoResult:
        """
        Executa o benchmark LoCoMo.
        
        Args:
            test_cases: Casos de teste (None = gera automaticamente)
            
        Returns:
            LoCoMoResult com métricas
        """
        if test_cases is None:
            test_cases = self.generate_test_cases()
        
        result = LoCoMoResult()
        all_latencies = []
        
        # Por categoria
        category_scores: dict[str, list[float]] = {
            "factual": [],
            "temporal": [],
            "preference": [],
            "event": [],
        }
        
        for test_case in test_cases:
            # Limpa e ingere caso de teste
            self.graph.clear()
            self.ingest_test_case(test_case)
            
            namespace = f"locomo:{test_case.persona_id}"
            
            # Avalia cada pergunta
            for qa in test_case.qa_pairs:
                answer, latency_ms = self.answer_question(qa.question, namespace)
                all_latencies.append(latency_ms)
                
                # Calcula métricas
                f1 = self.metrics.f1_score(answer, qa.expected_answer)
                em = self.metrics.exact_match(answer, qa.expected_answer)
                bleu = self.metrics.bleu_1(answer, qa.expected_answer)
                contains = self.metrics.contains_answer(answer, qa.expected_answer)
                
                # Armazena resultado
                qa_result = {
                    "question": qa.question,
                    "expected": qa.expected_answer,
                    "predicted": answer,
                    "f1": f1,
                    "exact_match": em,
                    "bleu_1": bleu,
                    "contains_answer": contains,
                    "category": qa.category,
                    "difficulty": qa.difficulty,
                    "latency_ms": latency_ms,
                }
                result.qa_results.append(qa_result)
                
                # Atualiza contadores
                result.total_questions += 1
                if em == 1.0:
                    result.correct_answers += 1
                elif contains:
                    result.partial_answers += 1
                
                # Por categoria
                if qa.category in category_scores:
                    category_scores[qa.category].append(f1)
        
        # Calcula métricas agregadas
        if result.qa_results:
            result.f1_score = sum(r["f1"] for r in result.qa_results) / len(result.qa_results)
            result.exact_match = sum(r["exact_match"] for r in result.qa_results) / len(result.qa_results)
            result.bleu_1 = sum(r["bleu_1"] for r in result.qa_results) / len(result.qa_results)
            result.recall_at_1 = sum(1 for r in result.qa_results if r["contains_answer"]) / len(result.qa_results)
        
        # Por categoria
        for category, scores in category_scores.items():
            if scores:
                avg = sum(scores) / len(scores)
                setattr(result, f"{category}_f1", avg)
        
        # Latência
        if all_latencies:
            result.avg_latency_ms = sum(all_latencies) / len(all_latencies)
            sorted_latencies = sorted(all_latencies)
            p95_idx = int(len(sorted_latencies) * 0.95)
            result.p95_latency_ms = sorted_latencies[min(p95_idx, len(sorted_latencies)-1)]
        
        return result
    
    def save_results(self, result: LoCoMoResult, output_path: str | Path) -> None:
        """Salva resultados em JSON."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "benchmark": "LoCoMo",
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "summary": result.to_dict(),
            "detailed_results": result.qa_results,
        }
        
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Resultados salvos em: {output_path}")


def run_locomo_benchmark() -> LoCoMoResult:
    """Função principal para executar o benchmark."""
    print("\n" + "="*60)
    print("🧠 LoCoMo Benchmark - Cortex Memory Evaluation")
    print("="*60 + "\n")
    
    benchmark = LoCoMoBenchmark()
    result = benchmark.run()
    
    # Exibe resultados
    print("\n📊 RESULTADOS:")
    print("-" * 40)
    print(f"F1 Score:        {result.f1_score:.2%}")
    print(f"Exact Match:     {result.exact_match:.2%}")
    print(f"BLEU-1:          {result.bleu_1:.2%}")
    print(f"Recall@1:        {result.recall_at_1:.2%}")
    print("-" * 40)
    print(f"Factual F1:      {result.factual_f1:.2%}")
    print(f"Temporal F1:     {result.temporal_f1:.2%}")
    print(f"Preference F1:   {result.preference_f1:.2%}")
    print(f"Event F1:        {result.event_f1:.2%}")
    print("-" * 40)
    print(f"Latência média:  {result.avg_latency_ms:.1f}ms")
    print(f"Latência P95:    {result.p95_latency_ms:.1f}ms")
    print("-" * 40)
    print(f"Total perguntas: {result.total_questions}")
    print(f"Corretas:        {result.correct_answers}")
    print(f"Parciais:        {result.partial_answers}")
    print()
    
    # Salva resultados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(__file__).parent / "results" / f"locomo_{timestamp}.json"
    benchmark.save_results(result, output_path)
    
    return result


if __name__ == "__main__":
    run_locomo_benchmark()
