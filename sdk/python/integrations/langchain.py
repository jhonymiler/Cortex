"""
Cortex LangChain Integration - Plug-and-play memory for LangChain.

Uso:
    from cortex_memory_sdk import CortexMemorySDK
    from integrations import CortexLangChainMemory
    from langchain.chains import LLMChain
    from langchain_openai import ChatOpenAI
    
    # Cria SDK
    sdk = CortexMemorySDK(namespace="meu_agente:usuario_123")
    
    # Cria memória Cortex
    memory = CortexLangChainMemory(sdk=sdk)
    
    # Usa normalmente com LangChain
    llm = ChatOpenAI()
    chain = LLMChain(llm=llm, memory=memory, prompt=prompt)
    
    # Recall/Store automáticos!
    response = chain.run("Olá, sou Maria")

Compatível com:
- LangChain >= 0.1.0
- LangChain-core
- LCEL (LangChain Expression Language)
"""

import sys
import os
from typing import Any

# Importação condicional do LangChain
try:
    from langchain_core.memory import BaseMemory
    from langchain_core.pydantic_v1 import Field
    LANGCHAIN_AVAILABLE = True
except ImportError:
    try:
        from langchain.memory.chat_memory import BaseMemory
        from pydantic import Field
        LANGCHAIN_AVAILABLE = True
    except ImportError:
        LANGCHAIN_AVAILABLE = False
        BaseMemory = object
        Field = lambda **kwargs: None

# Adiciona path do SDK
sdk_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sdk_path not in sys.path:
    sys.path.insert(0, sdk_path)

from cortex_memory_sdk import CortexMemorySDK, extract_action


class CortexLangChainMemory(BaseMemory):
    """
    Memória Cortex para LangChain.
    
    Implementa a interface BaseMemory do LangChain, permitindo
    uso plug-and-play com chains e agents.
    
    A memória é:
    - Persistente entre sessões
    - Isolada por namespace
    - Com extração automática de W5H
    
    Attributes:
        sdk: Instância do CortexMemorySDK
        memory_key: Chave usada no prompt (default: "history")
        input_key: Chave da mensagem do usuário (default: "input")
        output_key: Chave da resposta (default: "output")
    """
    
    sdk: CortexMemorySDK = None
    memory_key: str = "history"
    input_key: str = "input"
    output_key: str = "output"
    return_messages: bool = False
    context_limit: int = 3
    
    def __init__(
        self,
        sdk: CortexMemorySDK | None = None,
        namespace: str = "default",
        memory_key: str = "history",
        input_key: str = "input",
        output_key: str = "output",
        **kwargs,
    ):
        """
        Inicializa memória LangChain com Cortex.
        
        Args:
            sdk: Instância do CortexMemorySDK (ou cria um novo)
            namespace: Namespace se sdk não fornecido
            memory_key: Chave para memória no prompt
            input_key: Chave para entrada do usuário
            output_key: Chave para resposta do LLM
        """
        super().__init__(**kwargs)
        
        self.sdk = sdk or CortexMemorySDK(namespace=namespace)
        self.memory_key = memory_key
        self.input_key = input_key
        self.output_key = output_key
    
    @property
    def memory_variables(self) -> list[str]:
        """Retorna variáveis de memória para o prompt."""
        return [self.memory_key]
    
    def load_memory_variables(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """
        Carrega memórias relevantes para o prompt.
        
        Chamado automaticamente pelo LangChain antes de executar.
        """
        query = inputs.get(self.input_key, "")
        
        result = self.sdk.recall(query, limit=self.context_limit)
        
        if self.return_messages:
            from langchain_core.messages import SystemMessage
            return {
                self.memory_key: [SystemMessage(content=result.to_prompt_context())]
            }
        
        return {self.memory_key: result.to_prompt_context()}
    
    def save_context(self, inputs: dict[str, Any], outputs: dict[str, str]) -> None:
        """
        Salva contexto da interação na memória.
        
        Chamado automaticamente pelo LangChain após resposta.
        """
        input_text = inputs.get(self.input_key, "")
        output_text = outputs.get(self.output_key, "")
        
        # Tenta extrair do output primeiro (marcadores)
        action = extract_action(output_text)
        if action:
            self.sdk.remember(action)
            return
        
        # Senão, processa input como best-effort
        self.sdk.process(input_text)
    
    def clear(self) -> None:
        """Limpa histórico da sessão (não limpa memória persistente)."""
        pass
    
    @classmethod
    def from_namespace(cls, namespace: str, **kwargs) -> "CortexLangChainMemory":
        """
        Cria instância a partir de namespace.
        
        Args:
            namespace: Identificador único (ex: "support:user_123")
        """
        sdk = CortexMemorySDK(namespace=namespace)
        return cls(sdk=sdk, **kwargs)


# ============================================
# Exemplos de uso
# ============================================

def example_langchain_usage():
    """
    Exemplo completo de uso com LangChain.
    
    Requer:
        pip install langchain langchain-openai
    """
    if not LANGCHAIN_AVAILABLE:
        print("❌ LangChain não instalado")
        return
    
    from cortex_memory_sdk import CortexMemorySDK
    
    # 1. Cria SDK
    sdk = CortexMemorySDK(
        namespace="example:user_123",
        api_url="http://localhost:8000",
    )
    
    # 2. Cria memória
    memory = CortexLangChainMemory(sdk=sdk)
    
    # 3. Simula uso
    print("📝 Simulando LangChain...")
    
    # Load (antes de responder)
    context = memory.load_memory_variables({"input": "Olá, sou Carlos"})
    print(f"Contexto: {context}")
    
    # Save (após responder)
    memory.save_context(
        {"input": "Olá, sou Carlos"},
        {"output": "Olá Carlos! Como posso ajudar?"}
    )
    
    print("✅ Memória salva!")
    
    # Verifica recall
    context2 = memory.load_memory_variables({"input": "Qual era meu nome?"})
    print(f"Recall: {context2}")


if __name__ == "__main__":
    example_langchain_usage()
