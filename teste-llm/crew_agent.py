#!/usr/bin/env python3
"""
Agente CrewAI com Cortex como Memória Externa

Este é um agente REAL usando CrewAI que demonstra:
- Integração com Ollama como LLM
- Cortex SDK como sistema de memória externa
- Tools customizadas para recall/store
"""

import sys
from pathlib import Path

# Adiciona sdk/python ao path
sdk_path = Path(__file__).parent.parent / "sdk" / "python"
sys.path.insert(0, str(sdk_path))

from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from crewai import BaseLLM
from typing import Any, Dict, List, Optional, Union

import requests
from cortex_sdk import CortexClient, make_participant


# ==================== CORTEX TOOLS ====================

class CortexRecallTool(BaseTool):
    """Tool para buscar memórias relevantes no Cortex."""
    
    name: str = "cortex_recall"
    description: str = "Busca memórias relevantes no Cortex antes de responder"
    
    def __init__(self, cortex_client: CortexClient):
        super().__init__()
        self.cortex = cortex_client
    
    def _run(self, query: str, context: str = "") -> str:
        """
        Busca memórias relevantes.
        
        Args:
            query: O que buscar
            context: Contexto adicional
        
        Returns:
            Resumo das memórias encontradas
        """
        try:
            result = self.cortex.recall(query=query, context={"situation": context})
            
            if not result.get("success"):
                return "Nenhuma memória relevante encontrada."
            
            # Formata resultados
            output = []
            
            entities = result.get("entities", [])
            if entities:
                output.append(f"📌 Entidades ({len(entities)}):")
                for e in entities[:3]:  # Top 3
                    output.append(f"  - {e['name']} ({e['type']})")
            
            episodes = result.get("episodes", [])
            if episodes:
                output.append(f"\n📝 Episódios ({len(episodes)}):")
                for ep in episodes[:3]:  # Top 3
                    output.append(f"  - {ep['action']}: {ep['outcome']}")
            
            return "\n".join(output) if output else "Nenhuma memória relevante."
        
        except Exception as e:
            return f"Erro ao buscar memórias: {str(e)}"


class CortexStoreTool(BaseTool):
    """Tool para armazenar memórias no Cortex."""
    
    name: str = "cortex_store"
    description: str = "Armazena uma nova memória no Cortex após interação"
    
    def __init__(self, cortex_client: CortexClient):
        super().__init__()
        self.cortex = cortex_client
    
    def _run(
        self, 
        action: str, 
        outcome: str, 
        context: str = "",
        participant_name: str = "",
        participant_type: str = "user"
    ) -> str:
        """
        Armazena uma memória.
        
        Args:
            action: O que foi feito
            outcome: Resultado
            context: Contexto
            participant_name: Nome do participante
            participant_type: Tipo do participante
        
        Returns:
            Confirmação
        """
        try:
            participants = []
            if participant_name:
                participants.append(
                    make_participant(participant_type, participant_name)
                )
            
            result = self.cortex.store(
                action=action,
                outcome=outcome,
                participants=participants,
                context=context
            )
            
            if result.get("success"):
                return f"✅ Memória armazenada (ID: {result.get('episode_id', 'N/A')[:8]}...)"
            else:
                return "❌ Falha ao armazenar memória"
        
        except Exception as e:
            return f"Erro ao armazenar: {str(e)}"


# ==================== OLLAMA LLM CUSTOMIZADO ====================

