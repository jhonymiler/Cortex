"""
Consistency Metrics - Métricas de coerência entre sessões.

Avalia se o agente mantém consistência factual ao longo de múltiplas sessões:
1. Fact Consistency: Fatos mencionados são mantidos?
2. Identity Consistency: Identidade do usuário é lembrada?
3. Preference Consistency: Preferências são respeitadas?
4. Contradiction Detection: Contradições são evitadas?

Usado no paper para medir qualidade da memória além de hit rate.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import json

# Tenta importar LLM para avaliação
try:
    from benchmark.agents import call_llm_with_retry
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False


@dataclass
class ConsistencyResult:
    """Resultado de avaliação de consistência."""
    
    # Scores (0.0 - 1.0)
    fact_consistency: float = 0.0
    identity_consistency: float = 0.0
    preference_consistency: float = 0.0
    contradiction_score: float = 0.0  # Inverso: 1.0 = sem contradições
    
    # Score geral
    overall_score: float = 0.0
    
    # Detalhes
    facts_remembered: int = 0
    facts_forgotten: int = 0
    facts_contradicted: int = 0
    identity_matches: int = 0
    identity_misses: int = 0
    
    # Evidências
    contradictions_found: list[dict] = field(default_factory=list)
    facts_checked: list[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "fact_consistency": self.fact_consistency,
            "identity_consistency": self.identity_consistency,
            "preference_consistency": self.preference_consistency,
            "contradiction_score": self.contradiction_score,
            "overall_score": self.overall_score,
            "facts_remembered": self.facts_remembered,
            "facts_forgotten": self.facts_forgotten,
            "facts_contradicted": self.facts_contradicted,
            "contradictions_found": self.contradictions_found,
        }


@dataclass
class Fact:
    """Um fato extraído de uma conversa."""
    
    content: str
    fact_type: str  # "identity", "preference", "event", "attribute"
    entity: str  # Entidade relacionada
    session_id: str
    message_idx: int
    confidence: float = 1.0
    
    def matches(self, other: "Fact", threshold: float = 0.7) -> bool:
        """Verifica se dois fatos são sobre o mesmo assunto."""
        # Match por entidade
        if self.entity.lower() != other.entity.lower():
            return False
        
        # Match por tipo
        if self.fact_type != other.fact_type:
            return False
        
        # Match por conteúdo (simplificado)
        self_words = set(self.content.lower().split())
        other_words = set(other.content.lower().split())
        
        intersection = len(self_words & other_words)
        union = len(self_words | other_words)
        
        if union == 0:
            return False
        
        return (intersection / union) >= threshold
    
    def contradicts(self, other: "Fact") -> bool:
        """Verifica se dois fatos se contradizem."""
        if not self.matches(other, threshold=0.5):
            return False
        
        # Verifica negações
        negation_patterns = [
            (r'\bnão\b', r'\bsim\b'),
            (r'\bnunca\b', r'\bsempre\b'),
            (r'\bnenhum\b', r'\btodo\b'),
            (r'\bodeio\b', r'\bamo\b'),
            (r'\bprefiro\b', r'\bdetesto\b'),
        ]
        
        self_lower = self.content.lower()
        other_lower = other.content.lower()
        
        for neg, pos in negation_patterns:
            if re.search(neg, self_lower) and re.search(pos, other_lower):
                return True
            if re.search(pos, self_lower) and re.search(neg, other_lower):
                return True
        
        # Verifica valores diferentes para mesma propriedade
        # Ex: "meu nome é João" vs "meu nome é Pedro"
        name_match = re.search(r'(?:meu nome é|me chamo|sou o|sou a)\s+(\w+)', self_lower)
        other_name_match = re.search(r'(?:meu nome é|me chamo|sou o|sou a)\s+(\w+)', other_lower)
        
        if name_match and other_name_match:
            if name_match.group(1) != other_name_match.group(1):
                return True
        
        return False


class FactExtractor:
    """
    Extrai fatos de mensagens de conversa.
    
    Pode usar:
    - Regras heurísticas (rápido, menos preciso)
    - LLM (lento, mais preciso)
    """
    
    # Padrões para extração baseada em regras
    IDENTITY_PATTERNS = [
        (r'(?:meu nome é|me chamo|sou o|sou a)\s+(\w+)', 'name'),
        (r'(?:tenho|estou com)\s+(\d+)\s+anos?', 'age'),
        (r'(?:moro em|sou de|vivo em)\s+([^,.]+)', 'location'),
        (r'(?:trabalho com|sou|atuo como)\s+(\w+)', 'profession'),
    ]
    
    PREFERENCE_PATTERNS = [
        (r'(?:prefiro|gosto de|adoro|amo)\s+([^,.]+)', 'like'),
        (r'(?:não gosto de|odeio|detesto)\s+([^,.]+)', 'dislike'),
        (r'(?:uso|utilizo|trabalho com)\s+(\w+)', 'tool'),
    ]
    
    def __init__(self, use_llm: bool = False, model: str = "ministral-3:3b", ollama_url: str = "http://localhost:11434"):
        self.use_llm = use_llm and LLM_AVAILABLE
        self.model = model
        self.ollama_url = ollama_url
    
    def extract_facts(
        self,
        message: str,
        role: str,
        session_id: str,
        message_idx: int,
    ) -> list[Fact]:
        """Extrai fatos de uma mensagem."""
        if self.use_llm:
            return self._extract_with_llm(message, role, session_id, message_idx)
        return self._extract_with_rules(message, role, session_id, message_idx)
    
    def _extract_with_rules(
        self,
        message: str,
        role: str,
        session_id: str,
        message_idx: int,
    ) -> list[Fact]:
        """Extração baseada em regras."""
        facts = []
        message_lower = message.lower()
        
        # Extrai identidade
        for pattern, fact_subtype in self.IDENTITY_PATTERNS:
            match = re.search(pattern, message_lower)
            if match:
                facts.append(Fact(
                    content=match.group(0),
                    fact_type="identity",
                    entity=match.group(1),
                    session_id=session_id,
                    message_idx=message_idx,
                ))
        
        # Extrai preferências
        for pattern, fact_subtype in self.PREFERENCE_PATTERNS:
            match = re.search(pattern, message_lower)
            if match:
                facts.append(Fact(
                    content=match.group(0),
                    fact_type="preference",
                    entity=match.group(1),
                    session_id=session_id,
                    message_idx=message_idx,
                ))
        
        return facts
    
    def _extract_with_llm(
        self,
        message: str,
        role: str,
        session_id: str,
        message_idx: int,
    ) -> list[Fact]:
        """Extração usando LLM."""
        prompt = f"""Extraia os fatos importantes desta mensagem.

