"""
CortexAgent - Agente otimizado com extração [MEMORY] inline.

Diferenças do CortexAgent original:
1. NÃO faz chamada extra de LLM para extração
2. Injeta instrução [MEMORY] no prompt
3. Extrai memória do output do LLM
4. Remove bloco [MEMORY] da resposta final

Resultado: ~50% menos chamadas LLM, ~40% menos tokens
"""

import os
import re
import sys
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import litellm

# Configura logging
logger = logging.getLogger("cortex.benchmark.v2")

# Adiciona SDK ao path
sdk_path = Path(__file__).parent.parent / "sdk" / "python"
sys.path.insert(0, str(sdk_path))

from cortex_sdk import CortexClient

# Desabilita telemetria do LiteLLM
os.environ["LITELLM_TELEMETRY"] = "False"


# ==================== CONSTANTS ====================

# Instrução injetada no prompt
MEMORY_INSTRUCTION = """

REGRA IMPORTANTE: Ao final de TODA resposta, adicione um bloco de memória:

[MEMORY]
who: nome_participante
what: verbo_acao
why: motivo_breve
how: resultado_breve
[/MEMORY]

Exemplo:
[MEMORY]
who: Carlos
what: reportou_problema_internet
why: conexao_instavel
how: agendou_visita_tecnica
[/MEMORY]"""

# Entidades genéricas a filtrar
GENERIC_ENTITIES = {
    "user", "usuario", "usuário", "cliente", "sistema", "system",
    "assistant", "assistente", "troubleshooting", "support", "suporte",
}


# ==================== DATA CLASSES ====================


@dataclass
class AgentResponse:
    """Resposta de um agente com métricas reais."""
    content: str
    
    # Métricas de tokens
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # Métricas de tempo
    response_time_ms: float = 0
    recall_time_ms: float = 0
    store_time_ms: float = 0
    
    # Contexto
    context_from_memory: str = ""
    memory_entities: int = 0
    memory_episodes: int = 0
    memory_relations: int = 0
    
    # Extração
    memory_extracted: bool = False
    extracted_memory: dict = field(default_factory=dict)
    
    # Metadata
    model: str = ""
    has_memory: bool = True
    session_messages: int = 0
    
    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "response_time_ms": self.response_time_ms,
            "recall_time_ms": self.recall_time_ms,
            "store_time_ms": self.store_time_ms,
            "context_from_memory": self.context_from_memory,
            "memory_entities": self.memory_entities,
            "memory_episodes": self.memory_episodes,
            "memory_relations": self.memory_relations,
            "memory_extracted": self.memory_extracted,
            "extracted_memory": self.extracted_memory,
            "model": self.model,
            "has_memory": self.has_memory,
            "session_messages": self.session_messages,
        }


# ==================== MEMORY EXTRACTOR ====================


class MemoryExtractor:
    """Extrai e normaliza memórias do output do LLM."""
    
    PATTERNS = [
        r'\[MEMORY\]\s*\n(.+?)\[/MEMORY\]',
        r'\[MEMORY\]\s*\n(.+?)$',
        r'\[MEMORY\](.+?)\[/MEMORY\]',
    ]
    
    @classmethod
    def extract(cls, content: str) -> tuple[str, dict | None]:
        """
        Extrai memória do output e retorna resposta limpa.
        
        Returns:
            Tuple (resposta_limpa, memória_dict ou None)
        """
        for pattern in cls.PATTERNS:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                # Remove o bloco da resposta
                clean = re.sub(pattern, '', content, flags=re.DOTALL | re.IGNORECASE).strip()
                
                # Parseia memória
                memory = cls._parse_block(match.group(1))
                
                if memory and memory.get("what"):
                    return clean, memory
        
        return content, None
    
    @classmethod
    def _parse_block(cls, block: str) -> dict:
        """Parseia bloco de memória."""
        memory = {"who": "", "what": "", "why": "", "how": ""}
        
        for line in block.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'who':
                    memory['who'] = cls._normalize_who(value)
                elif key == 'what':
                    memory['what'] = cls._normalize_what(value)
                elif key == 'why':
                    memory['why'] = value
                elif key == 'how':
                    memory['how'] = value
        
        return memory
    
    @classmethod
    def _normalize_who(cls, value: str) -> str:
        """Remove entidades genéricas."""
        parts = [p.strip() for p in value.replace('[', '').replace(']', '').replace('"', '').split(',')]
        filtered = [p for p in parts if p.lower() not in GENERIC_ENTITIES]
        return ', '.join(filtered) if filtered else value
    
    @classmethod
    def _normalize_what(cls, value: str) -> str:
        """Normaliza 'what' para formato snake_case."""
        value = re.sub(r'^(o\s+)?(usuário|cliente|user)\s+', '', value, flags=re.IGNORECASE)
        if ' ' in value and '_' not in value:
            value = '_'.join(value.lower().split()[:3])
        return value.strip()


