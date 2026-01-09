"""
DecayManager - Gerencia decaimento de memórias baseado em Ebbinghaus.

Implementa:
- Curva de esquecimento exponencial: R = e^(-t/S)
- Spaced repetition: acessos aumentam stability
- Hub protection: memórias centrais decaem mais lentamente
- Consolidation bonus: memórias consolidadas são mais estáveis

Baseado em:
- Ebbinghaus (1885) - Forgetting Curve
- CoALA - Cognitive Architectures for Language Agents
- Generative Agents (Stanford)
"""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cortex.core.memory_graph import MemoryGraph
    from cortex.core.episode import Episode
    from cortex.core.entity import Entity


@dataclass
class DecayConfig:
    """Configuração do sistema de decaimento."""
    
    # Taxa base de decaimento (dias para reduzir 63% sem reforço)
    base_stability_days: float = 7.0
    
    # Multiplicadores de proteção
    consolidation_bonus: float = 2.0  # Memórias consolidadas decaem 2x mais lento
    hub_bonus: float = 1.5  # Hubs decaem 1.5x mais lento
    high_importance_bonus: float = 1.3  # Importância > 0.7 decai mais lento
    
    # Thresholds
    forgotten_threshold: float = 0.1  # Abaixo disso = esquecido
    weak_threshold: float = 0.3  # Abaixo disso = fraco
    hub_reference_threshold: int = 5  # 5+ referências = hub
    
    # Limites
    min_stability: float = 0.1  # Estabilidade mínima
    max_stability: float = 100.0  # Estabilidade máxima
    
    # Spaced repetition multiplier (cada acesso aumenta stability)
    access_stability_multiplier: float = 1.2


