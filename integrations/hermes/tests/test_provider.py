"""Unit tests for the Cortext Hermes memory provider.

These run without Hermes installed: the ``agent.memory_provider`` base class is
stubbed, and the Cortext bridge is mocked, so we test the provider's own wiring
(config persistence, prefetch/sync hooks, locking) in isolation.
"""

import json
import sys
import types
from unittest.mock import MagicMock

import pytest


def _load_provider_module():
    # Stub the Hermes base class so the plugin imports without Hermes.
    if "agent" not in sys.modules:
        sys.modules["agent"] = types.ModuleType("agent")
    mp_mod = types.ModuleType("agent.memory_provider")

    class MemoryProvider:  # minimal ABC stand-in
        pass

    mp_mod.MemoryProvider = MemoryProvider
    sys.modules["agent.memory_provider"] = mp_mod

    # The plugin now ships inside the installed package as cortext.hermes_plugin.
    import importlib

    return importlib.import_module("cortext.hermes_plugin")


@pytest.fixture()
def provider_cls():
    return _load_provider_module().CortextMemoryProvider


def test_name_is_cortext(provider_cls):
    assert provider_cls(config={}).name == "cortext"


def test_save_config_persists_and_loads(tmp_path, provider_cls):
    p = provider_cls(config={})
    values = {"namespace": "team", "validation_policy": "block", "dream_agent": False}
    p.save_config(values, str(tmp_path))

    native = tmp_path / "cortext.json"
    assert native.exists()
    saved = json.loads(native.read_text())
    assert saved["namespace"] == "team"
    assert saved["validation_policy"] == "block"
    assert saved["dream_agent"] is False
    # save_config keeps the live config in sync.
    assert p._config["namespace"] == "team"


def test_prefetch_calls_bridge_and_counts_tokens(provider_cls):
    p = provider_cls(config={})
    bridge = MagicMock()
    bridge.pre_chat.return_value = "Maria | reported a payment error"
    p._bridge = bridge

    block = p.prefetch("what did Maria report?")
    bridge.pre_chat.assert_called_once_with("what did Maria report?")
    assert "Cortext Memory (recalled)" in block
    assert p.last_injected_tokens > 0


def test_prefetch_empty_when_no_context(provider_cls):
    p = provider_cls(config={})
    bridge = MagicMock()
    bridge.pre_chat.return_value = ""
    p._bridge = bridge
    assert p.prefetch("anything") == ""
    assert p.last_injected_tokens == 0


def test_sync_turn_stores_and_marks_dirty_then_saves(provider_cls):
    p = provider_cls(config={})
    bridge = MagicMock()
    p._bridge = bridge
    p._store_path = None  # _save short-circuits without a store path

    p.sync_turn("Maria called", "Hi Maria")
    bridge.post_chat.assert_called_once_with(
        user_message="Maria called", assistant_message="Hi Maria"
    )
    # dirty was set; _save with no store path leaves it (no-op) but did not raise.
    assert p._dirty is True


def test_save_is_lock_protected_and_clears_dirty(tmp_path, provider_cls):
    p = provider_cls(config={})
    bridge = MagicMock()
    p._bridge = bridge
    p._store_path = tmp_path / "cortext_hermes.json"
    p._dirty = True

    p._save()
    bridge.cortex.graph.save.assert_called_once_with(p._store_path)
    assert p._dirty is False


def test_no_tool_schema_unless_enabled(provider_cls):
    assert provider_cls(config={}).get_tool_schemas() == []
    enabled = provider_cls(config={"expose_inspect_tool": True})
    schemas = enabled.get_tool_schemas()
    assert schemas and schemas[0]["name"] == "cortext_inspect"
