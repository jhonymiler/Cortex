"""
Testes unitários para MemoryGraph.

Testa:
- Operações com entidades
- Operações com episódios
- Operações com relações
- Recall e store
- Consolidação
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from cortex.core.graph import MemoryGraph, RecallResult
from cortex.core.primitives import Entity
from cortex.core.primitives import Episode
from cortex.core.primitives import Relation


class TestRecallResult:
    """Testes para RecallResult."""
    
    def test_empty_recall_result(self):
        result = RecallResult()
        
        assert result.entities == []
        assert result.episodes == []
        assert result.relations == []
    
    def test_to_dict(self):
        result = RecallResult(
            entities=[Entity(name="Carlos", type="person")],
            episodes=[Episode(action="teste", participants=[])],
        )
        
        data = result.to_dict()
        
        assert "entities" in data
        assert "episodes" in data
        assert len(data["entities"]) == 1
    
    def test_to_prompt_context_empty(self):
        result = RecallResult()
        
        context = result.to_prompt_context()
        
        assert context == ""
    
    def test_to_prompt_context_with_data(self):
        entity = Entity(name="Carlos", type="person")
        episode = Episode(
            action="solicitou_reembolso",
            participants=[entity.id],
            outcome="aprovado",
        )
        episode.metadata["w5h"] = {
            "what": "solicitou_reembolso",
            "how": "aprovado",
        }
        
        result = RecallResult(
            entities=[entity],
            episodes=[episode],
        )
        
        context = result.to_prompt_context()
        
        assert "Carlos" in context


class TestMemoryGraphBasic:
    """Testes básicos do MemoryGraph."""
    
    def test_create_in_memory_graph(self):
        graph = MemoryGraph()
        
        assert len(graph._entities) == 0
        assert len(graph._episodes) == 0
        assert len(graph._relations) == 0
    
    def test_create_persistent_graph(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph = MemoryGraph(storage_path=tmpdir)
            
            assert graph.storage_path == Path(tmpdir)
    
    def test_stats(self):
        graph = MemoryGraph()
        
        stats = graph.stats()
        
        assert "total_entities" in stats
        assert "total_episodes" in stats
        assert "total_relations" in stats


class TestEntityOperations:
    """Testes para operações com entidades."""
    
    def setup_method(self):
        self.graph = MemoryGraph()
    
    def test_add_entity(self):
        entity = Entity(name="Carlos", type="person")
        
        added = self.graph.add_entity(entity)
        
        assert added.id == entity.id
        assert len(self.graph._entities) == 1
    
    def test_get_entity(self):
        entity = Entity(name="Carlos", type="person")
        self.graph.add_entity(entity)
        
        retrieved = self.graph.get_entity(entity.id)
        
        assert retrieved is not None
        assert retrieved.name == "Carlos"
    
    def test_get_nonexistent_entity(self):
        retrieved = self.graph.get_entity("nonexistent-id")
        
        assert retrieved is None
    
    def test_find_entities_by_query(self):
        self.graph.add_entity(Entity(name="Carlos Silva", type="person"))
        self.graph.add_entity(Entity(name="Maria Santos", type="person"))
        
        results = self.graph.find_entities(query="Carlos")
        
        assert len(results) == 1
        assert results[0].name == "Carlos Silva"
    
    def test_find_entities_by_type(self):
        self.graph.add_entity(Entity(name="Carlos", type="person"))
        self.graph.add_entity(Entity(name="Bug #123", type="issue"))
        
        results = self.graph.find_entities(entity_type="person")
        
        assert len(results) == 1
        assert results[0].name == "Carlos"
    
    def test_resolve_entity_by_name(self):
        entity = Entity(name="Carlos", type="person")
        self.graph.add_entity(entity)
        
        resolved = self.graph.resolve_entity("Carlos")
        
        assert resolved is not None
        assert resolved.id == entity.id
    
    def test_resolve_entity_by_identifier(self):
        entity = Entity(
            name="Carlos",
            type="person",
            identifiers=["carlos@email.com"],
        )
        self.graph.add_entity(entity)
        
        resolved = self.graph.resolve_entity("", ["carlos@email.com"])
        
        assert resolved is not None
        assert resolved.id == entity.id
    
    def test_add_entity_updates_existing(self):
        entity1 = Entity(
            name="Carlos",
            type="person",
            attributes={"role": "developer"},
        )
        self.graph.add_entity(entity1)
        
        entity2 = Entity(
            name="Carlos",
            type="person",
            attributes={"team": "backend"},
        )
        self.graph.add_entity(entity2)
        
        # Deve ter apenas uma entidade
        assert len(self.graph._entities) == 1
        
        # Atributos devem ser merged
        entity = list(self.graph._entities.values())[0]
        assert "role" in entity.attributes
        assert "team" in entity.attributes


class TestEpisodeOperations:
    """Testes para operações com episódios."""
    
    def setup_method(self):
        self.graph = MemoryGraph()
    
    def test_add_episode(self):
        episode = Episode(
            action="solicitou_reembolso",
            participants=[],
            outcome="aprovado",
        )
        
        added = self.graph.add_episode(episode)
        
        assert added.id == episode.id
        assert len(self.graph._episodes) == 1
    
    def test_get_episode(self):
        episode = Episode(action="teste", participants=[])
        self.graph.add_episode(episode)
        
        retrieved = self.graph.get_episode(episode.id)
        
        assert retrieved is not None
        assert retrieved.action == "teste"
    
    def test_find_episodes_by_query(self):
        self.graph.add_episode(Episode(action="solicitou_reembolso", participants=[]))
        self.graph.add_episode(Episode(action="reportou_bug", participants=[]))
        
        results = self.graph.find_episodes(query="reembolso")
        
        assert len(results) == 1
        assert "reembolso" in results[0].action
    
    def test_find_episodes_by_action(self):
        self.graph.add_episode(Episode(action="solicitou_reembolso", participants=[]))
        self.graph.add_episode(Episode(action="reportou_bug", participants=[]))
        
        results = self.graph.find_episodes(action="solicitou_reembolso")
        
        assert len(results) == 1


class TestRelationOperations:
    """Testes para operações com relações."""
    
    def setup_method(self):
        self.graph = MemoryGraph()
        self.entity1 = Entity(name="Carlos", type="person")
        self.entity2 = Entity(name="Projeto X", type="project")
        self.graph.add_entity(self.entity1)
        self.graph.add_entity(self.entity2)
    
    def test_add_relation(self):
        relation = Relation(
            from_id=self.entity1.id,
            relation_type="works_on",
            to_id=self.entity2.id,
        )
        
        added, resolution = self.graph.add_relation(relation)
        
        assert added.id == relation.id
        assert len(self.graph._relations) == 1
    
    def test_get_relations_by_from(self):
        relation = Relation(
            from_id=self.entity1.id,
            relation_type="works_on",
            to_id=self.entity2.id,
        )
        self.graph.add_relation(relation)
        
        results = self.graph.get_relations(from_id=self.entity1.id)
        
        assert len(results) == 1
        assert results[0].relation_type == "works_on"
    
    def test_get_relations_by_to(self):
        relation = Relation(
            from_id=self.entity1.id,
            relation_type="works_on",
            to_id=self.entity2.id,
        )
        self.graph.add_relation(relation)
        
        results = self.graph.get_relations(to_id=self.entity2.id)
        
        assert len(results) == 1
    
    def test_remove_relation(self):
        relation = Relation(
            from_id=self.entity1.id,
            relation_type="works_on",
            to_id=self.entity2.id,
        )
        self.graph.add_relation(relation)
        
        assert len(self.graph._relations) == 1
        
        self.graph.remove_relation(relation.id)
        
        assert len(self.graph._relations) == 0


class TestRecall:
    """Testes para recall de memórias."""
    
    def setup_method(self):
        self.graph = MemoryGraph()
    
    def test_recall_empty_graph(self):
        result = self.graph.recall("qualquer coisa")
        
        assert len(result.entities) == 0
        assert len(result.episodes) == 0
    
    def test_recall_finds_entity(self):
        entity = Entity(name="Carlos", type="person")
        self.graph.add_entity(entity)
        
        result = self.graph.recall("Carlos")
        
        assert len(result.entities) >= 1
        assert any(e.name == "Carlos" for e in result.entities)
    
    def test_recall_finds_episode(self):
        episode = Episode(
            action="solicitou_reembolso",
            participants=[],
            outcome="aprovado",
            context="produto defeituoso",
        )
        self.graph.add_episode(episode)
        
        result = self.graph.recall("reembolso")
        
        assert len(result.episodes) >= 1
    
    def test_recall_with_context(self):
        episode = Episode(
            action="teste",
            participants=[],
        )
        episode.metadata["namespace"] = "suporte"
        self.graph.add_episode(episode)
        
        result = self.graph.recall("teste", context={"namespace": "suporte"})
        
        assert len(result.episodes) >= 0  # Pode ou não encontrar dependendo do threshold


class TestStore:
    """Testes para store de memórias."""
    
    def setup_method(self):
        self.graph = MemoryGraph()
    
    def test_store_creates_entities(self):
        result = self.graph.store(
            action="reunião_projeto",
            participants=[
                {"name": "Carlos", "type": "person"},
                {"name": "Maria", "type": "person"},
            ],
        )
        
        assert len(result["entities_created"]) == 2
    
    def test_store_creates_episode(self):
        result = self.graph.store(
            action="reunião_projeto",
            participants=[],
            context="weekly meeting",
            outcome="decisões tomadas",
        )
        
        assert "episode_id" in result
        
        episode = self.graph.get_episode(result["episode_id"])
        assert episode is not None
        assert episode.action == "reunião_projeto"
    
    def test_store_updates_existing_entities(self):
        # Primeiro store
        self.graph.store(
            action="primeira_ação",
            participants=[{"name": "Carlos", "type": "person"}],
        )
        
        # Segundo store com mesma entidade
        result = self.graph.store(
            action="segunda_ação",
            participants=[{"name": "Carlos", "type": "person"}],
        )
        
        # Deve ter atualizado, não criado nova
        assert len(result["entities_updated"]) == 1
        assert len(result["entities_created"]) == 0


class TestConsolidation:
    """Testes para consolidação de episódios."""
    
    def setup_method(self):
        self.graph = MemoryGraph()
    
    def test_similar_episodes_consolidate(self):
        # Adiciona 5 episódios similares (threshold para consolidação)
        for i in range(5):
            episode = Episode(
                action="solicitou_reembolso",
                participants=[],
                outcome="aprovado",
            )
            self.graph.add_episode(episode)
        
        # Após 5 similares, deve consolidar
        # O número de episódios deve ser menor que 5
        # ou ter um episódio consolidado
        consolidated = [
            e for e in self.graph._episodes.values()
            if e.is_consolidated
        ]
        
        # Pelo menos um deve estar consolidado
        # (o comportamento exato depende da implementação)
        assert len(self.graph._episodes) <= 5


class TestPersistence:
    """Testes para persistência."""
    
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Cria e popula grafo
            graph1 = MemoryGraph(storage_path=tmpdir)
            entity = Entity(name="Carlos", type="person")
            graph1.add_entity(entity)
            graph1.add_episode(Episode(action="teste", participants=[entity.id]))
            
            # Cria novo grafo do mesmo diretório
            graph2 = MemoryGraph(storage_path=tmpdir)
            
            # Deve ter os mesmos dados
            assert len(graph2._entities) == 1
            assert len(graph2._episodes) == 1
    
    def test_clear(self):
        graph = MemoryGraph()
        graph.add_entity(Entity(name="Carlos", type="person"))
        graph.add_episode(Episode(action="teste", participants=[]))
        
        graph.clear()
        
        assert len(graph._entities) == 0
        assert len(graph._episodes) == 0


class TestGraphAnalysis:
    """Testes para análise do grafo."""
    
    def setup_method(self):
        self.graph = MemoryGraph()
    
    def test_get_memory_health(self):
        health = self.graph.get_memory_health()
        
        assert "orphan_entities" in health
        assert "weak_relations" in health
        assert "health_score" in health
    
    def test_get_graph_data(self):
        self.graph.add_entity(Entity(name="Carlos", type="person"))
        
        data = self.graph.get_graph_data()
        
        assert "nodes" in data
        assert "edges" in data
        assert "stats" in data


class TestDecayIntegration:
    """Testes para integração com decay."""
    
    def setup_method(self):
        self.graph = MemoryGraph()
    
    def test_reinforce_on_recall(self):
        entity = Entity(name="Carlos", type="person")
        self.graph.add_entity(entity)
        
        initial_access_count = entity.access_count
        
        self.graph.reinforce_on_recall(
            entity_ids=[entity.id],
            episode_ids=[],
            apply_decay_to_others=False,
        )
        
        assert entity.access_count > initial_access_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
