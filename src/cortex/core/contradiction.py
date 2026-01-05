"""
Contradiction Detection and Resolution System.

Detecta e resolve contradições entre relações no grafo de memória.

Estratégias de resolução:
- MOST_RECENT: A informação mais recente prevalece
- STRONGEST: A relação mais forte prevalece  
- MOST_REINFORCED: A mais confirmada prevalece
- ASK_USER: Pergunta ao usuário
- KEEP_BOTH: Mantém ambas (marca como conflito)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable
from uuid import uuid4

if TYPE_CHECKING:
    from cortex.core.relation import Relation


class ResolutionStrategy(Enum):
    """Estratégias para resolver contradições."""
    
    MOST_RECENT = "most_recent"      # Mais recente ganha
    STRONGEST = "strongest"          # Mais forte ganha
    MOST_REINFORCED = "reinforced"   # Mais reforçada ganha
    ASK_USER = "ask_user"            # Pergunta ao usuário
    KEEP_BOTH = "keep_both"          # Mantém ambas como conflito


@dataclass
class Contradiction:
    """
    Representa uma contradição detectada entre duas relações.
    
    Attributes:
        id: Identificador único
        relation_a: Primeira relação
        relation_b: Segunda relação (contraditória)
        detected_at: Quando foi detectada
        resolved: Se já foi resolvida
        resolution: Como foi resolvida
        winner_id: ID da relação vencedora (se resolvida)
    """
    
    relation_a: "Relation"
    relation_b: "Relation"
    id: str = field(default_factory=lambda: str(uuid4()))
    detected_at: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution: ResolutionStrategy | None = None
    winner_id: str | None = None
    
    def describe(self) -> str:
        """Descrição legível da contradição."""
        return (
            f"CONTRADIÇÃO DETECTADA:\n"
            f"  A: {self.relation_a.to_triple()} (polarity={self.relation_a.polarity:.1f})\n"
            f"  B: {self.relation_b.to_triple()} (polarity={self.relation_b.polarity:.1f})\n"
            f"  Status: {'Resolvida' if self.resolved else 'Pendente'}"
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa para dicionário."""
        return {
            "id": self.id,
            "relation_a_id": self.relation_a.id,
            "relation_b_id": self.relation_b.id,
            "detected_at": self.detected_at.isoformat(),
            "resolved": self.resolved,
            "resolution": self.resolution.value if self.resolution else None,
            "winner_id": self.winner_id,
        }


