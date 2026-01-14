"""
Testes unitários para Memory (modelo W5H).

Testa:
- Criação e validação de memórias
- Cálculo de retrievability
- Consolidação e similarity
- Serialização/deserialização
"""

import pytest
import math
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cortex.core.primitives import Memory, Episode


class TestMemoryCreation:
    """Testes para criação de memórias."""
    
    def test_create_basic_memory(self):
        """Cria memória básica com campos obrigatórios."""
        memory = Memory(
            who=["carlos"],
            what="solicitou_reembolso",
        )
        
        assert memory.who == ["carlos"]
        assert memory.what == "solicitou_reembolso"
        assert memory.id is not None
    
    def test_create_full_w5h_memory(self):
        """Cria memória com todos os campos W5H."""
        memory = Memory(
            who=["maria", "sistema_pagamentos"],
            what="reportou erro de pagamento",
            why="cartão expirado",
            when=datetime(2026, 1, 9, 10, 30),
            where="suporte_cliente",
            how="orientada a atualizar dados",
        )
        
        assert memory.who == ["maria", "sistema_pagamentos"]
        assert memory.what == "reportou erro de pagamento"
        assert memory.why == "cartão expirado"
        assert memory.where == "suporte_cliente"
        assert memory.how == "orientada a atualizar dados"
    
    def test_default_values(self):
        """Verifica valores default."""
        memory = Memory(what="teste")
        
        assert memory.who == []
        assert memory.why == ""
        assert memory.where == "default"
        assert memory.how == ""
        assert memory.importance == 0.5
        assert memory.stability == 1.0
        assert memory.access_count == 0
    
    def test_episode_is_alias_for_memory(self):
        """Episode é alias para Memory (compatibilidade)."""
        assert Episode is Memory


class TestRetrievability:
    """Testes para cálculo de retrievability (Ebbinghaus)."""
    
    def test_fresh_memory_has_high_retrievability(self):
        """Memória recém-criada tem alta retrievability."""
        memory = Memory(what="teste")
        
        # Memória acabou de ser criada
        assert memory.retrievability >= 0.9
    
    def test_old_memory_has_lower_retrievability(self):
        """Memória antiga tem retrievability menor."""
        memory = Memory(
            what="teste",
            when=datetime.now() - timedelta(days=7),
        )
        
        # Após 7 dias com stability=1, deve estar bem baixa
        assert memory.retrievability < 0.5
    
    def test_accessed_memory_has_higher_retrievability(self):
        """Memória acessada frequentemente tem maior retrievability."""
        memory = Memory(
            what="teste",
            when=datetime.now() - timedelta(days=3),
        )
        
        initial = memory.retrievability
        
        # Simula vários acessos
        for _ in range(5):
            memory.touch()
        
        # Após acessos, retrievability deve ser maior
        assert memory.retrievability > initial
    
    def test_consolidated_memory_decays_slower(self):
        """Memória consolidada decai mais lentamente."""
        normal = Memory(
            what="teste",
            when=datetime.now() - timedelta(days=3),
        )
        
        consolidated = Memory(
            what="teste",
            when=datetime.now() - timedelta(days=3),
            consolidated_from=["mem1", "mem2", "mem3"],
        )
        
        assert consolidated.retrievability > normal.retrievability
    
    def test_consolidated_child_decays_faster(self):
        """Memória que foi consolidada (filha) decai mais rápido."""
        parent = Memory(
            what="teste",
            when=datetime.now() - timedelta(days=3),
        )
        
        child = Memory(
            what="teste",
            when=datetime.now() - timedelta(days=3),
            consolidated_into="parent_id",
        )
        
        assert child.retrievability < parent.retrievability
    
    def test_centrality_affects_retrievability(self):
        """Alta centralidade aumenta retrievability."""
        normal = Memory(
            what="teste",
            when=datetime.now() - timedelta(days=3),
        )
        
        hub = Memory(
            what="teste",
            when=datetime.now() - timedelta(days=3),
        )
        hub.set_centrality(1.0)  # Alta centralidade
        
        assert hub.retrievability > normal.retrievability


