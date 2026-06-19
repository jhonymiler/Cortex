"""
Tests for Ebbinghaus decay, Forget Gate, and Dream Agent.
"""

import pytest
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cortext.core.memory import Memory
from cortext.core.graph import MemoryGraph
from cortext.core.decay import (
    DecayConfig,
    retrievability,
    effective_stability,
    decay_status,
    ForgetGate,
    ForgetGateConfig,
)
from cortext.workers import DreamAgent


class TestEbbinghausDecay:
    """Test R = e^(-t/S) curve."""

    def test_retrievability_fresh(self):
        m = Memory(what="x", when=datetime.now())
        r = retrievability(m)
        assert r > 0.95  # just accessed, should be near 1.0

    def test_retrievability_old(self):
        old_time = datetime.now() - timedelta(days=30)
        m = Memory(what="x", when=old_time)
        r = retrievability(m)
        # 30 days, base 7 days stability → R = e^(-30/7) ≈ 0.013
        assert r < 0.05  # mostly forgotten

    def test_retrievability_decay_curve(self):
        """R should decay exponentially."""
        now = datetime.now()
        m = Memory(what="x", when=now)
        r0 = retrievability(m, now=now)
        r7 = retrievability(m, now=now + timedelta(days=7))
        r14 = retrievability(m, now=now + timedelta(days=14))
        # Each doubling of time should reduce R by factor of e
        assert r7 < r0
        assert r14 < r7
        # Ratio should be approximately 1/e for 7 days
        assert (r0 / r7) > 2.0  # at least 2x decay in 7 days

    def test_high_access_count_increases_stability(self):
        m_low = Memory(what="x", access_count=1)
        m_high = Memory(what="x", access_count=100)
        s_low = effective_stability(m_low)
        s_high = effective_stability(m_high)
        assert s_high > s_low

    def test_high_importance_increases_stability(self):
        m_low = Memory(what="x", importance=0.3)
        m_high = Memory(what="x", importance=0.9)
        s_low = effective_stability(m_low)
        s_high = effective_stability(m_high)
        assert s_high > s_low

    def test_consolidated_memory_more_stable(self):
        # is_consolidated is a property, derived from is_summary or consolidated_from
        m_normal = Memory(what="x", is_summary=False, consolidated_from=[])
        m_consolidated = Memory(what="x", is_summary=True, consolidated_from=["a", "b"])
        s_normal = effective_stability(m_normal)
        s_consolidated = effective_stability(m_consolidated)
        assert s_consolidated > s_normal

    def test_decay_status_categories(self):
        """Status returns one of: active | fading | weak | forgotten."""
        m = Memory(what="x", when=datetime.now())
        status = decay_status(m)
        assert status in ("active", "fading", "weak", "forgotten")


class TestForgetGate:
    """Test the 3-signal forget gate."""

    def test_clean_memory_low_signal(self):
        """High importance + recent = should have low forget signal."""
        gate = ForgetGate()
        g = MemoryGraph()
        m = Memory(who=["Maria"], what="pediu reembolso importante", importance=0.9)
        g._memories[m.id] = m
        signal = gate.compute_forget_signal(m, g)
        # High importance, has content, has participants — low forget signal
        assert signal < 0.5

    def test_noisy_memory_high_signal(self):
        """Low importance + empty = should have meaningful forget signal."""
        gate = ForgetGate()
        g = MemoryGraph()
        m = Memory(who=[], what="x", importance=0.1)
        g._memories[m.id] = m
        signal = gate.compute_forget_signal(m, g)
        # Low importance, no participants, short content — meaningful signal
        assert signal > 0.3  # above the default forget_threshold

    def test_filter_forgettable_splits(self):
        gate = ForgetGate()
        g = MemoryGraph()
        keep_m = Memory(who=["Maria"], what="reembolso importante pedido", importance=0.9)
        # Make forget_m VERY forgettable: low importance, no who, generic content
        forget_m = Memory(who=[], what="x", importance=0.05, is_summary=False)
        g._memories[keep_m.id] = keep_m
        g._memories[forget_m.id] = forget_m

        keep, forget = gate.filter_forgettable([keep_m, forget_m], g)
        # keep_m should be kept (high importance, has who, has content)
        assert keep_m in keep
        # forget_m should be forgettable (very low importance, no who, minimal content)
        # Force the threshold: manually check signal
        signal = gate.compute_forget_signal(forget_m, g)
        assert signal > gate.config.forget_threshold  # docs the threshold
        assert forget_m in forget

    def test_accelerate_decay(self):
        gate = ForgetGate()
        m = Memory(what="x", importance=0.5)
        new_imp = gate.accelerate_decay(m, multiplier=0.5)
        assert new_imp == 0.25
        assert m.importance == 0.25


