"""
Cortex LangChain Integration - Plug-and-play memory for LangChain.

Uso:
    from cortex.integrations import CortexLangChainMemory
    from langchain.chains import LLMChain
    from langchain_openai import ChatOpenAI
    
    # Cria memória Cortex
    memory = CortexLangChainMemory(namespace="meu_agente:usuario_123")
    
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

from typing import Any, Dict, List

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

import sys
import os

# Adiciona path do SDK
sdk_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sdk_path not in sys.path:
    sys.path.insert(0, sdk_path)

from cortex_memory import CortexMemory


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
        namespace: Identificador para isolamento de memórias
        memory_key: Chave usada no prompt (default: "history")
        input_key: Chave da mensagem do usuário (default: "input")
        output_key: Chave da resposta (default: "output")
    """
    
    namespace: str = "default"
    cortex_url: str = "http://localhost:8000"
    memory_key: str = "history"
    input_key: str = "input"
    output_key: str = "output"
    return_messages: bool = False
    
    # Internal
    _cortex: CortexMemory = None
    _last_context: str = ""
    
    class Config:
        arbitrary_types_allowed = True
        underscore_attrs_are_private = True
    
    def __init__(self, **kwargs):
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain não está instalado. "
                "Instale com: pip install langchain langchain-core"
            )
        
        super().__init__(**kwargs)
        self._cortex = CortexMemory(
            namespace=self.namespace,
            cortex_url=self.cortex_url,
        )
    
    @property
    def memory_variables(self) -> List[str]:
        """Variáveis de memória disponíveis para o prompt."""
        return [self.memory_key]
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Carrega memória ANTES da geração.
        
        Chamado automaticamente pelo LangChain antes de gerar resposta.
        Busca contexto relevante no Cortex.
        
        Args:
            inputs: Dict com inputs da chain (inclui mensagem do usuário)
            
        Returns:
            Dict com {memory_key: contexto}
        """
        # Extrai mensagem do usuário
        user_input = inputs.get(self.input_key, "")
        if not user_input:
            # Tenta encontrar em outras chaves
            for key in ["question", "query", "human_input", "text"]:
                if key in inputs:
                    user_input = inputs[key]
                    break
        
        # Busca contexto
        context = self._cortex.before(str(user_input))
        self._last_context = context
        
        if self.return_messages:
            # Retorna como mensagens (para ChatModels)
            from langchain_core.messages import SystemMessage
            if context:
                return {self.memory_key: [SystemMessage(content=context)]}
            return {self.memory_key: []}
        
        # Retorna como string (para LLMs)
        return {self.memory_key: context}
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, str]) -> None:
        """
        Salva contexto DEPOIS da geração.
        
        Chamado automaticamente pelo LangChain após gerar resposta.
        Armazena a interação no Cortex com extração automática de W5H.
        
        Args:
            inputs: Dict com inputs (mensagem do usuário)
            outputs: Dict com outputs (resposta do LLM)
        """
        # Extrai mensagem do usuário
        user_input = inputs.get(self.input_key, "")
        if not user_input:
            for key in ["question", "query", "human_input", "text"]:
                if key in inputs:
                    user_input = inputs[key]
                    break
        
        # Extrai resposta
        assistant_output = outputs.get(self.output_key, "")
        if not assistant_output:
            for key in ["answer", "response", "text", "output"]:
                if key in outputs:
                    assistant_output = outputs[key]
                    break
        
        # Armazena
        if user_input and assistant_output:
            self._cortex.after(str(user_input), str(assistant_output))
    
    def clear(self) -> None:
        """Limpa memória do namespace."""
        self._cortex.clear()
    
    @property
    def cortex(self) -> CortexMemory:
        """Acesso ao cliente Cortex subjacente."""
        return self._cortex