# ==================== LLM HELPER ====================


def call_llm_with_retry(
    model: str,
    messages: list[dict],
    api_base: str,
    max_retries: int = 10,
    initial_wait: float = 30.0,
    max_wait: float = 300.0,
    backoff_factor: float = 1.5,
) -> Any:
    """Chama LLM com retry para rate limits."""
    wait_time = initial_wait
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = litellm.completion(
                model=model,
                messages=messages,
                api_base=api_base,
            )
            return response
        except Exception as e:
            error_str = str(e).lower()
            last_error = e
            
            if "429" in error_str or "too many requests" in error_str or "rate limit" in error_str:
                print(f"\n   ⏳ Rate limit. Aguardando {wait_time:.0f}s... ({attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                wait_time = min(wait_time * backoff_factor, max_wait)
            else:
                raise e
    
    raise last_error


# ==================== CORTEX AGENT V2 ====================


class CortexAgent:
    """
    Agente Cortex otimizado com extração [MEMORY] inline.
    
    Fluxo:
    1. RECALL - Busca memórias relevantes
    2. GENERATE - Gera resposta com contexto + instrução [MEMORY]
    3. EXTRACT - Extrai [MEMORY] do output (regex, sem LLM extra)
    4. STORE - Armazena memória extraída
    
    Vantagens:
    - 50% menos chamadas LLM (sem chamada extra para extração)
    - ~40% menos tokens (extração inline)
    - Resposta limpa para o usuário (bloco removido)
    """
    
    SYSTEM_PROMPT_TEMPLATE = """Você é um assistente útil com memória de conversas anteriores.

{memory_section}

Use a memória para:
- Reconhecer o usuário e seu contexto
- Não pedir informações que já sabe
- Dar continuidade natural à conversa

Responda de forma natural e completa.
{memory_instruction}"""
    
    def __init__(
        self,
        model: str | None = None,
        ollama_url: str | None = None,
        cortex_url: str | None = None,
        context_window_size: int | None = None,
        namespace: str | None = None,
    ):
        # Usa variáveis de ambiente como fallback
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma3:4b")
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.cortex_url = cortex_url or os.getenv("CORTEX_API_URL", "http://localhost:8000")
        self.context_window_size = context_window_size or int(os.getenv("CORTEX_CONTEXT_WINDOW", "10"))
        self.namespace = namespace or os.getenv("CORTEX_NAMESPACE", "benchmark")
        
        os.environ["OLLAMA_API_BASE"] = self.ollama_url
        
        self.cortex = CortexClient(base_url=self.cortex_url, namespace=self.namespace)
        self._cortex_url = self.cortex_url
        
        self._session_history: list[dict] = []
        self._session_start: datetime | None = None
        self._current_user: str = "user"
        
        # Estatísticas
        self._total_messages = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_time_ms = 0
        self._total_recall_time_ms = 0
        self._total_store_time_ms = 0
        self._total_memory_entities = 0
        self._total_memory_episodes = 0
        self._total_extractions = 0
        self._successful_extractions = 0
        self._sessions_count = 0
    
    def new_session(self, user_id: str = "user") -> None:
        """Inicia nova sessão."""
        self._session_history = []
        self._session_start = datetime.now()
        self._current_user = user_id
        self._sessions_count += 1
    
    def _set_namespace(self, namespace: str) -> None:
        """Define namespace e recria cliente."""
        self.namespace = namespace
        self.cortex = CortexClient(base_url=self._cortex_url, namespace=namespace)
    
    def set_namespace(self, namespace: str) -> None:
        """Define namespace (alias público)."""
        self._set_namespace(namespace)
    
    def _recall_memory(self, query: str) -> tuple[str, int, int, int, float]:
        """Busca memórias relevantes."""
        start_time = time.time()
        
        try:
            result = self.cortex.recall(
                query=query,
                who=[self._current_user] if self._current_user else None,
                where=self.namespace,
                limit=10,
            )
            
            recall_time = (time.time() - start_time) * 1000
            
            entities = result.get("entities", [])
            episodes = result.get("episodes", [])
            
            prompt_ctx = result.get("prompt_context", "")
            if prompt_ctx and prompt_ctx.strip():
                context_text = prompt_ctx
            else:
                context_text = ""
            
            return context_text, len(entities), len(episodes), 0, recall_time
            
        except Exception as e:
            recall_time = (time.time() - start_time) * 1000
            return "", 0, 0, 0, recall_time
    
    def _store_memory(self, memory: dict) -> float:
        """Armazena memória extraída."""
        start_time = time.time()
        
        try:
            who_raw = memory.get("who", "")
            if isinstance(who_raw, list):
                who_list = who_raw
            else:
                who_list = [w.strip() for w in who_raw.split(',') if w.strip()]
            
            if self._current_user not in who_list:
                who_list.insert(0, self._current_user)
            
            self.cortex.remember(
                who=who_list[:5],
                what=memory.get("what", "interaction")[:100],
                why=memory.get("why", "")[:100],
                how=memory.get("how", "")[:150],
                where=self.namespace,
            )
            
        except Exception as e:
            logger.debug(f"Store error: {e}")
        
        return (time.time() - start_time) * 1000
    
    def process_message(self, message: str, user_context: dict | None = None) -> AgentResponse:
        """
        Processa mensagem com extração [MEMORY] inline.
        
        1. RECALL
        2. GENERATE (com instrução [MEMORY])
        3. EXTRACT [MEMORY] do output
        4. STORE memória extraída
        """
        total_start = time.time()
        
        if user_context and "user_id" in user_context:
            self._current_user = user_context["user_id"]
        
        # 1. RECALL
        memory_context, num_entities, num_episodes, num_relations, recall_time = self._recall_memory(message)
        
        # Adiciona mensagem ao histórico
        self._session_history.append({"role": "user", "content": message})
        context_messages = self._session_history[-self.context_window_size:]
        
        # Prepara prompt
        if memory_context:
            memory_section = f"MEMÓRIAS RELEVANTES:\n{memory_context}"
        else:
            memory_section = "Nenhuma memória prévia encontrada."
        
        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
            memory_section=memory_section,
            memory_instruction=MEMORY_INSTRUCTION,
        )
        
        messages = [{"role": "system", "content": system_prompt}, *context_messages]
        
        # 2. GENERATE
        llm_start = time.time()
        memory_extracted = False
        extracted_memory = {}
        
        try:
            response = call_llm_with_retry(
                model=f"ollama_chat/{self.model}",
                messages=messages,
                api_base=self.ollama_url,
            )
            
            raw_answer = response.choices[0].message.content
            
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0
            
        except Exception as e:
            raw_answer = f"[Erro: {e}]"
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
        
        llm_time = (time.time() - llm_start) * 1000
        
        # 3. EXTRACT [MEMORY]
        self._total_extractions += 1
        clean_answer, memory = MemoryExtractor.extract(raw_answer)
        
        if memory and memory.get("what"):
            memory_extracted = True
            extracted_memory = memory
            self._successful_extractions += 1
        
        # Adiciona resposta limpa ao histórico
        self._session_history.append({"role": "assistant", "content": clean_answer})
        
        # 4. STORE
        store_time = 0.0
        if memory_extracted:
            store_time = self._store_memory(extracted_memory)
        
        total_time = (time.time() - total_start) * 1000
        
        # Atualiza estatísticas
        self._total_messages += 1
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens
        self._total_time_ms += total_time
        self._total_recall_time_ms += recall_time
        self._total_store_time_ms += store_time
        self._total_memory_entities += num_entities
        self._total_memory_episodes += num_episodes
        
        return AgentResponse(
            content=clean_answer,  # Resposta LIMPA, sem [MEMORY]
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            response_time_ms=total_time,
            recall_time_ms=recall_time,
            store_time_ms=store_time,
            context_from_memory=memory_context,
            memory_entities=num_entities,
            memory_episodes=num_episodes,
            memory_relations=num_relations,
            memory_extracted=memory_extracted,
            extracted_memory=extracted_memory,
            model=self.model,
            has_memory=True,
            session_messages=len(self._session_history),
        )
    
    def get_stats(self) -> dict:
        """Retorna estatísticas."""
        return {
            "type": "cortex_v2",
            "model": self.model,
            "has_memory": True,
            "namespace": self.namespace,
            "total_messages": self._total_messages,
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
            "total_time_ms": self._total_time_ms,
            "total_recall_time_ms": self._total_recall_time_ms,
            "total_store_time_ms": self._total_store_time_ms,
            "total_memory_entities": self._total_memory_entities,
            "total_memory_episodes": self._total_memory_episodes,
            "sessions_count": self._sessions_count,
            "total_extractions": self._total_extractions,
            "successful_extractions": self._successful_extractions,
            "extraction_rate": (
                self._successful_extractions / self._total_extractions
                if self._total_extractions > 0 else 0
            ),
            "avg_prompt_tokens": (
                self._total_prompt_tokens / self._total_messages
                if self._total_messages > 0 else 0
            ),
            "avg_completion_tokens": (
                self._total_completion_tokens / self._total_messages
                if self._total_messages > 0 else 0
            ),
            "avg_response_time_ms": (
                self._total_time_ms / self._total_messages
                if self._total_messages > 0 else 0
            ),
        }
    
    def test_connection(self) -> bool:
        """Testa conexões."""
        try:
            litellm.completion(
                model=f"ollama_chat/{self.model}",
                messages=[{"role": "user", "content": "test"}],
                api_base=self.ollama_url,
                max_tokens=1,
            )
            self.cortex.stats()
            return True
        except Exception:
            return False
    
    def clear_namespace(self) -> bool:
        """Limpa memórias do namespace."""
        try:
            self.cortex.clear()
            return True
        except Exception:
            return False

