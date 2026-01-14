"""
Relation - Representa conexões entre entidades e episódios.

Relações formam o grafo de conhecimento:
- Conexões causais (caused_by, resolved_by, enabled)
- Conexões associativas (related_to, similar_to)
- Conexões semânticas (loves, hates, prefers)
- Conexões temporais (followed_by, preceded_by)

Polaridade:
- +1.0 = afirmativo ("Maria gosta de pizza")
- -1.0 = negativo ("Maria NÃO gosta de pizza")
- 0.0 = neutro/incerto
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4


@dataclass
class Relation:
    """
    Uma relação conecta duas coisas (entidades ou episódios).
    
    Relações são tipadas livremente pelo cliente:
    - "caused_by", "resolved_by" (causais)
    - "loves", "hates", "trusts" (afetivas)
    - "part_of", "contains" (composição)
    - "requires", "enables" (dependência)
    - "similar_to", "related_to" (associação)
    
    A força da relação (strength) é reforçada com o uso.
    A polaridade indica se é afirmativa (+1) ou negativa (-1).
    
    Attributes:
        id: Identificador único
        from_id: ID da origem (Entity ou Episode)
        relation_type: Tipo da relação (verbo livre)
        to_id: ID do destino (Entity ou Episode)
        strength: Força da conexão (0.0 - 1.0)
        polarity: Polaridade (-1.0 negativo, 0.0 neutro, +1.0 positivo)
        context: Metadados sobre quando/como foi criada
        created_at: Quando foi criada
        reinforced_count: Quantas vezes foi reforçada
        
    Examples:
        # Afirmativo (polarity=1.0)
        Relation(from_id="maria", relation_type="likes", to_id="pizza", polarity=1.0)
        
        # Negativo (polarity=-1.0)  
        Relation(from_id="maria", relation_type="likes", to_id="sushi", polarity=-1.0)
        # Significa: Maria NÃO gosta de sushi
        
        # Incerto (polarity próximo de 0)
        Relation(from_id="maria", relation_type="likes", to_id="pasta", polarity=0.3)
        # Significa: Maria talvez goste de pasta
    """
    
    from_id: str
    relation_type: str
    to_id: str
    strength: float = 0.5
    polarity: float = 1.0  # -1.0 a +1.0
    context: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    reinforced_count: int = 0
    
    def reinforce(self, amount: float = 0.1) -> None:
        """
        Reforça a relação (aumenta strength).
        
        Chamado quando a relação é usada/referenciada novamente.
        """
        self.strength = min(1.0, self.strength + amount)
        self.reinforced_count += 1
        self.updated_at = datetime.now()
    
    def decay(self, factor: float = 0.95) -> None:
        """
        Aplica decay temporal na relação.
        
        Relações não usadas enfraquecem com o tempo.
        """
        self.strength *= factor
        self.updated_at = datetime.now()
    
    def is_weak(self, threshold: float = 0.1) -> bool:
        """Retorna True se a relação está fraca (candidata a remoção)."""
        return self.strength < threshold
    
    def is_positive(self) -> bool:
        """Retorna True se a polaridade é positiva (> 0.3)."""
        return self.polarity > 0.3
    
    def is_negative(self) -> bool:
        """Retorna True se a polaridade é negativa (< -0.3)."""
        return self.polarity < -0.3
    
    def is_neutral(self) -> bool:
        """Retorna True se a polaridade é neutra/incerta (-0.3 a 0.3)."""
        return -0.3 <= self.polarity <= 0.3
    
    def contradicts(self, other: "Relation") -> bool:
        """
        Verifica se esta relação contradiz outra.
        
        Contradição ocorre quando:
        - Mesmo from_id, to_id e relation_type
        - Polaridades opostas (uma positiva, outra negativa)
        
        Args:
            other: Outra relação para comparar
            
        Returns:
            True se são contraditórias
        """
        if not self._same_triple(other):
            return False
        
        # Polaridades opostas = contradição
        return (self.is_positive() and other.is_negative()) or \
               (self.is_negative() and other.is_positive())
    
    def _same_triple(self, other: "Relation") -> bool:
        """Verifica se representa a mesma tripla (from, type, to)."""
        return (
            self.from_id == other.from_id and
            self.to_id == other.to_id and
            self.relation_type.lower() == other.relation_type.lower()
        )
    
    def matches(
        self,
        from_id: str | None = None,
        to_id: str | None = None,
        relation_type: str | None = None,
    ) -> bool:
        """
        Verifica se a relação corresponde aos filtros.
        
        Filtros None são ignorados.
        """
        if from_id is not None and self.from_id != from_id:
            return False
        if to_id is not None and self.to_id != to_id:
            return False
        if relation_type is not None and self.relation_type.lower() != relation_type.lower():
            return False
        return True
    
    def involves(self, entity_or_episode_id: str) -> bool:
        """Retorna True se a relação envolve o ID especificado."""
        return self.from_id == entity_or_episode_id or self.to_id == entity_or_episode_id
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa para dicionário."""
        return {
            "id": self.id,
            "from_id": self.from_id,
            "relation_type": self.relation_type,
            "to_id": self.to_id,
            "strength": self.strength,
            "polarity": self.polarity,
            "context": self.context,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "reinforced_count": self.reinforced_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Relation":
        """Deserializa de dicionário."""
        return cls(
            id=data["id"],
            from_id=data["from_id"],
            relation_type=data["relation_type"],
            to_id=data["to_id"],
            strength=data.get("strength", 0.5),
            polarity=data.get("polarity", 1.0),
            context=data.get("context", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            reinforced_count=data.get("reinforced_count", 0),
        )
    
    def to_triple(self) -> str:
        """Retorna representação como tripla: (from) -[type]-> (to)"""
        polarity_symbol = "+" if self.polarity > 0 else "-" if self.polarity < 0 else "~"
        return f"({self.from_id[:8]}) -[{polarity_symbol}{self.relation_type}]-> ({self.to_id[:8]})"
    
    def __repr__(self) -> str:
        return f"Relation({self.from_id[:8]}... -{self.relation_type}-> {self.to_id[:8]}..., strength={self.strength:.2f})"
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Relation):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        return hash(self.id)


# Tipos de relação comuns (sugestões, não obrigatórios)
class RelationTypes:
    """Tipos de relação comuns para referência."""
    
    # Causais
    CAUSED_BY = "caused_by"
    RESOLVED_BY = "resolved_by"
    ENABLED = "enabled"
    PREVENTED = "prevented"
    TRIGGERED = "triggered"
    
    # Dependência
    REQUIRES = "requires"
    DEPENDS_ON = "depends_on"
    BLOCKS = "blocks"
    
    # Composição
    PART_OF = "part_of"
    CONTAINS = "contains"
    BELONGS_TO = "belongs_to"
    
    # Associação
    RELATED_TO = "related_to"
    SIMILAR_TO = "similar_to"
    OPPOSITE_OF = "opposite_of"
    
    # Afetivas
    LOVES = "loves"
    HATES = "hates"
    TRUSTS = "trusts"
    FEARS = "fears"
    
    # Preferências
    PREFERS = "prefers"
    DISLIKES = "dislikes"
    
    # Temporais
    FOLLOWED_BY = "followed_by"
    PRECEDED_BY = "preceded_by"
    CONCURRENT_WITH = "concurrent_with"
