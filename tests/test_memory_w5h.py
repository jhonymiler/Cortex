"""
Testes para Memory (modelo W5H) e DecayManager.

Testa:
- Criação de memórias com campos W5H
- Cálculo de retrievability (Ebbinghaus)
- Decaimento ao longo do tempo
- Consolidação e hub bonuses
- Serialização/deserialização
"""

import math
from datetime import datetime, timedelta

import pytest

from cortex.core.memory import Memory
from cortex.core.decay import (
    DecayManager,
    DecayConfig,
    create_default_decay_manager,
    create_aggressive_decay_manager,
    create_gentle_decay_manager,
)


class TestMemoryCreation:
    """Testes de criação de memórias W5H."""
    
    def test_create_basic_memory(self):
        """Cria memória com campos mínimos."""
        memory = Memory(
            who=["user_123"],
            what="solicitou ajuda com login",
        )
        
        assert memory.who == ["user_123"]
        assert memory.what == "solicitou ajuda com login"
        assert memory.why == ""
        assert memory.how == ""
        assert memory.where == "default"
        assert memory.importance == 0.5
        assert memory.access_count == 0
        assert not memory.is_consolidated
        assert not memory.is_forgotten
    
    def test_create_full_w5h_memory(self):
        """Cria memória com todos os campos W5H."""
        memory = Memory(
            who=["maria@email.com", "sistema_pagamentos"],
            what="reportou erro de pagamento",
            why="cartão expirado",
            how="orientada a atualizar dados do cartão",
            where="suporte_cliente",
            temporal_context="durante horário comercial",
        )
        
        assert len(memory.who) == 2
        assert memory.what == "reportou erro de pagamento"
        assert memory.why == "cartão expirado"
        assert memory.how == "orientada a atualizar dados do cartão"
        assert memory.where == "suporte_cliente"
        assert memory.temporal_context == "durante horário comercial"
    
    def test_memory_has_uuid(self):
        """Memória tem UUID único."""
        m1 = Memory(what="test1")
        m2 = Memory(what="test2")
        
        assert m1.id != m2.id
        assert len(m1.id) == 36  # UUID format
    
    def test_memory_has_timestamp(self):
        """Memória tem timestamp de criação."""
        before = datetime.now()
        memory = Memory(what="test")
        after = datetime.now()
        
        assert before <= memory.when <= after
        assert before <= memory.created_at <= after


class TestMemoryRetrievability:
    """Testes de cálculo de retrievability (Ebbinghaus)."""
    
    def test_fresh_memory_has_high_retrievability(self):
        """Memória recém-criada tem alta retrievability."""
        memory = Memory(what="test")
        
        # Memória fresca deve ter retrievability próxima de 1.0
        assert memory.retrievability > 0.99
    
    def test_retrievability_decreases_over_time(self):
        """Retrievability diminui com o tempo."""
        memory = Memory(what="test")
        
        # Simula 1 dia atrás
        memory.when = datetime.now() - timedelta(days=1)
        memory.last_accessed = None
        r1 = memory.retrievability
        
        # Simula 7 dias atrás
        memory.when = datetime.now() - timedelta(days=7)
        r7 = memory.retrievability
        
        # Simula 30 dias atrás
        memory.when = datetime.now() - timedelta(days=30)
        r30 = memory.retrievability
        
        assert r1 > r7 > r30
        assert r1 < 1.0  # Já decaiu um pouco
    
    def test_access_increases_stability(self):
        """Acessar memória aumenta stability e retrievability."""
        m1 = Memory(what="not accessed")
        m2 = Memory(what="accessed")
        
        # Simula acesso
        m2.touch()
        m2.touch()
        m2.touch()
        
        # Ambas criadas 5 dias atrás
        old_time = datetime.now() - timedelta(days=5)
        m1.when = old_time
        m1.last_accessed = old_time
        m2.when = old_time
        m2.last_accessed = datetime.now()  # Acessada agora
        
        # Memória acessada tem maior retrievability
        assert m2.retrievability > m1.retrievability
        assert m2.stability > m1.stability
    
    def test_consolidated_memory_decays_slower(self):
        """Memórias consolidadas decaem mais lentamente."""
        m1 = Memory(what="single occurrence")
        m2 = Memory(what="consolidated", consolidated_from=["a", "b", "c"])
        
        # Ambas 10 dias atrás
        old_time = datetime.now() - timedelta(days=10)
        m1.when = old_time
        m1.last_accessed = old_time
        m2.when = old_time
        m2.last_accessed = old_time
        
        # Consolidada deve ter maior retrievability
        assert m2.is_consolidated
        assert not m1.is_consolidated
        assert m2.retrievability > m1.retrievability
    
    def test_centrality_affects_retrievability(self):
        """Memórias com alta centralidade decaem mais lentamente."""
        m1 = Memory(what="low centrality")
        m2 = Memory(what="high centrality (hub)")
        
        m2.set_centrality(2.0)  # Alta centralidade
        
        # Ambas 10 dias atrás
        old_time = datetime.now() - timedelta(days=10)
        m1.when = old_time
        m1.last_accessed = old_time
        m2.when = old_time
        m2.last_accessed = old_time
        
        assert m2.retrievability > m1.retrievability


