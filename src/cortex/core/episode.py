"""
Episode - Representa um acontecimento/experiência no sistema de memória.

Episódios são a unidade fundamental de memória experiencial:
- O QUE aconteceu (action)
- QUEM/O QUE participou (participants)
- CONTEXTO/SITUAÇÃO
- RESULTADO (outcome)
- QUANDO
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class Episode:
    """
    Um episódio é uma experiência que pode ser lembrada.
    
    Episódios são automaticamente consolidados quando padrões se repetem.
    Por exemplo, 10 análises do mesmo log viram 1 episódio consolidado.
    
    Attributes:
        id: Identificador único (UUID)
        timestamp: Quando aconteceu
        action: Verbo descrevendo a ação (analyzed, resolved, discussed, met...)
        participants: IDs das entidades envolvidas
        context: Descrição da situação/cenário
        outcome: Resultado/conclusão
        occurrence_count: Quantas vezes este padrão ocorreu
        consolidated_from: IDs de episódios que foram consolidados neste
        importance: Importância (0.0 - 1.0), aumenta com acesso e consolidação
        
    Examples:
        # Dev
        Episode(
            action="debugged",
            participants=["entity_bug_123", "entity_file_456"],
            context="production server crash",
            outcome="fixed memory leak by closing connections"
        )
        
        # Roleplay
        Episode(
            action="confessed",
            participants=["entity_elena", "entity_marcus"],
            context="moonlit rooftop",
            outcome="mutual feelings revealed"
        )
        
        # Chatbot
        Episode(
            action="resolved_complaint",
            participants=["entity_customer_maria", "entity_product_laptop"],
            context="delivery delay issue",
            outcome="refund processed, customer satisfied"
        )
    """
    
    action: str
    participants: list[str] = field(default_factory=list)  # Entity IDs
    context: str = ""
    outcome: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    occurrence_count: int = 1
    consolidated_from: list[str] = field(default_factory=list)
    importance: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Context tracking (para recall melhorado)
    conversation_id: str | None = None
    session_id: str | None = None
    
    # Embedding para busca semântica (vetor de 1024 dimensões)
    embedding: list[float] | None = None
    
    @property
    def is_consolidated(self) -> bool:
        """Retorna True se este episódio é resultado de consolidação."""
        return len(self.consolidated_from) > 0
    
    @property
    def consolidation_level(self) -> int:
        """Retorna o nível de consolidação (1 = original, N = consolidou N episódios)."""
        return max(1, len(self.consolidated_from))
    
    def boost_importance(self, amount: float = 0.1) -> None:
        """Aumenta a importância do episódio (max 1.0)."""
        self.importance = min(1.0, self.importance + amount)
    
    def decay_importance(self, factor: float = 0.95) -> None:
        """Reduz a importância do episódio (decay temporal)."""
        self.importance *= factor
    
    def matches_pattern(self, other: "Episode", threshold: float = 0.7) -> bool:
        """
        Verifica se outro episódio tem padrão similar.
        
        Considera:
        - Mesma ação
        - Participantes similares (interseção)
        - Contexto/outcome similar (keywords)
        """
        # Ação diferente = padrão diferente
        if self.action.lower() != other.action.lower():
            return False
        
        # Calcula interseção de participantes
        self_parts = set(self.participants)
        other_parts = set(other.participants)
        
        if self_parts and other_parts:
            intersection = len(self_parts & other_parts)
            union = len(self_parts | other_parts)
            participant_similarity = intersection / union if union > 0 else 0
        else:
            participant_similarity = 0.5  # Neutro se um não tem participantes
        
        # Similaridade de contexto (simples: palavras em comum)
        self_words = set(self.context.lower().split())
        other_words = set(other.context.lower().split())
        
        if self_words and other_words:
            context_similarity = len(self_words & other_words) / len(self_words | other_words)
        else:
            context_similarity = 0.5
        
        # Score final
        score = (participant_similarity * 0.5) + (context_similarity * 0.5)
        
        return score >= threshold
    
    def similarity_score(self, query: str, context: dict[str, Any] | None = None) -> float:
        """
        Calcula score de relevância (0.0 - 1.0) para uma query.
        
        OTIMIZADO v2:
        - Usa tokenização consistente (remove stopwords)
        - Match por todos os campos (action, context, outcome)
        - Boost por importância e consolidação
        """
        from cortex.core.language import tokenize_to_set
        
        query_tokens = tokenize_to_set(query)
        if not query_tokens:
            return 0.0
        
        score = 0.0
        
        # Match por ação (peso maior)
        action_tokens = tokenize_to_set(self.action)
        if action_tokens:
            overlap = len(query_tokens & action_tokens) / len(query_tokens)
            if overlap > 0:
                # Base 0.4 + até 0.4 de overlap
                score = max(score, 0.4 + (overlap * 0.4))
        
        # Match por contexto
        context_tokens = tokenize_to_set(self.context)
        if context_tokens:
            overlap = len(query_tokens & context_tokens) / len(query_tokens)
            if overlap > 0:
                score = max(score, 0.3 + (overlap * 0.3))
        
        # Match por outcome
        outcome_tokens = tokenize_to_set(self.outcome)
        if outcome_tokens:
            overlap = len(query_tokens & outcome_tokens) / len(query_tokens)
            if overlap > 0:
                score = max(score, 0.3 + (overlap * 0.3))
        
        # Boost por importância (0.5 a 1.0)
        score *= (0.5 + self.importance * 0.5)
        
        # Boost por consolidação (episódios consolidados são mais relevantes)
        if self.is_consolidated:
            score *= 1.1
        
        # Boost por contexto externo
        if context:
            # Se participantes estão no contexto
            if context.get("entity_ids"):
                matching = set(self.participants) & set(context["entity_ids"])
                if matching:
                    score = min(1.0, score + 0.2)
        
        return min(1.0, score)

    def get_consolidation_threshold(self, mode: str = "progressive") -> int:
        """
        Calcula threshold dinâmico para consolidação baseado na idade do padrão.

        Progressive Consolidation (age-aware):
        - Padrões emergentes (< 7 dias): threshold = 2 (consolida rápido)
        - Padrões recorrentes (7-30 dias): threshold = 4
        - Padrões estáveis (30-90 dias): threshold = 8
        - Padrões cristalizados (> 90 dias): threshold = 16

        Args:
            mode: "progressive" (age-aware) ou "fixed" (legacy, threshold=5)

        Returns:
            Threshold de consolidação (número de ocorrências necessárias)
        """
        if mode == "fixed":
            return 5  # Legacy behavior

        # Calculate pattern age
        if not self.timestamp:
            return 2  # Default to emerging pattern

        days_old = (datetime.now() - self.timestamp).days

        # Progressive thresholds based on age
        if days_old < 7:
            return 2  # Emerging: consolidate fast
        elif days_old < 30:
            return 4  # Recurring: medium threshold
        elif days_old < 90:
            return 8  # Stable: higher evidence needed
        else:
            return 16  # Crystallized: very high threshold

    def to_summary(self) -> str:
        """Gera um resumo legível do episódio."""
        parts = [f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}]"]
        parts.append(f"Action: {self.action}")
        
        if self.context:
            parts.append(f"Context: {self.context}")
        
        if self.outcome:
            parts.append(f"Outcome: {self.outcome}")
        
        if self.is_consolidated:
            parts.append(f"(Consolidated from {self.consolidation_level} episodes)")
        
        return " | ".join(parts)
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa para dicionário."""
        result = {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "participants": self.participants,
            "context": self.context,
            "outcome": self.outcome,
            "occurrence_count": self.occurrence_count,
            "consolidated_from": self.consolidated_from,
            "importance": self.importance,
            "metadata": self.metadata,
        }
        # Só inclui embedding se existir (economiza espaço)
        if self.embedding:
            result["embedding"] = self.embedding
        return result
    
    def get_text_for_embedding(self) -> str:
        """
        Gera texto representativo do episódio para embedding.
        
        Converte formato técnico (underscores) para linguagem natural
        para melhorar matching semântico com queries em linguagem natural.
        
        Exemplo:
            action="problema_login_sistema", context="senha_expirada"
            → "problema login sistema senha expirada"
        """
        def expand_underscores(text: str) -> str:
            """Converte underscores para espaços."""
            return text.replace("_", " ") if text else ""
        
        parts = []
        
        # Adiciona ação (what) expandida
        if self.action:
            parts.append(expand_underscores(self.action))
        
        # Adiciona contexto/razão (why) expandido
        if self.context:
            parts.append(expand_underscores(self.context))
        
        # Adiciona outcome (how) expandido
        if self.outcome:
            parts.append(expand_underscores(self.outcome))
        
        # Adiciona participantes (who) se disponíveis
        # Isso ajuda queries como "cliente João" a encontrar memórias
        if self.participants:
            for p in self.participants[:3]:  # Limita a 3 participantes
                if p and len(p) > 2:  # Ignora IDs curtos
                    parts.append(expand_underscores(p))
        
        return " ".join(parts)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Episode":
        """Deserializa de dicionário."""
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            action=data["action"],
            participants=data.get("participants", []),
            context=data.get("context", ""),
            outcome=data.get("outcome", ""),
            occurrence_count=data.get("occurrence_count", 1),
            consolidated_from=data.get("consolidated_from", []),
            importance=data.get("importance", 0.5),
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding"),  # Pode ser None
        )
    
    @classmethod
    def consolidate(cls, episodes: list["Episode"]) -> "Episode":
        """
        Cria um episódio consolidado a partir de múltiplos episódios similares.
        
        O episódio consolidado:
        - Mantém a ação comum
        - Une participantes
        - Sumariza contextos/outcomes
        - Registra contagem de ocorrências
        """
        if not episodes:
            raise ValueError("Cannot consolidate empty list")
        
        if len(episodes) == 1:
            return episodes[0]
        
        # Usa a ação do primeiro (devem ser iguais para consolidar)
        action = episodes[0].action
        
        # Une todos os participantes
        all_participants = set()
        for ep in episodes:
            all_participants.update(ep.participants)
        
        # Encontra contexto mais comum ou combina
        contexts = [ep.context for ep in episodes if ep.context]
        if contexts:
            # Por simplicidade, usa o mais recente
            context = contexts[-1]
        else:
            context = ""
        
        # Encontra outcome mais comum
        outcomes = [ep.outcome for ep in episodes if ep.outcome]
        if outcomes:
            # Usa o mais recente
            outcome = f"Pattern ({len(episodes)}x): {outcomes[-1]}"
        else:
            outcome = f"Occurred {len(episodes)} times"
        
        # IDs consolidados
        consolidated_ids = [ep.id for ep in episodes]
        
        # Soma importância (consolidação aumenta relevância)
        avg_importance = sum(ep.importance for ep in episodes) / len(episodes)
        boosted_importance = min(1.0, avg_importance + 0.1 * len(episodes))
        
        return cls(
            action=action,
            participants=list(all_participants),
            context=context,
            outcome=outcome,
            occurrence_count=len(episodes),
            consolidated_from=consolidated_ids,
            importance=boosted_importance,
            metadata={"source": "consolidation"},
        )
    
    def __repr__(self) -> str:
        return f"Episode(action={self.action!r}, id={self.id[:8]}..., count={self.occurrence_count})"
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Episode):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        return hash(self.id)
