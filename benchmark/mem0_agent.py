"""
Mem0Agent - Baseline usando Mem0 para comparação com Cortex.

Mem0 é um sistema de memória open-source para LLM agents.
https://github.com/mem0ai/mem0

Este agente implementa integração com Mem0:
- Armazena memórias via API do Mem0
- Busca memórias relevantes antes de responder
- Usado como baseline para comparar com Cortex no paper

Instalação:
    pip install mem0ai
"""

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Tenta importar mem0
try:
    from mem0 import Memory
    MEM0_AVAILABLE = True
except ImportError:
    MEM0_AVAILABLE = False
    Memory = None

try:
    from benchmark.agents import call_llm_with_retry
except ImportError:
    from agents import call_llm_with_retry


@dataclass
class Mem0Response:
    """Resposta do Mem0 agent."""
    
    content: str
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    context_from_memory: str = ""
    memories_retrieved: int = 0


class SimpleMem0Memory:
    """
    Implementação simples que simula Mem0 para quando não está instalado.
    
    Armazena memórias como lista e busca por keywords.
    """
    
    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self._memories: list[dict] = []
    
    def add(self, messages: list[dict], user_id: str = None) -> dict:
        """Adiciona memória extraindo fatos das mensagens."""
        user_id = user_id or self.user_id
        
        # Extrai conteúdo das mensagens
        content_parts = []
        for msg in messages:
            if isinstance(msg, dict):
                content_parts.append(f"{msg.get('role', 'user')}: {msg.get('content', '')}")
            else:
                content_parts.append(str(msg))
        
        content = " ".join(content_parts)
        
        memory = {
            "id": f"mem_{len(self._memories)}",
            "memory": content,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
        }
        self._memories.append(memory)
        
        return {"results": [memory]}
    
    def search(self, query: str, user_id: str = None, limit: int = 5) -> dict:
        """Busca memórias por keywords."""
        user_id = user_id or self.user_id
        query_words = set(query.lower().split())
        
        scored = []
        for mem in self._memories:
            if mem["user_id"] != user_id:
                continue
            
            mem_words = set(mem["memory"].lower().split())
            intersection = len(query_words & mem_words)
            
            if intersection > 0:
                scored.append((mem, intersection))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return {"results": [m for m, _ in scored[:limit]]}
    
    def get_all(self, user_id: str = None) -> dict:
        """Retorna todas as memórias do usuário."""
        user_id = user_id or self.user_id
        memories = [m for m in self._memories if m["user_id"] == user_id]
        return {"results": memories}
    
    def delete_all(self, user_id: str = None) -> dict:
        """Deleta todas as memórias do usuário."""
        user_id = user_id or self.user_id
        self._memories = [m for m in self._memories if m["user_id"] != user_id]
        return {"success": True}


class RealMem0Memory:
    """
    Integração real com Mem0.
    
    Requer:
        pip install mem0ai
        
    E configuração de LLM (OpenAI ou Ollama).
    """
    
    def __init__(
        self,
        user_id: str = "default",
        ollama_url: str = "http://localhost:11434",
        model: str = "ministral-3:3b",
    ):
        if not MEM0_AVAILABLE:
            raise ImportError("mem0ai não está instalado. Use: pip install mem0ai")
        
        self.user_id = user_id
        
        # Configura Mem0 para usar Ollama
        config = {
            "llm": {
                "provider": "ollama",
                "config": {
                    "model": model,
                    "ollama_base_url": ollama_url,
                    "temperature": 0.1,
                },
            },
            "embedder": {
                "provider": "ollama",
                "config": {
                    "model": "nomic-embed-text",
                    "ollama_base_url": ollama_url,
                },
            },
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": f"mem0_{user_id}",
                },
            },
        }
        
        self._memory = Memory.from_config(config)
    
    def add(self, messages: list[dict], user_id: str = None) -> dict:
        """Adiciona memória via Mem0."""
        user_id = user_id or self.user_id
        result = self._memory.add(messages, user_id=user_id)
        return result
    
    def search(self, query: str, user_id: str = None, limit: int = 5) -> dict:
        """Busca memórias via Mem0."""
        user_id = user_id or self.user_id
        result = self._memory.search(query, user_id=user_id, limit=limit)
        return result
    
    def get_all(self, user_id: str = None) -> dict:
        """Retorna todas as memórias."""
        user_id = user_id or self.user_id
        result = self._memory.get_all(user_id=user_id)
        return result
    
    def delete_all(self, user_id: str = None) -> dict:
        """Deleta todas as memórias."""
        user_id = user_id or self.user_id
        result = self._memory.delete_all(user_id=user_id)
        return result


