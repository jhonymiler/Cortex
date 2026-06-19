"""
Entity — represents a "thing" that can be referenced in memories.

Entities are language-agnostic. A person named "Maria" in PT and
"Maria" in EN is the same entity. The name is just a string.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class Entity:
    """
    A referenceable thing in the memory system.

    Attributes:
        type: type tag (e.g., "person", "place", "concept", "file")
        name: display name (in any language)
        identifiers: list of ways to identify this entity (emails, IDs, paths)
        attributes: free-form metadata
    """

    type: str
    name: str
    identifiers: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        if not self.type or not self.type.strip():
            raise ValueError("Entity 'type' is required")
        if not self.name or not self.name.strip():
            raise ValueError("Entity 'name' is required")
        self.type = self.type.strip()
        self.name = self.name.strip()

    def matches(self, query: str) -> bool:
        """Check if this entity matches a query (name, ID, or identifier)."""
        if not query:
            return False
        q = query.lower()
        if q == self.id or q == self.name.lower():
            return True
        if any(q in ident.lower() for ident in self.identifiers):
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "identifiers": list(self.identifiers),
            "attributes": dict(self.attributes),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entity":
        return cls(
            id=data.get("id", str(uuid4())),
            type=data.get("type", ""),
            name=data.get("name", ""),
            identifiers=data.get("identifiers", []),
            attributes=data.get("attributes", {}),
        )

    def __repr__(self) -> str:
        return f"Entity(type={self.type!r}, name={self.name!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
