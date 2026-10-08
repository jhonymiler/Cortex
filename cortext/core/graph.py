"""
MemoryGraph — memories, entities and relations, with inverted indexes.

Every lookup the hot path needs is served from an index, never from a scan:

  token  -> memory ids   (content tokens of what/why/how/who/where)
  who    -> memory ids   (lowercased participant name)
  where  -> memory ids
  entity name -> entity ids
  node id -> relation ids (both directions)

The memory table is a dict subclass that keeps the indexes in sync, so code
that writes ``graph._memories[id] = m`` directly (older callers, tests) stays
correct. The graph also records which memories changed since the last flush
(``drain_changes``), which is what lets a store persist incrementally instead
of rewriting everything on each write.

Entities and memories form a bipartite graph through ``who``: two memories are
neighbours when they share a participant (``neighbors``).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Optional

from cortext.core.entity import Entity
from cortext.core.memory import Memory
from cortext.core.relation import Relation
from cortext.core.text import fold, tokenize


@dataclass
class RecallResult:
    """Result of a memory recall operation."""

    memories: list[Memory] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    intent: Any = None  # the QueryIntent the parser extracted (object, not dict)

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


def _add(index: dict[str, set[str]], key: str, mid: str) -> None:
    bucket = index.get(key)
    if bucket is None:
        index[key] = {mid}
    else:
        bucket.add(mid)


def _discard(index: dict[str, set[str]], key: str, mid: str) -> None:
    bucket = index.get(key)
    if bucket is not None:
        bucket.discard(mid)
        if not bucket:
            del index[key]


class _MemoryTable(dict):
    """dict of id -> Memory that maintains the owning graph's indexes."""

    __slots__ = ("_graph",)

    def __init__(self, graph: "MemoryGraph") -> None:
        super().__init__()
        self._graph = graph

    def __setitem__(self, key: str, memory: Memory) -> None:
        old = dict.get(self, key)
        if old is not None:
            self._graph._unindex(key)
        dict.__setitem__(self, key, memory)
        self._graph._index(key, memory)

    def __delitem__(self, key: str) -> None:
        dict.__delitem__(self, key)
        self._graph._unindex(key)
        self._graph._deleted.add(key)

    def pop(self, key: str, *default: Any) -> Any:
        if key in self:
            value = dict.pop(self, key)
            self._graph._unindex(key)
            self._graph._deleted.add(key)
            return value
        if default:
            return default[0]
        raise KeyError(key)

    def popitem(self) -> tuple[str, Memory]:
        key, value = dict.popitem(self)
        self._graph._unindex(key)
        self._graph._deleted.add(key)
        return key, value

    def clear(self) -> None:
        for key in list(self.keys()):
            self.pop(key)

    def update(self, *args: Any, **kwargs: Any) -> None:
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def setdefault(self, key: str, default: Memory = None) -> Memory:  # type: ignore[assignment]
        if key not in self:
            self[key] = default
        return dict.__getitem__(self, key)


class _EntityTable(dict):
    """dict of id -> Entity that maintains the owning graph's name index."""

    __slots__ = ("_graph",)

    def __init__(self, graph: "MemoryGraph") -> None:
        super().__init__()
        self._graph = graph

    def __setitem__(self, key: str, entity: Entity) -> None:
        old = dict.get(self, key)
        if old is not None:
            _discard(self._graph._entity_by_name, fold(old.name), key)
        dict.__setitem__(self, key, entity)
        _add(self._graph._entity_by_name, fold(entity.name), key)
        self._graph._touch_other("entity", key)

    def __delitem__(self, key: str) -> None:
        old = dict.pop(self, key)
        _discard(self._graph._entity_by_name, fold(old.name), key)
        self._graph._touch_other("entity", key, deleted=True)

    def pop(self, key: str, *default: Any) -> Any:
        if key in self:
            old = dict.__getitem__(self, key)
            del self[key]
            return old
        if default:
            return default[0]
        raise KeyError(key)


