"""Tests for Cortex v5 core data structures."""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add cortex_v5 to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "cortex-v5"))

from cortex_v5.core.memory import Memory, _tokenize
from cortex_v5.core.entity import Entity
from cortex_v5.core.relation import Relation, RelationType
from cortex_v5.core.graph import MemoryGraph, RecallResult


class TestMemory:
    """Tests for the Memory dataclass (W5H)."""

    def test_create_minimal_memory(self):
        """Only 'what' is required."""
        m = Memory(what="Maria ligou")
        assert m.what == "Maria ligou"
        assert m.who == []
        assert m.where == "default"
        assert m.id is not None

    def test_create_full_w5h_memory(self):
        """All 6 W5H fields."""
        m = Memory(
            who=["Maria", "sistema"],
            what="reportou erro",
            why="cartão expirado",
            when=datetime(2026, 3, 22),
            where="suporte",
            how="orientada a atualizar",
        )
        assert m.who == ["Maria", "sistema"]
        assert m.what == "reportou erro"
        assert m.why == "cartão expirado"
        assert m.where == "suporte"
        assert m.how == "orientada a atualizar"

    def test_empty_what_raises(self):
        """Schema enforcement: 'what' cannot be empty."""
        with pytest.raises(ValueError, match="'what' field is required"):
            Memory(what="")

    def test_whitespace_only_what_raises(self):
        """Whitespace-only 'what' is treated as empty."""
        with pytest.raises(ValueError, match="'what' field is required"):
            Memory(what="   ")

    def test_importance_range_enforced(self):
        """importance must be 0.0-1.0."""
        with pytest.raises(ValueError, match="importance must be"):
            Memory(what="x", importance=1.5)

    def test_who_normalized(self):
        """who is stripped of empty entries."""
        m = Memory(who=["Maria", "", "  ", "João"], what="x")
        assert m.who == ["Maria", "João"]

    def test_touch_increments_access(self):
        """touch() bumps access_count and updates timestamp."""
        m = Memory(what="x")
        assert m.access_count == 0
        m.touch()
        assert m.access_count == 1
        assert m.last_accessed is not None
        m.touch()
        assert m.access_count == 2

    def test_is_about(self):
        """is_about checks substring match in who list."""
        m = Memory(who=["Maria Silva", "João"], what="x")
        assert m.is_about("Maria") is True
        assert m.is_about("maria") is True  # case-insensitive
        assert m.is_about("João") is True
        assert m.is_about("Pedro") is False

    def test_matches_text_token_jaccard(self):
        """matches_text uses token overlap (language-agnostic)."""
        m = Memory(what="Maria reportou erro de pagamento", who=["Maria"])
        # PT query
        assert m.matches_text("Maria reportou erro") > 0.5
        # EN query - same semantics, partial overlap
        assert m.matches_text("Maria reported error") > 0
        # Unrelated
        assert m.matches_text("João comprou pizza") < 0.1

    def test_to_dict_from_dict_roundtrip(self):
        """Serialization is lossless."""
        m = Memory(
            who=["Maria"],
            what="comprou algo",
            why="preço bom",
            where="loja",
            how="cartão de crédito",
            importance=0.7,
        )
        d = m.to_dict()
        m2 = Memory.from_dict(d)
        assert m2.who == m.who
        assert m2.what == m.what
        assert m2.why == m.why
        assert m2.where == m.where
        assert m2.how == m.how
        assert m2.importance == m.importance

    def test_equality_by_id(self):
        """Two memories with same id are equal."""
        m1 = Memory(id="abc", what="x")
        m2 = Memory(id="abc", what="y")
        assert m1 == m2

    def test_tokenize_removes_stopwords(self):
        """_tokenize strips PT/EN stopwords and short tokens."""
        tokens = _tokenize("O usuário fez login no sistema")
        assert "o" not in tokens
        assert "no" not in tokens
        assert "usuário" in tokens or "fez" in tokens or "login" in tokens or "sistema" in tokens


class TestEntity:
    """Tests for the Entity dataclass."""

    def test_create_entity(self):
        e = Entity(type="person", name="Maria", identifiers=["maria@email.com"])
        assert e.type == "person"
        assert e.name == "Maria"
        assert "maria@email.com" in e.identifiers

    def test_empty_type_raises(self):
        with pytest.raises(ValueError, match="Entity 'type' is required"):
            Entity(type="", name="Maria")

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="Entity 'name' is required"):
            Entity(type="person", name="")

    def test_matches_by_id(self):
        e = Entity(type="person", name="Maria")
        assert e.matches(e.id) is True
        assert e.matches("maria") is True  # case-insensitive
        assert e.matches("João") is False

    def test_matches_by_identifier(self):
        e = Entity(type="person", name="Maria", identifiers=["maria@x.com"])
        assert e.matches("maria@x.com") is True
        assert e.matches("MARIA@X.COM") is True

    def test_to_dict_from_dict_roundtrip(self):
        e = Entity(type="file", name="test.py", identifiers=["sha256:abc"], attributes={"size": 1024})
        d = e.to_dict()
        e2 = Entity.from_dict(d)
        assert e2.type == e.type
        assert e2.name == e.name
        assert e2.identifiers == e.identifiers
        assert e2.attributes == e.attributes


