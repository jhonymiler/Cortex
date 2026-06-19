"""
Tests for the CortexV5 facade (public API).
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cortext import (
    CortexV5,
    Memory,
    Entity,
    Relation,
    ValidationStatus,
)
from cortext.core.validation import ValidationPolicy


class TestCortexV5Init:
    """Test instantiation and configuration."""

    def test_default_init(self):
        cortex = CortexV5()
        assert cortex.namespace == "default"
        assert cortex.validator.policy == ValidationPolicy.WARN
        assert len(cortex.graph) == 0

    def test_custom_namespace(self):
        cortex = CortexV5(namespace="myapp")
        assert cortex.namespace == "myapp"
        assert cortex.graph.namespace == "myapp"

    def test_strict_policy(self):
        cortex = CortexV5(validation_policy=ValidationPolicy.BLOCK)
        assert cortex.validator.policy == ValidationPolicy.BLOCK

    def test_dream_agent_opt_in(self):
        cortex_default = CortexV5()
        assert cortex_default.dream_agent is None

        cortex_with = CortexV5(enable_dream_agent=True)
        assert cortex_with.dream_agent is not None


class TestRemember:
    """Test the remember() write API."""

    def test_remember_minimal(self):
        cortex = CortexV5()
        memory, result = cortex.remember(what="Maria pediu reembolso")
        assert isinstance(memory, Memory)
        assert memory.what == "Maria pediu reembolso"
        assert memory.id in cortex.graph._memories
        assert result.status == ValidationStatus.OK

    def test_remember_full_w5h(self):
        from datetime import datetime
        cortex = CortexV5()
        memory, result = cortex.remember(
            who=["Maria"],
            what="reportou erro de pagamento",
            why="cartão expirado",
            when=datetime(2026, 1, 9),
            where="suporte",
            how="orientada a atualizar",
            importance=0.8,
            lang="pt",
        )
        assert memory.who == ["Maria"]
        assert memory.what == "reportou erro de pagamento"
        assert memory.why == "cartão expirado"
        assert memory.where == "suporte"
        assert memory.importance == 0.8
        assert memory.lang == "pt"

    def test_remember_empty_what_raises(self):
        cortex = CortexV5()
        with pytest.raises(ValueError):
            cortex.remember(what="")

    def test_remember_with_similar_to(self):
        cortex = CortexV5()
        ref, _ = cortex.remember(who=["João"], what="comprou carro", where="vendas", importance=0.8)
        m2, _ = cortex.remember(
            what="João comprou moto",  # different content
            similar_to=ref,
        )
        # Inherited from ref
        assert m2.where == "vendas"
        # Decayed importance
        assert m2.importance == pytest.approx(0.64)  # 0.8 * 0.8

    def test_remember_blocked_returns_without_storing(self):
        cortex = CortexV5(validation_policy=ValidationPolicy.BLOCK)
        # First, store a memory
        existing, _ = cortex.remember(who=["Maria"], what="gosta pizza")
        # Now try to store a contradiction
        memory, result = cortex.remember(who=["Maria"], what="não gosta pizza")
        assert result.status == ValidationStatus.BLOCKED
        assert memory.id not in cortex.graph._memories  # not stored
        # But original is still there
        assert existing.id in cortex.graph._memories

    def test_remember_warned_does_store(self):
        cortex = CortexV5(validation_policy=ValidationPolicy.WARN)
        existing, _ = cortex.remember(who=["Maria"], what="gosta pizza")
        memory, result = cortex.remember(who=["Maria"], what="não gosta pizza")
        # WARN policy downgrades BLOCKED to WARN — but still stores
        assert result.status == ValidationStatus.WARN
        assert memory.id in cortex.graph._memories


class TestRecall:
    """Test the recall() read API."""

    def test_recall_structural(self):
        cortex = CortexV5()
        cortex.remember(who=["Maria"], what="pediu reembolso", where="suporte", lang="pt")
        cortex.remember(who=["João"], what="comprou carro", where="vendas", lang="pt")
        context, result = cortex.recall("O que Maria pediu?", lang="pt")
        assert "Maria" in context
        assert "pediu reembolso" in context
        # Verify João's memory is NOT in context (different who)
        assert "João" not in context or "comprou carro" not in context

    def test_recall_cross_language(self):
        """PT query → EN memory via structural (who match) + token Jaccard."""
        cortex = CortexV5()
        cortex.remember(who=["Maria"], what="loved pizza", lang="en")
        context, result = cortex.recall("O que Maria pediu?", lang="pt")
        # Should find via who match (Maria is universal across langs)
        # Token match for "pizza" is also there
        assert "Maria" in context

    def test_recall_returns_compact_string(self):
        cortex = CortexV5()
        cortex.remember(who=["Maria"], what="pediu reembolso")
        context, result = cortex.recall("O que Maria pediu?")
        assert isinstance(context, str)
        assert len(context) > 0
        assert len(context) < 500  # compact, not full memory

    def test_recall_empty_graph(self):
        cortex = CortexV5()
        context, result = cortex.recall("anything")
        assert context == ""
        assert result.is_empty()


class TestRememberAndRecall:
    """One-shot convenience API."""

    def test_remember_and_recall(self):
        cortex = CortexV5()
        memory, context = cortex.remember_and_recall(
            who=["Maria"], what="pediu reembolso", where="suporte",
        )
        assert isinstance(memory, Memory)
        assert "Maria" in context


class TestBackground:
    """Dream Agent background operations."""

    def test_dream_cycle_disabled_by_default(self):
        cortex = CortexV5()
        with pytest.raises(RuntimeError, match="DreamAgent not enabled"):
            cortex.run_dream_cycle()

    def test_dream_cycle_when_enabled(self):
        cortex = CortexV5(enable_dream_agent=True)
        cortex.remember(who=["Maria"], what="pediu reembolso", importance=0.8)
        result = cortex.run_dream_cycle()
        assert hasattr(result, "n_replayed")
        assert hasattr(result, "n_consolidated")


class TestStats:
    """Stats and introspection."""

    def test_stats_empty(self):
        cortex = CortexV5(namespace="myapp")
        stats = cortex.stats()
        assert stats["namespace"] == "myapp"
        assert stats["graph"]["total_memories"] == 0
        assert stats["validator_policy"] == "WARN"

    def test_stats_after_writes(self):
        cortex = CortexV5()
        cortex.remember(who=["Maria"], what="x")
        cortex.remember(who=["João"], what="y")
        stats = cortex.stats()
        assert stats["graph"]["total_memories"] == 2
        assert stats["writes"]["writes_total"] == 2

    def test_repr(self):
        cortex = CortexV5(namespace="test")
        r = repr(cortex)
        assert "CortexV5" in r
        # Repr uses Python's default repr (with quotes around string)
        assert "test" in r


class TestEndToEnd:
    """Integration scenarios that exercise the full pipeline."""

    def test_customer_support_scenario_pt(self):
        """Full Brazilian customer support flow."""
        cortex = CortexV5(namespace="support")
        # Customer service agent stores memories
        cortex.remember(who=["Maria"], what="pediu reembolso", why="cartão expirado", where="suporte", importance=0.7)
        cortex.remember(who=["João"], what="comprou produto", where="suporte", importance=0.5)
        cortex.remember(who=["Maria"], what="ligou reclamando", where="suporte", importance=0.6)

        # Query: what did Maria ask?
        context, result = cortex.recall("O que Maria pediu?")
        # Should have Maria's memories
        assert "Maria" in context
        # João's memory may or may not be there (no Maria overlap)
        # But context is compact
        assert len(context) < 500

    def test_personal_assistant_scenario_en(self):
        """English personal assistant flow."""
        cortex = CortexV5(namespace="pa")
        cortex.remember(who=["User"], what="prefers coffee without sugar", where="preferences", lang="en")
        cortex.remember(who=["User"], what="works best in morning", where="habits", lang="en")

        # EN query
        context, result = cortex.recall("What does User like?", lang="en")
        assert "User" in context
        # Coffee preference should be there
        assert "coffee" in context.lower() or "sugar" in context.lower()

    def test_contradiction_caught_in_writes(self):
        """Strict policy blocks contradictions."""
        cortex = CortexV5(validation_policy=ValidationPolicy.BLOCK, namespace="strict")
        cortex.remember(who=["X"], what="loves pizza", lang="en")
        # Try to contradict
        memory, result = cortex.remember(who=["X"], what="hates pizza", lang="en")
        assert result.status == ValidationStatus.BLOCKED
        # Confirm only 1 memory in graph
        assert len(cortex.graph) == 1