class MemoryGraph:
    """In-memory graph of memories, entities and relations, fully indexed."""

    def __init__(self, namespace: str = "default") -> None:
        self.namespace = namespace
        # Inverted indexes (memory side)
        self._tok: dict[str, set[str]] = {}
        self._who: dict[str, set[str]] = {}
        self._where: dict[str, set[str]] = {}
        self._nowho: set[str] = set()
        self._indexed: dict[str, tuple[frozenset[str], tuple[str, ...], str]] = {}
        # Change tracking for incremental persistence
        self._dirty: set[str] = set()
        self._deleted: set[str] = set()
        self._other_changes: dict[tuple[str, str], bool] = {}  # (kind, id) -> deleted?
        self._version = 0
        # Tables
        self._memories: _MemoryTable = _MemoryTable(self)
        self._entity_by_name: dict[str, set[str]] = {}
        self._entities: _EntityTable = _EntityTable(self)
        self._relations: dict[str, Relation] = {}
        self._rel_by_node: dict[str, dict[str, None]] = {}  # ordered: insertion order
        self.lock = threading.RLock()

    # === Index maintenance ===

    def _index(self, mid: str, memory: Memory) -> None:
        tokens = memory.index_tokens()
        who = tuple(fold(w) for w in (memory.who or ()))
        where = memory.where or "default"
        tok = self._tok
        for t in tokens:  # inlined _add: this loop runs once per token of every load
            bucket = tok.get(t)
            if bucket is None:
                tok[t] = {mid}
            else:
                bucket.add(mid)
        for w in who:
            _add(self._who, w, mid)
        if not who:
            self._nowho.add(mid)
        _add(self._where, where, mid)
        self._indexed[mid] = (tokens, who, where)
        self._dirty.add(mid)
        self._deleted.discard(mid)
        self._version += 1

    def _unindex(self, mid: str) -> None:
        entry = self._indexed.pop(mid, None)
        if entry is None:
            return
        tokens, who, where = entry
        for t in tokens:
            _discard(self._tok, t, mid)
        for w in who:
            _discard(self._who, w, mid)
        self._nowho.discard(mid)
        _discard(self._where, where, mid)
        self._dirty.discard(mid)
        self._version += 1

    def _touch_other(self, kind: str, oid: str, deleted: bool = False) -> None:
        self._other_changes[(kind, oid)] = deleted
        self._version += 1

    def reindex(self, memory: Memory) -> None:
        """Re-index a memory after its W5H fields were edited in place."""
        if memory.id in self._memories:
            self._unindex(memory.id)
            self._index(memory.id, memory)

    def mark_dirty(self, memories: Iterable[Memory] | Memory) -> None:
        """Flag memories whose metadata changed (access, importance, merge)."""
        if isinstance(memories, Memory):
            memories = (memories,)
        for m in memories:
            if m.id in self._memories:
                self._dirty.add(m.id)
        self._version += 1

    def mark_all_dirty(self) -> None:
        self._dirty.update(self._memories.keys())
        self._version += 1

    def drain_changes(self) -> tuple[list[Memory], list[str]]:
        """Return (changed memories, deleted ids) since the last drain, and reset."""
        changed = [self._memories[i] for i in self._dirty if i in self._memories]
        deleted = list(self._deleted)
        self._dirty.clear()
        self._deleted.clear()
        return changed, deleted

    def drain_all_changes(self) -> dict[str, Any]:
        """Like drain_changes, plus entity and relation upserts/deletes."""
        memories, deleted = self.drain_changes()
        out: dict[str, Any] = {
            "memories": memories, "deleted_memories": deleted,
            "entities": [], "deleted_entities": [],
            "relations": [], "deleted_relations": [],
        }
        tables = {"entity": (self._entities, "entities"), "relation": (self._relations, "relations")}
        for (kind, oid), gone in self._other_changes.items():
            table, key = tables[kind]
            if gone or oid not in table:
                out["deleted_" + key].append(oid)
            else:
                out[key].append(table[oid])
        self._other_changes.clear()
        return out

    @property
    def version(self) -> int:
        """Monotonic counter bumped on every mutation (cheap change detection)."""
        return self._version

    # === Add / remove ===

    def add_memory(self, memory: Memory) -> Memory:
        """Add (or replace) a memory. Returns the memory."""
        if not isinstance(memory, Memory):
            raise TypeError(f"expected Memory, got {type(memory).__name__}")
        self._memories[memory.id] = memory
        return memory

    def remove_memory(self, memory_id: str) -> Optional[Memory]:
        """Remove a memory and the relations touching it. Returns it, or None."""
        memory = self._memories.pop(memory_id, None)
        if memory is not None:
            for rid in list(self._rel_by_node.get(memory_id, ())):
                self.remove_relation(rid)
        return memory

    def add_entity(self, entity: Entity) -> Entity:
        """Add an entity. Returns the entity."""
        if not isinstance(entity, Entity):
            raise TypeError(f"expected Entity, got {type(entity).__name__}")
        self._entities[entity.id] = entity
        return entity

    def add_relation(self, relation: Relation) -> Relation:
        """Add a relation. Returns the relation."""
        if not isinstance(relation, Relation):
            raise TypeError(f"expected Relation, got {type(relation).__name__}")
        self._relations[relation.id] = relation
        self._rel_by_node.setdefault(relation.from_id, {})[relation.id] = None
        self._rel_by_node.setdefault(relation.to_id, {})[relation.id] = None
        self._touch_other("relation", relation.id)
        return relation

    def remove_relation(self, relation_id: str) -> Optional[Relation]:
        rel = self._relations.pop(relation_id, None)
        if rel is not None:
            for node in (rel.from_id, rel.to_id):
                adj = self._rel_by_node.get(node)
                if adj is not None:
                    adj.pop(rel.id, None)
                    if not adj:
                        del self._rel_by_node[node]
            self._touch_other("relation", rel.id, deleted=True)
        return rel

    # === Get ===

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

    # === Index queries (the hot path) ===

    def ids_for_token(self, token: str) -> set[str]:
        """Memory ids whose content holds ``token`` (already folded)."""
        return self._tok.get(token, set())

    def ids_for_tokens(self, tokens: Iterable[str], prefix: bool = False) -> set[str]:
        """Union of memory ids holding any of ``tokens``.

        With ``prefix``, a token absent from the vocabulary also matches the
        vocabulary entries it is a prefix of ("reemb" -> "reembolso"), which
        keeps abbreviation tolerance without a scan over memories.
        """
        out: set[str] = set()
        for t in tokens:
            hit = self._tok.get(t)
            if hit:
                out |= hit
            elif prefix and len(t) >= 3:
                for vocab, ids in self._tok.items():
                    if vocab.startswith(t):
                        out |= ids
        return out

    def ids_for_who(self, name: str) -> set[str]:
        """Memory ids whose participants match ``name`` (exact or by word)."""
        key = fold(name.strip())
        if not key:
            return set()
        out = set(self._who.get(key, ()))
        # "Maria" should reach "Maria Silva": match on the name's tokens, then
        # confirm against the participant list.
        name_tokens = tokenize(name)
        if name_tokens:
            pool: Optional[set[str]] = None
            for t in name_tokens:
                ids = self._tok.get(t, set())
                pool = set(ids) if pool is None else pool & ids
                if not pool:
                    break
            for mid in pool or ():
                if mid not in out and self._memories[mid].is_about(name):
                    out.add(mid)
        return out

    def ids_for_exact_who(self, names: Iterable[str]) -> set[str]:
        """Memory ids having any of ``names`` as a participant (whole-name match)."""
        out: set[str] = set()
        for n in names:
            out |= self._who.get(fold(n.strip()), set())
        return out

    def filter_by_tokens(self, ids: Iterable[str], tokens: Iterable[str]) -> set[str]:
        """The ids in ``ids`` whose memory holds at least one of ``tokens``.

        The cheap side of an intersection: when ``ids`` is small and the
        tokens are common, checking each id beats materializing the postings.
        """
        wanted = tokens if isinstance(tokens, (set, frozenset)) else frozenset(tokens)
        indexed = self._indexed
        return {i for i in ids if i in indexed and not wanted.isdisjoint(indexed[i][0])}

    def postings_size(self, tokens: Iterable[str]) -> int:
        return sum(len(self._tok.get(t, ())) for t in tokens)

    def ids_without_who(self) -> set[str]:
        """Memory ids with no participants."""
        return self._nowho

    def ids_for_where(self, where: str) -> set[str]:
        return self._where.get(where, set())

    def document_frequency(self, token: str) -> int:
        return len(self._tok.get(token, ()))

    @property
    def vocabulary_size(self) -> int:
        return len(self._tok)

    def neighbors(self, memory: Memory, limit: int = 20) -> list[Memory]:
        """Memories sharing a participant with ``memory`` (1 hop on the entity graph)."""
        seen: set[str] = {memory.id}
        out: list[Memory] = []
        for w in memory.who or ():
            for mid in self._who.get(fold(w), ()):
                if mid not in seen:
                    seen.add(mid)
                    out.append(self._memories[mid])
                    if len(out) >= limit:
                        return out
        return out

    # === Find (filtered queries, served from indexes) ===

    def find_memories(
        self,
        who: Optional[str] = None,
        where: Optional[str] = None,
        what_contains: Optional[str] = None,
    ) -> list[Memory]:
        """Find memories matching all given filters.

        Args:
            who: participant (case-insensitive; matches by whole name or word)
            where: exact namespace/location
            what_contains: substring of ``what`` (case-insensitive)
        """
        pool: Optional[set[str]] = None
        if who is not None:
            # Index first; substring semantics of Memory.is_about as fallback
            # for partial names ("Mar" -> "Maria").
            pool = self.ids_for_who(who)
            if not pool:
                pool = {m.id for m in self._memories.values() if m.is_about(who)}
        if where is not None:
            ids = self._where.get(where, set())
            pool = set(ids) if pool is None else pool & ids
        if what_contains is not None:
            needle = what_contains.lower()
            tokens = tokenize(what_contains)
            if pool is None and tokens:
                pool = self.ids_for_tokens(tokens, prefix=True)
            source = (self._memories[i] for i in pool) if pool is not None else self._memories.values()
            return [m for m in source if needle in m.what.lower()]
        if pool is None:
            return list(self._memories.values())
        if len(pool) > len(self._memories) // 4:
            return [m for k, m in self._memories.items() if k in pool]  # insertion order
        return sorted((self._memories[i] for i in pool), key=lambda m: m.created_at)

    def find_entities_by_name(self, name: str) -> list[Entity]:
        """Find entities by name (case/accent-insensitive exact match)."""
        return [self._entities[i] for i in self._entity_by_name.get(fold(name), ())]

    def find_relations(
        self,
        from_id: Optional[str] = None,
        to_id: Optional[str] = None,
        relation_type: Optional[str] = None,
    ) -> list[Relation]:
        """Find relations matching filters (served from the node adjacency)."""
        anchor = from_id if from_id is not None else to_id
        if anchor is not None:
            source: Iterable[Relation] = (self._relations[r] for r in self._rel_by_node.get(anchor, ()))
        else:
            source = self._relations.values()
        rtype = relation_type.lower() if relation_type is not None else None
        return [
            r for r in source
            if (from_id is None or r.from_id == from_id)
            and (to_id is None or r.to_id == to_id)
            and (rtype is None or r.relation_type == rtype)
        ]

    # === Persistence (JSON snapshot; see cortext.store for incremental stores) ===

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
        graph.drain_all_changes()
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
        self.drain_changes()

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
            "vocabulary": len(self._tok),
            "participants": len(self._who),
        }

    def __len__(self) -> int:
        return len(self._memories)

    def __repr__(self) -> str:
        return f"MemoryGraph(ns={self.namespace!r}, M={len(self._memories)}, E={len(self._entities)}, R={len(self._relations)})"
