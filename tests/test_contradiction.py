"""
Tests for Polarity and Contradiction Detection.

Testa:
- Polaridade nas relações
- Detecção de contradições
- Estratégias de resolução
- Integração com MemoryGraph
"""

import pytest
from datetime import datetime, timedelta

from cortex.core.relation import Relation
from cortex.core.contradiction import (
    ContradictionDetector,
    Contradiction,
    ResolutionStrategy,
    ResolutionResult,
    create_default_detector,
    create_conservative_detector,
    create_strict_detector,
)
from cortex.core.memory_graph import MemoryGraph


class TestRelationPolarity:
    """Tests for relation polarity."""
    
    def test_default_polarity_is_positive(self) -> None:
        """Default polarity should be 1.0 (positive)."""
        relation = Relation(
            from_id="maria",
            relation_type="likes",
            to_id="pizza",
        )
        assert relation.polarity == 1.0
    
    def test_negative_polarity(self) -> None:
        """Test negative polarity."""
        relation = Relation(
            from_id="maria",
            relation_type="likes",
            to_id="sushi",
            polarity=-1.0,
        )
        assert relation.polarity == -1.0
        assert relation.is_negative()
        assert not relation.is_positive()
    
    def test_neutral_polarity(self) -> None:
        """Test neutral polarity."""
        relation = Relation(
            from_id="maria",
            relation_type="likes",
            to_id="pasta",
            polarity=0.0,
        )
        assert relation.is_neutral()
        assert not relation.is_positive()
        assert not relation.is_negative()
    
    def test_polarity_classification(self) -> None:
        """Test polarity classification thresholds."""
        # Positive > 0.3
        assert Relation("a", "r", "b", polarity=0.5).is_positive()
        assert Relation("a", "r", "b", polarity=1.0).is_positive()
        
        # Negative < -0.3
        assert Relation("a", "r", "b", polarity=-0.5).is_negative()
        assert Relation("a", "r", "b", polarity=-1.0).is_negative()
        
        # Neutral between -0.3 and 0.3
        assert Relation("a", "r", "b", polarity=0.0).is_neutral()
        assert Relation("a", "r", "b", polarity=0.2).is_neutral()
        assert Relation("a", "r", "b", polarity=-0.2).is_neutral()
    
    def test_polarity_in_to_dict(self) -> None:
        """Test polarity is serialized."""
        relation = Relation(
            from_id="a",
            relation_type="r",
            to_id="b",
            polarity=-0.8,
        )
        data = relation.to_dict()
        assert "polarity" in data
        assert data["polarity"] == -0.8
    
    def test_polarity_in_from_dict(self) -> None:
        """Test polarity is deserialized."""
        relation = Relation(
            from_id="a",
            relation_type="r",
            to_id="b",
            polarity=-0.5,
        )
        data = relation.to_dict()
        restored = Relation.from_dict(data)
        assert restored.polarity == -0.5
    
    def test_polarity_in_triple(self) -> None:
        """Test polarity shows in triple representation."""
        positive = Relation("a", "likes", "b", polarity=1.0)
        negative = Relation("a", "likes", "b", polarity=-1.0)
        neutral = Relation("a", "likes", "b", polarity=0.0)
        
        assert "+likes" in positive.to_triple()
        assert "-likes" in negative.to_triple()
        assert "~likes" in neutral.to_triple()


class TestContradictionDetection:
    """Tests for contradiction detection."""
    
    def test_contradicts_same_triple_opposite_polarity(self) -> None:
        """Two relations with same triple but opposite polarity are contradictory."""
        rel_a = Relation("maria", "likes", "pizza", polarity=1.0)
        rel_b = Relation("maria", "likes", "pizza", polarity=-1.0)
        
        assert rel_a.contradicts(rel_b)
        assert rel_b.contradicts(rel_a)
    
    def test_not_contradicts_same_polarity(self) -> None:
        """Two relations with same polarity don't contradict."""
        rel_a = Relation("maria", "likes", "pizza", polarity=1.0)
        rel_b = Relation("maria", "likes", "pizza", polarity=0.8)
        
        assert not rel_a.contradicts(rel_b)
    
    def test_not_contradicts_different_triple(self) -> None:
        """Different triples don't contradict even with opposite polarity."""
        rel_a = Relation("maria", "likes", "pizza", polarity=1.0)
        rel_b = Relation("maria", "likes", "sushi", polarity=-1.0)  # Different to_id
        
        assert not rel_a.contradicts(rel_b)
    
    def test_detector_finds_contradiction(self) -> None:
        """Detector finds contradiction when adding conflicting relation."""
        detector = create_default_detector()
        
        existing = [
            Relation("maria", "likes", "pizza", polarity=1.0),
        ]
        new_relation = Relation("maria", "likes", "pizza", polarity=-1.0)
        
        contradiction = detector.check_for_contradiction(new_relation, existing)
        
        assert contradiction is not None
        assert contradiction.relation_a == existing[0]
        assert contradiction.relation_b == new_relation
    
    def test_detector_no_contradiction(self) -> None:
        """Detector returns None when no contradiction."""
        detector = create_default_detector()
        
        existing = [
            Relation("maria", "likes", "pizza", polarity=1.0),
        ]
        new_relation = Relation("maria", "likes", "sushi", polarity=1.0)
        
        contradiction = detector.check_for_contradiction(new_relation, existing)
        
        assert contradiction is None
    
    def test_find_all_contradictions(self) -> None:
        """Find all contradictions in a list of relations."""
        detector = create_default_detector()
        
        relations = [
            Relation("maria", "likes", "pizza", polarity=1.0),
            Relation("maria", "likes", "pizza", polarity=-1.0),  # Contradicts [0]
            Relation("joao", "trusts", "maria", polarity=1.0),
            Relation("joao", "trusts", "maria", polarity=-0.8),  # Contradicts [2]
        ]
        
        contradictions = detector.find_all_contradictions(relations)
        
        assert len(contradictions) == 2