class TestMemoryTouch:
    """Testes de touch (acesso à memória)."""
    
    def test_touch_increments_access_count(self):
        """Touch incrementa contador de acesso."""
        memory = Memory(what="test")
        
        assert memory.access_count == 0
        
        memory.touch()
        assert memory.access_count == 1
        
        memory.touch()
        memory.touch()
        assert memory.access_count == 3
    
    def test_touch_updates_last_accessed(self):
        """Touch atualiza last_accessed."""
        memory = Memory(what="test")
        
        assert memory.last_accessed is None
        
        before = datetime.now()
        memory.touch()
        after = datetime.now()
        
        assert memory.last_accessed is not None
        assert before <= memory.last_accessed <= after
    
    def test_touch_increases_stability(self):
        """Touch aumenta stability (spaced repetition)."""
        memory = Memory(what="test")
        
        initial = memory.stability
        
        memory.touch()
        assert memory.stability > initial
        
        memory.touch()
        memory.touch()
        assert memory.stability > initial * 1.2
    
    def test_touch_revives_forgotten(self):
        """Touch revive memória esquecida."""
        memory = Memory(what="test")
        memory.forget()
        
        assert memory.is_forgotten
        
        memory.touch()
        
        assert not memory.is_forgotten


class TestMemorySerialization:
    """Testes de serialização/deserialização."""
    
    def test_to_dict(self):
        """Converte memória para dict."""
        memory = Memory(
            who=["user"],
            what="action",
            why="reason",
            how="result",
            where="namespace",
        )
        memory.touch()
        
        data = memory.to_dict()
        
        assert data["who"] == ["user"]
        assert data["what"] == "action"
        assert data["why"] == "reason"
        assert data["how"] == "result"
        assert data["where"] == "namespace"
        assert data["access_count"] == 1
    
    def test_from_dict(self):
        """Reconstrói memória de dict."""
        original = Memory(
            who=["user1", "user2"],
            what="action",
            why="reason",
            how="result",
            where="namespace",
            importance=0.8,
        )
        original.touch()
        original.touch()
        
        data = original.to_dict()
        restored = Memory.from_dict(data)
        
        assert restored.who == original.who
        assert restored.what == original.what
        assert restored.why == original.why
        assert restored.how == original.how
        assert restored.where == original.where
        assert restored.access_count == original.access_count
        assert restored.importance == original.importance
    
    def test_to_w5h_dict(self):
        """Gera dict apenas com campos W5H."""
        memory = Memory(
            who=["user"],
            what="action",
            why="reason",
            how="result",
            where="namespace",
            importance=0.9,  # Não incluído em W5H
        )
        
        w5h = memory.to_w5h_dict()
        
        assert "who" in w5h
        assert "what" in w5h
        assert "why" in w5h
        assert "when" in w5h
        assert "where" in w5h
        assert "how" in w5h
        assert "importance" not in w5h  # Não é W5H


class TestMemorySimilarity:
    """Testes de similaridade para consolidação."""
    
    def test_identical_memories_have_high_similarity(self):
        """Memórias idênticas têm alta similaridade."""
        m1 = Memory(who=["user"], what="action", where="ns")
        m2 = Memory(who=["user"], what="action", where="ns")
        
        similarity = m1.similarity_to(m2)
        
        assert similarity > 0.9
    
    def test_different_memories_have_low_similarity(self):
        """Memórias diferentes têm baixa similaridade."""
        m1 = Memory(who=["user1"], what="action1", where="ns1")
        m2 = Memory(who=["user2"], what="action2", where="ns2")
        
        similarity = m1.similarity_to(m2)
        
        assert similarity < 0.3
    
    def test_partial_overlap_has_medium_similarity(self):
        """Memórias com overlap parcial têm similaridade média."""
        m1 = Memory(who=["user1", "user2"], what="action", where="ns")
        m2 = Memory(who=["user2", "user3"], what="action", where="ns")
        
        similarity = m1.similarity_to(m2)
        
        assert 0.4 < similarity < 0.9


