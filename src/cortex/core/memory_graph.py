"""
MemoryGraph - Grafo de memória que conecta entidades, episódios e relações.

O MemoryGraph é o coração do Cortex:
- Armazena entidades (coisas)
- Armazena episódios (acontecimentos)
- Conecta tudo via relações
- Busca por relevância contextual
- Consolida episódios repetidos
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from cortex.core.entity import Entity
from cortex.core.episode import Episode
from cortex.core.relation import Relation


@dataclass
class RecallResult:
    """Resultado de uma busca de memória."""
    
    entities: list[Entity] = field(default_factory=list)
    episodes: list[Episode] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    context_summary: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "episodes": [e.to_dict() for e in self.episodes],
            "relations": [r.to_dict() for r in self.relations],
            "context_summary": self.context_summary,
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
    
    def _to_yaml_context(self) -> str:
        """Formato YAML ultra-compacto para LLMs."""
        lines = ["# MEMÓRIA DO USUÁRIO"]
        
        if self.entities:
            lines.append("conhecidos:")
            for e in self.entities[:5]:
                # Formato: "- nome (tipo): atributos principais"
                attrs = ", ".join(f"{k}={v}" for k, v in list(e.attributes.items())[:3])
                if attrs:
                    lines.append(f"  - {e.name} ({e.type}): {attrs}")
                else:
                    lines.append(f"  - {e.name} ({e.type})")
        
        if self.episodes:
            lines.append("histórico:")
            for ep in self.episodes[:5]:
                # Formato compacto: ação + resultado em uma linha
                if ep.is_consolidated:
                    lines.append(f"  - [{ep.occurrence_count}x] {ep.action}: {ep.outcome}")
                else:
                    lines.append(f"  - {ep.action}: {ep.outcome}")
        
        if self.relations:
            # Só mostra relações fortes e relevantes
            strong_rels = [r for r in self.relations if r.strength > 0.5][:3]
            if strong_rels:
                lines.append("conexões:")
                for r in strong_rels:
                    lines.append(f"  - {r.relation_type}")
        
        if self.context_summary:
            lines.append(f"resumo: {self.context_summary}")
        
        return "\n".join(lines)
    
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
    
    Funcionalidades:
    - store(): Armazena nova memória
    - recall(): Busca memórias relevantes
    - consolidate(): Compacta episódios repetidos
    - resolve_entity(): Identifica entidades ambíguas
    """
    
    def __init__(self, storage_path: Path | str | None = None):
        """
        Inicializa o grafo de memória.
        
        Args:
            storage_path: Caminho para persistência (None = apenas memória)
        """
        self.storage_path = Path(storage_path) if storage_path else None
        
        # Índices em memória
        self._entities: dict[str, Entity] = {}
        self._episodes: dict[str, Episode] = {}
        self._relations: dict[str, Relation] = {}
        
        # Índices secundários para busca rápida
        self._entity_by_name: dict[str, list[str]] = {}  # name -> [entity_ids]
        self._entity_by_type: dict[str, list[str]] = {}  # type -> [entity_ids]
        self._relations_by_from: dict[str, list[str]] = {}  # from_id -> [relation_ids]
        self._relations_by_to: dict[str, list[str]] = {}  # to_id -> [relation_ids]
        
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
            return existing
        
        # Adiciona nova
        self._entities[entity.id] = entity
        self._index_entity(entity)
        self._save()
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
    
    def add_episode(self, episode: Episode) -> Episode:
        """
        Adiciona um episódio e verifica se deve consolidar.
        """
        # Verifica se deve consolidar com episódios similares
        similar = self._find_similar_episodes(episode)
        
        if len(similar) >= 4:  # 5 ou mais = consolida
            # Consolida todos + o novo
            consolidated = Episode.consolidate(similar + [episode])
            
            # Remove os antigos
            for old in similar:
                self._episodes.pop(old.id, None)
            
            # Adiciona consolidado
            self._episodes[consolidated.id] = consolidated
            self._save()
            return consolidated
        
        # Adiciona normal
        self._episodes[episode.id] = episode
        
        # Cria relações automáticas episódio ↔ participantes
        self._create_episode_relations(episode)
        
        self._save()
        return episode
    
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
    ) -> list[Episode]:
        """
        Busca episódios por diversos critérios.
        """
        candidates = list(self._episodes.values())
        
        # Filtra por ação
        if action:
            candidates = [e for e in candidates if e.action.lower() == action.lower()]
        
        # Filtra por participantes
        if participant_ids:
            participant_set = set(participant_ids)
            candidates = [
                e for e in candidates
                if set(e.participants) & participant_set
            ]
        
        # Pontua por query
        if query:
            scored = []
            for episode in candidates:
                score = episode.similarity_score(query, context)
                if score > 0:
                    scored.append((episode, score))
            
            scored.sort(key=lambda x: x[1], reverse=True)
            candidates = [e for e, _ in scored[:limit]]
        else:
            # Ordena por importância/recência
            candidates.sort(
                key=lambda e: (e.importance, e.timestamp),
                reverse=True,
            )
        
        return candidates[:limit]
    
    def _find_similar_episodes(self, episode: Episode, threshold: float = 0.7) -> list[Episode]:
        """Encontra episódios similares para consolidação."""
        similar = []
        
        for existing in self._episodes.values():
            if existing.id != episode.id and episode.matches_pattern(existing, threshold):
                similar.append(existing)
        
        return similar
    
    # ==================== RELATION OPERATIONS ====================
    
    def add_relation(self, relation: Relation) -> Relation:
        """
        Adiciona ou reforça uma relação.
        """
        # Verifica se já existe
        existing = self._find_existing_relation(
            relation.from_id,
            relation.relation_type,
            relation.to_id,
        )
        
        if existing:
            existing.reinforce()
            self._save()
            return existing
        
        # Adiciona nova
        self._relations[relation.id] = relation
        self._index_relation(relation)
        self._save()
        return relation
    
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
        
        Args:
            query: Texto da pergunta/contexto do usuário
            context: Informações adicionais (entidades conhecidas, etc.)
            limit: Máximo de resultados por tipo
            
        Returns:
            RecallResult com entidades, episódios e relações relevantes
        """
        context = context or {}
        
        # Busca entidades
        entities = self.find_entities(query=query, limit=limit)
        
        # Extrai IDs para contexto
        entity_ids = [e.id for e in entities]
        enriched_context = {**context, "entity_ids": entity_ids}
        
        # Busca episódios
        episodes = self.find_episodes(
            query=query,
            participant_ids=entity_ids if entity_ids else None,
            limit=limit,
            context=enriched_context,
        )
        
        # Busca relações entre os encontrados
        all_ids = entity_ids + [ep.id for ep in episodes]
        relations = []
        for id_ in all_ids:
            relations.extend(self.get_relations(from_id=id_))
            relations.extend(self.get_relations(to_id=id_))
        
        # Remove duplicatas
        seen_relation_ids = set()
        unique_relations = []
        for rel in relations:
            if rel.id not in seen_relation_ids:
                seen_relation_ids.add(rel.id)
                unique_relations.append(rel)
        
        # Gera resumo
        summary = self._generate_context_summary(entities, episodes, unique_relations)
        
        # Marca como acessadas
        for entity in entities:
            entity.touch()
        for episode in episodes:
            episode.boost_importance(0.05)
        
        self._save()
        
        return RecallResult(
            entities=entities,
            episodes=episodes,
            relations=unique_relations[:10],  # Limita relações
            context_summary=summary,
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
    
    def add_episode_with_consolidation(self, episode: Episode) -> tuple[bool, int]:
        """
        Adiciona episódio e verifica se deve consolidar.
        
        Returns:
            Tuple of (was_consolidated, consolidation_count)
        """
        # Busca episódios similares
        similar = self._find_similar_episodes(episode)
        
        if len(similar) >= 4:  # 5+ similares = consolida
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
        
        if self.storage_path:
            graph_file = self.storage_path / "memory_graph.json"
            if graph_file.exists():
                graph_file.unlink()
    
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
        }
    
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
            avg_importance = 0
        
        # Força média das relações
        if self._relations:
            avg_strength = sum(r.strength for r in self._relations.values()) / len(self._relations)
        else:
            avg_strength = 0
        
        return {
            "total_entities": len(self._entities),
            "total_episodes": len(self._episodes),
            "total_relations": len(self._relations),
            "orphan_entities": len(orphan_entities),
            "lonely_episodes": len(lonely_episodes),
            "weak_relations": len(weak_relations),
            "avg_episode_importance": round(avg_importance, 3),
            "avg_relation_strength": round(avg_strength, 3),
            "health_score": self._calculate_health_score(
                orphan_entities, lonely_episodes, weak_relations
            ),
        }
    
    def _calculate_health_score(
        self,
        orphan_entities: list[str],
        lonely_episodes: list[Episode],
        weak_relations: list[Relation],
    ) -> float:
        """Calcula um score de saúde do grafo (0-100)."""
        total = len(self._entities) + len(self._episodes) + len(self._relations)
        if total == 0:
            return 100.0
        
        problems = len(orphan_entities) + len(lonely_episodes) + len(weak_relations)
        health = max(0, 100 - (problems / total * 100))
        
        return round(health, 1)

    def __repr__(self) -> str:
        stats = self.stats()
        return (
            f"MemoryGraph(entities={stats['total_entities']}, "
            f"episodes={stats['total_episodes']}, "
            f"relations={stats['total_relations']})"
        )
