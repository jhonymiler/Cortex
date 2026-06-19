"""
Relation — typed connection between entities or memories.

Relations are language-agnostic. The `relation_type` is a string tag
(you define your own vocabulary) — values stored in attributes can
be in any language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


class RelationType:
    """Suggested relation types. Free-form strings are also accepted."""

    # Causal
    CAUSED_BY = "caused_by"
    ENABLED = "enabled"
    PREVENTED = "prevented"
    TRIGGERED = "triggered"

    # Dependency
    REQUIRES = "requires"
    DEPENDS_ON = "depends_on"
    BLOCKS = "blocks"

    # Composition
    PART_OF = "part_of"
    CONTAINS = "contains"
    BELONGS_TO = "belongs_to"

    # Associative
    RELATED_TO = "related_to"
    SIMILAR_TO = "similar_to"
    OPPOSITE_OF = "opposite_of"

    # Affinity
    PREFERS = "prefers"
    DISLIKES = "dislikes"

    # Temporal
    FOLLOWED_BY = "followed_by"
    PRECEDED_BY = "preceded_by"
    CONCURRENT_WITH = "concurrent_with"


@dataclass
class Relation:
    """
    A typed connection between two entities or memories.

    Attributes:
        from_id: source ID (Entity or Memory)
        relation_type: string tag (use RelationType constants or custom)
        to_id: target ID
        strength: 0.0-1.0, decays over time without reinforcement
        polarity: -1.0 to +1.0, can be negative/positive/neutral
        attributes: free-form metadata (e.g., value text in any language)
    """

    from_id: str
    relation_type: str
    to_id: str
    strength: float = 0.5
    polarity: float = 1.0
    attributes: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.from_id or not self.to_id:
            raise ValueError("Relation requires both from_id and to_id")
        if not self.relation_type or not self.relation_type.strip():
            raise ValueError("Relation requires a non-empty relation_type")
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength must be in [0.0, 1.0], got {self.strength}")
        if not -1.0 <= self.polarity <= 1.0:
            raise ValueError(f"polarity must be in [-1.0, 1.0], got {self.polarity}")
        self.relation_type = self.relation_type.strip().lower()

    def contradicts(self, other: "Relation") -> bool:
        """Check if this relation contradicts another (same triple, opposite polarity)."""
        if (
            self.from_id == other.from_id
            and self.to_id == other.to_id
            and self.relation_type == other.relation_type
        ):
            # Opposite polarities = contradiction
            if (self.polarity > 0 and other.polarity < 0) or (self.polarity < 0 and other.polarity > 0):
                return True
        return False

    def is_positive(self) -> bool:
        return self.polarity > 0.3

    def is_negative(self) -> bool:
        return self.polarity < -0.3

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_id": self.from_id,
            "relation_type": self.relation_type,
            "to_id": self.to_id,
            "strength": self.strength,
            "polarity": self.polarity,
            "attributes": dict(self.attributes),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Relation":
        return cls(
            id=data.get("id", str(uuid4())),
            from_id=data.get("from_id", ""),
            relation_type=data.get("relation_type", ""),
            to_id=data.get("to_id", ""),
            strength=data.get("strength", 0.5),
            polarity=data.get("polarity", 1.0),
            attributes=data.get("attributes", {}),
        )

    def __repr__(self) -> str:
        pol = "+" if self.polarity > 0 else "-" if self.polarity < 0 else "~"
        return f"Relation({self.from_id[:6]} -{pol}{self.relation_type}-> {self.to_id[:6]})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Relation):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
