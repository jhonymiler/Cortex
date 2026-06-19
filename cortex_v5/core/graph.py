"""
MemoryGraph — collection of memories, entities, and relations.

Enxuto, sem feature flags, sem BFS/Louvain/PageRank. Operations are
O(1) for direct lookup, O(n) for scans. The Dream Agent (background
worker) handles consolidation separately.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from cortex_v5.core.memory import Memory
from cortex_v5.core.entity import Entity
from cortex_v5.core.relation import Relation


@dataclass
class RecallResult:
    """Result of a memory recall operation."""

    memories: list[Memory] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.memories)

    def is_empty(self) -> bool:
        return len(self.memories) == 0 and len(self.entities) == 0 and len(self.relations) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "memories": [m.to_dict() for m in self.memories],
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "metrics": self.metrics,
        }


class MemoryGraph:
    """
    In-memory graph of memories, entities, and relations.

    API enxuto: 5 métodos públicos (add_memory, add_entity, add_relation,
    get_*, iter_*) + 1 busca livre (find). Sem indexação sofisticada
    (sem inverted index, sem BFS expansion). Dream Agent pode adicionar
    indexação opcional se necessário.
    """

    def __init__(self, namespace: str = "default") -> None:
        """Initialize an in-memory graph (no persistence in v5 core)."""
        self.namespace = namespace
        self._memories: dict[str, Memory] = {}
        self._entities: dict[str, Entity] = {}
        self._relations: dict[str, Relation] = {}

    # === Add operations ===

    def add_memory(self, memory: Memory) -> Memory:
        """Add a memory. Returns the memory (with id)."""
        if not isinstance(memory, Memory):
            raise TypeError(f"expected Memory, got {type(memory).__name__}")
        self._memories[memory.id] = memory
        return memory

    def add_entity(self, entity: Entity) -> Entity:
        """Add an entity. Returns the entity (with id)."""
        if not isinstance(entity, Entity):
            raise TypeError(f"expected Entity, got {type(entity).__name__}")
        self._entities[entity.id] = entity
        return entity

    def add_relation(self, relation: Relation) -> Relation:
        """Add a relation. Returns the relation (with id)."""
        if not isinstance(relation, Relation):
            raise TypeError(f"expected Relation, got {type(relation).__name__}")
        self._relations[relation.id] = relation
        return relation

    # === Get operations ===

    def get_memory(self, memory_id: str) -> Optional[Memory]:
        return self._memories.get(memory_id)

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        return self._entities.get(entity_id)

    def get_relation(self, relation_id: str) -> Optional[Relation]:
        return self._relations.get(relation_id)

    # === Iteration ===

    def iter_memories(self) -> Iterator[Memory]:
        return iter(self._memories.values())

    def iter_entities(self) -> Iterator[Entity]:
        return iter(self._entities.values())

    def iter_relations(self) -> Iterator[Relation]:
        return iter(self._relations.values())

    def all_memories(self) -> list[Memory]:
        return list(self._memories.values())

    def all_entities(self) -> list[Entity]:
        return list(self._entities.values())

    def all_relations(self) -> list[Relation]:
        return list(self._relations.values())

    # === Find operations ===

    def find_memories(
        self,
        who: Optional[str] = None,
        where: Optional[str] = None,
        what_contains: Optional[str] = None,
    ) -> list[Memory]:
        """
        Find memories matching filters. O(n) scan.

        Args:
            who: filter by participant (case-insensitive substring)
            where: filter by namespace/exact match
            what_contains: filter by substring in 'what' field
        """
        results: list[Memory] = []
        for mem in self._memories.values():
            if who is not None and not mem.is_about(who):
                continue
            if where is not None and mem.where != where:
                continue
            if what_contains is not None and what_contains.lower() not in mem.what.lower():
                continue
            results.append(mem)
        return results

    def find_entities_by_name(self, name: str) -> list[Entity]:
        """Find entities by name (case-insensitive exact match)."""
        name_lower = name.lower()
        return [e for e in self._entities.values() if e.name.lower() == name_lower]

    def find_relations(
        self,
        from_id: Optional[str] = None,
        to_id: Optional[str] = None,
        relation_type: Optional[str] = None,
    ) -> list[Relation]:
        """Find relations matching filters. O(n) scan."""
        results: list[Relation] = []
        for rel in self._relations.values():
            if from_id is not None and rel.from_id != from_id:
                continue
            if to_id is not None and rel.to_id != to_id:
                continue
            if relation_type is not None and rel.relation_type != relation_type.lower():
                continue
            results.append(rel)
        return results

    # === Persistence ===

    def to_dict(self) -> dict[str, Any]:
        """Serialize the whole graph to a plain dict (JSON-ready)."""
        return {
            "namespace": self.namespace,
            "memories": [m.to_dict() for m in self._memories.values()],
            "entities": [e.to_dict() for e in self._entities.values()],
            "relations": [r.to_dict() for r in self._relations.values()],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryGraph":
        """Reconstruct a graph from a dict produced by ``to_dict``."""
        graph = cls(namespace=data.get("namespace", "default"))
        for m in data.get("memories", []):
            graph.add_memory(Memory.from_dict(m))
        for e in data.get("entities", []):
            graph.add_entity(Entity.from_dict(e))
        for r in data.get("relations", []):
            graph.add_relation(Relation.from_dict(r))
        return graph

    def save(self, path: Any) -> None:
        """Persist the graph to a JSON file at ``path`` (atomic write)."""
        import json
        import os
        from pathlib import Path

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, default=str)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: Any, namespace: str = "default") -> "MemoryGraph":
        """Load a graph from a JSON file. Returns an empty graph if missing."""
        import json
        from pathlib import Path

        path = Path(path)
        if not path.exists():
            return cls(namespace=namespace)
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    # === Stats ===

    def stats(self) -> dict[str, Any]:
        return {
            "namespace": self.namespace,
            "total_memories": len(self._memories),
            "total_entities": len(self._entities),
            "total_relations": len(self._relations),
        }

    def __len__(self) -> int:
        return len(self._memories)

    def __repr__(self) -> str:
        return f"MemoryGraph(ns={self.namespace!r}, M={len(self._memories)}, E={len(self._entities)}, R={len(self._relations)})"
