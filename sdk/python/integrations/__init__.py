"""
Cortex Integrations - Adaptadores plug-and-play para frameworks populares.

Integrações disponíveis:
- LangChain: CortexLangChainMemory
- CrewAI: (em desenvolvimento)
- LangGraph: (em desenvolvimento)

Uso:
    from cortex.integrations import CortexLangChainMemory
    
    memory = CortexLangChainMemory(namespace="meu_agente")
    chain = LLMChain(llm=llm, memory=memory)  # Plug and play!
"""

# Importações lazy para evitar dependências obrigatórias
def __getattr__(name):
    if name == "CortexLangChainMemory":
        from .langchain import CortexLangChainMemory
        return CortexLangChainMemory
    
    if name == "CortexCrewAIMemory":
        from .crewai import CortexCrewAIMemory
        return CortexCrewAIMemory
    
    raise AttributeError(f"module 'cortex.integrations' has no attribute '{name}'")


__all__ = [
    "CortexLangChainMemory",
    "CortexCrewAIMemory",
]