@dataclass
class ResolutionResult:
    """Resultado de uma resolução de contradição."""
    
    contradiction: Contradiction
    strategy_used: ResolutionStrategy
    winner: "Relation | None"
    loser: "Relation | None"
    action_taken: str  # "kept_winner", "marked_conflict", "asked_user"
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa para dicionário."""
        return {
            "contradiction_id": self.contradiction.id,
            "strategy_used": self.strategy_used.value,
            "winner_id": self.winner.id if self.winner else None,
            "loser_id": self.loser.id if self.loser else None,
            "action_taken": self.action_taken,
        }


class ContradictionDetector:
    """
    Detecta e resolve contradições no grafo de memória.
    
    Uso:
        detector = ContradictionDetector(strategy=ResolutionStrategy.MOST_RECENT)
        
        # Detectar ao adicionar nova relação
        contradiction = detector.check_for_contradiction(new_relation, existing_relations)
        
        if contradiction:
            result = detector.resolve(contradiction)
            # result.winner é a relação que deve ser mantida
            # result.loser pode ser removida ou marcada
    """
    
    def __init__(
        self,
        strategy: ResolutionStrategy = ResolutionStrategy.MOST_RECENT,
        on_ask_user: Callable[[Contradiction], "Relation"] | None = None,
    ) -> None:
        """
        Inicializa o detector.
        
        Args:
            strategy: Estratégia padrão de resolução
            on_ask_user: Callback para estratégia ASK_USER
        """
        self.strategy = strategy
        self.on_ask_user = on_ask_user
        self._history: list[Contradiction] = []
    
    def check_for_contradiction(
        self,
        new_relation: "Relation",
        existing_relations: list["Relation"],
    ) -> Contradiction | None:
        """
        Verifica se uma nova relação contradiz alguma existente.
        
        Args:
            new_relation: Relação sendo adicionada
            existing_relations: Relações existentes no grafo
            
        Returns:
            Contradiction se encontrar, None caso contrário
        """
        for existing in existing_relations:
            if new_relation.contradicts(existing):
                contradiction = Contradiction(
                    relation_a=existing,
                    relation_b=new_relation,
                )
                self._history.append(contradiction)
                return contradiction
        
        return None
    
    def find_all_contradictions(
        self,
        relations: list["Relation"],
    ) -> list[Contradiction]:
        """
        Encontra todas as contradições em uma lista de relações.
        
        Útil para auditoria do grafo de memória.
        
        Args:
            relations: Lista de relações para analisar
            
        Returns:
            Lista de contradições encontradas
        """
        contradictions: list[Contradiction] = []
        checked_pairs: set[tuple[str, str]] = set()
        
        for i, rel_a in enumerate(relations):
            for rel_b in relations[i + 1:]:
                # Evitar verificar o mesmo par duas vezes
                pair_key = tuple(sorted([rel_a.id, rel_b.id]))
                if pair_key in checked_pairs:
                    continue
                checked_pairs.add(pair_key)
                
                if rel_a.contradicts(rel_b):
                    contradiction = Contradiction(
                        relation_a=rel_a,
                        relation_b=rel_b,
                    )
                    contradictions.append(contradiction)
        
        return contradictions
    
    def resolve(
        self,
        contradiction: Contradiction,
        strategy: ResolutionStrategy | None = None,
    ) -> ResolutionResult:
        """
        Resolve uma contradição usando a estratégia especificada.
        
        Args:
            contradiction: Contradição a resolver
            strategy: Estratégia a usar (ou usa a padrão)
            
        Returns:
            ResolutionResult com a decisão tomada
        """
        strategy = strategy or self.strategy
        
        rel_a = contradiction.relation_a
        rel_b = contradiction.relation_b
        
        winner: "Relation | None" = None
        loser: "Relation | None" = None
        action_taken = "unknown"
        
        if strategy == ResolutionStrategy.MOST_RECENT:
            # Mais recente ganha
            if rel_a.created_at >= rel_b.created_at:
                winner, loser = rel_a, rel_b
            else:
                winner, loser = rel_b, rel_a
            action_taken = "kept_winner"
            
        elif strategy == ResolutionStrategy.STRONGEST:
            # Mais forte ganha
            if rel_a.strength >= rel_b.strength:
                winner, loser = rel_a, rel_b
            else:
                winner, loser = rel_b, rel_a
            action_taken = "kept_winner"
            
        elif strategy == ResolutionStrategy.MOST_REINFORCED:
            # Mais reforçada ganha
            if rel_a.reinforced_count >= rel_b.reinforced_count:
                winner, loser = rel_a, rel_b
            else:
                winner, loser = rel_b, rel_a
            action_taken = "kept_winner"
            
        elif strategy == ResolutionStrategy.ASK_USER:
            # Pergunta ao usuário
            if self.on_ask_user:
                winner = self.on_ask_user(contradiction)
                loser = rel_b if winner == rel_a else rel_a
                action_taken = "asked_user"
            else:
                # Fallback para MOST_RECENT se não há callback
                if rel_a.created_at >= rel_b.created_at:
                    winner, loser = rel_a, rel_b
                else:
                    winner, loser = rel_b, rel_a
                action_taken = "fallback_most_recent"
                
        elif strategy == ResolutionStrategy.KEEP_BOTH:
            # Mantém ambas (marca como conflito)
            winner = None
            loser = None
            action_taken = "marked_conflict"
        
        # Atualizar estado da contradição
        contradiction.resolved = True
        contradiction.resolution = strategy
        contradiction.winner_id = winner.id if winner else None
        
        return ResolutionResult(
            contradiction=contradiction,
            strategy_used=strategy,
            winner=winner,
            loser=loser,
            action_taken=action_taken,
        )
    
    def get_history(self) -> list[Contradiction]:
        """Retorna histórico de contradições detectadas."""
        return self._history.copy()
    
    def get_unresolved(self) -> list[Contradiction]:
        """Retorna contradições não resolvidas."""
        return [c for c in self._history if not c.resolved]
    
    def clear_history(self) -> None:
        """Limpa o histórico."""
        self._history.clear()
    
    def stats(self) -> dict[str, Any]:
        """Retorna estatísticas."""
        total = len(self._history)
        resolved = sum(1 for c in self._history if c.resolved)
        
        return {
            "total_detected": total,
            "resolved": resolved,
            "pending": total - resolved,
            "resolution_breakdown": self._resolution_breakdown(),
        }
    
    def _resolution_breakdown(self) -> dict[str, int]:
        """Contagem por tipo de resolução."""
        breakdown: dict[str, int] = {}
        for c in self._history:
            if c.resolution:
                key = c.resolution.value
                breakdown[key] = breakdown.get(key, 0) + 1
        return breakdown


def create_default_detector() -> ContradictionDetector:
    """
    Cria detector com configuração padrão.
    
    Usa MOST_RECENT como estratégia (informação mais nova prevalece).
    """
    return ContradictionDetector(strategy=ResolutionStrategy.MOST_RECENT)


def create_conservative_detector() -> ContradictionDetector:
    """
    Cria detector conservador.
    
    Usa MOST_REINFORCED (informação mais confirmada prevalece).
    Bom para memórias de longo prazo onde repetição = confiança.
    """
    return ContradictionDetector(strategy=ResolutionStrategy.MOST_REINFORCED)


def create_strict_detector() -> ContradictionDetector:
    """
    Cria detector estrito.
    
    Usa STRONGEST (relações mais fortes prevalecem).
    Bom para informações críticas onde força = importância.
    """
    return ContradictionDetector(strategy=ResolutionStrategy.STRONGEST)