class Mem0Agent:
    """
    Agente LLM com memória Mem0.
    
    Implementa o padrão Mem0:
    1. Recebe query do usuário
    2. Busca memórias relevantes no Mem0
    3. Injeta memórias no prompt
    4. Gera resposta
    5. Armazena interação no Mem0
    
    Diferenças vs Cortex:
    - Usa salience extraction (Mem0 extrai fatos importantes)
    - Sem modelo W5H estruturado
    - Sem decaimento baseado em Ebbinghaus
    - Sem distinção personal/shared
    - Usa embeddings para busca
    """
    
    SYSTEM_PROMPT_TEMPLATE = """Você é um assistente útil e amigável com memória persistente.

{memory_context}

INSTRUÇÕES:
- Use as memórias para personalizar suas respostas.
- Se lembrar de algo sobre o usuário, mencione naturalmente.
- Seja consistente com informações anteriores.
"""
    
    def __init__(
        self,
        model: str = "ministral-3:3b",
        ollama_url: str = "http://localhost:11434",
        user_id: str = "mem0_benchmark",
        use_real_mem0: bool = False,
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.user_id = user_id
        
        # Seleciona implementação
        if use_real_mem0 and MEM0_AVAILABLE:
            try:
                self._memory = RealMem0Memory(
                    user_id=user_id,
                    ollama_url=ollama_url,
                    model=model,
                )
            except Exception as e:
                print(f"⚠️ Falha ao inicializar Mem0 real: {e}")
                print("   Usando implementação simples...")
                self._memory = SimpleMem0Memory(user_id=user_id)
        else:
            self._memory = SimpleMem0Memory(user_id=user_id)
        
        # Estado da sessão
        self._current_user: str | None = None
        self._session_history: list[dict] = []
        self._context_window_size = 10
        
        # Métricas
        self._total_messages = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_memory_time_ms = 0.0
    
    def new_session(self, user_id: str | None = None) -> None:
        """Inicia nova sessão."""
        self._current_user = user_id or self.user_id
        self._session_history = []
    
    def process_message(
        self,
        user_message: str,
        verbose: bool = False,
    ) -> Mem0Response:
        """
        Processa uma mensagem do usuário.
        
        1. Busca memórias relevantes no Mem0
        2. Gera resposta com contexto
        3. Armazena interação no Mem0
        """
        start_time = time.time()
        user_id = self._current_user or self.user_id
        
        # 1. Memory Search
        search_start = time.time()
        search_result = self._memory.search(user_message, user_id=user_id, limit=5)
        memories = search_result.get("results", [])
        search_time = (time.time() - search_start) * 1000
        
        # Formata contexto de memória
        if memories:
            context_parts = ["[Memórias Relevantes]"]
            for mem in memories[:3]:
                mem_text = mem.get("memory", str(mem))[:200]
                context_parts.append(f"- {mem_text}")
            memory_context = "\n".join(context_parts)
        else:
            memory_context = ""
        
        # 2. Gera resposta
        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(memory_context=memory_context)
        
        messages = [{"role": "system", "content": system_prompt}]
        for msg in self._session_history[-self._context_window_size:]:
            messages.append(msg)
        messages.append({"role": "user", "content": user_message})
        
        # Chama LLM
        response = call_llm_with_retry(
            model=f"ollama_chat/{self.model}",
            messages=messages,
            api_base=self.ollama_url,
            max_retries=3,
            initial_wait=5.0,
        )
        
        assistant_response = response.choices[0].message.content
        
        # 3. Armazena no Mem0
        store_start = time.time()
        self._memory.add(
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_response},
            ],
            user_id=user_id,
        )
        store_time = (time.time() - store_start) * 1000
        
        # Atualiza histórico da sessão
        self._session_history.append({"role": "user", "content": user_message})
        self._session_history.append({"role": "assistant", "content": assistant_response})
        
        # Métricas
        total_time = (time.time() - start_time) * 1000
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0
        
        self._total_messages += 1
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens
        self._total_memory_time_ms += search_time + store_time
        
        if verbose:
            print(f"    Mem0: {len(memories)} memories, {search_time:.0f}ms search, {store_time:.0f}ms store")
        
        return Mem0Response(
            content=assistant_response,
            total_tokens=prompt_tokens + completion_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=total_time,
            context_from_memory=memory_context,
            memories_retrieved=len(memories),
        )
    
    def clear_memory(self) -> None:
        """Limpa toda a memória."""
        user_id = self._current_user or self.user_id
        self._memory.delete_all(user_id=user_id)
    
    def get_stats(self) -> dict[str, Any]:
        """Retorna estatísticas do agente."""
        return {
            "type": "mem0",
            "model": self.model,
            "has_memory": True,
            "memory_type": "salience_extraction",
            "user_id": self.user_id,
            "uses_real_mem0": isinstance(self._memory, RealMem0Memory),
            "total_messages": self._total_messages,
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
            "total_memory_time_ms": self._total_memory_time_ms,
        }
    
    def set_namespace(self, namespace: str) -> None:
        """Atualiza o user_id/namespace."""
        self.user_id = namespace
        if isinstance(self._memory, SimpleMem0Memory):
            self._memory.user_id = namespace


# Para testes rápidos
if __name__ == "__main__":
    print("🔬 Testando Mem0Agent...")
    print(f"   Mem0 disponível: {MEM0_AVAILABLE}")
    
    agent = Mem0Agent(
        model="ministral-3:3b",
        user_id="mem0_test",
        use_real_mem0=False,  # Usa simples para teste
    )
    
    # Sessão 1
    agent.new_session(user_id="test_user")
    
    response1 = agent.process_message(
        "Olá, meu nome é Carlos e sou desenvolvedor Python.",
        verbose=True,
    )
    print(f"Response 1: {response1.content[:100]}...")
    
    response2 = agent.process_message(
        "Qual linguagem eu uso?",
        verbose=True,
    )
    print(f"Response 2: {response2.content[:100]}...")
    
    # Nova sessão
    agent.new_session(user_id="test_user")
    
    response3 = agent.process_message(
        "Você lembra do meu nome?",
        verbose=True,
    )
    print(f"Response 3 (nova sessão): {response3.content[:100]}...")
    
    print("\n📊 Stats:")
    for k, v in agent.get_stats().items():
        print(f"   {k}: {v}")
    
    # Limpa
    agent.clear_memory()
    print("\n✅ Teste completo!")

