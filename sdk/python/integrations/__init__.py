"""
Cortex Integrations - Adaptadores plug-and-play para frameworks populares.

Integrações disponíveis:
- LangChain: CortexLangChainMemory
- CrewAI: CortexCrewAIMemory
- Google ADK: CortexADKMemory

Uso:
    from cortex_memory_sdk import CortexMemorySDK
    from integrations import CortexADKMemory
    
    sdk = CortexMemorySDK(namespace="meu_agente:user_123")
    memory = CortexADKMemory(sdk)
"""

# Importações lazy para evitar dependências obrigatórias
def __getattr__(name):
    if name == "CortexLangChainMemory":
        from .langchain import CortexLangChainMemory
        return CortexLangChainMemory
    
    if name == "CortexCrewAIMemory":
        from .crewai import CortexCrewAIMemory
        return CortexCrewAIMemory
    
    if name == "CortexADKMemory":
        from .google_adk import CortexADKMemory
        return CortexADKMemory
    
    raise AttributeError(f"module 'integrations' has no attribute '{name}'")


__all__ = [
    "CortexLangChainMemory",
    "CortexCrewAIMemory",
    "CortexADKMemory",
]

