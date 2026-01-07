"""
Cortex Google ADK Integration - Memory for Google Agent Development Kit.

Uso:
    from cortex_memory_sdk import CortexMemorySDK
    from integrations.google_adk import CortexADKMemory
    from google.adk import Agent
    
    # Cria SDK
    sdk = CortexMemorySDK(namespace="meu_agente:usuario_123")
    memory = CortexADKMemory(sdk)
    
    # Integra com agente
    agent = Agent(
        name="support-agent",
        model="gemini-pro",
    )
    
    # No loop de interação
    response = agent.run(user_input)
    memory.after_response(user_input, response)
    
    # Busca contexto
    context = memory.get_context(user_input)

Compatível com:
- Google ADK >= 0.1.0
- Gemini API
"""

import sys
import os
from typing import Any, Optional
from dataclasses import dataclass

# Adiciona path do SDK
sdk_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sdk_path not in sys.path:
    sys.path.insert(0, sdk_path)

from cortex_memory_sdk import CortexMemorySDK, extract_action, remove_memory_marker


@dataclass
class MemoryContext:
    """Contexto de memória para injeção no prompt."""
    text: str
    memories_count: int
    
    def __bool__(self) -> bool:
        return bool(self.text)
    
    def __str__(self) -> str:
        return self.text


class CortexADKMemory:
    """
    Integração de memória Cortex para Google ADK.
    
    Fornece:
    - get_context(): Busca memórias antes de responder
    - after_response(): Armazena memória após resposta
    - wrap_agent(): Decorator para automatizar
    
    Example:
        sdk = CortexMemorySDK(namespace="support:user_123")
        memory = CortexADKMemory(sdk)
        
        # Manual
        context = memory.get_context("Olá, sou Maria")
        response = agent.run(user_input, context=context.text)
        memory.after_response(user_input, response)
        
        # Ou automático
        wrapped_agent = memory.wrap_agent(agent)
        response = wrapped_agent.run("Olá, sou Maria")
    """
    
    def __init__(
        self,
        sdk: CortexMemorySDK,
        auto_extract: bool = True,
        context_limit: int = 3,
    ):
        """
        Inicializa integração.
        
        Args:
            sdk: Instância do CortexMemorySDK
            auto_extract: Se True, tenta extrair Action automaticamente
            context_limit: Máximo de memórias no contexto
        """
        self.sdk = sdk
        self.auto_extract = auto_extract
        self.context_limit = context_limit
    
    def get_context(self, query: str) -> MemoryContext:
        """
        Busca memórias relevantes para a query.
        
        Args:
            query: Mensagem do usuário
        
        Returns:
            MemoryContext com texto formatado para prompt
        """
        result = self.sdk.recall(query, limit=self.context_limit)
        
        if not result:
            return MemoryContext(text="", memories_count=0)
        
        return MemoryContext(
            text=result.to_prompt_context(),
            memories_count=len(result),
        )
    
    def after_response(
        self,
        user_input: str,
        agent_response: str,
        extract_from: str = "both",
    ) -> dict[str, Any]:
        """
        Processa resposta e armazena memória.
        
        Args:
            user_input: Mensagem original do usuário
            agent_response: Resposta do agente
            extract_from: "user", "agent", ou "both"
        
        Returns:
            Resultado do armazenamento
        """
        results = {"stored": [], "type": None}
        
        # Tenta extrair do agente primeiro (pode ter marcador)
        if extract_from in ("agent", "both"):
            action = extract_action(agent_response)
            if action:
                resp = self.sdk.remember(action)
                results["stored"].append(resp)
                results["type"] = "event"
        
        # Se não extraiu do agente, tenta do usuário
        if not results["stored"] and extract_from in ("user", "both"):
            if self.auto_extract:
                resp, tipo = self.sdk.process(user_input)
                results["stored"].append(resp)
                results["type"] = tipo
        
        return results
    
    def clean_response(self, response: str) -> str:
        """Remove marcadores de memória da resposta."""
        return remove_memory_marker(response)
    
    def remember(self, action: dict) -> dict[str, Any]:
        """
        Armazena memória explicitamente.
        
        Args:
            action: { verb, subject, object, modifiers }
        """
        return self.sdk.remember(action)
    
    def observe(self, text: str) -> dict[str, Any]:
        """Armazena observação bruta."""
        return self.sdk.observe(text)
    
    def wrap_agent(self, agent: Any) -> "WrappedADKAgent":
        """
        Wrapa um agente ADK para memória automática.
        
        Args:
            agent: Instância de google.adk.Agent
        
        Returns:
            Agente com memória integrada
        """
        return WrappedADKAgent(agent, self)


class WrappedADKAgent:
    """
    Wrapper para agente Google ADK com memória automática.
    
    Intercepta chamadas e adiciona:
    - Recall antes de responder
    - Store após responder
    """
    
    def __init__(self, agent: Any, memory: CortexADKMemory):
        self._agent = agent
        self._memory = memory
    
    def run(self, user_input: str, **kwargs) -> str:
        """
        Executa agente com memória.
        
        1. Busca contexto
        2. Injeta no prompt
        3. Executa agente
        4. Armazena memória
        5. Retorna resposta limpa
        """
        # 1. Busca contexto
        context = self._memory.get_context(user_input)
        
        # 2. Injeta contexto (se agente suportar)
        if context and hasattr(self._agent, 'context'):
            original_context = getattr(self._agent, 'context', '')
            self._agent.context = f"{original_context}\n\nMemórias:\n{context.text}"
        
        # 3. Executa
        response = self._agent.run(user_input, **kwargs)
        
        # 4. Armazena
        self._memory.after_response(user_input, response)
        
        # 5. Limpa resposta
        clean = self._memory.clean_response(response)
        
        return clean
    
    def __getattr__(self, name: str) -> Any:
        """Delega outros métodos ao agente original."""
        return getattr(self._agent, name)


# =============================================================================
# Exemplo de uso com Google ADK
# =============================================================================

def example_usage():
    """
    Exemplo de integração com Google ADK.
    
    Requer:
        pip install google-adk
    """
    from cortex_memory_sdk import CortexMemorySDK
    
    # 1. Cria SDK
    sdk = CortexMemorySDK(
        namespace="support:user_123",
        api_url="http://localhost:8000",
    )
    
    # 2. Cria integração
    memory = CortexADKMemory(sdk)
    
    # 3. Simula agente (sem Google ADK real)
    class MockAgent:
        def run(self, input: str) -> str:
            return f"Resposta para: {input}"
    
    agent = MockAgent()
    
    # 4. Uso manual
    user_input = "Olá, sou Carlos e preciso de ajuda"
    
    # Busca contexto
    context = memory.get_context(user_input)
    print(f"Contexto: {context}")
    
    # Executa
    response = agent.run(user_input)
    print(f"Resposta: {response}")
    
    # Armazena
    memory.after_response(user_input, response)
    
    # 5. Ou uso com wrapper
    wrapped = memory.wrap_agent(agent)
    response = wrapped.run("Qual era meu nome?")
    print(f"Resposta wrapped: {response}")


if __name__ == "__main__":
    example_usage()