Mensagem ({role}): {message}

Retorne em YAML:
facts:
  - content: <fato exato>
    type: identity|preference|event|attribute
    entity: <entidade relacionada>

Exemplo:
facts:
  - content: "meu nome é João"
    type: identity
    entity: João
  - content: "prefiro Python"
    type: preference
    entity: Python

Se não houver fatos, retorne:
facts: []
"""
        
        try:
            response = call_llm_with_retry(
                model=f"ollama_chat/{self.model}",
                messages=[{"role": "user", "content": prompt}],
                api_base=self.ollama_url,
                max_retries=2,
                initial_wait=2.0,
            )
            
            import yaml
            content = response.choices[0].message.content
            data = yaml.safe_load(content)
            
            facts = []
            for f in data.get("facts", []):
                facts.append(Fact(
                    content=f.get("content", ""),
                    fact_type=f.get("type", "event"),
                    entity=f.get("entity", "unknown"),
                    session_id=session_id,
                    message_idx=message_idx,
                ))
            
            return facts
            
        except Exception as e:
            # Fallback para regras
            return self._extract_with_rules(message, role, session_id, message_idx)


class ConsistencyEvaluator:
    """
    Avalia consistência de um agente ao longo de múltiplas sessões.
    
    Processo:
    1. Extrai fatos de cada sessão
    2. Verifica se fatos de sessões anteriores são mantidos
    3. Detecta contradições
    4. Calcula scores
    """
    
    def __init__(
        self,
        use_llm: bool = False,
        model: str = "ministral-3:3b",
        ollama_url: str = "http://localhost:11434",
    ):
        self.extractor = FactExtractor(use_llm=use_llm, model=model, ollama_url=ollama_url)
        self.use_llm = use_llm
        self.model = model
        self.ollama_url = ollama_url
    
    def evaluate_conversation(
        self,
        sessions: list[dict],
    ) -> ConsistencyResult:
        """
        Avalia consistência de uma conversa com múltiplas sessões.
        
        Args:
            sessions: Lista de sessões, cada uma com 'messages' (lista de dicts com 'role' e 'content')
            
        Returns:
            ConsistencyResult com scores e detalhes
        """
        result = ConsistencyResult()
        
        # Extrai fatos de todas as sessões
        all_facts: list[Fact] = []
        facts_by_session: dict[str, list[Fact]] = {}
        
        for session_idx, session in enumerate(sessions):
            session_id = session.get("id", f"session_{session_idx}")
            session_facts = []
            
            for msg_idx, msg in enumerate(session.get("messages", [])):
                facts = self.extractor.extract_facts(
                    message=msg.get("content", ""),
                    role=msg.get("role", "user"),
                    session_id=session_id,
                    message_idx=msg_idx,
                )
                session_facts.extend(facts)
            
            facts_by_session[session_id] = session_facts
            all_facts.extend(session_facts)
        
        result.facts_checked = [{"content": f.content, "type": f.fact_type, "entity": f.entity} for f in all_facts]
        
        if not all_facts:
            result.overall_score = 1.0  # Sem fatos = sem inconsistências
            return result
        
        # Verifica contradições
        contradictions = self._find_contradictions(all_facts)
        result.contradictions_found = contradictions
        result.facts_contradicted = len(contradictions)
        
        # Calcula scores
        # Fact Consistency: fatos lembrados / total de fatos
        identity_facts = [f for f in all_facts if f.fact_type == "identity"]
        preference_facts = [f for f in all_facts if f.fact_type == "preference"]
        
        # Identity Consistency
        if identity_facts:
            unique_identities = self._count_unique_facts(identity_facts)
            result.identity_matches = unique_identities
            result.identity_consistency = min(1.0, unique_identities / max(1, len(identity_facts)))
        else:
            result.identity_consistency = 1.0
        
        # Preference Consistency
        if preference_facts:
            unique_preferences = self._count_unique_facts(preference_facts)
            result.preference_consistency = min(1.0, unique_preferences / max(1, len(preference_facts)))
        else:
            result.preference_consistency = 1.0
        
        # Contradiction Score (inverso: 1.0 = sem contradições)
        total_facts = len(all_facts)
        result.contradiction_score = max(0.0, 1.0 - (len(contradictions) / max(1, total_facts)))
        
        # Fact Consistency (geral)
        result.facts_remembered = len(all_facts) - len(contradictions)
        result.facts_forgotten = 0  # TODO: implementar detecção de esquecimento
        result.fact_consistency = max(0.0, 1.0 - (len(contradictions) / max(1, total_facts)))
        
        # Overall Score
        result.overall_score = (
            result.fact_consistency * 0.3 +
            result.identity_consistency * 0.3 +
            result.preference_consistency * 0.2 +
            result.contradiction_score * 0.2
        )
        
        return result
    
    def _find_contradictions(self, facts: list[Fact]) -> list[dict]:
        """Encontra contradições entre fatos."""
        contradictions = []
        
        for i, fact1 in enumerate(facts):
            for fact2 in facts[i + 1:]:
                if fact1.contradicts(fact2):
                    contradictions.append({
                        "fact1": fact1.content,
                        "fact1_session": fact1.session_id,
                        "fact2": fact2.content,
                        "fact2_session": fact2.session_id,
                        "entity": fact1.entity,
                    })
        
        return contradictions
    
    def _count_unique_facts(self, facts: list[Fact]) -> int:
        """Conta fatos únicos (não duplicados)."""
        unique = []
        for fact in facts:
            is_duplicate = False
            for existing in unique:
                if fact.matches(existing, threshold=0.8):
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique.append(fact)
        return len(unique)
    
    def evaluate_with_llm(
        self,
        sessions: list[dict],
    ) -> ConsistencyResult:
        """
        Avalia consistência usando LLM como juiz.
        
        Mais preciso mas mais caro.
        """
        if not LLM_AVAILABLE:
            return self.evaluate_conversation(sessions)
        
        # Prepara resumo das sessões
        session_summaries = []
        for idx, session in enumerate(sessions):
            messages = session.get("messages", [])
            summary_parts = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:200]
                summary_parts.append(f"{role}: {content}")
            
            session_summaries.append(f"Sessão {idx + 1}:\n" + "\n".join(summary_parts))
        
        prompt = f"""Analise a consistência desta conversa multi-sessão.