class OllamaLLM(BaseLLM):
    """LLM customizado para Ollama local."""
    
    def __init__(
        self, 
        model: str = "llama3.2:3b",
        base_url: str = "http://localhost:11434",
        temperature: Optional[float] = 0.7
    ):
        super().__init__(model=model, temperature=temperature)
        self.base_url = base_url
        self.endpoint = f"{base_url}/api/generate"
    
    def call(
        self,
        messages: Union[str, List[Dict[str, str]]],
        tools: Optional[List[dict]] = None,
        callbacks: Optional[List[Any]] = None,
        available_functions: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Chama o Ollama local."""
        # Converte mensagens para prompt único
        if isinstance(messages, str):
            prompt = messages
        else:
            # Converte lista de mensagens em prompt único
            prompt_parts = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_parts.append(f"{role}: {content}")
            prompt = "\n".join(prompt_parts)
        
        # Chama Ollama
        try:
            response = requests.post(
                self.endpoint,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature or 0.7
                    }
                },
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        
        except Exception as e:
            return f"Erro ao chamar Ollama: {str(e)}"
    
    def supports_function_calling(self) -> bool:
        """Ollama não tem suporte nativo a function calling."""
        return False
    
    def get_context_window_size(self) -> int:
        """Context window do modelo."""
        return 8192


# ==================== AGENTE CREWAI ====================

class CortexCrew:
    """Crew com agente usando Cortex como memória."""
    
    def __init__(
        self,
        cortex_url: str = "http://localhost:8000",
        ollama_model: str = "llama3.2:3b",
        ollama_url: str = "http://localhost:11434"
    ):
        # Clientes
        self.cortex = CortexClient(base_url=cortex_url)
        self.llm = OllamaLLM(model=ollama_model, base_url=ollama_url)
        
        # Tools
        self.recall_tool = CortexRecallTool(cortex_client=self.cortex)
        self.store_tool = CortexStoreTool(cortex_client=self.cortex)
        
        # Agente
        self.agent = Agent(
            role="Assistente Inteligente com Memória",
            goal="Ajudar o usuário lembrando de interações anteriores e aprendendo com cada conversa",
            backstory="""
            Você é um assistente inteligente que usa o sistema Cortex para lembrar
            de conversas anteriores. Antes de responder, você SEMPRE busca memórias
            relevantes. Após responder, você SEMPRE armazena o que aprendeu.
            """,
            llm=self.llm,
            tools=[self.recall_tool, self.store_tool],
            verbose=True,
            allow_delegation=False
        )
    
    def chat(self, user_message: str) -> str:
        """
        Conversa com memória.
        
        Flow:
        1. Busca memórias relevantes (recall_tool)
        2. Processa com LLM
        3. Armazena interação (store_tool)
        """
        # Task com instruções claras
        task = Task(
            description=f"""
            ETAPA 1 - RECALL:
            Use a ferramenta cortex_recall para buscar memórias sobre: "{user_message}"
            
            ETAPA 2 - PROCESSAR:
            Analise as memórias e responda a mensagem do usuário: "{user_message}"
            
            ETAPA 3 - STORE:
            Use a ferramenta cortex_store para salvar:
            - action: "responded_to_user"
            - outcome: [seu resumo da resposta]
            - context: "{user_message}"
            - participant_name: "user"
            - participant_type: "person"
            
            Sua resposta final deve ser apenas a resposta ao usuário, sem mencionar as ferramentas.
            """,
            expected_output="Resposta útil ao usuário baseada em memórias",
            agent=self.agent
        )
        
        # Executa crew
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            process=Process.sequential,
            verbose=True
        )
        
        result = crew.kickoff()
        return result.raw if hasattr(result, 'raw') else str(result)


# ==================== CLI ====================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Agente CrewAI com Cortex Memory")
    parser.add_argument("--cortex-url", default="http://localhost:8000", help="URL do Cortex API")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="URL do Ollama")
    parser.add_argument("--model", default="llama3.2:3b", help="Modelo Ollama")
    parser.add_argument("--interactive", "-i", action="store_true", help="Modo interativo")
    parser.add_argument("message", nargs="*", help="Mensagem para o agente")
    
    args = parser.parse_args()
    
    # Cria crew
    print("🚀 Iniciando CortexCrew...")
    crew = CortexCrew(
        cortex_url=args.cortex_url,
        ollama_model=args.model,
        ollama_url=args.ollama_url
    )
    print("✅ Crew pronta!\n")
    
    if args.interactive:
        # Modo interativo
        print("💬 Modo interativo (Ctrl+C para sair)\n")
        while True:
            try:
                user_input = input("Você: ").strip()
                if not user_input:
                    continue
                
                print("\n🤖 Agente:")
                response = crew.chat(user_input)
                print(f"{response}\n")
            
            except KeyboardInterrupt:
                print("\n\n👋 Até logo!")
                break
            except Exception as e:
                print(f"❌ Erro: {e}\n")
    
    elif args.message:
        # Mensagem única
        message = " ".join(args.message)
        print(f"📨 Mensagem: {message}\n")
        print("🤖 Agente:")
        response = crew.chat(message)
        print(f"{response}\n")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
