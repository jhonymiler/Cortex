"""
Backward-compatibility shim.

``HermesCortexBridge`` was the original name of the framework-agnostic bridge.
It is kept as a thin alias of :class:`cortext.integration.bridge.AgentMemoryBridge`
so existing imports keep working. New code should use ``AgentMemoryBridge``.
"""

from __future__ import annotations

from cortext.integration.bridge import AgentMemoryBridge


class HermesCortexBridge(AgentMemoryBridge):
    """Deprecated alias of :class:`AgentMemoryBridge`. Use that instead."""

    def __init__(self, namespace: str = "hermes", **kwargs) -> None:
        super().__init__(namespace=namespace, **kwargs)


__all__ = ["HermesCortexBridge"]