class TestDecayManager:
    """Testes do DecayManager."""
    
    def test_default_config(self):
        """DecayManager usa configuração padrão."""
        dm = create_default_decay_manager()
        
        assert dm.config.daily_decay_rate == 0.95
        assert dm.config.forgotten_threshold == 0.1
    
    def test_aggressive_decay(self):
        """Configuração agressiva tem decay mais rápido."""
        dm = create_aggressive_decay_manager()
        
        assert dm.config.daily_decay_rate < 0.95
        assert dm.config.forgotten_threshold > 0.1
    
    def test_gentle_decay(self):
        """Configuração gentle tem decay mais lento."""
        dm = create_gentle_decay_manager()
        
        assert dm.config.daily_decay_rate > 0.95
        assert dm.config.forgotten_threshold < 0.1
    
    def test_apply_decay_reduces_importance(self):
        """apply_decay reduz importance de memória antiga."""
        dm = create_default_decay_manager()
        memory = Memory(what="test", importance=0.8)
        
        # Simula 10 dias sem acesso
        memory.when = datetime.now() - timedelta(days=10)
        memory.last_accessed = memory.when
        
        dm.apply_decay(memory)
        
        assert memory.importance < 0.8
    
    def test_apply_decay_skips_recent_memory(self):
        """apply_decay não afeta memória acessada hoje."""
        dm = create_default_decay_manager()
        memory = Memory(what="test", importance=0.8)
        memory.touch()  # Acessada agora
        
        dm.apply_decay(memory)
        
        # Importance aumentou levemente pelo touch, mas não decaiu
        assert memory.importance >= 0.8
    
    def test_touch_resets_decay(self):
        """touch reseta decaimento."""
        dm = create_default_decay_manager()
        memory = Memory(what="test")
        
        # Simula memória antiga
        memory.when = datetime.now() - timedelta(days=30)
        memory.last_accessed = memory.when
        memory.importance = 0.3
        
        # Touch revive
        dm.touch(memory)
        
        assert memory.last_accessed.date() == datetime.now().date()
        assert memory.importance > 0.3  # Boost leve
    
    def test_get_memory_health(self):
        """get_memory_health retorna status correto."""
        dm = create_default_decay_manager()
        
        # Memória fresca
        fresh = Memory(what="fresh")
        fresh.touch()
        health = dm.get_memory_health(fresh)
        assert health["status"] == "fresh"
        
        # Memória esquecida
        forgotten = Memory(what="forgotten")
        forgotten.forget()
        health = dm.get_memory_health(forgotten)
        assert health["status"] == "forgotten"
    
    def test_consolidated_memory_decays_slower(self):
        """Memória consolidada recebe bonus de decay."""
        dm = create_default_decay_manager()
        
        m1 = Memory(what="single", importance=0.8)
        m2 = Memory(what="consolidated", importance=0.8, consolidated_from=["a", "b"])
        
        # Ambas 20 dias atrás
        old_time = datetime.now() - timedelta(days=20)
        m1.when = old_time
        m1.last_accessed = old_time
        m2.when = old_time
        m2.last_accessed = old_time
        
        dm.apply_decay(m1)
        dm.apply_decay(m2)
        
        # Consolidada decaiu menos
        assert m2.importance > m1.importance


class TestDecayManagerConfig:
    """Testes de configuração do DecayManager."""
    
    def test_custom_config(self):
        """Aceita configuração customizada."""
        config = DecayConfig(
            daily_decay_rate=0.90,
            forgotten_threshold=0.2,
            hub_min_references=10,
        )
        dm = DecayManager(config)
        
        assert dm.config.daily_decay_rate == 0.90
        assert dm.config.forgotten_threshold == 0.2
        assert dm.config.hub_min_references == 10
    
    def test_min_importance_prevents_zero(self):
        """min_importance previne importance de ir a zero."""
        config = DecayConfig(min_importance=0.05)
        dm = DecayManager(config)
        
        memory = Memory(what="test", importance=0.1)
        memory.when = datetime.now() - timedelta(days=365)  # 1 ano
        memory.last_accessed = memory.when
        
        dm.apply_decay(memory)
        
        assert memory.importance >= config.min_importance


class TestMemoryToSummary:
    """Testes de geração de resumo."""
    
    def test_basic_summary(self):
        """Gera resumo básico."""
        memory = Memory(
            who=["user"],
            what="solicitou ajuda",
            how="resolvido via chat",
        )
        
        summary = memory.to_summary()
        
        assert "user" in summary
        assert "solicitou ajuda" in summary
        assert "resolvido via chat" in summary
    
    def test_consolidated_summary_shows_count(self):
        """Resumo de memória consolidada mostra contagem."""
        memory = Memory(
            what="padrão repetido",
            occurrence_count=5,
            consolidated_from=["a", "b", "c", "d", "e"],
        )
        
        summary = memory.to_summary()
        
        assert "[5x]" in summary
    
    def test_many_participants_truncated(self):
        """Muitos participantes são truncados."""
        memory = Memory(
            who=["user1", "user2", "user3", "user4", "user5"],
            what="reunião",
        )
        
        summary = memory.to_summary()
        
        assert "+2" in summary  # 5 - 3 = 2 extras
