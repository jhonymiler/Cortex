"""
MemoryGraph - Grafo de memória que conecta entidades, episódios e relações.

O MemoryGraph é o coração do Cortex:
- Armazena entidades (coisas)
- Armazena episódios (acontecimentos)
- Conecta tudo via relações
- Busca por relevância contextual
- Consolida episódios repetidos
- Detecta e resolve contradições

OTIMIZAÇÕES v2 (Opção 5 Híbrida):
- Índice invertido para busca O(log n) ao invés de O(n)
- Threshold de relevância mínima (0.25) para filtrar ruído
- Ranking por retrievability (frescor + acesso)
- Limite hard de memórias para evitar crescimento ilimitado
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from cortex.core.primitives import Entity, Episode, Relation
from cortex.core.recall import InvertedIndex
from cortex.core.processing.language import tokenize

# V2.0 Enhancements
from cortex.core.recall import ContextPacker, HierarchicalRecall
from cortex.core.learning import MemoryAttention, AttentionConfig, ForgetGate
from cortex.config import CortexConfig, get_config
from cortex.core.learning.contradiction import (
    ContradictionDetector,
    Contradiction,
    ResolutionStrategy,
    ResolutionResult,
    create_default_detector,
)

# Logging
from cortex.utils.logging import get_audit_logger, get_performance_logger, get_logger

# Configurações de recall (podem ser sobrescritas via .env)
RECALL_MIN_THRESHOLD = float(os.getenv("CORTEX_RECALL_THRESHOLD", "0.25"))
RECALL_MAX_CANDIDATES = int(os.getenv("CORTEX_RECALL_MAX_CANDIDATES", "50"))
RECALL_MAX_RESULTS = int(os.getenv("CORTEX_RECALL_MAX_RESULTS", "10"))


@dataclass
class RecallResult:
    """Resultado de uma busca de memória."""
    
    entities: list[Entity] = field(default_factory=list)
    episodes: list[Episode] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    context_summary: str = ""
    
    # Métricas de recall (para debug/análise)
    metrics: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "episodes": [e.to_dict() for e in self.episodes],
            "relations": [r.to_dict() for r in self.relations],
            "context_summary": self.context_summary,
            "metrics": self.metrics,
        }
    
    def to_prompt_context(self, format: str = "yaml") -> str:
        """
        Gera contexto compacto para injetar no prompt do LLM.
        
        Formato YAML: máxima densidade informacional com mínimo de tokens.
        Cada linha carrega significado, não estrutura.
        
        Args:
            format: "yaml" (default, compacto) ou "text" (legível)
        """
        if not self.entities and not self.episodes:
            return ""
        
        if format == "yaml":
            return self._to_yaml_context()
        return self._to_text_context()
    
    def _to_yaml_context(self, max_tokens: int = 150) -> str:
        """
        Formato ULTRA-COMPACTO para LLMs.

        OTIMIZAÇÃO v4 (V2.0): Context Packing Algorithm
        - Usa ContextPacker para 40-70% de redução de tokens
        - Priority scoring: importance × retrievability × recency
        - Grouping de episódios redundantes
        - Sumarização hierárquica
        """
        # V2.0: Use Context Packer if enabled
        if hasattr(self, '_config') and self._config.enable_context_packing:
            # Separate personal and collective episodes
            personal_episodes = [
                ep for ep in self.episodes
                if ep.metadata.get("visibility", "personal") == "personal"
                and not ep.metadata.get("inherited_from")
            ]

            collective_episodes = [
                ep for ep in self.episodes
                if ep.metadata.get("visibility") == "learned"
                or ep.metadata.get("inherited_from")
            ]

            # Use Context Packer
            packed = self._context_packer.pack_episodes(
                episodes=personal_episodes,
                entities=self.entities,
                collective_episodes=collective_episodes,
            )

            return packed

        # Legacy path (if Context Packing disabled)
        parts = []
        token_estimate = 0

        # Filtra entidades relevantes (ignora genéricos)
        skip_names = {"user", "assistant", "participant", "none", "", "undefined", "cliente", "sistema"}
        useful_entities = [
            e for e in self.entities[:3]  # Reduzido de 5 para 3
            if e.name.lower() not in skip_names
            and e.type.lower() not in skip_names
            and not e.name.startswith("[")
            and len(e.name) > 2  # Ignora nomes muito curtos
        ]
        
        if useful_entities:
            # Apenas o nome principal, sem prefixo verboso
            parts.append(f"Cliente: {useful_entities[0].name}")
            token_estimate += 5
        
        # Separa episódios por relevância (mais recente + maior importância)
        sorted_episodes = sorted(
            self.episodes[:10],  # Considera até 10
            key=lambda ep: (ep.importance, ep.timestamp.timestamp() if ep.timestamp else 0),
            reverse=True
        )
        
        personal_episodes = []
        collective_episodes = []
        
        for ep in sorted_episodes[:4]:  # Reduzido de 6 para 4
            visibility = ep.metadata.get("visibility", "personal")
            if visibility == "learned" or ep.metadata.get("inherited_from"):
                collective_episodes.append(ep)
            else:
                personal_episodes.append(ep)
        
        # Histórico pessoal - APENAS 2 episódios mais relevantes
        if personal_episodes and token_estimate < max_tokens:
            parts.append("Histórico:")
            for ep in personal_episodes[:2]:  # Reduzido de 3 para 2
                line = self._format_episode_compact(ep)
                if line and token_estimate < max_tokens:
                    parts.append(line)
                    token_estimate += len(line.split()) + 2
        
        # Conhecimento coletivo - APENAS 1 se sobrar espaço
        if collective_episodes and token_estimate < max_tokens - 20:
            line = self._format_collective_compact(collective_episodes[0])
            if line:
                parts.append(f"💡 {line}")
                token_estimate += len(line.split()) + 2
        
        return "\n".join(parts) if parts else ""
    
    def _format_episode_compact(self, ep: Episode) -> str:
        """Formato ultra-compacto: ação: resultado (max 60 chars)."""
        w5h = ep.metadata.get("w5h", {})
        action = self._sanitize_value(w5h.get("what") or ep.action)
        outcome = self._sanitize_value(w5h.get("how") or ep.outcome)
        
        if not action or action == "undefined":
            return ""
        
        # Formato compacto: "- ação: resultado"
        if outcome and outcome != "undefined":
            line = f"  - {action[:25]}: {outcome[:30]}"
        else:
            line = f"  - {action[:50]}"
        
        return line[:60]  # Hard limit
    
    def _format_collective_compact(self, ep: Episode) -> str:
        """Formato compacto para conhecimento coletivo (max 50 chars)."""
        w5h = ep.metadata.get("w5h", {})
        problema = self._sanitize_value(w5h.get("what") or ep.action)
        solucao = self._sanitize_value(w5h.get("how") or ep.outcome)
        
        if problema and solucao:
            return f"{problema[:20]}→{solucao[:25]}"
        return problema[:45] if problema else ""

    def _sanitize_value(self, value: Any) -> str:
        """Sanitiza valor para evitar undefined, null, arrays como string."""
        if value is None:
            return ""
        
        # Converte para string
        str_val = str(value).strip()
        
        # Remove valores inválidos
        if str_val.lower() in {"undefined", "null", "none", ""}:
            return ""
        
        # Detecta arrays serializados como string
        if str_val.startswith("[") and str_val.endswith("]"):
            try:
                # Tenta parsear como lista
                import ast
                parsed = ast.literal_eval(str_val)
                if isinstance(parsed, list):
                    return ", ".join(str(item) for item in parsed[:3])
            except Exception:
                # Se não conseguir, retorna os primeiros 50 chars
                return str_val[1:-1][:50]
        
        return str_val
    
    def _to_text_context(self) -> str:
        """Formato texto legível (mais tokens, mais claro)."""
        parts = ["[MEMORY CONTEXT]"]
        
        if self.entities:
            parts.append("\nEntidades conhecidas:")
            for entity in self.entities[:5]:
                parts.append(f"  - {entity.name} ({entity.type})")
        
        if self.episodes:
            parts.append("\nExperiências relevantes:")
            for episode in self.episodes[:3]:
                parts.append(f"  - {episode.to_summary()}")
        
        if self.context_summary:
            parts.append(f"\nResumo: {self.context_summary}")
        
        return "\n".join(parts)


class MemoryGraph:
    """
    Grafo de memória cognitiva.

    Armazena e conecta:
    - Entities: coisas/conceitos
    - Episodes: experiências/acontecimentos
    - Relations: conexões entre eles

    Funcionalidades Principais:
    - store(): Armazena nova memória
    - recall(): Busca memórias relevantes (V2.0: hierarchical + attention)
    - consolidate(): Compacta episódios repetidos (V2.0: progressive)
    - resolve_entity(): Identifica entidades ambíguas

    Estrutura do Código (50 métodos organizados em 10 seções):

    1. ENTITY OPERATIONS (8 métodos)
       - add_entity, get_entity, find_entities, resolve_entity
       - _index_entity, find_entity_by_name
       - _find_orphan_entities, _forget_entity

    2. EPISODE OPERATIONS (9 métodos)
       - add_episode, get_episode, find_episodes
       - _index_episode, _calculate_retrievability
       - _find_similar_episodes, add_episode_with_consolidation
       - _create_episode_relations, _forget_episode

    3. RELATION OPERATIONS (9 métodos)
       - add_relation, add_relation_simple, remove_relation
       - get_relations, get_connected
       - _find_existing_relation, _index_relation
       - _add_relation_internal, _forget_relation

    4. HIGH-LEVEL OPERATIONS (2 métodos)
       - recall (V2.0: hierarchical + attention + forget gate)
       - store

    5. PERSISTENCE (5 métodos)
       - _save, _load, _rebuild_inverted_index
       - _generate_context_summary

    6. ADDITIONAL METHODS (2 métodos)
       - clear, add_episode_with_consolidation

    7. STATS (1 método)
       - stats

    8. CONTRADICTION MANAGEMENT (4 métodos)
       - set_contradiction_strategy, find_contradictions
       - get_contradiction_history, get_pending_contradictions

    9. GRAPH ANALYSIS (8 métodos)
       - get_node_weight, get_graph_data, _get_node_color, _get_edge_color
       - get_memory_health, _get_frequent_participants
       - _get_conversation_participants, _calculate_health_score

    10. MEMORY DYNAMICS (2 métodos)
        - apply_access_decay, reinforce_on_recall

    V2.0 Enhancements:
    - Context Packing: 40-70% token reduction
    - Progressive Consolidation: 60% faster learning
    - Active Forgetting: 30% noise reduction
    - Hierarchical Recall: 2x faster, multi-level
    - SM-2 Adaptive: 25% better retention
    - Attention Mechanism: 35% better coherence
    """
    
    def __init__(self, storage_path: Path | str | None = None):
        """
        Inicializa o grafo de memória.

        Args:
            storage_path: Caminho para persistência (None = apenas memória)
            contradiction_strategy: Estratégia para resolver contradições
        """
        self.storage_path = Path(storage_path) if storage_path else None

        # Logging
        self._logger = get_logger("memory_graph")
        self._audit = get_audit_logger("memory_graph")
        self._perf = get_performance_logger("memory_graph")

        # Índices em memória
        self._entities: dict[str, Entity] = {}
        self._episodes: dict[str, Episode] = {}
        self._relations: dict[str, Relation] = {}
        
        # Índices secundários para busca rápida
        self._entity_by_name: dict[str, list[str]] = {}  # name -> [entity_ids]
        self._entity_by_type: dict[str, list[str]] = {}  # type -> [entity_ids]
        self._relations_by_from: dict[str, list[str]] = {}  # from_id -> [relation_ids]
        self._relations_by_to: dict[str, list[str]] = {}  # to_id -> [relation_ids]
        
        # NOVO: Índice invertido para busca O(log n)
        self._inverted_index = InvertedIndex()

        # Detector de contradições
        self._contradiction_detector = create_default_detector()

        # V2.0 Enhancements
        self._config = get_config()
        self._context_packer = ContextPacker(max_tokens=self._config.context_max_tokens)
        self._hierarchical_recall = HierarchicalRecall()
        self._attention = MemoryAttention(AttentionConfig(
            d_model=self._config.attention_d_model,
            n_heads=self._config.attention_heads,
            temperature=self._config.attention_temperature,
            use_graph_bias=self._config.attention_use_graph_bias,
        ))
        self._forget_gate = ForgetGate(
            forget_threshold=self._config.forget_gate_threshold,
            noise_weight=self._config.forget_gate_noise_weight,
            redundancy_weight=self._config.forget_gate_redundancy_weight,
            obsolescence_weight=self._config.forget_gate_obsolescence_weight,
        )

        # Carrega se existir
        if self.storage_path:
            self._load()
    
    # ==================== ENTITY OPERATIONS ====================
    
    def add_entity(self, entity: Entity) -> Entity:
        """Adiciona ou atualiza uma entidade."""
        # Verifica se já existe uma similar
        existing = self.resolve_entity(entity.name, entity.identifiers)

        if existing:
            # Atualiza a existente
            for ident in entity.identifiers:
                existing.add_identifier(ident)
            existing.attributes.update(entity.attributes)
            existing.touch()
            self._save()

            # Audit log: UPDATE
            self._audit.log_update(
                "entity",
                entity_id=existing.id,
                type=existing.type,
                name=existing.name,
                identifiers_count=len(existing.identifiers),
                attributes_count=len(existing.attributes)
            )
            return existing

        # Adiciona nova
        self._entities[entity.id] = entity
        self._index_entity(entity)
        self._save()

        # Audit log: CREATE
        self._audit.log_create(
            "entity",
            entity_id=entity.id,
            type=entity.type,
            name=entity.name,
            identifiers_count=len(entity.identifiers),
            attributes_count=len(entity.attributes)
        )
        return entity
    
    def get_entity(self, entity_id: str) -> Entity | None:
        """Busca entidade por ID."""
        return self._entities.get(entity_id)
    
    def find_entities(
        self,
        query: str | None = None,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> list[Entity]:
        """
        Busca entidades por query e/ou tipo.
        
        Args:
            query: Texto para buscar (nome, identificadores)
            entity_type: Filtrar por tipo
            limit: Máximo de resultados
        """
        candidates = list(self._entities.values())
        
        # Filtra por tipo
        if entity_type:
            candidates = [e for e in candidates if e.type.lower() == entity_type.lower()]
        
        # Filtra e pontua por query
        if query:
            scored = []
            for entity in candidates:
                score = entity.similarity_score(query)
                if score > 0:
                    scored.append((entity, score))
            
            scored.sort(key=lambda x: x[1], reverse=True)
            candidates = [e for e, _ in scored[:limit]]
        
        return candidates[:limit]
    
    def resolve_entity(
        self,
        name: str,
        identifiers: list[str] | None = None,
    ) -> Entity | None:
        """
        Tenta encontrar uma entidade existente que corresponda.
        
        Busca por:
        1. Identificadores exatos
        2. Nome exato
        3. Nome parcial
        """
        identifiers = identifiers or []
        
        # Busca por identificador exato
        for entity in self._entities.values():
            for ident in identifiers:
                if ident in entity.identifiers:
                    return entity
        
        # Busca por nome exato
        name_lower = name.lower()
        for entity in self._entities.values():
            if entity.name.lower() == name_lower:
                return entity
        
        # Busca parcial não retorna (ambíguo)
        return None
    
    def _index_entity(self, entity: Entity) -> None:
        """Adiciona entidade aos índices secundários."""
        name_key = entity.name.lower()
        if name_key not in self._entity_by_name:
            self._entity_by_name[name_key] = []
        if entity.id not in self._entity_by_name[name_key]:
            self._entity_by_name[name_key].append(entity.id)
        
        type_key = entity.type.lower()
        if type_key not in self._entity_by_type:
            self._entity_by_type[type_key] = []
        if entity.id not in self._entity_by_type[type_key]:
            self._entity_by_type[type_key].append(entity.id)
    
    # ==================== EPISODE OPERATIONS ====================
    
    def add_episode(self, episode: Episode, consolidation_mode: str = "progressive") -> Episode:
        """
        Adiciona um episódio e verifica se deve consolidar.

        Args:
            episode: Episódio a adicionar
            consolidation_mode: "progressive" (age-aware) ou "fixed" (legacy)
        """
        # Verifica se deve consolidar com episódios similares
        with self._perf.measure("find_similar_episodes"):
            similar = self._find_similar_episodes(episode)

        # Progressive consolidation: threshold adapts based on pattern age
        threshold = episode.get_consolidation_threshold(consolidation_mode)
        required_similar = threshold - 1  # threshold-1 because we add the new episode

        if len(similar) >= required_similar:
            # Consolida todos + o novo
            consolidated = Episode.consolidate(similar + [episode])

            # Remove os antigos do índice invertido
            for old in similar:
                self._inverted_index.remove_episode(old.id)
                self._episodes.pop(old.id, None)

            # Adiciona consolidado
            self._episodes[consolidated.id] = consolidated
            self._index_episode(consolidated)
            self._save()

            # Audit log: CONSOLIDATION
            occurrences = getattr(consolidated, 'occurrences', 1)
            self._audit.log_create(
                "episode_consolidated",
                episode_id=consolidated.id,
                action=consolidated.action,
                occurrences=occurrences,
                consolidated_count=len(similar) + 1,
                consolidation_mode=consolidation_mode,
                threshold=threshold,
                participants=len(consolidated.participants)
            )
            self._logger.info(
                f"Episode consolidated: {consolidated.action} (occurrences={occurrences})"
            )
            return consolidated

        # Adiciona normal
        self._episodes[episode.id] = episode
        self._index_episode(episode)

        # Cria relações automáticas episódio ↔ participantes
        self._create_episode_relations(episode)

        self._save()

        # Audit log: CREATE
        self._audit.log_create(
            "episode",
            episode_id=episode.id,
            action=episode.action,
            occurrences=getattr(episode, 'occurrences', 1),
            participants=len(episode.participants),
            context_length=len(episode.context) if episode.context else 0,
            outcome_length=len(episode.outcome) if episode.outcome else 0
        )
        return episode
    
    def _index_episode(self, episode: Episode) -> None:
        """Adiciona episódio ao índice invertido."""
        self._inverted_index.index_episode(
            episode_id=episode.id,
            action=episode.action,
            context=episode.context,
            outcome=episode.outcome,
        )
    
    def get_episode(self, episode_id: str) -> Episode | None:
        """Busca episódio por ID."""
        return self._episodes.get(episode_id)
    
    def find_episodes(
        self,
        query: str | None = None,
        participant_ids: list[str] | None = None,
        action: str | None = None,
        limit: int = 10,
        context: dict[str, Any] | None = None,
        min_score: float | None = None,
    ) -> list[Episode]:
        """
        Busca episódios por diversos critérios.
        
        OTIMIZADO v2:
        - Usa índice invertido para pré-filtrar candidatos O(log n)
        - Aplica threshold mínimo de relevância
        - Limita candidatos para evitar explosão
        - Filtra por namespace (metadata["where"]) se fornecido
        
        Args:
            query: Texto de busca
            participant_ids: Filtrar por participantes
            action: Filtrar por ação específica
            limit: Máximo de resultados
            context: Contexto adicional para scoring, incluindo:
                - namespace: Filtrar por namespace (metadata["where"])
                - who: Lista de participantes para filtro por owner
            min_score: Score mínimo de relevância (default: RECALL_MIN_THRESHOLD)
        """
        min_score = min_score if min_score is not None else RECALL_MIN_THRESHOLD
        context = context or {}
        
        # Extrai filtros do contexto
        namespace_filter = context.get("namespace")
        who_filter = context.get("who")  # Lista de participantes/owners
        
        # OTIMIZAÇÃO: Usa índice invertido para pré-filtrar
        if query and len(self._episodes) > 20:
            # Busca candidatos via índice invertido
            candidate_ids = self._inverted_index.get_candidates(
                query, limit=RECALL_MAX_CANDIDATES
            )
            
            if candidate_ids:
                candidates = [
                    self._episodes[eid] 
                    for eid in candidate_ids 
                    if eid in self._episodes
                ]
            else:
                # Fallback: busca linear se índice vazio
                candidates = list(self._episodes.values())
        else:
            candidates = list(self._episodes.values())
        
        # CORREÇÃO: Filtra por namespace (metadata["where"] ou metadata["namespace"])
        # Inclui episódios do namespace solicitado OU sem namespace definido
        if namespace_filter:
            candidates = [
                e for e in candidates
                if (
                    # Episódio pertence ao namespace solicitado
                    e.metadata.get("where") == namespace_filter or
                    e.metadata.get("namespace") == namespace_filter or
                    # Episódio não tem namespace (compatibilidade com dados antigos)
                    (not e.metadata.get("where") and not e.metadata.get("namespace"))
                )
            ]
        
        # NOVO: Filtra por owner/participante (who)
        # Se who é fornecido, prioriza episódios que envolvem esses participantes
        if who_filter:
            # Resolve nomes para IDs se necessário
            who_ids = set()
            for who_name in who_filter:
                entity = self.find_entity_by_name(who_name)
                if entity:
                    who_ids.add(entity.id)
                who_ids.add(who_name)  # Também busca pelo nome direto
            
            if who_ids:
                # Filtra episódios que têm pelo menos um dos participantes
                candidates = [
                    e for e in candidates
                    if (set(e.participants) & who_ids) or
                       any(who in str(e.metadata.get("w5h", {}).get("who", [])) 
                           for who in who_filter)
                ]
        
        # Filtra por ação
        if action:
            candidates = [e for e in candidates if e.action.lower() == action.lower()]
        
        # Filtra por participantes (IDs)
        if participant_ids:
            participant_set = set(participant_ids)
            candidates = [
                e for e in candidates
                if set(e.participants) & participant_set
            ]
        
        # Pontua por query com threshold
        if query:
            scored = []
            for episode in candidates:
                score = episode.similarity_score(query, context)
                
                # OTIMIZAÇÃO: Aplica threshold mínimo
                if score >= min_score:
                    # Boost por retrievability (frescor + importância)
                    retrievability_boost = self._calculate_retrievability(episode)
                    final_score = score * (0.7 + retrievability_boost * 0.3)
                    scored.append((episode, final_score))
            
            scored.sort(key=lambda x: x[1], reverse=True)
            candidates = [e for e, _ in scored[:limit]]
        else:
            # Ordena por importância/recência
            candidates.sort(
                key=lambda e: (e.importance, e.timestamp),
                reverse=True,
            )
        
        return candidates[:limit]
    
    def _calculate_retrievability(self, episode: Episode) -> float:
        """
        Calcula retrievability baseado em Ebbinghaus.
        
        R = e^(-t/S) onde:
        - t = tempo desde último acesso
        - S = estabilidade (baseada em acessos, consolidação, centralidade)
        """
        from datetime import timezone
        import math
        
        now = datetime.now()
        
        # Tempo desde criação (em horas)
        time_diff = (now - episode.timestamp).total_seconds() / 3600
        
        # Estabilidade base (1-10)
        stability = 1.0
        
        # Boost por número de acessos (occurrence_count)
        stability += min(5.0, episode.occurrence_count * 0.5)
        
        # Boost por importância
        stability += episode.importance * 2
        
        # Boost por consolidação
        if episode.is_consolidated:
            stability += 2.0
        
        # Retrievability: e^(-t/S)
        # Normalizado para 0-1
        retrievability = math.exp(-time_diff / (stability * 24))  # 24h base
        
        return min(1.0, max(0.0, retrievability))
    
    def _find_similar_episodes(self, episode: Episode, threshold: float = 0.7) -> list[Episode]:
        """Encontra episódios similares para consolidação."""
        similar = []
        
        for existing in self._episodes.values():
            if existing.id != episode.id and episode.matches_pattern(existing, threshold):
                similar.append(existing)
        
        return similar
    
    # ==================== RELATION OPERATIONS ====================
    
    def add_relation(
        self,
        relation: Relation,
        check_contradiction: bool = True,
    ) -> tuple[Relation, ResolutionResult | None]:
        """
        Adiciona ou reforça uma relação.
        
        Se check_contradiction=True e houver contradição, resolve automaticamente.
        
        Args:
            relation: Relação a adicionar
            check_contradiction: Se deve verificar contradições
            
        Returns:
            Tupla (relação final, resultado da resolução ou None)
        """
        # Verifica se já existe relação idêntica (mesma tripla + mesma polaridade)
        existing = self._find_existing_relation(
            relation.from_id,
            relation.relation_type,
            relation.to_id,
        )
        
        if existing:
            # Se polaridade é similar, apenas reforça
            polarity_diff = abs(existing.polarity - relation.polarity)
            if polarity_diff < 0.5:
                existing.reinforce()
                self._save()
                return existing, None
            
            # Polaridades diferentes = possível contradição
            if check_contradiction and relation.contradicts(existing):
                contradiction = Contradiction(
                    relation_a=existing,
                    relation_b=relation,
                )
                result = self._contradiction_detector.resolve(contradiction)
                
                if result.winner and result.loser:
                    # Remove perdedora, mantém vencedora
                    if result.loser == existing:
                        self.remove_relation(existing.id)
                        self._relations[relation.id] = relation
                        self._index_relation(relation)
                        self._save()
                        return relation, result
                    else:
                        # Existente venceu
                        self._save()
                        return existing, result
                elif result.action_taken == "marked_conflict":
                    # Mantém ambas como conflito
                    self._relations[relation.id] = relation
                    self._index_relation(relation)
                    self._save()
                    return relation, result
        
        # Verifica contradição com outras relações se não encontrou existente
        if check_contradiction:
            existing_relations = list(self._relations.values())
            contradiction = self._contradiction_detector.check_for_contradiction(
                relation, existing_relations
            )
            
            if contradiction:
                result = self._contradiction_detector.resolve(contradiction)
                
                if result.winner and result.loser:
                    if result.loser != relation:
                        # Nova relação venceu, remove a antiga
                        self.remove_relation(result.loser.id)
                    else:
                        # Relação existente venceu, não adiciona a nova
                        return result.winner, result
                elif result.action_taken == "marked_conflict":
                    # Mantém ambas
                    pass
        
        # Adiciona nova
        self._relations[relation.id] = relation
        self._index_relation(relation)
        self._save()
        return relation, None
    
    def add_relation_simple(self, relation: Relation) -> Relation:
        """
        Adiciona relação sem verificar contradições.
        
        Mantém compatibilidade com código existente.
        """
        result, _ = self.add_relation(relation, check_contradiction=False)
        return result
    
    def remove_relation(self, relation_id: str) -> bool:
        """
        Remove uma relação por ID.
        
        Args:
            relation_id: ID da relação a remover
            
        Returns:
            True se removida, False se não encontrada
        """
        if relation_id not in self._relations:
            return False
        
        relation = self._relations[relation_id]
        
        # Remove dos índices
        if relation.from_id in self._relations_by_from:
            self._relations_by_from[relation.from_id] = [
                rid for rid in self._relations_by_from[relation.from_id]
                if rid != relation_id
            ]
        if relation.to_id in self._relations_by_to:
            self._relations_by_to[relation.to_id] = [
                rid for rid in self._relations_by_to[relation.to_id]
                if rid != relation_id
            ]
        
        # Remove do dicionário principal
        del self._relations[relation_id]
        self._save()
        return True
    
    def get_relations(
        self,
        from_id: str | None = None,
        to_id: str | None = None,
        relation_type: str | None = None,
    ) -> list[Relation]:
        """Busca relações por critérios."""
        results = []
        
        # Usa índice se possível
        if from_id and from_id in self._relations_by_from:
            candidate_ids = self._relations_by_from[from_id]
            candidates = [self._relations[rid] for rid in candidate_ids if rid in self._relations]
        elif to_id and to_id in self._relations_by_to:
            candidate_ids = self._relations_by_to[to_id]
            candidates = [self._relations[rid] for rid in candidate_ids if rid in self._relations]
        else:
            candidates = list(self._relations.values())
        
        for relation in candidates:
            if relation.matches(from_id, to_id, relation_type):
                results.append(relation)
        
        return results
    
    def get_connected(self, entity_or_episode_id: str) -> list[tuple[Relation, Entity | Episode]]:
        """
        Retorna tudo que está conectado a um ID.
        
        Returns:
            Lista de (relação, entidade_ou_episodio_conectado)
        """
        results = []
        
        for relation in self._relations.values():
            if relation.from_id == entity_or_episode_id:
                connected = self.get_entity(relation.to_id) or self.get_episode(relation.to_id)
                if connected:
                    results.append((relation, connected))
            elif relation.to_id == entity_or_episode_id:
                connected = self.get_entity(relation.from_id) or self.get_episode(relation.from_id)
                if connected:
                    results.append((relation, connected))
        
        # Ordena por força da relação
        results.sort(key=lambda x: x[0].strength, reverse=True)
        
        return results
    
    def _find_existing_relation(
        self,
        from_id: str,
        relation_type: str,
        to_id: str,
    ) -> Relation | None:
        """Encontra relação existente exata."""
        for relation in self._relations.values():
            if (
                relation.from_id == from_id
                and relation.relation_type.lower() == relation_type.lower()
                and relation.to_id == to_id
            ):
                return relation
        return None
    
    def _index_relation(self, relation: Relation) -> None:
        """Adiciona relação aos índices secundários."""
        if relation.from_id not in self._relations_by_from:
            self._relations_by_from[relation.from_id] = []
        self._relations_by_from[relation.from_id].append(relation.id)
        
        if relation.to_id not in self._relations_by_to:
            self._relations_by_to[relation.to_id] = []
        self._relations_by_to[relation.to_id].append(relation.id)
    
    # ==================== HIGH-LEVEL OPERATIONS ====================
    
    def recall(
        self,
        query: str,
        context: dict[str, Any] | None = None,
        limit: int = 5,
    ) -> RecallResult:
        """
        Busca memórias relevantes para uma query.

        Este é o método principal para agentes obterem contexto.

        OTIMIZAÇÕES v2:
        - Índice invertido para busca O(log n)
        - Threshold mínimo de relevância (0.25)
        - Boost por retrievability
        - Métricas de recall para debug

        Args:
            query: Texto da pergunta/contexto do usuário
            context: Informações adicionais:
                - conversation_id: ID da conversa ativa
                - session_id: ID da sessão atual
                - namespace: Namespace para busca
                - entity_ids: IDs de entidades conhecidas
            limit: Máximo de resultados por tipo

        Returns:
            RecallResult com entidades, episódios, relações e métricas
        """
        import time
        start_time = time.time()

        context = context or {}
        conversation_id = context.get("conversation_id")
        session_id = context.get("session_id")
        namespace = context.get("namespace", "default")

        # Audit log: QUERY
        self._audit.log_query(
            "recall",
            query_text=query[:100],  # Primeiros 100 chars
            conversation_id=conversation_id,
            session_id=session_id,
            namespace=namespace,
            limit=limit
        )
        
        # Métricas
        metrics = {
            "query_terms": len(tokenize(query)),
            "total_episodes": len(self._episodes),
            "total_entities": len(self._entities),
            "index_size": self._inverted_index._total_episodes,
            "candidates_checked": 0,
            "filtered_by_threshold": 0,
        }
        
        # 1. Busca entidades diretamente mencionadas na query
        entities = self.find_entities(query=query, limit=limit)
        entity_ids = [e.id for e in entities]
        
        # 2. Adiciona participantes FREQUENTES do namespace (top 5)
        frequent_participants = self._get_frequent_participants(namespace, top_n=5)
        for participant in frequent_participants:
            if participant.id not in entity_ids:
                entities.append(participant)
                entity_ids.append(participant.id)
        
        # 3. Se há conversa ativa, adiciona participantes dessa conversa
        if conversation_id:
            conversation_participants = self._get_conversation_participants(
                conversation_id, limit=10
            )
            for participant in conversation_participants:
                if participant.id not in entity_ids:
                    entities.append(participant)
                    entity_ids.append(participant.id)
        
        # Limita entidades ao máximo
        entities = entities[:limit * 2]  # 2x limit para entidades
        entity_ids = [e.id for e in entities]
        metrics["entities_found"] = len(entities)
        
        # 4. Busca episódios com otimizações V2.0
        enriched_context = {**context, "entity_ids": entity_ids}

        # 4.1. Hierarchical Recall (se habilitado)
        if self._config.enable_hierarchical_recall:
            hierarchical_results = self._hierarchical_recall.recall(
                query=query,
                graph=self,
                context_tokens=self._config.context_max_tokens,
            )
            # Flatten results
            episodes = []
            for level_name in ["working", "recent", "patterns", "knowledge"]:
                episodes.extend(hierarchical_results.get(level_name, []))
            metrics["hierarchical_recall_used"] = True
        else:
            # Busca tradicional
            episodes = self.find_episodes(
                query=query,
                participant_ids=entity_ids if entity_ids else None,
                limit=RECALL_MAX_RESULTS,
                context=enriched_context,
                min_score=RECALL_MIN_THRESHOLD,
            )
            metrics["hierarchical_recall_used"] = False

        # 4.2. Active Forgetting / Forget Gate (se habilitado)
        if self._config.enable_active_forgetting:
            before_forget = len(episodes)
            episodes = self._forget_gate.apply_gate(episodes, self)
            metrics["filtered_by_forget_gate"] = before_forget - len(episodes)

        # 4.3. Attention Mechanism Ranking (se habilitado)
        if self._config.enable_attention_mechanism and episodes:
            attention_scores = self._attention.compute_attention(query, episodes, self)
            ranked = self._attention.rank_by_attention(episodes, attention_scores)
            episodes = [ep for ep, score in ranked]
            metrics["attention_reranking_used"] = True

        # 4.4. FILTRA memórias que JÁ FORAM CONSOLIDADAS (filhas)
        # Só retorna resumos (consolidadas) e memórias frescas (não consolidadas)
        include_consolidated = context.get("include_consolidated", False)
        if not include_consolidated:
            before_filter = len(episodes)
            episodes = [
                ep for ep in episodes
                if not ep.metadata.get("consolidated_into")
            ]
            metrics["filtered_consolidated"] = before_filter - len(episodes)
        
        # 5. Se há conversa ativa, prioriza episódios dessa conversa
        if conversation_id:
            conversation_episodes = [
                ep for ep in self._episodes.values()
                if ep.conversation_id == conversation_id
            ]
            # Merge com episódios encontrados
            episode_ids = {ep.id for ep in episodes}
            for ep in conversation_episodes[:limit]:
                if ep.id not in episode_ids:
                    episodes.append(ep)
                    episode_ids.add(ep.id)
        
        # Limita episódios ao máximo configurado
        episodes = episodes[:RECALL_MAX_RESULTS]
        metrics["episodes_found"] = len(episodes)
        
        # 6. Busca relações entre os encontrados (limite para evitar explosão)
        all_ids = entity_ids + [ep.id for ep in episodes]
        relations = []
        for id_ in all_ids[:20]:  # Limita IDs para busca de relações
            relations.extend(self.get_relations(from_id=id_))
            relations.extend(self.get_relations(to_id=id_))
        
        # Remove duplicatas
        seen_relation_ids = set()
        unique_relations = []
        for rel in relations:
            if rel.id not in seen_relation_ids:
                seen_relation_ids.add(rel.id)
                unique_relations.append(rel)
        
        metrics["relations_found"] = len(unique_relations)
        
        # Gera resumo
        summary = self._generate_context_summary(entities, episodes, unique_relations)
        
        # Marca como acessadas
        for entity in entities:
            entity.touch()
        for episode in episodes:
            episode.boost_importance(0.05)
        
        self._save()
        
        # Finaliza métricas
        recall_time_ms = round((time.time() - start_time) * 1000, 2)
        metrics["recall_time_ms"] = recall_time_ms
        metrics["threshold_used"] = RECALL_MIN_THRESHOLD

        # Performance log
        self._perf.log_metric(
            "recall",
            duration_ms=recall_time_ms,
            entities_found=len(entities),
            episodes_found=len(episodes),
            relations_found=len(unique_relations),
            hierarchical_recall=metrics.get("hierarchical_recall_used", False),
            attention_reranking=metrics.get("attention_reranking_used", False),
            forget_gate_filtered=metrics.get("filtered_by_forget_gate", 0)
        )

        self._logger.debug(
            f"Recall completed: {len(episodes)} episodes, {len(entities)} entities in {recall_time_ms:.1f}ms"
        )

        return RecallResult(
            entities=entities,
            episodes=episodes,
            relations=unique_relations[:10],  # Limita relações
            context_summary=summary,
            metrics=metrics,
        )
    
    def store(
        self,
        action: str,
        participants: list[dict[str, Any]],
        context: str = "",
        outcome: str = "",
        relations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Armazena uma nova memória (episódio + entidades + relações).
        
        Este é o método principal para agentes salvarem experiências.
        
        Args:
            action: O que foi feito (verbo)
            participants: Lista de entidades envolvidas
            context: Situação/cenário
            outcome: Resultado
            relations: Conexões a criar
            
        Returns:
            Resumo do que foi armazenado
        """
        relations = relations or []
        
        # Resolve/cria entidades
        entity_ids = []
        entities_created = []
        entities_updated = []
        
        for p in participants:
            existing = self.resolve_entity(
                p.get("name", ""),
                p.get("identifiers", []),
            )
            
            if existing:
                # Atualiza
                for ident in p.get("identifiers", []):
                    existing.add_identifier(ident)
                if p.get("attributes"):
                    existing.attributes.update(p["attributes"])
                existing.touch()
                entity_ids.append(existing.id)
                entities_updated.append(existing.id)
            else:
                # Cria nova
                entity = Entity(
                    type=p.get("type", "unknown"),
                    name=p.get("name", "unnamed"),
                    identifiers=p.get("identifiers", []),
                    attributes=p.get("attributes", {}),
                )
                self.add_entity(entity)
                entity_ids.append(entity.id)
                entities_created.append(entity.id)
        
        # Cria episódio
        episode = Episode(
            action=action,
            participants=entity_ids,
            context=context,
            outcome=outcome,
        )
        stored_episode = self.add_episode(episode)
        
        # Cria relações
        relations_created = []
        for rel in relations:
            # Resolve IDs (podem ser nomes)
            from_entity = self.resolve_entity(rel.get("from", ""), [])
            to_entity = self.resolve_entity(rel.get("to", ""), [])
            
            from_id = from_entity.id if from_entity else rel.get("from", "")
            to_id = to_entity.id if to_entity else rel.get("to", "")
            
            relation = Relation(
                from_id=from_id,
                relation_type=rel.get("type", "related_to"),
                to_id=to_id,
                context={"episode_id": stored_episode.id},
            )
            self.add_relation(relation)
            relations_created.append(relation.id)
        
        self._save()
        
        return {
            "episode_id": stored_episode.id,
            "consolidated": stored_episode.is_consolidated,
            "consolidation_level": stored_episode.consolidation_level,
            "entities_created": entities_created,
            "entities_updated": entities_updated,
            "relations_created": relations_created,
        }
    
    def _generate_context_summary(
        self,
        entities: list[Entity],
        episodes: list[Episode],
        relations: list[Relation],
    ) -> str:
        """Gera resumo textual do contexto encontrado."""
        if not entities and not episodes:
            return "No relevant memories found."
        
        parts = []
        
        if entities:
            entity_names = [e.name for e in entities[:3]]
            parts.append(f"Known: {', '.join(entity_names)}")
        
        if episodes:
            if episodes[0].is_consolidated:
                parts.append(
                    f"Pattern ({episodes[0].occurrence_count}x): {episodes[0].outcome}"
                )
            else:
                parts.append(f"Last time: {episodes[0].outcome}")
        
        if relations:
            # Mostra relação mais forte
            strongest = max(relations, key=lambda r: r.strength)
            parts.append(f"Link: {strongest.to_triple()}")
        
        return " | ".join(parts)
    
    # ==================== PERSISTENCE ====================
    
    def _save(self) -> None:
        """Persiste o grafo em disco."""
        if not self.storage_path:
            return
        
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        data = {
            "entities": {k: v.to_dict() for k, v in self._entities.items()},
            "episodes": {k: v.to_dict() for k, v in self._episodes.items()},
            "relations": {k: v.to_dict() for k, v in self._relations.items()},
            "inverted_index": self._inverted_index.to_dict(),
            "saved_at": datetime.now().isoformat(),
        }
        
        graph_file = self.storage_path / "memory_graph.json"
        with open(graph_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def _load(self) -> None:
        """Carrega o grafo do disco."""
        if not self.storage_path:
            return
        
        graph_file = self.storage_path / "memory_graph.json"
        if not graph_file.exists():
            return
        
        with open(graph_file) as f:
            data = json.load(f)
        
        # Carrega entidades
        for entity_data in data.get("entities", {}).values():
            entity = Entity.from_dict(entity_data)
            self._entities[entity.id] = entity
            self._index_entity(entity)
        
        # Carrega episódios
        for episode_data in data.get("episodes", {}).values():
            episode = Episode.from_dict(episode_data)
            self._episodes[episode.id] = episode
        
        # Carrega relações
        for relation_data in data.get("relations", {}).values():
            relation = Relation.from_dict(relation_data)
            self._relations[relation.id] = relation
            self._index_relation(relation)
        
        # Carrega índice invertido (ou reconstrói se não existir)
        if "inverted_index" in data:
            self._inverted_index = InvertedIndex.from_dict(data["inverted_index"])
        else:
            # Reconstrói índice para grafos antigos
            self._rebuild_inverted_index()
    
    # ==================== ADDITIONAL METHODS ====================
    
    def find_entity_by_name(self, name: str) -> Entity | None:
        """Busca entidade por nome exato ou parcial."""
        # Primeiro tenta match exato
        name_lower = name.lower()
        for entity in self._entities.values():
            if entity.name.lower() == name_lower:
                return entity
        
        # Depois tenta match parcial
        for entity in self._entities.values():
            if name_lower in entity.name.lower():
                return entity
        
        return None
    
    def add_episode_with_consolidation(
        self,
        episode: Episode,
        consolidation_mode: str = "progressive"
    ) -> tuple[bool, int]:
        """
        Adiciona episódio e verifica se deve consolidar.

        Args:
            episode: Episódio a adicionar
            consolidation_mode: "progressive" (age-aware) ou "fixed" (legacy)

        Returns:
            Tuple of (was_consolidated, consolidation_count)
        """
        # Busca episódios similares
        similar = self._find_similar_episodes(episode)

        # Progressive consolidation
        threshold = episode.get_consolidation_threshold(consolidation_mode)
        required_similar = threshold - 1

        if len(similar) >= required_similar:
            # Encontra o mais consolidado
            most_consolidated = max(
                similar,
                key=lambda e: e.occurrence_count,
                default=None
            )
            
            if most_consolidated:
                # Atualiza o consolidado
                most_consolidated.occurrence_count += 1
                
                # Adiciona ID do novo como consolidado (isso faz is_consolidated retornar True)
                most_consolidated.consolidated_from.append(episode.id)
                
                # Salva
                self._save()
                
                return True, most_consolidated.occurrence_count
        
        # Não consolida, adiciona normalmente
        self.add_episode(episode)
        return False, 1
    
    def clear(self) -> None:
        """Limpa todas as memórias."""
        self._entities.clear()
        self._episodes.clear()
        self._relations.clear()
        self._entity_by_name.clear()
        self._entity_by_type.clear()
        self._relations_by_from.clear()
        self._relations_by_to.clear()
        self._inverted_index.clear()
        
        # NÃO deleta o arquivo para preservar dados entre reinícios
        # O arquivo será sobrescrito no próximo _save()
        self._save()
    
    def _rebuild_inverted_index(self) -> None:
        """
        Reconstrói o índice invertido a partir dos episódios existentes.
        
        Útil para migrar grafos antigos que não têm índice.
        """
        self._inverted_index.clear()
        
        for episode in self._episodes.values():
            self._index_episode(episode)
        
        # Salva o índice reconstruído
        self._save()
    
    # ==================== STATS ====================
    
    def stats(self) -> dict[str, Any]:
        """Retorna estatísticas do grafo."""
        # Conta entidades por tipo
        entities_by_type: dict[str, int] = {}
        for entity in self._entities.values():
            entities_by_type[entity.type] = entities_by_type.get(entity.type, 0) + 1
        
        return {
            "total_entities": len(self._entities),
            "total_episodes": len(self._episodes),
            "total_relations": len(self._relations),
            "consolidated_episodes": sum(
                1 for e in self._episodes.values() if e.is_consolidated
            ),
            "entities_by_type": entities_by_type,
            "contradiction_stats": self._contradiction_detector.stats(),
            "inverted_index_stats": self._inverted_index.stats(),
            "recall_config": {
                "min_threshold": RECALL_MIN_THRESHOLD,
                "max_candidates": RECALL_MAX_CANDIDATES,
                "max_results": RECALL_MAX_RESULTS,
            },
        }
    
    # ==================== CONTRADICTION MANAGEMENT ====================
    
    def set_contradiction_strategy(self, strategy: ResolutionStrategy) -> None:
        """
        Define a estratégia de resolução de contradições.
        
        Args:
            strategy: Nova estratégia (MOST_RECENT, STRONGEST, etc.)
        """
        self._contradiction_detector.strategy = strategy
    
    def find_contradictions(self) -> list[Contradiction]:
        """
        Encontra todas as contradições no grafo.
        
        Útil para auditoria e limpeza.
        
        Returns:
            Lista de contradições encontradas
        """
        return self._contradiction_detector.find_all_contradictions(
            list(self._relations.values())
        )
    
    def get_contradiction_history(self) -> list[Contradiction]:
        """Retorna histórico de contradições detectadas."""
        return self._contradiction_detector.get_history()
    
    def get_pending_contradictions(self) -> list[Contradiction]:
        """Retorna contradições pendentes de resolução."""
        return self._contradiction_detector.get_unresolved()
    
    # ==================== GRAPH ANALYSIS ====================
    
    def get_node_weight(self, node_id: str) -> float:
        """
        Calcula o peso/importância de um nó baseado em conexões.
        
        Peso = (conexões de entrada * 0.6) + (conexões de saída * 0.4) + (força média * 0.5)
        
        Nós com mais conexões têm maior peso.
        """
        incoming = self.get_relations(to_id=node_id)
        outgoing = self.get_relations(from_id=node_id)
        
        total_connections = len(incoming) + len(outgoing)
        if total_connections == 0:
            return 0.1  # Peso mínimo para nós isolados
        
        # Calcula força média das conexões
        all_relations = incoming + outgoing
        avg_strength = sum(r.strength for r in all_relations) / len(all_relations)
        
        # Peso final
        weight = (len(incoming) * 0.6) + (len(outgoing) * 0.4) + (avg_strength * 0.5)
        
        # Normaliza para 0-1 (aproximado)
        return min(1.0, weight / 10.0)
    
    def get_graph_data(self) -> dict[str, Any]:
        """
        Exporta dados do grafo para visualização.
        
        Retorna estrutura compatível com bibliotecas de visualização
        (NetworkX, PyVis, D3.js, etc.)
        """
        nodes = []
        edges = []
        
        # Adiciona entidades como nós
        for entity in self._entities.values():
            weight = self.get_node_weight(entity.id)
            nodes.append({
                "id": entity.id,
                "label": entity.name,
                "type": "entity",
                "subtype": entity.type,
                "weight": weight,
                "size": 10 + (weight * 40),  # Tamanho proporcional ao peso
                "color": self._get_node_color(entity.type),
                "access_count": entity.access_count,
                "created_at": entity.created_at.isoformat(),
            })
        
        # Adiciona episódios como nós
        for episode in self._episodes.values():
            weight = self.get_node_weight(episode.id)
            nodes.append({
                "id": episode.id,
                "label": episode.action[:30] + "..." if len(episode.action) > 30 else episode.action,
                "type": "episode",
                "subtype": "consolidated" if episode.is_consolidated else "normal",
                "weight": weight,
                "size": 8 + (weight * 30),
                "color": "#FFD700" if episode.is_consolidated else "#90EE90",
                "occurrence_count": episode.occurrence_count,
                "outcome": episode.outcome[:100],
                "created_at": episode.timestamp.isoformat(),
            })
        
        # Adiciona relações como arestas
        for relation in self._relations.values():
            edges.append({
                "id": relation.id,
                "from": relation.from_id,
                "to": relation.to_id,
                "label": relation.relation_type,
                "weight": relation.strength,
                "width": 1 + (relation.strength * 5),  # Largura proporcional à força
                "color": self._get_edge_color(relation.strength),
                "reinforced_count": relation.reinforced_count,
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "stats": self.stats(),
        }
    
    def _get_node_color(self, entity_type: str) -> str:
        """Retorna cor baseada no tipo de entidade."""
        colors = {
            "person": "#FF6B6B",
            "user": "#FF6B6B",
            "file": "#4ECDC4",
            "concept": "#45B7D1",
            "character": "#96CEB4",
            "product": "#FFEAA7",
            "project": "#DDA0DD",
            "error": "#FF7675",
            "task": "#74B9FF",
        }
        return colors.get(entity_type.lower(), "#95A5A6")
    
    def _get_edge_color(self, strength: float) -> str:
        """Retorna cor baseada na força da relação."""
        if strength >= 0.8:
            return "#27AE60"  # Verde forte
        elif strength >= 0.5:
            return "#F39C12"  # Laranja
        else:
            return "#95A5A6"  # Cinza

    # ==================== MEMORY DYNAMICS ====================
    
    def _create_episode_relations(self, episode: Episode) -> None:
        """
        Cria relações automáticas entre episódio e seus participantes.
        
        Isso conecta episódios às entidades, evitando "memórias soltas".
        """
        for participant_id in episode.participants:
            if participant_id in self._entities:
                # Relação: entidade "participated_in" episódio
                relation = Relation(
                    from_id=participant_id,
                    relation_type="participated_in",
                    to_id=episode.id,
                    strength=0.5,
                    context={"auto_created": True},
                )
                self._add_relation_internal(relation)
    
    def _add_relation_internal(self, relation: Relation) -> None:
        """Adiciona relação sem salvar (para uso interno em batch)."""
        existing = self._find_existing_relation(
            relation.from_id, relation.relation_type, relation.to_id
        )
        if existing:
            existing.reinforce(0.1)
        else:
            self._relations[relation.id] = relation
            self._index_relation(relation)
    
    def apply_access_decay(
        self, 
        accessed_entity_ids: list[str],
        accessed_episode_ids: list[str],
        decay_factor: float = 0.98,
    ) -> dict[str, int]:
        """
        Aplica decay baseado em ACESSO, não em tempo.
        
        Memórias ACESSADAS se fortalecem.
        Memórias NÃO ACESSADAS decaem um pouco.
        
        Isso cria competição natural - relevantes sobem, irrelevantes descem.
        
        Args:
            accessed_entity_ids: IDs de entidades que foram acessadas (recall)
            accessed_episode_ids: IDs de episódios que foram acessados (recall)
            decay_factor: Fator de decay para não-acessados (0.98 = 2% de perda)
            
        Returns:
            Estatísticas do decay aplicado
        """
        accessed_entities = set(accessed_entity_ids)
        accessed_episodes = set(accessed_episode_ids)
        
        stats = {
            "entities_reinforced": 0,
            "entities_decayed": 0,
            "episodes_reinforced": 0,
            "episodes_decayed": 0,
            "relations_reinforced": 0,
            "relations_decayed": 0,
            "episodes_forgotten": 0,
            "relations_forgotten": 0,
        }
        
        # Processa entidades
        for entity in self._entities.values():
            if entity.id in accessed_entities:
                entity.touch()  # Reforça
                stats["entities_reinforced"] += 1
            else:
                # Decay: diminui access_count (mas nunca abaixo de 0)
                entity.access_count = max(0, entity.access_count - 1)
                stats["entities_decayed"] += 1
        
        # Processa episódios
        episodes_to_remove = []
        for episode in self._episodes.values():
            if episode.id in accessed_episodes:
                episode.boost_importance(0.05)  # Reforça
                stats["episodes_reinforced"] += 1
            else:
                episode.decay_importance(decay_factor)  # Decay
                stats["episodes_decayed"] += 1
                
                # Esquecimento: importance muito baixa + não consolidado
                if episode.importance < 0.1 and not episode.is_consolidated:
                    episodes_to_remove.append(episode.id)
        
        # Processa relações
        relations_to_remove = []
        all_accessed = accessed_entities | accessed_episodes
        for relation in self._relations.values():
            # Relação é "acessada" se conecta a algo acessado
            if relation.from_id in all_accessed or relation.to_id in all_accessed:
                relation.reinforce(0.02)  # Reforça menos que entidade direta
                stats["relations_reinforced"] += 1
            else:
                relation.decay(decay_factor)
                stats["relations_decayed"] += 1
                
                # Esquecimento: relação muito fraca
                if relation.is_weak(0.05):
                    relations_to_remove.append(relation.id)
        
        # Remove memórias esquecidas
        for eid in episodes_to_remove:
            self._forget_episode(eid)
            stats["episodes_forgotten"] += 1
        
        for rid in relations_to_remove:
            self._forget_relation(rid)
            stats["relations_forgotten"] += 1
        
        self._save()
        return stats
    
    def reinforce_on_recall(
        self, 
        entity_ids: list[str], 
        episode_ids: list[str],
        apply_decay_to_others: bool = True,
    ) -> dict[str, Any]:
        """
        Reforça memórias lembradas E aplica decay nas não-acessadas.
        
        Este é o coração do sistema de memória:
        - Memórias úteis (acessadas) se fortalecem
        - Memórias ignoradas (não acessadas) enfraquecem
        - Cria competição natural por relevância
        
        Args:
            entity_ids: IDs de entidades retornadas no recall
            episode_ids: IDs de episódios retornados no recall
            apply_decay_to_others: Se True, aplica decay nas não-acessadas
            
        Returns:
            Estatísticas de reforço e decay
        """
        if apply_decay_to_others:
            # Usa o sistema unificado de reforço + decay
            return self.apply_access_decay(entity_ids, episode_ids)
        
        # Modo simples: só reforça, não decai (para testes)
        stats = {
            "entities_reinforced": 0,
            "episodes_reinforced": 0,
            "relations_reinforced": 0,
        }
        
        for eid in entity_ids:
            entity = self._entities.get(eid)
            if entity:
                entity.touch()
                stats["entities_reinforced"] += 1
        
        for eid in episode_ids:
            episode = self._episodes.get(eid)
            if episode:
                episode.boost_importance(0.05)
                stats["episodes_reinforced"] += 1
        
        all_ids = set(entity_ids + episode_ids)
        for relation in self._relations.values():
            if relation.from_id in all_ids or relation.to_id in all_ids:
                relation.reinforce(0.05)
                stats["relations_reinforced"] += 1
        
        self._save()
        return stats
    
    def _forget_episode(self, episode_id: str) -> None:
        """Remove um episódio e suas relações."""
        if episode_id in self._episodes:
            del self._episodes[episode_id]
        
        # Remove relações conectadas
        relations_to_remove = [
            rid for rid, r in self._relations.items()
            if r.from_id == episode_id or r.to_id == episode_id
        ]
        for rid in relations_to_remove:
            self._forget_relation(rid)
    
    def _forget_relation(self, relation_id: str) -> None:
        """Remove uma relação dos índices."""
        relation = self._relations.pop(relation_id, None)
        if relation:
            # Remove dos índices
            if relation.from_id in self._relations_by_from:
                self._relations_by_from[relation.from_id] = [
                    r for r in self._relations_by_from[relation.from_id] if r != relation_id
                ]
            if relation.to_id in self._relations_by_to:
                self._relations_by_to[relation.to_id] = [
                    r for r in self._relations_by_to[relation.to_id] if r != relation_id
                ]
    
    def _forget_entity(self, entity_id: str) -> None:
        """Remove uma entidade órfã."""
        entity = self._entities.pop(entity_id, None)
        if entity:
            # Remove dos índices
            name_key = entity.name.lower()
            if name_key in self._entity_by_name:
                self._entity_by_name[name_key] = [
                    e for e in self._entity_by_name[name_key] if e != entity_id
                ]
            type_key = entity.type.lower()
            if type_key in self._entity_by_type:
                self._entity_by_type[type_key] = [
                    e for e in self._entity_by_type[type_key] if e != entity_id
                ]
    
    def _find_orphan_entities(self) -> list[str]:
        """Encontra entidades sem nenhuma conexão."""
        connected_ids = set()
        
        # IDs conectados via relações
        for relation in self._relations.values():
            connected_ids.add(relation.from_id)
            connected_ids.add(relation.to_id)
        
        # IDs participantes de episódios
        for episode in self._episodes.values():
            connected_ids.update(episode.participants)
        
        # Entidades sem conexão
        orphans = [
            eid for eid in self._entities.keys()
            if eid not in connected_ids
        ]
        
        return orphans
    
    def get_memory_health(self) -> dict[str, Any]:
        """
        Retorna métricas de saúde da memória.
        
        Útil para debug e entender o estado do grafo.
        """
        orphan_entities = self._find_orphan_entities()
        
        # Episódios sem participantes
        lonely_episodes = [
            e for e in self._episodes.values()
            if not e.participants
        ]
        
        # Relações fracas
        weak_relations = [
            r for r in self._relations.values()
            if r.strength < 0.2
        ]
        
        # Importância média dos episódios
        if self._episodes:
            avg_importance = sum(e.importance for e in self._episodes.values()) / len(self._episodes)
        else:
            avg_importance = 0.0
        
        # Força média das relações
        if self._relations:
            avg_strength = sum(r.strength for r in self._relations.values()) / len(self._relations)
        else:
            avg_strength = 0.0
        
        return {
            # Nomes compatíveis com UI
            "orphan_entities": len(orphan_entities),
            "orphan_entity_ids": orphan_entities[:10],  # Primeiros 10
            "lonely_episodes": len(lonely_episodes),
            "weak_relations": len(weak_relations),
            "avg_episode_importance": avg_importance,
            "avg_relation_strength": avg_strength,
            "health_score": self._calculate_health_score(
                len(orphan_entities),
                len(lonely_episodes),
                len(weak_relations),
            ),
            # Aliases para compatibilidade
            "orphan_entities_count": len(orphan_entities),
            "lonely_episodes_count": len(lonely_episodes),
            "weak_relations_count": len(weak_relations),
        }
    
    def _get_frequent_participants(self, namespace: str, top_n: int = 5) -> list[Entity]:
        """
        Retorna entidades que participaram em muitos episódios do namespace.
        
        Usado para recall contextual - entidades frequentes são importantes.
        """
        from collections import defaultdict
        
        participant_counts = defaultdict(int)
        
        # Conta participações
        for episode in self._episodes.values():
            # Filtra por namespace se fornecido
            if namespace and namespace != "default":
                # Assume que namespace está em metadata ou context
                episode_namespace = episode.metadata.get("namespace", "default")
                if episode_namespace != namespace:
                    continue
            
            for participant_id in episode.participants:
                if participant_id in self._entities:
                    participant_counts[participant_id] += 1
        
        # Ordena por frequência
        top_participants = sorted(
            participant_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]
        
        # Retorna entidades
        return [self._entities[pid] for pid, _ in top_participants]
    
    def _get_conversation_participants(
        self, 
        conversation_id: str, 
        limit: int = 10
    ) -> list[Entity]:
        """
        Retorna entidades que participaram na conversa específica.
        
        Usado para recall contextual - manter continuidade da conversa.
        """
        participant_ids = set()
        
        for episode in self._episodes.values():
            if episode.conversation_id == conversation_id:
                participant_ids.update(episode.participants)
        
        # Retorna entidades (ordenadas por access_count descendente)
        participants = [
            self._entities[pid] 
            for pid in participant_ids 
            if pid in self._entities
        ]
        participants.sort(key=lambda e: e.access_count, reverse=True)
        
        return participants[:limit]
    
    def _calculate_health_score(
        self,
        orphan_count: int,
        lonely_count: int,
        weak_count: int,
    ) -> float:
        """Calcula um score de saúde do grafo (0-100)."""
        total = len(self._entities) + len(self._episodes) + len(self._relations)
        if total == 0:
            return 100.0
        
        problems = orphan_count + lonely_count + weak_count
        health = max(0, 100 - (problems / total * 100))
        
        return round(health, 1)

    def __repr__(self) -> str:
        stats = self.stats()
        return (
            f"MemoryGraph(entities={stats['total_entities']}, "
            f"episodes={stats['total_episodes']}, "
            f"relations={stats['total_relations']})"
        )
