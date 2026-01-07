"""
Cortex CrewAI Integration - Memory for CrewAI agents.

Uso:
    from cortex_memory_sdk import CortexMemorySDK
    from integrations import CortexCrewAIMemory
    from crewai import Agent, Task, Crew
    
    # Cria SDK
    sdk = CortexMemorySDK(namespace="crew:mission_1")
    memory = CortexCrewAIMemory(sdk)
    
    # Cria agente com memória
    agent = Agent(
        role='Pesquisador',
        goal='Encontrar informações',
        backstory='Especialista em pesquisa',
    )
    
    # Usa memória no contexto das tasks
    context = memory.get_context("pesquisa anterior")
    task = Task(
        description=f"Continue a pesquisa. Contexto: {context}",
        agent=agent
    )

Compatível com:
- CrewAI >= 0.1.0
"""

import sys
import os
from typing import Any
from dataclasses import dataclass

# Adiciona path do SDK
sdk_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sdk_path not in sys.path:
    sys.path.insert(0, sdk_path)

from cortex_memory_sdk import CortexMemorySDK, extract_action


@dataclass
class MemoryContext:
    """Contexto de memória para CrewAI."""
    text: str
    count: int
    
    def __bool__(self) -> bool:
        return bool(self.text)
    
    def __str__(self) -> str:
        return self.text


class CortexCrewAIMemory:
    """
    Integração de memória Cortex para CrewAI.
    
    Fornece contexto persistente para crews e agents.
    
    Attributes:
        sdk: Instância do CortexMemorySDK
        context_limit: Máximo de memórias retornadas
    """
    
    def __init__(
        self,
        sdk: CortexMemorySDK,
        context_limit: int = 5,
    ):
        """
        Inicializa integração CrewAI.
        
        Args:
            sdk: Instância do CortexMemorySDK
            context_limit: Máximo de memórias no contexto
        """
        self.sdk = sdk
        self.context_limit = context_limit
    
    def get_context(self, query: str) -> MemoryContext:
        """
        Busca contexto para uma task ou goal.
        
        Args:
            query: Descrição da task ou objetivo
        
        Returns:
            MemoryContext com texto formatado
        """
        result = self.sdk.recall(query, limit=self.context_limit)
        
        return MemoryContext(
            text=result.to_prompt_context(),
            count=len(result),
        )
    
    def remember_task(
        self,
        task_description: str,
        result: str,
        agent_role: str = "",
    ) -> dict[str, Any]:
        """
        Armazena resultado de uma task.
        
        Args:
            task_description: Descrição da task executada
            result: Resultado obtido
            agent_role: Role do agente que executou
        """
        # Tenta extrair de marcadores primeiro
        action = extract_action(result)
        if action:
            return self.sdk.remember(action)
        
        # Cria action a partir dos parâmetros
        return self.sdk.remember({
            "verb": "completed_task",
            "subject": agent_role or "agent",
            "object": task_description[:50],
            "modifiers": [result[:100]] if result else [],
        })
    
    def remember_crew_result(
        self,
        crew_goal: str,
        final_output: str,
        agents: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Armazena resultado final de uma crew.
        
        Args:
            crew_goal: Objetivo da crew
            final_output: Resultado final
            agents: Lista de agentes que participaram
        """
        modifiers = []
        if agents:
            modifiers.append(f"agents:{','.join(agents)}")
        if final_output:
            modifiers.append(final_output[:100])
        
        return self.sdk.remember({
            "verb": "completed_crew",
            "subject": "crew",
            "object": crew_goal[:50],
            "modifiers": modifiers,
        })
    
    def enrich_task_description(
        self,
        original_description: str,
        query: str | None = None,
    ) -> str:
        """
        Enriquece descrição de task com contexto de memória.
        
        Args:
            original_description: Descrição original da task
            query: Query para buscar contexto (usa description se None)
        
        Returns:
            Descrição enriquecida com contexto
        """
        search_query = query or original_description
        context = self.get_context(search_query)
        
        if not context:
            return original_description
        
        return f"""{original_description}

CONTEXTO RELEVANTE:
{context.text}"""
    
    @classmethod
    def from_namespace(cls, namespace: str, **kwargs) -> "CortexCrewAIMemory":
        """
        Cria instância a partir de namespace.
        
        Args:
            namespace: Identificador único (ex: "crew:mission_1")
        """
        sdk = CortexMemorySDK(namespace=namespace)
        return cls(sdk=sdk, **kwargs)


# ============================================
# Exemplos de uso
# ============================================

def example_crewai_usage():
    """
    Exemplo de uso com CrewAI.
    
    Requer:
        pip install crewai
    """
    from cortex_memory_sdk import CortexMemorySDK
    
    # 1. Cria SDK
    sdk = CortexMemorySDK(
        namespace="crew:research_123",
        api_url="http://localhost:8000",
    )
    
    # 2. Cria integração
    memory = CortexCrewAIMemory(sdk)
    
    # 3. Simula uso
    print("📝 Simulando CrewAI...")
    
    # Busca contexto para task
    context = memory.get_context("pesquisa sobre mercado")
    print(f"Contexto: {context}")
    
    # Enriquece task
    enriched = memory.enrich_task_description(
        "Pesquisar tendências de mercado",
        "pesquisa mercado"
    )
    print(f"Task enriquecida:\n{enriched}")
    
    # Armazena resultado
    memory.remember_task(
        "Pesquisar tendências",
        "Encontradas 5 tendências principais",
        "Researcher"
    )
    print("✅ Resultado armazenado!")
    
    # Armazena resultado da crew
    memory.remember_crew_result(
        "Análise de mercado",
        "Relatório completo gerado",
        ["Researcher", "Writer"]
    )
    print("✅ Crew result armazenado!")


if __name__ == "__main__":
    example_crewai_usage()