class TestResolutionStrategies:
    """Tests for contradiction resolution strategies."""
    
    def test_most_recent_strategy(self) -> None:
        """Most recent relation wins."""
        detector = ContradictionDetector(strategy=ResolutionStrategy.MOST_RECENT)
        
        old_time = datetime.now() - timedelta(days=1)
        new_time = datetime.now()
        
        rel_old = Relation("a", "r", "b", polarity=1.0)
        rel_old.created_at = old_time
        
        rel_new = Relation("a", "r", "b", polarity=-1.0)
        rel_new.created_at = new_time
        
        contradiction = Contradiction(relation_a=rel_old, relation_b=rel_new)
        result = detector.resolve(contradiction)
        
        assert result.winner == rel_new
        assert result.loser == rel_old
        assert result.strategy_used == ResolutionStrategy.MOST_RECENT
    
    def test_strongest_strategy(self) -> None:
        """Strongest relation wins."""
        detector = ContradictionDetector(strategy=ResolutionStrategy.STRONGEST)
        
        rel_weak = Relation("a", "r", "b", polarity=1.0, strength=0.3)
        rel_strong = Relation("a", "r", "b", polarity=-1.0, strength=0.9)
        
        contradiction = Contradiction(relation_a=rel_weak, relation_b=rel_strong)
        result = detector.resolve(contradiction)
        
        assert result.winner == rel_strong
        assert result.loser == rel_weak
        assert result.strategy_used == ResolutionStrategy.STRONGEST
    
    def test_most_reinforced_strategy(self) -> None:
        """Most reinforced relation wins."""
        detector = ContradictionDetector(strategy=ResolutionStrategy.MOST_REINFORCED)
        
        rel_few = Relation("a", "r", "b", polarity=1.0)
        rel_few.reinforced_count = 2
        
        rel_many = Relation("a", "r", "b", polarity=-1.0)
        rel_many.reinforced_count = 10
        
        contradiction = Contradiction(relation_a=rel_few, relation_b=rel_many)
        result = detector.resolve(contradiction)
        
        assert result.winner == rel_many
        assert result.loser == rel_few
        assert result.strategy_used == ResolutionStrategy.MOST_REINFORCED
    
    def test_keep_both_strategy(self) -> None:
        """Keep both relations as conflict."""
        detector = ContradictionDetector(strategy=ResolutionStrategy.KEEP_BOTH)
        
        rel_a = Relation("a", "r", "b", polarity=1.0)
        rel_b = Relation("a", "r", "b", polarity=-1.0)
        
        contradiction = Contradiction(relation_a=rel_a, relation_b=rel_b)
        result = detector.resolve(contradiction)
        
        assert result.winner is None
        assert result.loser is None
        assert result.action_taken == "marked_conflict"
    
    def test_ask_user_fallback(self) -> None:
        """Ask user falls back to most recent without callback."""
        detector = ContradictionDetector(strategy=ResolutionStrategy.ASK_USER)
        
        old_time = datetime.now() - timedelta(days=1)
        new_time = datetime.now()
        
        rel_old = Relation("a", "r", "b", polarity=1.0)
        rel_old.created_at = old_time
        
        rel_new = Relation("a", "r", "b", polarity=-1.0)
        rel_new.created_at = new_time
        
        contradiction = Contradiction(relation_a=rel_old, relation_b=rel_new)
        result = detector.resolve(contradiction)
        
        assert result.winner == rel_new
        assert result.action_taken == "fallback_most_recent"
    
    def test_ask_user_with_callback(self) -> None:
        """Ask user uses callback when provided."""
        def user_chooses_a(contradiction: Contradiction) -> Relation:
            return contradiction.relation_a
        
        detector = ContradictionDetector(
            strategy=ResolutionStrategy.ASK_USER,
            on_ask_user=user_chooses_a,
        )
        
        rel_a = Relation("a", "r", "b", polarity=1.0)
        rel_b = Relation("a", "r", "b", polarity=-1.0)
        
        contradiction = Contradiction(relation_a=rel_a, relation_b=rel_b)
        result = detector.resolve(contradiction)
        
        assert result.winner == rel_a
        assert result.loser == rel_b
        assert result.action_taken == "asked_user"


