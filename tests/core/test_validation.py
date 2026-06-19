"""
Tests for CanonicalValidator V2 (3-level NORMA detection).
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cortext.core.memory import Memory
from cortext.core.entity import Entity
from cortext.core.graph import MemoryGraph
from cortext.core.validation import (
    ValidationStatus,
    create_default_validator,
    create_strict_validator,
)


@pytest.fixture
def empty_graph():
    return MemoryGraph()


@pytest.fixture
def warn_validator():
    return create_default_validator()


@pytest.fixture
def strict_validator():
    return create_strict_validator()


def _add_memory(graph, memory):
    """Bypass any complex add methods — direct dict insertion."""
    graph._memories[memory.id] = memory
    return memory


def _add_entity(graph, entity):
    graph._entities[entity.id] = entity
    return entity


class TestSchemaCheck:
    """Schema enforcement (highest priority)."""

    def test_empty_what_blocked(self, empty_graph, strict_validator):
        with pytest.raises(ValueError):
            Memory(what="")  # __post_init__ raises

    def test_whitespace_what_blocked_at_construction(self, empty_graph):
        with pytest.raises(ValueError):
            Memory(what="   \n\t  ")

    def test_far_future_when_warns(self, empty_graph, warn_validator):
        from datetime import datetime
        m = Memory(who=["João"], what="algo", when=datetime(2300, 1, 1))
        result = warn_validator.validate_write(m, empty_graph)
        assert result.status == ValidationStatus.WARN
        assert "future" in result.reason.lower()

    def test_valid_memory_ok(self, empty_graph, warn_validator):
        m = Memory(who=["João"], what="comprou algo")
        result = warn_validator.validate_write(m, empty_graph)
        assert result.status == ValidationStatus.OK


class TestAmbiguityCheck:
    """Homonym detection (who-field matches multiple entities)."""

    def test_no_who_no_ambiguity(self, empty_graph, warn_validator):
        m = Memory(what="algo")
        result = warn_validator.validate_write(m, empty_graph)
        assert result.status == ValidationStatus.OK

    def test_homonym_warns(self, empty_graph, warn_validator):
        e1 = Entity(type="person", name="Carlos", identifiers=["carlos@a.com"])
        e2 = Entity(type="person", name="Carlos", identifiers=["carlos@b.com"])
        _add_entity(empty_graph, e1)
        _add_entity(empty_graph, e2)
        m = Memory(who=["Carlos"], what="pediu reunião")
        result = warn_validator.validate_write(m, empty_graph)
        assert result.status == ValidationStatus.WARN
        assert len(result.ambiguous_entities) == 2


class TestRedundancyCheck:
    """Near-duplicate detection (token Jaccard)."""

    def test_no_overlap_ok(self, empty_graph, warn_validator):
        existing = Memory(who=["João"], what="comprou pizza")
        _add_memory(empty_graph, existing)
        m = Memory(who=["Maria"], what="vendeu casa")
        result = warn_validator.validate_write(m, empty_graph)
        assert result.status == ValidationStatus.OK

    def test_high_similarity_warns(self, empty_graph, warn_validator):
        existing = Memory(who=["João"], what="solicitou reembolso do pedido 12345 ontem")
        _add_memory(empty_graph, existing)
        m = Memory(who=["João"], what="ontem solicitou reembolso do pedido 12345")
        result = warn_validator.validate_write(m, empty_graph)
        assert result.status == ValidationStatus.WARN
        assert result.similar_memory is not None


class TestContradictionCheck:
    """Heuristic + embedding contradiction detection (the key NORMA test)."""

    def test_negation_contradiction_pt(self, empty_graph, strict_validator):
        """PT: 'gosta' vs 'não gosta'."""
        existing = Memory(who=["Maria"], what="gosta de pizza", where="suporte")
        _add_memory(empty_graph, existing)
        m = Memory(who=["Maria"], what="não gosta de pizza", where="suporte")
        result = strict_validator.validate_write(m, empty_graph)
        assert result.status == ValidationStatus.BLOCKED
        assert result.conflicting_memory is not None
        assert result.detection_level == "heuristic"

    def test_negation_contradiction_en(self, empty_graph, strict_validator):
        """EN: 'loves' vs 'hates' — 'hates' has negation signal."""
        existing = Memory(who=["Maria"], what="loves pizza", where="home", lang="en")
        _add_memory(empty_graph, existing)
        m = Memory(who=["Maria"], what="hates pizza", where="home", lang="en")
        result = strict_validator.validate_write(m, empty_graph)
        assert result.status == ValidationStatus.BLOCKED
        assert result.detection_level == "heuristic"

    def test_negation_contradiction_es(self, empty_graph, strict_validator):
        """ES: 'gusta' vs 'odia' — 'odia' has negation signal."""
        existing = Memory(who=["Maria"], what="gusta pizza", where="casa", lang="es")
        _add_memory(empty_graph, existing)
        m = Memory(who=["Maria"], what="odia pizza", where="casa", lang="es")
        result = strict_validator.validate_write(m, empty_graph)
        assert result.status == ValidationStatus.BLOCKED
        assert result.detection_level == "heuristic"

    def test_no_contradiction_when_compatible(self, empty_graph, strict_validator):
        existing = Memory(who=["João"], what="gosta de pizza", where="suporte")
        _add_memory(empty_graph, existing)
        m = Memory(who=["João"], what="gosta de lasanha", where="suporte")
        result = strict_validator.validate_write(m, empty_graph)
        # No contradiction: same polarity, different content
        assert result.status == ValidationStatus.OK

    def test_contradiction_different_people_no_block(self, empty_graph, strict_validator):
        """Same negation, different people = not a contradiction."""
        existing = Memory(who=["Maria"], what="gosta de pizza", where="suporte")
        _add_memory(empty_graph, existing)
        m = Memory(who=["João"], what="não gosta de pizza", where="suporte")
        result = strict_validator.validate_write(m, empty_graph)
        # Different who — different referent
        assert result.status == ValidationStatus.OK


class TestPolicy:
    """Policy behavior (WARN vs BLOCK)."""

    def test_warn_policy_downgrades_blocked(self, empty_graph):
        validator = create_default_validator()  # WARN
        existing = Memory(who=["Maria"], what="gosta pizza")
        _add_memory(empty_graph, existing)
        m = Memory(who=["Maria"], what="não gosta pizza")
        result = validator.validate_write(m, empty_graph)
        # In WARN policy, BLOCKED is downgraded
        assert result.status == ValidationStatus.WARN
        assert result.metadata.get("downgraded_from") == "BLOCKED"

    def test_block_policy_keeps_blocked(self, empty_graph):
        validator = create_strict_validator()  # BLOCK
        existing = Memory(who=["Maria"], what="gosta pizza")
        _add_memory(empty_graph, existing)
        m = Memory(who=["Maria"], what="não gosta pizza")
        result = validator.validate_write(m, empty_graph)
        assert result.status == ValidationStatus.BLOCKED


class TestDetectionLevel:
    """Verify the 3-level detection system reports the right level."""

    def test_heuristic_detected_via_negation(self, empty_graph, strict_validator):
        existing = Memory(who=["Maria"], what="adora pizza")
        _add_memory(empty_graph, existing)
        m = Memory(who=["Maria"], what="odeia pizza")
        result = strict_validator.validate_write(m, empty_graph)
        assert result.status == ValidationStatus.BLOCKED
        assert result.detection_level == "heuristic"

    def test_token_detected_via_similarity(self, empty_graph, warn_validator):
        """Redundancy threshold (>0.85) catches near-duplicates."""
        # Use an almost-identical pair to trigger redundancy
        existing = Memory(who=["João"], what="Maria pediu reembolso do pedido 12345")
        _add_memory(empty_graph, existing)
        m = Memory(who=["João"], what="Maria pediu reembolso do pedido 12345")  # identical
        result = warn_validator.validate_write(m, empty_graph)
        assert result.status == ValidationStatus.WARN
        assert result.detection_level == "token"

    def test_ok_has_no_detection_level_set(self, empty_graph, warn_validator):
        m = Memory(who=["João"], what="algo novo")
        result = warn_validator.validate_write(m, empty_graph)
        # OK status, no specific detection level
        assert result.status == ValidationStatus.OK


class TestHistoryAndStats:
    """History and stats methods."""

    def test_history_recorded(self, empty_graph, warn_validator):
        m1 = Memory(who=["A"], what="x")
        m2 = Memory(who=["B"], what="y")
        warn_validator.validate_write(m1, empty_graph)
        warn_validator.validate_write(m2, empty_graph)
        assert len(warn_validator.get_history()) == 2

    def test_clear_history(self, empty_graph, warn_validator):
        m = Memory(what="x")
        warn_validator.validate_write(m, empty_graph)
        warn_validator.clear_history()
        assert len(warn_validator.get_history()) == 0

    def test_stats(self, empty_graph, warn_validator):
        # 1 OK + 1 BLOCKED (downgraded to WARN in WARN policy)
        warn_validator.validate_write(Memory(what="ok"), empty_graph)
        existing = Memory(who=["X"], what="gosta")
        _add_memory(empty_graph, existing)
        warn_validator.validate_write(Memory(who=["X"], what="não gosta"), empty_graph)
        stats = warn_validator.stats()
        assert stats["total"] == 2
        assert stats["policy"] == "WARN"
