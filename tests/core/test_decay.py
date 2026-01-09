"""
Testes unitários para DecayManager.

Testa:
- Cálculo de retrievability (curva de Ebbinghaus)
- Cálculo de stability (spaced repetition)
- Proteção de hubs
- Ciclo de decay
"""

import pytest
import math
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cortex.core.decay import (
    DecayManager,
    DecayConfig,
    create_decay_manager,
    create_default_decay_manager,
    create_aggressive_decay_manager,
    create_gentle_decay_manager,
)


class TestDecayConfig:
    """Testes para configuração de decay."""
    
    def test_default_config(self):
        config = DecayConfig()
        assert config.base_stability_days == 7.0
        assert config.consolidation_bonus == 2.0
        assert config.hub_bonus == 1.5
        assert config.forgotten_threshold == 0.1
        assert config.weak_threshold == 0.3
    
    def test_custom_config(self):
        config = DecayConfig(
            base_stability_days=14.0,
            consolidation_bonus=3.0,
            hub_bonus=2.0,
        )
        assert config.base_stability_days == 14.0
        assert config.consolidation_bonus == 3.0
        assert config.hub_bonus == 2.0


class TestRetrievabilityCalculation:
    """Testes para cálculo de retrievability (Ebbinghaus)."""
    
    def setup_method(self):
        self.manager = DecayManager()
    
    def test_fresh_memory_has_full_retrievability(self):
        """Memória recém-acessada tem retrievability = 1.0."""
        now = datetime.now()
        retrievability = self.manager.calculate_retrievability(
            last_accessed=now,
            stability=1.0,
            now=now,
        )
        assert retrievability == 1.0
    
    def test_old_memory_decays(self):
        """Memória antiga tem retrievability menor."""
        now = datetime.now()
        one_day_ago = now - timedelta(days=1)
        
        retrievability = self.manager.calculate_retrievability(
            last_accessed=one_day_ago,
            stability=1.0,
            now=now,
        )
        
        # Com stability=1 e t=1, R = e^(-1) ≈ 0.368
        assert 0.35 < retrievability < 0.40
    
    def test_ebbinghaus_formula(self):
        """Verifica fórmula R = e^(-t/S)."""
        now = datetime.now()
        days_since = 7
        last_accessed = now - timedelta(days=days_since)
        stability = 7.0  # Base
        
        retrievability = self.manager.calculate_retrievability(
            last_accessed=last_accessed,
            stability=stability,
            now=now,
        )
        
        # R = e^(-7/7) = e^(-1) ≈ 0.368
        expected = math.exp(-days_since / stability)
        assert abs(retrievability - expected) < 0.01
    
    def test_high_stability_slows_decay(self):
        """Alta estabilidade faz memória decair mais lentamente."""
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)
        
        low_stability = self.manager.calculate_retrievability(
            last_accessed=one_week_ago,
            stability=1.0,
            now=now,
        )
        
        high_stability = self.manager.calculate_retrievability(
            last_accessed=one_week_ago,
            stability=14.0,
            now=now,
        )
        
        assert high_stability > low_stability
    
    def test_retrievability_never_negative(self):
        """Retrievability nunca é negativo."""
        now = datetime.now()
        very_old = now - timedelta(days=365)
        
        retrievability = self.manager.calculate_retrievability(
            last_accessed=very_old,
            stability=1.0,
            now=now,
        )
        
        assert retrievability >= 0.0
    
    def test_retrievability_never_exceeds_one(self):
        """Retrievability nunca excede 1.0."""
        now = datetime.now()
        
        retrievability = self.manager.calculate_retrievability(
            last_accessed=now,
            stability=100.0,
            now=now,
        )
        
        assert retrievability <= 1.0


class TestStabilityCalculation:
    """Testes para cálculo de stability (spaced repetition)."""
    
    def setup_method(self):
        self.manager = DecayManager()
    
    def test_base_stability(self):
        """Sem modificadores, retorna base stability."""
        stability = self.manager.calculate_stability(
            access_count=0,
            centrality=0.0,
            is_consolidated=False,
            importance=0.5,
        )
        
        # Base = 7.0, com log(1) = 0, então 7 * 1 = 7
        assert 6.9 < stability < 7.1
    
    def test_access_count_increases_stability(self):
        """Mais acessos = maior stability (spaced repetition)."""
        no_access = self.manager.calculate_stability(access_count=0)
        many_accesses = self.manager.calculate_stability(access_count=10)
        
        assert many_accesses > no_access
    
    def test_consolidation_bonus(self):
        """Memórias consolidadas têm maior stability."""
        normal = self.manager.calculate_stability(
            access_count=0,
            is_consolidated=False,
        )
        consolidated = self.manager.calculate_stability(
            access_count=0,
            is_consolidated=True,
        )
        
        # Consolidation bonus = 2x
        assert consolidated == normal * 2
    
    def test_hub_bonus(self):
        """Hubs (alta centralidade) têm maior stability."""
        normal = self.manager.calculate_stability(
            access_count=0,
            centrality=0.0,
        )
        hub = self.manager.calculate_stability(
            access_count=0,
            centrality=1.0,
        )
        
        assert hub > normal
    
    def test_high_importance_bonus(self):
        """Alta importância (>0.7) dá bônus de stability."""
        low_importance = self.manager.calculate_stability(
            access_count=0,
            importance=0.5,
        )
        high_importance = self.manager.calculate_stability(
            access_count=0,
            importance=0.9,
        )
        
        assert high_importance > low_importance
    
    def test_stability_respects_max_limit(self):
        """Stability não excede o máximo configurado."""
        config = DecayConfig(max_stability=10.0)
        manager = DecayManager(config)
        
        stability = manager.calculate_stability(
            access_count=1000,
            centrality=1.0,
            is_consolidated=True,
            importance=1.0,
        )
        
        assert stability <= config.max_stability