{chr(10).join(session_summaries)}

Avalie:
1. fact_consistency: Fatos mencionados são mantidos? (0.0-1.0)
2. identity_consistency: Identidade do usuário é lembrada? (0.0-1.0)
3. preference_consistency: Preferências são respeitadas? (0.0-1.0)
4. contradiction_score: Ausência de contradições (0.0-1.0, 1.0=sem contradições)

Retorne em YAML:
fact_consistency: 0.X
identity_consistency: 0.X
preference_consistency: 0.X
contradiction_score: 0.X
contradictions:
  - "descrição da contradição"
"""
        
        try:
            response = call_llm_with_retry(
                model=f"ollama_chat/{self.model}",
                messages=[{"role": "user", "content": prompt}],
                api_base=self.ollama_url,
                max_retries=2,
                initial_wait=3.0,
            )
            
            import yaml
            content = response.choices[0].message.content
            data = yaml.safe_load(content)
            
            result = ConsistencyResult(
                fact_consistency=float(data.get("fact_consistency", 0.5)),
                identity_consistency=float(data.get("identity_consistency", 0.5)),
                preference_consistency=float(data.get("preference_consistency", 0.5)),
                contradiction_score=float(data.get("contradiction_score", 0.5)),
            )
            
            result.overall_score = (
                result.fact_consistency * 0.3 +
                result.identity_consistency * 0.3 +
                result.preference_consistency * 0.2 +
                result.contradiction_score * 0.2
            )
            
            result.contradictions_found = [
                {"description": c} for c in data.get("contradictions", [])
            ]
            
            return result
            
        except Exception as e:
            print(f"⚠️ Erro na avaliação LLM: {e}")
            return self.evaluate_conversation(sessions)


def calculate_consistency_score(
    sessions: list[dict],
    use_llm: bool = False,
    model: str = "ministral-3:3b",
    ollama_url: str = "http://localhost:11434",
) -> ConsistencyResult:
    """
    Função de conveniência para calcular consistência.
    
    Args:
        sessions: Lista de sessões com mensagens
        use_llm: Se deve usar LLM para avaliação mais precisa
        model: Modelo Ollama
        ollama_url: URL do Ollama
        
    Returns:
        ConsistencyResult com scores
    """
    evaluator = ConsistencyEvaluator(
        use_llm=use_llm,
        model=model,
        ollama_url=ollama_url,
    )
    
    if use_llm:
        return evaluator.evaluate_with_llm(sessions)
    return evaluator.evaluate_conversation(sessions)


# Teste
if __name__ == "__main__":
    print("🔬 Testando Consistency Metrics...")
    
    # Sessões de exemplo
    sessions = [
        {
            "id": "session_1",
            "messages": [
                {"role": "user", "content": "Olá, meu nome é Carlos e sou desenvolvedor Python."},
                {"role": "assistant", "content": "Olá Carlos! Python é uma ótima linguagem."},
                {"role": "user", "content": "Prefiro usar VSCode como editor."},
                {"role": "assistant", "content": "VSCode é uma excelente escolha!"},
            ],
        },
        {
            "id": "session_2",
            "messages": [
                {"role": "user", "content": "Voltei! Ainda estou trabalhando no projeto Python."},
                {"role": "assistant", "content": "Olá novamente! Como posso ajudar?"},
                {"role": "user", "content": "Qual editor eu uso mesmo?"},
                {"role": "assistant", "content": "Você usa VSCode, Carlos!"},
            ],
        },
    ]
    
    result = calculate_consistency_score(sessions, use_llm=False)
    
    print("\n📊 Resultados:")
    print(f"   Fact Consistency: {result.fact_consistency:.2%}")
    print(f"   Identity Consistency: {result.identity_consistency:.2%}")
    print(f"   Preference Consistency: {result.preference_consistency:.2%}")
    print(f"   Contradiction Score: {result.contradiction_score:.2%}")
    print(f"   Overall Score: {result.overall_score:.2%}")
    
    if result.contradictions_found:
        print(f"\n⚠️ Contradições encontradas:")
        for c in result.contradictions_found:
            print(f"   - {c}")
    
    print("\n✅ Teste completo!")

