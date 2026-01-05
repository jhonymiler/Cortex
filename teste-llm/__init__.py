
"""
Agentes de Teste - Cortex Memory System

Este módulo contém agentes que demonstram diferentes formas de integração:

Agentes Disponíveis:
- agent.py: ADK + Ollama (sem memória - agnóstico)
- agent_with_sdk.py: ADK + Cortex via MemoryService SDK
- agent_with_mcp.py: ADK + Cortex via MCP (agnóstico)
- crew_agent.py: CrewAI + Ollama + Cortex SDK

Integração de Memória:
1. SDK (agent_with_sdk.py): Usa biblioteca específica do Cortex
2. MCP (agent_with_mcp.py): Usa Model Context Protocol (padrão)

Veja README.md para mais detalhes.
"""

__version__ = "3.0.0"
__all__ = ["create_agent", "create_agent_with_memory", "create_agent_with_mcp"]