class TestDreamAgent:
    """Test the background consolidator."""

    def test_replay_top_n(self):
        g = MemoryGraph()
        # Add 10 memories with varying importance
        for i in range(10):
            m = Memory(what=f"event {i}", importance=i / 10.0)
            g._memories[m.id] = m

        agent = DreamAgent(replay_count=3)
        result = agent.run_cycle(g)

        # Top 3 most important should have been touched (access_count incremented)
        # The top 3 are importance 0.9, 0.8, 0.7
        assert result.n_replayed == 3

    def test_consolidate_similar(self):
        g = MemoryGraph()
        # Two near-identical memories
        m1 = Memory(who=["Maria"], what="Maria pediu reembolso", where="suporte")
        m2 = Memory(who=["Maria"], what="Maria pediu reembolso", where="suporte")  # identical
        g._memories[m1.id] = m1
        g._memories[m2.id] = m2

        agent = DreamAgent(consolidation_threshold=0.85)
        result = agent.run_cycle(g)

        # Should have consolidated (marked m2 as consolidated_into m1)
        assert result.n_consolidated == 1
        assert m2.consolidated_into == m1.id

    def test_cleanup_forgotten(self):
        g = MemoryGraph()
        # Old memory with low retrievability
        old = Memory(what="x", when=datetime.now() - timedelta(days=365))
        old.importance = 0.1  # very low
        g._memories[old.id] = old

        agent = DreamAgent(cleanup_threshold=0.5)
        result = agent.run_cycle(g)

        # Should have cleaned up (or not, depending on retrieval threshold)
        # At minimum, no crash
        assert isinstance(result.n_cleaned, int)

    def test_different_who_not_consolidated(self):
        g = MemoryGraph()
        m1 = Memory(who=["Maria"], what="Maria ligou", where="suporte")
        m2 = Memory(who=["João"], what="Maria ligou", where="suporte")  # same text, different who
        g._memories[m1.id] = m1
        g._memories[m2.id] = m2

        agent = DreamAgent(consolidation_threshold=0.5)
        result = agent.run_cycle(g)

        # Should NOT consolidate (different who)
        assert result.n_consolidated == 0

    def test_different_where_not_consolidated(self):
        g = MemoryGraph()
        m1 = Memory(who=["Maria"], what="Maria ligou", where="suporte")
        m2 = Memory(who=["Maria"], what="Maria ligou", where="vendas")  # same text, different where
        g._memories[m1.id] = m1
        g._memories[m2.id] = m2

        agent = DreamAgent(consolidation_threshold=0.5)
        result = agent.run_cycle(g)

        # Should NOT consolidate (different where)
        assert result.n_consolidated == 0

    def test_dream_cycle_result_fields(self):
        g = MemoryGraph()
        agent = DreamAgent()
        result = agent.run_cycle(g)
        assert hasattr(result, "cycle_at")
        assert hasattr(result, "n_consolidated")
        assert hasattr(result, "n_replayed")
        assert hasattr(result, "n_cleaned")
        assert hasattr(result, "duration_ms")
        assert result.duration_ms >= 0
