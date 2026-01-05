"""
Tests for core models.
"""

from cortex.core import Entity, Episode, Relation


class TestEntity:
    """Tests for Entity model."""
    
    def test_create_entity(self) -> None:
        """Test creating a basic entity."""
        entity = Entity(
            type="person",
            name="João",
            identifiers=["joao@email.com"],
        )
        
        assert entity.type == "person"
        assert entity.name == "João"
        assert "joao@email.com" in entity.identifiers
        assert entity.id is not None
    
    def test_entity_matches_by_name(self) -> None:
        """Test entity matching by name."""
        entity = Entity(type="person", name="João Silva")
        
        assert entity.matches("João")
        assert entity.matches("silva")
        assert not entity.matches("Maria")
    
    def test_entity_matches_by_identifier(self) -> None:
        """Test entity matching by identifier."""
        entity = Entity(
            type="person",
            name="João",
            identifiers=["joao@email.com", "user_123"],
        )
        
        assert entity.matches("joao@email")
        assert entity.matches("user_123")
        assert not entity.matches("other@email")
    
    def test_entity_serialization(self) -> None:
        """Test entity to_dict and from_dict."""
        entity = Entity(
            type="file",
            name="config.yaml",
            identifiers=["sha256:abc"],
            attributes={"path": "/etc/config.yaml"},
        )
        
        data = entity.to_dict()
        restored = Entity.from_dict(data)
        
        assert restored.type == entity.type
        assert restored.name == entity.name
        assert restored.identifiers == entity.identifiers
        assert restored.attributes == entity.attributes


class TestEpisode:
    """Tests for Episode model."""
    
    def test_create_episode(self) -> None:
        """Test creating a basic episode."""
        episode = Episode(
            action="analyzed",
            participants=["entity_1", "entity_2"],
            context="debugging session",
            outcome="found bug",
        )
        
        assert episode.action == "analyzed"
        assert len(episode.participants) == 2
        assert episode.outcome == "found bug"
        assert episode.id is not None
    
    def test_episode_serialization(self) -> None:
        """Test episode to_dict and from_dict."""
        episode = Episode(
            action="resolved",
            participants=["entity_1"],
            outcome="success",
        )
        
        data = episode.to_dict()
        restored = Episode.from_dict(data)
        
        assert restored.action == episode.action
        assert restored.participants == episode.participants
        assert restored.outcome == episode.outcome


class TestRelation:
    """Tests for Relation model."""
    
    def test_create_relation(self) -> None:
        """Test creating a basic relation."""
        relation = Relation(
            from_id="entity_1",
            relation_type="caused_by",
            to_id="entity_2",
        )
        
        assert relation.from_id == "entity_1"
        assert relation.relation_type == "caused_by"
        assert relation.to_id == "entity_2"
        assert relation.strength == 0.5  # default is 0.5
    
    def test_relation_serialization(self) -> None:
        """Test relation to_dict and from_dict."""
        relation = Relation(
            from_id="a",
            relation_type="loves",
            to_id="b",
            strength=0.8,
        )
        
        data = relation.to_dict()
        restored = Relation.from_dict(data)
        
        assert restored.from_id == relation.from_id
        assert restored.relation_type == relation.relation_type
        assert restored.to_id == relation.to_id
        assert restored.strength == relation.strength