class TestMemoryStatus:
    """Testes para classificação de status de memória."""
    
    def setup_method(self):
        self.manager = DecayManager()
    
    def test_active_status(self):
        """Retrievability >= 0.7 é 'active'."""
        assert self.manager.get_memory_status(0.9) == "active"
        assert self.manager.get_memory_status(0.7) == "active"
    
    def test_fading_status(self):
        """0.3 <= Retrievability < 0.7 é 'fading'."""
        assert self.manager.get_memory_status(0.5) == "fading"
        assert self.manager.get_memory_status(0.3) == "fading"
    
    def test_weak_status(self):
        """0.1 <= Retrievability < 0.3 é 'weak'."""
        assert self.manager.get_memory_status(0.2) == "weak"
        assert self.manager.get_memory_status(0.1) == "weak"
    
    def test_forgotten_status(self):
        """Retrievability < 0.1 é 'forgotten'."""
        assert self.manager.get_memory_status(0.05) == "forgotten"
        assert self.manager.get_memory_status(0.0) == "forgotten"


class TestFactoryFunctions:
    """Testes para factory functions."""
    
    def test_create_default_decay_manager(self):
        manager = create_default_decay_manager()
        assert manager.config.base_stability_days == 7.0
    
    def test_create_aggressive_decay_manager(self):
        manager = create_aggressive_decay_manager()
        assert manager.config.base_stability_days == 3.0
        assert manager.config.forgotten_threshold == 0.15
    
    def test_create_gentle_decay_manager(self):
        manager = create_gentle_decay_manager()
        assert manager.config.base_stability_days == 14.0
        assert manager.config.hub_bonus == 2.0
    
    def test_create_decay_manager_with_custom_config(self):
        config = DecayConfig(base_stability_days=30.0)
        manager = create_decay_manager(config)
        assert manager.config.base_stability_days == 30.0


class TestHubDetection:
    """Testes para detecção de hubs."""
    
    def setup_method(self):
        self.manager = DecayManager()
    
    def test_is_hub_with_many_connections(self):
        """Entidade com 5+ conexões é hub."""
        # Mock do grafo
        graph = MagicMock()
        graph.get_relations.return_value = [1, 2, 3, 4, 5]  # 5 relações
        
        assert self.manager.is_hub("entity_1", graph)
    
    def test_is_not_hub_with_few_connections(self):
        """Entidade com <5 conexões não é hub."""
        graph = MagicMock()
        graph.get_relations.return_value = [1, 2]  # 2 relações
        
        assert not self.manager.is_hub("entity_1", graph)


class TestIntegration:
    """Testes de integração com cenários reais."""
    
    def test_spaced_repetition_scenario(self):
        """Simula cenário de spaced repetition."""
        manager = create_default_decay_manager()
        
        # Dia 1: primeira visualização
        stability_day1 = manager.calculate_stability(access_count=1)
        
        # Dia 2: segunda visualização
        stability_day2 = manager.calculate_stability(access_count=2)
        
        # Dia 5: terceira visualização
        stability_day5 = manager.calculate_stability(access_count=3)
        
        # Stability aumenta com cada acesso
        assert stability_day2 > stability_day1
        assert stability_day5 > stability_day2
    
    def test_hub_protection_scenario(self):
        """Hubs são protegidos contra decay rápido."""
        manager = create_default_decay_manager()
        
        # Memória normal
        normal_stability = manager.calculate_stability(
            access_count=2,
            centrality=0.0,
        )
        
        # Hub (alta centralidade)
        hub_stability = manager.calculate_stability(
            access_count=2,
            centrality=1.0,
        )
        
        # Hub tem stability maior
        assert hub_stability > normal_stability
        
        # Isso significa que hub decai mais lentamente
        now = datetime.now()
        one_week_ago = now - timedelta(days=7)
        
        normal_retrievability = manager.calculate_retrievability(
            last_accessed=one_week_ago,
            stability=normal_stability,
            now=now,
        )
        
        hub_retrievability = manager.calculate_retrievability(
            last_accessed=one_week_ago,
            stability=hub_stability,
            now=now,
        )
        
        # Hub é mais fácil de lembrar
        assert hub_retrievability > normal_retrievability


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
