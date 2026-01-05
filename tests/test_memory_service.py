"""
Tests for MemoryService.
"""

import tempfile
from pathlib import Path

import pytest

from cortex.services.memory_service import (
    MemoryService,
    StoreRequest,
    RecallRequest,
    ParticipantInput,
    RelationInput,
)


@pytest.fixture
def service() -> MemoryService:
    """Create a MemoryService with temporary storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield MemoryService(storage_path=Path(tmpdir))


class TestStoreMemory:
    """Tests for storing memories."""
    
    def test_store_basic_episode(self, service: MemoryService) -> None:
        """Test storing a basic episode without participants."""
        request = StoreRequest(
            action="tested",
            outcome="success",
        )
        
        response = service.store(request)
        
        assert response.success is True
        assert response.episode_id is not None
        assert response.entities_created == 0
        assert response.consolidated is False
    
    def test_store_with_participants(self, service: MemoryService) -> None:
        """Test storing episode with participant entities."""
        request = StoreRequest(
            action="analyzed",
            outcome="found 3 errors",
            participants=[
                ParticipantInput(
                    type="file",
                    name="apache.log",
                    identifiers=["sha256:abc123"],
                ),
            ],
        )
        
        response = service.store(request)
        
        assert response.success is True
        assert response.entities_created == 1
    
    def test_store_updates_existing_entity(self, service: MemoryService) -> None:
        """Test that storing with same identifier updates existing entity."""
        # First store
        request1 = StoreRequest(
            action="first_action",
            outcome="first_outcome",
            participants=[
                ParticipantInput(
                    type="person",
                    name="João",
                    identifiers=["joao@email.com"],
                ),
            ],
        )
        response1 = service.store(request1)
        
        # Second store with same identifier
        request2 = StoreRequest(
            action="second_action",
            outcome="second_outcome",
            participants=[
                ParticipantInput(
                    type="person",
                    name="João Silva",  # Name changed
                    identifiers=["joao@email.com"],  # Same identifier
                ),
            ],
        )
        response2 = service.store(request2)
        
        assert response1.entities_created == 1
        assert response2.entities_created == 0
        assert response2.entities_updated == 1


class TestRecallMemory:
    """Tests for recalling memories."""
    
    def test_recall_empty(self, service: MemoryService) -> None:
        """Test recall with no memories stored."""
        request = RecallRequest(query="anything")
        
        response = service.recall(request)
        
        assert response.entities_found == 0
        assert response.episodes_found == 0
    
    def test_recall_finds_stored(self, service: MemoryService) -> None:
        """Test that recall finds stored memories."""
        # Store something
        store_request = StoreRequest(
            action="analyzed_log",
            outcome="found errors",
            participants=[
                ParticipantInput(type="file", name="apache.log"),
            ],
        )
        service.store(store_request)
        
        # Recall
        recall_request = RecallRequest(query="apache log")
        response = service.recall(recall_request)
        
        assert response.entities_found >= 1
        assert any(e.name == "apache.log" for e in response.entities)


class TestStats:
    """Tests for statistics."""
    
    def test_stats_empty(self, service: MemoryService) -> None:
        """Test stats with empty graph."""
        stats = service.stats()
        
        assert stats.total_entities == 0
        assert stats.total_episodes == 0
        assert stats.total_relations == 0
    
    def test_stats_after_store(self, service: MemoryService) -> None:
        """Test stats after storing."""
        request = StoreRequest(
            action="test",
            outcome="success",
            participants=[
                ParticipantInput(type="test", name="entity1"),
            ],
        )
        service.store(request)
        
        stats = service.stats()
        
        assert stats.total_entities == 1
        assert stats.total_episodes == 1


class TestClear:
    """Tests for clearing memories."""
    
    def test_clear(self, service: MemoryService) -> None:
        """Test clearing all memories."""
        # Store something
        request = StoreRequest(
            action="test",
            outcome="success",
            participants=[
                ParticipantInput(type="test", name="entity1"),
            ],
        )
        service.store(request)
        
        # Verify stored
        assert service.stats().total_entities == 1
        
        # Clear
        service.clear()
        
        # Verify cleared
        assert service.stats().total_entities == 0
        assert service.stats().total_episodes == 0
