"""Integration: framework-agnostic bridges to external systems.

The primary entry point for any framework (LangChain, LangGraph, CrewAI, a
plain loop, …) is :class:`cortext.CortexV5` directly. ``AgentMemoryBridge`` is
optional convenience sugar for the common recall-before / store-after chat
pattern. ``HermesCortexBridge`` is a deprecated alias kept for compatibility.
"""

from cortext.integration.bridge import AgentMemoryBridge
from cortext.integration.hermes_bridge import HermesCortexBridge

__all__ = ["AgentMemoryBridge", "HermesCortexBridge"]