class TestTouch:
    """Testes para método touch() (spaced repetition)."""
    
    def test_touch_increments_access_count(self):
        memory = Memory(what="teste")
        
        assert memory.access_count == 0
        memory.touch()
        assert memory.access_count == 1
        memory.touch()
        assert memory.access_count == 2
    
    def test_touch_updates_last_accessed(self):
        memory = Memory(what="teste")
        
        assert memory.last_accessed is None
        memory.touch()
        assert memory.last_accessed is not None
    
    def test_touch_increases_stability(self):
        memory = Memory(what="teste")
        
        initial_stability = memory.stability
        memory.touch()
        
        assert memory.stability > initial_stability
    
    def test_touch_has_max_stability(self):
        memory = Memory(what="teste")
        
        # Muitos acessos
        for _ in range(100):
            memory.touch()
        
        # Stability não excede 10.0
        assert memory.stability <= 10.0
    
    def test_touch_revives_forgotten_memory(self):
        memory = Memory(what="teste")
        memory.forget()
        
        assert memory.is_forgotten
        
        memory.touch()
        
        assert not memory.is_forgotten


class TestConsolidation:
    """Testes para consolidação de memórias."""
    
    def test_is_consolidated_with_sources(self):
        """Memória com sources é consolidada."""
        memory = Memory(
            what="teste",
            consolidated_from=["mem1", "mem2"],
        )
        
        assert memory.is_consolidated
    
    def test_is_consolidated_with_summary_flag(self):
        """Memória com is_summary=True é consolidada."""
        memory = Memory(what="teste", is_summary=True)
        
        assert memory.is_consolidated
    
    def test_was_consolidated(self):
        """Memória com consolidated_into foi consolidada em outra."""
        memory = Memory(
            what="teste",
            consolidated_into="parent_id",
        )
        
        assert memory.was_consolidated
    
    def test_occurrence_count(self):
        """Conta ocorrências para consolidação."""
        memory = Memory(what="teste")
        
        assert memory.occurrence_count == 1
        
        memory.occurrence_count = 5
        assert memory.occurrence_count == 5


class TestSimilarity:
    """Testes para cálculo de similaridade."""
    
    def test_identical_memories_have_high_similarity(self):
        """Memórias idênticas têm alta similaridade."""
        mem1 = Memory(
            who=["carlos"],
            what="solicitou_reembolso",
            where="suporte",
        )
        mem2 = Memory(
            who=["carlos"],
            what="solicitou_reembolso",
            where="suporte",
        )
        
        similarity = mem1.similarity_to(mem2)
        assert similarity >= 0.9
    
    def test_different_memories_have_low_similarity(self):
        """Memórias diferentes têm baixa similaridade."""
        mem1 = Memory(
            who=["carlos"],
            what="solicitou_reembolso",
            where="suporte",
        )
        mem2 = Memory(
            who=["maria"],
            what="reportou_bug",
            where="dev",
        )
        
        similarity = mem1.similarity_to(mem2)
        assert similarity < 0.3
    
    def test_partial_match(self):
        """Match parcial tem similaridade intermediária."""
        mem1 = Memory(
            who=["carlos", "maria"],
            what="discutiram_projeto",
            where="meeting",
        )
        mem2 = Memory(
            who=["carlos"],
            what="discutiram_projeto",
            where="meeting",
        )
        
        similarity = mem1.similarity_to(mem2)
        assert 0.5 < similarity < 0.9


