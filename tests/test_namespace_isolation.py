"""
Tests for namespace isolation feature.

Validates that memories are properly isolated between namespaces,
ensuring no data leakage between different clients/users.
"""

import tempfile
from pathlib import Path

import pytest

from cortex.services.memory_service import (
    NamespacedMemoryService,
    StoreRequest,
    RecallRequest,
    ParticipantInput,
)


class TestNamespaceIsolation:
    """Tests for multi-tenant memory isolation."""

    @pytest.fixture
    def namespaced_service(self) -> NamespacedMemoryService:
        """Create a fresh namespaced service with temp storage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield NamespacedMemoryService(base_path=Path(tmpdir))

    def test_namespaces_are_isolated(self, namespaced_service: NamespacedMemoryService) -> None:
        """Test that different namespaces don't share memories."""
        # Store in namespace A
        namespaced_service.store(
            "agent_a:user_123",
            StoreRequest(
                action="analyzed",
                outcome="Found bug in auth module",
                participants=[ParticipantInput(type="file", name="auth.py")],
            ),
        )

        # Store in namespace B (different agent, same user)
        namespaced_service.store(
            "agent_b:user_123",
            StoreRequest(
                action="recommended",
                outcome="Suggested blue widgets",
                participants=[ParticipantInput(type="product", name="Blue Widget")],
            ),
        )

        # Store in namespace C (same agent, different user)
        namespaced_service.store(
            "agent_a:user_456",
            StoreRequest(
                action="resolved",
                outcome="Fixed login issue",
                participants=[ParticipantInput(type="ticket", name="TICKET-789")],
            ),
        )

        # Recall from namespace A - should only see auth.py
        result_a = namespaced_service.recall(
            "agent_a:user_123",
            RecallRequest(query="auth"),
        )
        assert result_a.entities_found >= 1
        assert any(e.name == "auth.py" for e in result_a.entities)
        # Should NOT see Blue Widget or TICKET-789
        assert not any(e.name == "Blue Widget" for e in result_a.entities)
        assert not any(e.name == "TICKET-789" for e in result_a.entities)

        # Recall from namespace B - should only see Blue Widget
        result_b = namespaced_service.recall(
            "agent_b:user_123",
            RecallRequest(query="widget"),
        )
        assert result_b.entities_found >= 1
        assert any(e.name == "Blue Widget" for e in result_b.entities)
        # Should NOT see auth.py or TICKET-789
        assert not any(e.name == "auth.py" for e in result_b.entities)
        assert not any(e.name == "TICKET-789" for e in result_b.entities)

        # Recall from namespace C - should only see TICKET-789
        result_c = namespaced_service.recall(
            "agent_a:user_456",
            RecallRequest(query="ticket"),
        )
        assert result_c.entities_found >= 1
        assert any(e.name == "TICKET-789" for e in result_c.entities)
        # Should NOT see auth.py or Blue Widget
        assert not any(e.name == "auth.py" for e in result_c.entities)
        assert not any(e.name == "Blue Widget" for e in result_c.entities)

    def test_empty_namespace_returns_nothing(self, namespaced_service: NamespacedMemoryService) -> None:
        """Test that new namespaces start empty."""
        # Store in one namespace
        namespaced_service.store(
            "populated_ns",
            StoreRequest(action="test", outcome="test data"),
        )

        # Recall from empty namespace
        result = namespaced_service.recall(
            "empty_ns",
            RecallRequest(query="test"),
        )

        assert result.entities_found == 0
        assert result.episodes_found == 0

    def test_namespace_stats_are_independent(self, namespaced_service: NamespacedMemoryService) -> None:
        """Test that stats are tracked per namespace."""
        # Store multiple items in namespace A
        for i in range(3):
            namespaced_service.store(
                "ns_a",
                StoreRequest(
                    action=f"action_{i}",
                    outcome=f"outcome_{i}",
                    participants=[ParticipantInput(type="entity", name=f"entity_{i}")],
                ),
            )

        # Store one item in namespace B
        namespaced_service.store(
            "ns_b",
            StoreRequest(action="single", outcome="single outcome"),
        )

        # Check stats are independent
        stats_a = namespaced_service.stats("ns_a")
        stats_b = namespaced_service.stats("ns_b")

        assert stats_a.total_episodes == 3
        assert stats_a.total_entities == 3
        assert stats_b.total_episodes == 1
        assert stats_b.total_entities == 0  # No participants

    def test_list_namespaces(self, namespaced_service: NamespacedMemoryService) -> None:
        """Test listing active namespaces."""
        # Create multiple namespaces
        namespaces = ["agent_1:user_a", "agent_1:user_b", "agent_2:user_a"]
        for ns in namespaces:
            namespaced_service.store(ns, StoreRequest(action="test", outcome="test"))

        # List should show all
        active = namespaced_service.list_namespaces()
        for ns in namespaces:
            assert ns in active

    def test_delete_namespace(self, namespaced_service: NamespacedMemoryService) -> None:
        """Test deleting a namespace removes all its data."""
        namespace = "to_delete:user"

        # Store some data
        namespaced_service.store(
            namespace,
            StoreRequest(
                action="important",
                outcome="valuable data",
                participants=[ParticipantInput(type="secret", name="TOP_SECRET")],
            ),
        )

        # Verify it exists
        result_before = namespaced_service.recall(namespace, RecallRequest(query="secret"))
        assert result_before.entities_found >= 1

        # Delete the namespace
        deleted = namespaced_service.delete_namespace(namespace)
        assert deleted

        # Verify it's gone - new recall should be empty
        result_after = namespaced_service.recall(namespace, RecallRequest(query="secret"))
        assert result_after.entities_found == 0
        assert result_after.episodes_found == 0

    def test_namespace_format_flexibility(self, namespaced_service: NamespacedMemoryService) -> None:
        """Test various namespace formats work correctly."""
        # Different format patterns
        formats = [
            "simple",
            "agent:user",
            "company_dept_team",
            "v1-prod-west-2",
            "user@email.com",  # Will be sanitized
        ]

        for ns in formats:
            namespaced_service.store(
                ns,
                StoreRequest(action="test", outcome=f"tested {ns}"),
            )

            result = namespaced_service.recall(ns, RecallRequest(query="test"))
            # Should at least find the episode (it's stored but entity might not match query)
            stats = namespaced_service.stats(ns)
            assert stats.total_episodes >= 1

    def test_global_stats(self, namespaced_service: NamespacedMemoryService) -> None:
        """Test aggregated stats across all namespaces."""
        # Create multiple namespaces with different data
        namespaced_service.store("ns1", StoreRequest(action="a1", outcome="o1"))
        namespaced_service.store("ns2", StoreRequest(action="a2", outcome="o2"))
        namespaced_service.store("ns2", StoreRequest(action="a3", outcome="o3"))

        # Global stats should aggregate
        global_stats = namespaced_service.global_stats()

        assert global_stats["total_namespaces"] >= 2
        assert "ns1" in global_stats["namespaces"]
        assert "ns2" in global_stats["namespaces"]


class TestNamespaceAPIIntegration:
    """Tests for API-level namespace handling."""

    def test_default_namespace(self) -> None:
        """Test that no header means 'default' namespace."""
        from cortex.api.app import get_namespace

        # When header is None, should return "default"
        assert get_namespace(None) == "default"

    def test_custom_namespace_from_header(self) -> None:
        """Test that header value is used as namespace."""
        from cortex.api.app import get_namespace

        assert get_namespace("my_agent:user_123") == "my_agent:user_123"
        assert get_namespace("production") == "production"