class DecayManager:
    """
    Gerencia o decaimento de memórias baseado na curva de Ebbinghaus.
    
    Formula: R = e^(-t/S)
    Onde:
        R = retrievability (0.0 - 1.0)
        t = tempo desde último acesso (dias)
        S = stability (durabilidade da memória)
    
    Stability é afetada por:
        - access_count (spaced repetition)
        - centrality (hubs são mais estáveis)
        - consolidation (memórias consolidadas são mais estáveis)
        - importance declarada
    """
    
    def __init__(self, config: DecayConfig | None = None):
        self.config = config or DecayConfig()
        self._centrality_cache: dict[str, float] = {}
    
    def calculate_retrievability(
        self,
        last_accessed: datetime,
        stability: float,
        now: datetime | None = None,
    ) -> float:
        """
        Calcula a facilidade de recuperação de uma memória.
        
        Args:
            last_accessed: Quando foi acessada pela última vez
            stability: Estabilidade atual da memória
            now: Momento atual (default: agora)
            
        Returns:
            Retrievability entre 0.0 e 1.0
        """
        now = now or datetime.now()
        days_since = (now - last_accessed).total_seconds() / 86400  # Converte para dias
        
        if days_since <= 0:
            return 1.0
        
        # R = e^(-t/S)
        effective_stability = max(self.config.min_stability, stability)
        retrievability = math.exp(-days_since / effective_stability)
        
        return max(0.0, min(1.0, retrievability))
    
    def calculate_stability(
        self,
        access_count: int,
        centrality: float = 0.0,
        is_consolidated: bool = False,
        importance: float = 0.5,
    ) -> float:
        """
        Calcula a estabilidade de uma memória.
        
        Stability = base × (1 + log(access + 1)) × bonuses
        
        Args:
            access_count: Quantas vezes foi acessada
            centrality: Score de centralidade (0.0 - 1.0)
            is_consolidated: Se é uma memória consolidada
            importance: Importância declarada (0.0 - 1.0)
            
        Returns:
            Estabilidade (dias)
        """
        base = self.config.base_stability_days
        
        # Spaced repetition: cada acesso aumenta estabilidade logaritmicamente
        access_factor = 1 + math.log(access_count + 1)
        
        # Bônus por centralidade
        centrality_factor = 1 + (centrality * (self.config.hub_bonus - 1))
        
        # Bônus por consolidação
        consolidation_factor = self.config.consolidation_bonus if is_consolidated else 1.0
        
        # Bônus por alta importância
        importance_factor = self.config.high_importance_bonus if importance > 0.7 else 1.0
        
        stability = base * access_factor * centrality_factor * consolidation_factor * importance_factor
        
        return min(self.config.max_stability, stability)
    
    def calculate_entity_centrality(
        self,
        entity_id: str,
        graph: "MemoryGraph",
    ) -> float:
        """
        Calcula a centralidade de uma entidade no grafo.
        
        Centrality = log(1 + incoming_relations + episodes_referencing)
        
        Normalizado para 0.0 - 1.0
        """
        # Conta relações de entrada
        incoming = len(graph.get_relations(to_id=entity_id))
        
        # Conta episódios que referenciam esta entidade
        referencing_episodes = sum(
            1 for ep in graph._episodes.values()
            if entity_id in ep.participants
        )
        
        total_references = incoming + referencing_episodes
        
        # Log para suavizar
        raw_centrality = math.log(1 + total_references)
        
        # Normaliza baseado no threshold de hub
        normalized = min(1.0, raw_centrality / math.log(1 + self.config.hub_reference_threshold * 2))
        
        return normalized
    
    def calculate_episode_centrality(
        self,
        episode_id: str,
        graph: "MemoryGraph",
    ) -> float:
        """
        Calcula a centralidade de um episódio no grafo.
        
        Episódios são centrais se:
        - Conectam entidades importantes
        - São referenciados por outras relações
        - Têm muitos participantes
        - São mencionados textualmente por outros episódios
        """
        episode = graph.get_episode(episode_id)
        if not episode:
            return 0.0
        
        # Fator 1: Número de participantes
        participant_factor = math.log(1 + len(episode.participants)) / 3  # Normalizado
        
        # Fator 2: Centralidade média dos participantes
        participant_centralities = []
        for pid in episode.participants:
            if pid in self._centrality_cache:
                participant_centralities.append(self._centrality_cache[pid])
            else:
                centrality = self.calculate_entity_centrality(pid, graph)
                self._centrality_cache[pid] = centrality
                participant_centralities.append(centrality)
        
        avg_participant_centrality = (
            sum(participant_centralities) / len(participant_centralities)
            if participant_centralities else 0.0
        )
        
        # Fator 3: Relações de entrada (grafo explícito)
        incoming = len(graph.get_relations(to_id=episode_id))
        relation_factor = min(1.0, incoming / self.config.hub_reference_threshold)
        
        # Fator 4: Referências textuais implícitas
        # Conta quantos episódios mencionam action/outcome/context deste episódio
        textual_references = self._count_textual_references(episode, graph)
        textual_factor = min(1.0, textual_references / self.config.hub_reference_threshold)
        
        # Combina fatores (inclui referências textuais)
        centrality = (
            (participant_factor * 0.2) + 
            (avg_participant_centrality * 0.3) + 
            (relation_factor * 0.2) +
            (textual_factor * 0.3)  # Referências textuais são importantes
        )
        
        return min(1.0, centrality)
    
    def _count_textual_references(
        self,
        episode: "Episode",
        graph: "MemoryGraph",
    ) -> int:
        """
        Conta quantos outros episódios referenciam este textualmente.
        
        Verifica se action, outcome ou w5h.what deste episódio aparecem
        no context, why ou action de outros episódios.
        """
        if not episode:
            return 0
        
        # Termos-chave deste episódio
        key_terms = set()
        if episode.action:
            key_terms.add(episode.action.lower())
        if episode.outcome:
            key_terms.add(episode.outcome.lower())
        
        # Adiciona W5H se disponível
        w5h = episode.metadata.get("w5h", {})
        if w5h.get("what"):
            key_terms.add(str(w5h["what"]).lower())
        
        if not key_terms:
            return 0
        
        # Conta referências em outros episódios
        count = 0
        for other_id, other in graph._episodes.items():
            if other_id == episode.id:
                continue
            
            # Verifica se algum termo-chave aparece no contexto/why do outro
            other_text = (
                (other.context or "") + " " +
                (other.metadata.get("w5h", {}).get("why", "") or "")
            ).lower()
            
            for term in key_terms:
                if term in other_text:
                    count += 1
                    break  # Só conta uma vez por episódio
        
        return count
    
    def is_hub(self, entity_or_episode_id: str, graph: "MemoryGraph") -> bool:
        """Verifica se uma memória é um hub (altamente conectada)."""
        incoming = len(graph.get_relations(to_id=entity_or_episode_id))
        outgoing = len(graph.get_relations(from_id=entity_or_episode_id))
        return (incoming + outgoing) >= self.config.hub_reference_threshold
    
    def apply_decay_to_episode(
        self,
        episode: "Episode",
        graph: "MemoryGraph",
        now: datetime | None = None,
    ) -> tuple[float, float]:
        """
        Aplica decaimento a um episódio e retorna (retrievability, new_stability).
        
        Não modifica o episódio diretamente - retorna valores calculados.
        """
        now = now or datetime.now()
        
        # Último acesso (usa timestamp se nunca foi acessado)
        last_accessed = getattr(episode, 'last_accessed', None) or episode.timestamp
        
        # Calcula centralidade
        centrality = self.calculate_episode_centrality(episode.id, graph)
        
        # Calcula estabilidade
        access_count = getattr(episode, 'access_count', 0)
        stability = self.calculate_stability(
            access_count=access_count,
            centrality=centrality,
            is_consolidated=episode.is_consolidated,
            importance=episode.importance,
        )
        
        # Calcula retrievability
        retrievability = self.calculate_retrievability(last_accessed, stability, now)
        
        return retrievability, stability
    
    def apply_decay_to_entity(
        self,
        entity: "Entity",
        graph: "MemoryGraph",
        now: datetime | None = None,
    ) -> tuple[float, float]:
        """
        Aplica decaimento a uma entidade e retorna (retrievability, new_stability).
        """
        now = now or datetime.now()
        
        last_accessed = entity.last_accessed or entity.created_at
        centrality = self.calculate_entity_centrality(entity.id, graph)
        
        # Entidades consolidadas implicitamente (se referenciadas em muitos episódios)
        episode_count = sum(
            1 for ep in graph._episodes.values()
            if entity.id in ep.participants
        )
        is_consolidated = episode_count >= 5
        
        stability = self.calculate_stability(
            access_count=entity.access_count,
            centrality=centrality,
            is_consolidated=is_consolidated,
            importance=0.5,  # Entidades têm importância base
        )
        
        retrievability = self.calculate_retrievability(last_accessed, stability, now)
        
        return retrievability, stability
    
    def get_memory_status(self, retrievability: float) -> str:
        """
        Retorna o status de uma memória baseado na retrievability.
        
        Returns:
            "active" | "fading" | "weak" | "forgotten"
        """
        if retrievability >= 0.7:
            return "active"
        elif retrievability >= self.config.weak_threshold:
            return "fading"
        elif retrievability >= self.config.forgotten_threshold:
            return "weak"
        else:
            return "forgotten"
    
    def touch_memory(
        self,
        entity_or_episode: "Entity | Episode",
        graph: "MemoryGraph",
    ) -> float:
        """
        Marca uma memória como acessada, aumentando sua estabilidade.
        
        Implementa spaced repetition - cada acesso fortalece a memória.
        
        Returns:
            Nova estabilidade após o touch
        """
        # Aumenta access_count
        if hasattr(entity_or_episode, 'touch'):
            entity_or_episode.touch()
        else:
            # Fallback para episódios (não tem touch nativo)
            if hasattr(entity_or_episode, 'access_count'):
                entity_or_episode.access_count = getattr(entity_or_episode, 'access_count', 0) + 1
            entity_or_episode.last_accessed = datetime.now()
        
        # Recalcula estabilidade
        if hasattr(entity_or_episode, 'participants'):  # É Episode
            _, stability = self.apply_decay_to_episode(entity_or_episode, graph)
        else:  # É Entity
            _, stability = self.apply_decay_to_entity(entity_or_episode, graph)
        
        return stability
    
    def run_decay_cycle(
        self,
        graph: "MemoryGraph",
        now: datetime | None = None,
    ) -> dict[str, int]:
        """
        Executa um ciclo de decaimento em todo o grafo.
        
        Este método deve ser chamado periodicamente (ex: diariamente).
        
        Returns:
            Estatísticas do ciclo
        """
        now = now or datetime.now()
        stats = {
            "episodes_active": 0,
            "episodes_fading": 0,
            "episodes_weak": 0,
            "episodes_forgotten": 0,
            "entities_active": 0,
            "entities_fading": 0,
            "entities_weak": 0,
            "entities_forgotten": 0,
            "hubs_protected": 0,
        }
        
        # Limpa cache de centralidade
        self._centrality_cache.clear()
        
        # Processa episódios
        for episode in list(graph._episodes.values()):
            retrievability, stability = self.apply_decay_to_episode(episode, graph, now)
            status = self.get_memory_status(retrievability)
            
            # Atualiza metadata do episódio
            episode.metadata["retrievability"] = retrievability
            episode.metadata["stability"] = stability
            episode.metadata["decay_status"] = status
            
            stats[f"episodes_{status}"] += 1
            
            if self.is_hub(episode.id, graph):
                stats["hubs_protected"] += 1
        
        # Processa entidades
        for entity in list(graph._entities.values()):
            retrievability, stability = self.apply_decay_to_entity(entity, graph, now)
            status = self.get_memory_status(retrievability)
            
            # Atualiza attributes da entidade
            entity.attributes["retrievability"] = retrievability
            entity.attributes["stability"] = stability
            entity.attributes["decay_status"] = status
            
            stats[f"entities_{status}"] += 1
            
            if self.is_hub(entity.id, graph):
                stats["hubs_protected"] += 1
        
        return stats
    
    def get_decay_report(self, graph: "MemoryGraph") -> dict:
        """
        Gera relatório detalhado do estado de decaimento.
        """
        now = datetime.now()
        
        episodes_by_status: dict[str, list] = {
            "active": [], "fading": [], "weak": [], "forgotten": []
        }
        entities_by_status: dict[str, list] = {
            "active": [], "fading": [], "weak": [], "forgotten": []
        }
        
        for episode in graph._episodes.values():
            retrievability, _ = self.apply_decay_to_episode(episode, graph, now)
            status = self.get_memory_status(retrievability)
            episodes_by_status[status].append({
                "id": episode.id,
                "action": episode.action,
                "retrievability": round(retrievability, 3),
                "is_hub": self.is_hub(episode.id, graph),
            })
        
        for entity in graph._entities.values():
            retrievability, _ = self.apply_decay_to_entity(entity, graph, now)
            status = self.get_memory_status(retrievability)
            entities_by_status[status].append({
                "id": entity.id,
                "name": entity.name,
                "retrievability": round(retrievability, 3),
                "is_hub": self.is_hub(entity.id, graph),
            })
        
        return {
            "timestamp": now.isoformat(),
            "episodes": {
                status: len(items) for status, items in episodes_by_status.items()
            },
            "entities": {
                status: len(items) for status, items in entities_by_status.items()
            },
            "top_active_episodes": sorted(
                episodes_by_status["active"],
                key=lambda x: x["retrievability"],
                reverse=True,
            )[:10],
            "top_active_entities": sorted(
                entities_by_status["active"],
                key=lambda x: x["retrievability"],
                reverse=True,
            )[:10],
            "forgotten_episodes": episodes_by_status["forgotten"][:10],
            "forgotten_entities": entities_by_status["forgotten"][:10],
        }


# Factory functions
def create_decay_manager(config: DecayConfig | None = None) -> DecayManager:
    """Cria um DecayManager com configuração padrão ou customizada."""
    return DecayManager(config)


def create_default_decay_manager() -> DecayManager:
    """Cria DecayManager com configuração padrão (7 dias base stability)."""
    return DecayManager(DecayConfig())


def create_aggressive_decay_manager() -> DecayManager:
    """Cria DecayManager agressivo (3 dias base stability, esquece rápido)."""
    return DecayManager(DecayConfig(
        base_stability_days=3.0,
        forgotten_threshold=0.15,
        weak_threshold=0.4,
    ))


def create_gentle_decay_manager() -> DecayManager:
    """Cria DecayManager gentil (14 dias base stability, esquece devagar)."""
    return DecayManager(DecayConfig(
        base_stability_days=14.0,
        forgotten_threshold=0.05,
        weak_threshold=0.2,
        hub_bonus=2.0,
        consolidation_bonus=3.0,
    ))