class TestDetectorStats:
    """Tests for detector statistics."""
    
    def test_history_tracking(self) -> None:
        """Detector tracks contradiction history."""
        detector = create_default_detector()
        
        existing = [Relation("a", "r", "b", polarity=1.0)]
        new_rel = Relation("a", "r", "b", polarity=-1.0)
        
        detector.check_for_contradiction(new_rel, existing)
        
        history = detector.get_history()
        assert len(history) == 1
    
    def test_unresolved_tracking(self) -> None:
        """Detector tracks unresolved contradictions."""
        detector = create_default_detector()
        
        existing = [Relation("a", "r", "b", polarity=1.0)]
        new_rel = Relation("a", "r", "b", polarity=-1.0)
        
        contradiction = detector.check_for_contradiction(new_rel, existing)
        
        assert len(detector.get_unresolved()) == 1
        
        detector.resolve(contradiction)
        
        assert len(detector.get_unresolved()) == 0
    
    def test_stats(self) -> None:
        """Test stats output."""
        detector = create_default_detector()
        
        existing = [Relation("a", "r", "b", polarity=1.0)]
        new_rel = Relation("a", "r", "b", polarity=-1.0)
        
        contradiction = detector.check_for_contradiction(new_rel, existing)
        detector.resolve(contradiction)
        
        stats = detector.stats()
        
        assert stats["total_detected"] == 1
        assert stats["resolved"] == 1
        assert stats["pending"] == 0


class TestMemoryGraphContradiction:
    """Tests for contradiction handling in MemoryGraph."""
    
    def test_add_relation_detects_contradiction(self) -> None:
        """Adding contradictory relation is detected."""
        graph = MemoryGraph()
        
        # Add positive relation
        rel_positive = Relation("maria", "likes", "pizza", polarity=1.0)
        result1, resolution1 = graph.add_relation(rel_positive)
        
        assert resolution1 is None  # No contradiction on first add
        
        # Add contradictory relation
        rel_negative = Relation("maria", "likes", "pizza", polarity=-1.0)
        result2, resolution2 = graph.add_relation(rel_negative)
        
        assert resolution2 is not None  # Contradiction detected
    
    def test_most_recent_wins_by_default(self) -> None:
        """By default, most recent relation wins."""
        graph = MemoryGraph()
        
        # Add old relation
        rel_old = Relation("maria", "likes", "pizza", polarity=1.0)
        graph.add_relation(rel_old)
        
        # Add new contradictory relation
        rel_new = Relation("maria", "likes", "pizza", polarity=-1.0)
        result, resolution = graph.add_relation(rel_new)
        
        # New should win
        assert result.polarity == -1.0
        
        # Only one relation should remain
        relations = graph.get_relations(from_id="maria", to_id="pizza")
        assert len(relations) == 1
        assert relations[0].polarity == -1.0
    
    def test_change_resolution_strategy(self) -> None:
        """Can change resolution strategy."""
        graph = MemoryGraph()
        graph.set_contradiction_strategy(ResolutionStrategy.STRONGEST)
        
        # Add weak relation
        rel_weak = Relation("a", "r", "b", polarity=1.0, strength=0.2)
        graph.add_relation(rel_weak)
        
        # Add strong contradictory relation
        rel_strong = Relation("a", "r", "b", polarity=-1.0, strength=0.9)
        result, resolution = graph.add_relation(rel_strong)
        
        # Strong should win
        assert result.polarity == -1.0
        
        relations = graph.get_relations()
        assert len(relations) == 1
        assert relations[0].strength == 0.9
    
    def test_find_contradictions_audit(self) -> None:
        """Can audit graph for contradictions."""
        graph = MemoryGraph()
        
        # Add relations with check disabled
        graph.add_relation_simple(Relation("a", "r", "b", polarity=1.0))
        graph.add_relation_simple(Relation("a", "r", "b", polarity=-1.0))
        
        # Now audit
        contradictions = graph.find_contradictions()
        
        assert len(contradictions) == 1
    
    def test_contradiction_stats_in_graph_stats(self) -> None:
        """Contradiction stats appear in graph stats."""
        graph = MemoryGraph()
        
        rel_a = Relation("a", "r", "b", polarity=1.0)
        rel_b = Relation("a", "r", "b", polarity=-1.0)
        
        graph.add_relation(rel_a)
        graph.add_relation(rel_b)
        
        stats = graph.stats()
        
        assert "contradiction_stats" in stats
        assert stats["contradiction_stats"]["total_detected"] >= 0


class TestFactoryFunctions:
    """Tests for factory functions."""
    
    def test_create_default_detector(self) -> None:
        """Default detector uses MOST_RECENT."""
        detector = create_default_detector()
        assert detector.strategy == ResolutionStrategy.MOST_RECENT
    
    def test_create_conservative_detector(self) -> None:
        """Conservative detector uses MOST_REINFORCED."""
        detector = create_conservative_detector()
        assert detector.strategy == ResolutionStrategy.MOST_REINFORCED
    
    def test_create_strict_detector(self) -> None:
        """Strict detector uses STRONGEST."""
        detector = create_strict_detector()
        assert detector.strategy == ResolutionStrategy.STRONGEST
