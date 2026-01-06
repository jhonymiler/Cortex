"""
DecayManager - Gerencia decaimento de memórias baseado em Ebbinghaus.

O decaimento simula o esquecimento natural:
- Memórias não acessadas perdem importância ao longo do tempo
- Memórias acessadas frequentemente são reforçadas
- Hubs (memórias muito referenciadas) decaem mais lentamente
- Memórias consolidadas são mais duráveis

Baseado na Curva de Esquecimento de Ebbinghaus (1885):
    R = e^(-t/S)

Onde:
    R = retrievability (facilidade de recuperação)
    t = tempo desde último acesso
    S = stability (durabilidade da memória)
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Any

if TYPE_CHECKING:
    from cortex.core.memory import Memory
    from cortex.core.memory_graph import MemoryGraph


@dataclass
class DecayConfig:
    """Configuração do sistema de decaimento."""
    
    # Taxa de decaimento diário base (5% por dia)
    daily_decay_rate: float = 0.95
    
    # Multiplicadores
    consolidation_bonus: float = 2.0  # Memórias consolidadas decaem 2x mais lento
    hub_bonus: float = 1.5  # Hubs decaem 1.5x mais lento
    high_importance_bonus: float = 1.3  # importance > 0.7 decai 1.3x mais lento
    
    # Thresholds
    forgotten_threshold: float = 0.1  # Abaixo disso = esquecida
    hub_min_references: int = 5  # Mínimo de referências para ser hub
    
    # Limites
    min_importance: float = 0.01  # Nunca vai abaixo disso
    max_stability: float = 10.0  # Limite de stability
    
    # Spaced repetition
    touch_stability_increase: float = 1.2  # Cada acesso aumenta stability em 20%


class DecayManager:
    """
    Gerencia decaimento de memórias.
    
    Responsabilidades:
    - Aplicar decaimento periódico a todas as memórias
    - Calcular retrievability
    - Marcar memórias como "esquecidas"
    - Reforçar memórias acessadas
    
    Example:
        decay_manager = DecayManager()
        
        # Aplicar decaimento diário
        decay_manager.apply_decay_batch(graph)
        
        # Quando memória é acessada
        decay_manager.touch(memory)
    """
    
    def __init__(self, config: Optional[DecayConfig] = None):
        """
        Inicializa o gerenciador de decaimento.
        
        Args:
            config: Configuração customizada (usa defaults se None)
        """
        self.config = config or DecayConfig()
    
    def apply_decay(self, memory: "Memory", graph: Optional["MemoryGraph"] = None) -> None:
        """
        Aplica decaimento a uma memória individual.
        
        Args:
            memory: Memória a processar
            graph: Grafo para calcular centralidade (opcional)
        """
        # Calcula dias desde último acesso
        reference_time = memory.last_accessed or memory.when
        days_since = (datetime.now() - reference_time).total_seconds() / 86400
        
        if days_since < 1:
            return  # Menos de 1 dia, sem decaimento
        
        # Calcula multiplicadores
        total_multiplier = 1.0
        
        # Bonus para memórias consolidadas
        if memory.is_consolidated:
            total_multiplier *= self.config.consolidation_bonus
        
        # Bonus para hubs
        if graph and self._is_hub(memory, graph):
            total_multiplier *= self.config.hub_bonus
        
        # Bonus para alta importância
        if memory.importance > 0.7:
            total_multiplier *= self.config.high_importance_bonus
        
        # Aplica decaimento
        # importance_new = importance_old * (decay_rate ^ days) * multiplier_adjustment
        effective_days = days_since / total_multiplier
        decay_factor = self.config.daily_decay_rate ** effective_days
        
        memory.importance = max(
            self.config.min_importance,
            memory.importance * decay_factor
        )
        
        # Marca como esquecida se abaixo do threshold
        if memory.importance < self.config.forgotten_threshold:
            memory.metadata["forgotten"] = True
    
    def apply_decay_batch(
        self, 
        graph: "MemoryGraph",
        only_active: bool = True
    ) -> dict[str, int]:
        """
        Aplica decaimento a todas as memórias do grafo.
        
        Args:
            graph: Grafo de memória
            only_active: Se True, pula memórias já esquecidas
        
        Returns:
            Estatísticas do processamento
        """
        stats = {
            "processed": 0,
            "decayed": 0,
            "forgotten": 0,
            "skipped": 0,
        }
        
        for memory in graph.get_all_memories():
            # Pula já esquecidas se only_active
            if only_active and memory.is_forgotten:
                stats["skipped"] += 1
                continue
            
            old_importance = memory.importance
            self.apply_decay(memory, graph)
            stats["processed"] += 1
            
            if memory.importance < old_importance:
                stats["decayed"] += 1
            
            if memory.is_forgotten and old_importance >= self.config.forgotten_threshold:
                stats["forgotten"] += 1
        
        return stats
    
    def touch(self, memory: "Memory") -> None:
        """
        Marca memória como acessada, reforçando-a.
        
        Efeitos:
        - Incrementa access_count
        - Atualiza last_accessed
        - Aumenta stability (spaced repetition)
        - Aumenta importance levemente
        - Remove flag "forgotten" se existir
        
        Args:
            memory: Memória acessada
        """
        memory.access_count += 1
        memory.last_accessed = datetime.now()
        
        # Spaced repetition: cada acesso aumenta stability
        memory.stability = min(
            self.config.max_stability,
            memory.stability * self.config.touch_stability_increase
        )
        
        # Leve boost de importância
        memory.importance = min(1.0, memory.importance * 1.05)
        
        # Revive se esquecida
        if memory.metadata.get("forgotten"):
            del memory.metadata["forgotten"]
            memory.importance = max(memory.importance, 0.3)  # Volta com importância mínima
    
    def calculate_retrievability(self, memory: "Memory") -> float:
        """
        Calcula retrievability (facilidade de recuperação).
        
        Usa a fórmula de Ebbinghaus: R = e^(-t/S)
        
        Args:
            memory: Memória para calcular
        
        Returns:
            float entre 0.0 (impossível) e 1.0 (fácil)
        """
        return memory.retrievability
    
    def _is_hub(self, memory: "Memory", graph: "MemoryGraph") -> bool:
        """
        Verifica se a memória é um hub (muito referenciada).
        
        Args:
            memory: Memória a verificar
            graph: Grafo para contar referências
        
        Returns:
            True se for hub
        """
        incoming = graph.count_relations_to(memory.id)
        return incoming >= self.config.hub_min_references
    
    def get_memory_health(self, memory: "Memory") -> dict[str, Any]:
        """
        Retorna status de "saúde" de uma memória.
        
        Args:
            memory: Memória a analisar
        
        Returns:
            Dict com métricas de saúde
        """
        retrievability = self.calculate_retrievability(memory)
        
        # Classifica estado
        if memory.is_forgotten:
            status = "forgotten"
        elif retrievability > 0.7:
            status = "fresh"
        elif retrievability > 0.4:
            status = "stable"
        elif retrievability > 0.1:
            status = "fading"
        else:
            status = "near_forgotten"
        
        # Estima dias até esquecimento
        if retrievability > self.config.forgotten_threshold:
            # Resolve para t: forgotten_threshold = e^(-t/S)
            # ln(threshold) = -t/S
            # t = -S * ln(threshold)
            effective_stability = memory.stability * (1 + math.log(memory.access_count + 1))
            if memory.is_consolidated:
                effective_stability *= self.config.consolidation_bonus
            
            days_until_forgotten = -effective_stability * math.log(self.config.forgotten_threshold / max(retrievability, 0.01))
            days_until_forgotten = max(0, days_until_forgotten)
        else:
            days_until_forgotten = 0
        
        return {
            "status": status,
            "retrievability": round(retrievability, 3),
            "importance": round(memory.importance, 3),
            "stability": round(memory.stability, 3),
            "access_count": memory.access_count,
            "days_until_forgotten": round(days_until_forgotten, 1),
            "is_hub": memory._centrality_score > 0.5,
            "is_consolidated": memory.is_consolidated,
        }


def create_default_decay_manager() -> DecayManager:
    """Cria DecayManager com configuração padrão."""
    return DecayManager()


def create_aggressive_decay_manager() -> DecayManager:
    """Cria DecayManager com decaimento mais agressivo (para testes)."""
    return DecayManager(DecayConfig(
        daily_decay_rate=0.80,  # 20% por dia
        forgotten_threshold=0.2,
    ))


def create_gentle_decay_manager() -> DecayManager:
    """Cria DecayManager com decaimento mais suave (para memórias importantes)."""
    return DecayManager(DecayConfig(
        daily_decay_rate=0.98,  # 2% por dia
        forgotten_threshold=0.05,
        consolidation_bonus=3.0,
    ))