class TestSerialization:
    """Testes para serialização/deserialização."""
    
    def test_to_dict(self):
        """Serializa memória para dicionário."""
        memory = Memory(
            who=["carlos"],
            what="teste",
            why="razão",
            where="local",
            how="método",
            importance=0.8,
        )
        
        data = memory.to_dict()
        
        assert data["who"] == ["carlos"]
        assert data["what"] == "teste"
        assert data["why"] == "razão"
        assert data["where"] == "local"
        assert data["how"] == "método"
        assert data["importance"] == 0.8
    
    def test_from_dict(self):
        """Deserializa memória de dicionário."""
        data = {
            "id": "test-id",
            "who": ["carlos"],
            "what": "teste",
            "why": "razão",
            "when": "2026-01-09T10:30:00",
            "where": "local",
            "how": "método",
            "importance": 0.8,
            "stability": 2.0,
            "access_count": 5,
        }
        
        memory = Memory.from_dict(data)
        
        assert memory.id == "test-id"
        assert memory.who == ["carlos"]
        assert memory.what == "teste"
        assert memory.importance == 0.8
        assert memory.access_count == 5
    
    def test_roundtrip(self):
        """Serialização -> deserialização mantém dados."""
        original = Memory(
            who=["carlos", "maria"],
            what="projeto_finalizado",
            why="deadline",
            where="dev",
            how="deploy_produção",
            importance=0.9,
        )
        original.touch()
        original.touch()
        
        data = original.to_dict()
        restored = Memory.from_dict(data)
        
        assert restored.who == original.who
        assert restored.what == original.what
        assert restored.importance == original.importance
        assert restored.access_count == original.access_count
    
    def test_to_w5h_dict(self):
        """Retorna apenas campos W5H."""
        memory = Memory(
            who=["carlos"],
            what="teste",
            why="razão",
            where="local",
            how="método",
            importance=0.9,  # Não deve aparecer
        )
        
        w5h = memory.to_w5h_dict()
        
        assert "who" in w5h
        assert "what" in w5h
        assert "why" in w5h
        assert "when" in w5h
        assert "where" in w5h
        assert "how" in w5h
        assert "importance" not in w5h


class TestToSummary:
    """Testes para geração de resumo."""
    
    def test_basic_summary(self):
        """Gera resumo básico."""
        memory = Memory(
            who=["carlos"],
            what="solicitou_reembolso",
        )
        
        summary = memory.to_summary()
        
        assert "carlos" in summary
        assert "solicitou_reembolso" in summary
    
    def test_summary_with_outcome(self):
        """Resumo inclui outcome."""
        memory = Memory(
            who=["carlos"],
            what="solicitou_reembolso",
            how="aprovado",
        )
        
        summary = memory.to_summary()
        
        assert "→ aprovado" in summary
    
    def test_summary_consolidated(self):
        """Resumo mostra contagem de consolidação."""
        memory = Memory(
            who=["carlos"],
            what="solicitou_reembolso",
            occurrence_count=5,
            consolidated_from=["m1", "m2"],
        )
        
        summary = memory.to_summary()
        
        assert "[5x]" in summary
    
    def test_summary_truncates_long_who_list(self):
        """Trunca lista longa de participantes."""
        memory = Memory(
            who=["alice", "bob", "carlos", "david", "eve"],
            what="reunião",
        )
        
        summary = memory.to_summary()
        
        assert "+2" in summary  # 5 - 3 = 2 extras


class TestForget:
    """Testes para esquecimento."""
    
    def test_forget_marks_as_forgotten(self):
        memory = Memory(what="teste")
        
        assert not memory.is_forgotten
        
        memory.forget()
        
        assert memory.is_forgotten
    
    def test_is_forgotten_checks_metadata(self):
        memory = Memory(what="teste")
        memory.metadata["forgotten"] = True
        
        assert memory.is_forgotten


class TestCentrality:
    """Testes para centralidade."""
    
    def test_set_centrality(self):
        memory = Memory(what="teste")
        
        memory.set_centrality(0.8)
        
        assert memory._centrality_score == 0.8
    
    def test_centrality_never_negative(self):
        memory = Memory(what="teste")
        
        memory.set_centrality(-0.5)
        
        assert memory._centrality_score == 0.0


class TestMetadata:
    """Testes para metadata."""
    
    def test_metadata_default_empty(self):
        memory = Memory(what="teste")
        
        assert memory.metadata == {}
    
    def test_metadata_can_store_arbitrary_data(self):
        memory = Memory(
            what="teste",
            metadata={"custom_field": "value", "number": 42},
        )
        
        assert memory.metadata["custom_field"] == "value"
        assert memory.metadata["number"] == 42


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