class TestRelation:
    """Tests for the Relation dataclass."""

    def test_create_relation(self):
        r = Relation(
            from_id="maria",
            relation_type=RelationType.PREFERS,
            to_id="pizza",
            polarity=1.0,
        )
        assert r.relation_type == "prefers"
        assert r.is_positive() is True

    def test_polarity_normalized_lowercase(self):
        """relation_type is lowercased."""
        r = Relation(from_id="a", relation_type="LOVES", to_id="b")
        assert r.relation_type == "loves"

    def test_contradicts(self):
        """Same triple, opposite polarities = contradiction."""
        r1 = Relation(from_id="a", relation_type="likes", to_id="b", polarity=1.0)
        r2 = Relation(from_id="a", relation_type="likes", to_id="b", polarity=-1.0)
        assert r1.contradicts(r2) is True
        assert r2.contradicts(r1) is True

    def test_no_contradiction_same_polarity(self):
        """Same triple, same polarities = no contradiction."""
        r1 = Relation(from_id="a", relation_type="likes", to_id="b", polarity=1.0)
        r2 = Relation(from_id="a", relation_type="likes", to_id="b", polarity=0.5)
        assert r1.contradicts(r2) is False

    def test_no_contradiction_different_triples(self):
        """Different triples don't contradict even with opposite polarities."""
        r1 = Relation(from_id="a", relation_type="likes", to_id="b", polarity=1.0)
        r2 = Relation(from_id="a", relation_type="likes", to_id="c", polarity=-1.0)
        assert r1.contradicts(r2) is False

    def test_strength_range_enforced(self):
        with pytest.raises(ValueError, match="strength must be"):
            Relation(from_id="a", relation_type="x", to_id="b", strength=2.0)

    def test_polarity_range_enforced(self):
        with pytest.raises(ValueError, match="polarity must be"):
            Relation(from_id="a", relation_type="x", to_id="b", polarity=-2.0)


class TestMemoryGraph:
    """Tests for the MemoryGraph."""

    def test_create_empty_graph(self):
        g = MemoryGraph(namespace="test")
        assert g.namespace == "test"
        assert len(g) == 0
        assert g.stats()["total_memories"] == 0

    def test_add_and_get_memory(self):
        g = MemoryGraph()
        m = Memory(what="test")
        g.add_memory(m)
        assert g.get_memory(m.id) is m
        assert len(g) == 1

    def test_add_and_get_entity(self):
        g = MemoryGraph()
        e = Entity(type="person", name="Maria")
        g.add_entity(e)
        assert g.get_entity(e.id) is e

    def test_add_and_get_relation(self):
        g = MemoryGraph()
        r = Relation(from_id="a", relation_type="likes", to_id="b")
        g.add_relation(r)
        assert g.get_relation(r.id) is r

    def test_find_memories_by_who(self):
        g = MemoryGraph()
        m1 = Memory(who=["Maria"], what="comprou")
        m2 = Memory(who=["João"], what="vendeu")
        m3 = Memory(who=["Maria Silva"], what="viajou")
        g.add_memory(m1)
        g.add_memory(m2)
        g.add_memory(m3)
        results = g.find_memories(who="Maria")
        # m1 and m3 (substring match)
        assert len(results) == 2
        assert m1 in results
        assert m3 in results

    def test_find_memories_by_where(self):
        g = MemoryGraph()
        m1 = Memory(what="a", where="suporte")
        m2 = Memory(what="b", where="vendas")
        g.add_memory(m1)
        g.add_memory(m2)
        assert g.find_memories(where="suporte") == [m1]
        assert g.find_memories(where="vendas") == [m2]

    def test_find_memories_by_what_contains(self):
        g = MemoryGraph()
        g.add_memory(Memory(what="Maria reportou erro"))
        g.add_memory(Memory(what="João viajou"))
        results = g.find_memories(what_contains="reportou")
        assert len(results) == 1
        assert "reportou" in results[0].what

    def test_find_entities_by_name(self):
        g = MemoryGraph()
        e1 = Entity(type="person", name="Maria")
        e2 = Entity(type="person", name="João")
        g.add_entity(e1)
        g.add_entity(e2)
        assert g.find_entities_by_name("Maria") == [e1]
        # Case-insensitive
        assert g.find_entities_by_name("maria") == [e1]
        assert g.find_entities_by_name("MARIA") == [e1]

    def test_find_relations(self):
        g = MemoryGraph()
        r1 = Relation(from_id="a", relation_type="likes", to_id="b")
        r2 = Relation(from_id="a", relation_type="knows", to_id="c")
        r3 = Relation(from_id="b", relation_type="likes", to_id="c")
        g.add_relation(r1)
        g.add_relation(r2)
        g.add_relation(r3)
        assert g.find_relations(from_id="a") == [r1, r2]
        assert g.find_relations(to_id="c") == [r2, r3]
        assert g.find_relations(relation_type="likes") == [r1, r3]

    def test_stats(self):
        g = MemoryGraph(namespace="myapp")
        g.add_memory(Memory(what="a"))
        g.add_memory(Memory(what="b"))
        g.add_entity(Entity(type="p", name="Maria"))
        g.add_relation(Relation(from_id="a", relation_type="x", to_id="b"))
        stats = g.stats()
        assert stats["namespace"] == "myapp"
        assert stats["total_memories"] == 2
        assert stats["total_entities"] == 1
        assert stats["total_relations"] == 1

    def test_iteration(self):
        g = MemoryGraph()
        m1 = Memory(what="a")
        m2 = Memory(what="b")
        g.add_memory(m1)
        g.add_memory(m2)
        all_mems = list(g.iter_memories())
        assert m1 in all_mems
        assert m2 in all_mems
        assert len(g.all_memories()) == 2

    def test_add_wrong_type_raises(self):
        g = MemoryGraph()
        with pytest.raises(TypeError, match="expected Memory"):
            g.add_memory("not a memory")

    def test_recall_result_empty(self):
        result = RecallResult()
        assert result.is_empty() is True
        assert len(result) == 0

    def test_recall_result_with_memories(self):
        m1 = Memory(what="a")
        m2 = Memory(what="b")
        result = RecallResult(memories=[m1, m2])
        assert result.is_empty() is False
        assert len(result) == 2
