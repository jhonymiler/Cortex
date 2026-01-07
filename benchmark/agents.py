"""
Agentes para Benchmark - Usando LLM Real (Ollama)

Dois agentes:
1. BaselineAgent - Usa Ollama SEM memória persistente
2. CortexAgent - Usa Ollama COM memória Cortex

Ambos coletam métricas reais: tokens, tempo de resposta, etc.
"""

import os
import re
import sys
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import litellm
import yaml

# Configura logging para benchmark
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cortex.benchmark")

# Silencia logs verbosos do LiteLLM
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Adiciona SDK ao path
sdk_path = Path(__file__).parent.parent / "sdk" / "python"
sys.path.insert(0, str(sdk_path))

from cortex_sdk import CortexClient


# Desabilita telemetria do LiteLLM
os.environ["LITELLM_TELEMETRY"] = "False"


def call_llm_with_retry(
    model: str,
    messages: list[dict],
    api_base: str,
    max_retries: int = 10,
    initial_wait: float = 30.0,
    max_wait: float = 300.0,
    backoff_factor: float = 1.5,
) -> Any:
    """
    Chama LLM com retry e backoff exponencial para rate limits.
    
    Args:
        model: Nome do modelo (ex: ollama_chat/ministral-3:3b)
        messages: Lista de mensagens
        api_base: URL base do Ollama
        max_retries: Máximo de tentativas
        initial_wait: Tempo inicial de espera (segundos)
        max_wait: Tempo máximo de espera (segundos)
        backoff_factor: Fator de multiplicação do backoff
        
    Returns:
        Response do LiteLLM
        
    Raises:
        Exception se todas as tentativas falharem
    """
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
            
            # Verifica se é rate limit (429)
            if "429" in error_str or "too many requests" in error_str or "rate limit" in error_str:
                print(f"\n   ⏳ Rate limit atingido. Aguardando {wait_time:.0f}s... (tentativa {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                wait_time = min(wait_time * backoff_factor, max_wait)
            else:
                # Outro erro, não faz retry
                raise e
    
    # Todas tentativas falharam
    raise last_error


def evaluate_responses(
    model: str,
    api_base: str,
    user_message: str,
    baseline_response: str,
    cortex_response: str,
    memory_context: str = "",
) -> dict:
    """
    Usa LLM para avaliar qual resposta é melhor.
    
    Retorna scores de 1-5 para cada aspecto.
    Formato YAML para economizar tokens.
    """
    eval_prompt = f"""Compare these two AI responses. Score 1-5 each aspect.

USER QUESTION: {user_message[:150]}

RESPONSE A (without memory):
{baseline_response[:300]}

RESPONSE B (with memory context):
{cortex_response[:300]}

Memory context used by B: {memory_context[:100] if memory_context else "none"}

Reply ONLY in YAML:
relevance_a: 1-5
relevance_b: 1-5
coherence_a: 1-5
coherence_b: 1-5
personalization_a: 1-5
personalization_b: 1-5
winner: A or B or TIE
reason: brief explanation"""

    try:
        response = call_llm_with_retry(
            model=model,
            messages=[{"role": "user", "content": eval_prompt}],
            api_base=api_base,
            max_retries=2,
            initial_wait=5.0,
        )
        
        content = response.choices[0].message.content
        content = re.sub(r'```ya?ml\s*|\s*```', '', content).strip()
        
        try:
            result = yaml.safe_load(content)
            if isinstance(result, dict):
                return {
                    "baseline_score": (
                        result.get("relevance_a", 3) + 
                        result.get("coherence_a", 3) + 
                        result.get("personalization_a", 3)
                    ) / 3,
                    "cortex_score": (
                        result.get("relevance_b", 3) + 
                        result.get("coherence_b", 3) + 
                        result.get("personalization_b", 3)
                    ) / 3,
                    "winner": result.get("winner", "TIE"),
                    "reason": result.get("reason", ""),
                    "raw": result,
                }
        except Exception:
            pass
        
        return {"baseline_score": 3, "cortex_score": 3, "winner": "TIE", "error": "parse_failed"}
        
    except Exception as e:
        return {"baseline_score": 3, "cortex_score": 3, "winner": "TIE", "error": str(e)}


@dataclass
class AgentResponse:
    """Resposta de um agente com métricas reais."""
    content: str
    
    # Métricas de tokens (do LiteLLM)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # Métricas de tempo
    response_time_ms: float = 0
    recall_time_ms: float = 0  # Tempo gasto buscando memória (só Cortex)
    store_time_ms: float = 0   # Tempo gasto salvando memória (só Cortex)
    
    # Contexto
    context_from_memory: str = ""  # Memórias usadas (só Cortex)
    memory_entities: int = 0
    memory_episodes: int = 0
    memory_relations: int = 0
    
    # Metadata
    model: str = ""
    has_memory: bool = False
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
            "model": self.model,
            "has_memory": self.has_memory,
            "session_messages": self.session_messages,
        }


class BaseAgent(ABC):
    """Interface base para agentes."""
    
    @abstractmethod
    def process_message(self, message: str, user_context: dict | None = None) -> AgentResponse:
        """Processa uma mensagem e retorna resposta com métricas."""
        pass
    
    @abstractmethod
    def new_session(self) -> None:
        """Inicia uma nova sessão (limpa contexto de sessão)."""
        pass
    
    @abstractmethod
    def get_stats(self) -> dict:
        """Retorna estatísticas acumuladas do agente."""
        pass


class BaselineAgent(BaseAgent):
    """
    Agente que usa Ollama SEM memória persistente.
    
    Cada sessão é completamente isolada. O agente só tem
    acesso às mensagens da sessão atual (context window).
    """
    
    SYSTEM_PROMPT = """Você é um assistente útil e amigável.
Responda de forma clara e concisa.
Se não souber algo ou não tiver contexto, diga honestamente."""
    
    def __init__(
        self,
        model: str | None = None,
        ollama_url: str | None = None,
        context_window_size: int | None = None,
    ):
        # Usa variáveis de ambiente como fallback
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma3:4b")
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.context_window_size = context_window_size or int(os.getenv("CORTEX_CONTEXT_WINDOW", "10"))
        
        # Configura LiteLLM
        os.environ["OLLAMA_API_BASE"] = self.ollama_url
        
        # Estado da sessão atual
        self._session_history: list[dict] = []
        self._session_start: datetime | None = None
        
        # Estatísticas globais
        self._total_messages = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_time_ms = 0
        self._sessions_count = 0
    
    def new_session(self) -> None:
        """Inicia nova sessão - limpa todo histórico."""
        self._session_history = []
        self._session_start = datetime.now()
        self._sessions_count += 1
    
    def process_message(self, message: str, user_context: dict | None = None) -> AgentResponse:
        """
        Processa mensagem usando Ollama SEM memória persistente.
        
        O baseline não tem acesso a:
        - Sessões anteriores
        - Informações do usuário de outras sessões
        - Preferências aprendidas
        - Histórico de interações passadas
        """
        start_time = time.time()
        
        # Adiciona mensagem ao histórico da sessão
        self._session_history.append({
            "role": "user",
            "content": message,
        })
        
        # Monta contexto (últimas N mensagens apenas)
        context_messages = self._session_history[-self.context_window_size:]
        
        # Prepara mensagens para o LLM
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            *context_messages
        ]
        
        # Chama Ollama via LiteLLM (com retry para rate limit)
        try:
            response = call_llm_with_retry(
                model=f"ollama_chat/{self.model}",
                messages=messages,
                api_base=self.ollama_url,
            )
            
            answer = response.choices[0].message.content
            
            # Extrai métricas de tokens
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0
            
        except Exception as e:
            # Em caso de erro, retorna mensagem de erro
            answer = f"[Erro ao processar: {e}]"
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
        
        # Adiciona resposta ao histórico
        self._session_history.append({
            "role": "assistant",
            "content": answer,
        })
        
        response_time = (time.time() - start_time) * 1000
        
        # Atualiza estatísticas
        self._total_messages += 1
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens
        self._total_time_ms += response_time
        
        return AgentResponse(
            content=answer,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            response_time_ms=response_time,
            model=self.model,
            has_memory=False,
            session_messages=len(self._session_history),
        )
    
    def get_stats(self) -> dict:
        """Retorna estatísticas acumuladas."""
        return {
            "type": "baseline",
            "model": self.model,
            "has_memory": False,
            "total_messages": self._total_messages,
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
            "total_time_ms": self._total_time_ms,
            "sessions_count": self._sessions_count,
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
        """Testa se o Ollama está acessível."""
        try:
            response = litellm.completion(
                model=f"ollama_chat/{self.model}",
                messages=[{"role": "user", "content": "test"}],
                api_base=self.ollama_url,
                max_tokens=1,
            )
            return True
        except Exception:
            return False


class CortexAgent(BaseAgent):
    """
    Agente que usa Ollama COM memória Cortex.
    
    Antes de responder, busca memórias relevantes.
    Depois de responder, armazena a interação.
    
    O agente tem acesso a:
    - Informações de sessões anteriores
    - Preferências do usuário
    - Histórico de interações
    - Padrões consolidados
    """
    
    SYSTEM_PROMPT_TEMPLATE = """Você é um assistente útil com memória de conversas anteriores.

{memory_section}

Use a memória para:
- Reconhecer o usuário e seu contexto
- Não pedir informações que já sabe
- Dar continuidade natural à conversa
- Ser mais preciso e relevante nas respostas

Responda de forma natural e completa."""
    
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
        
        # Configura LiteLLM
        os.environ["OLLAMA_API_BASE"] = self.ollama_url
        
        # Cliente Cortex com namespace para isolamento
        self.cortex = CortexClient(base_url=self.cortex_url, namespace=self.namespace)
        self._cortex_url = self.cortex_url  # Guarda para recriar cliente
        
        # Estado da sessão atual
        self._session_history: list[dict] = []
        self._session_start: datetime | None = None
        self._current_user: str = "user"
        
        # Estatísticas globais
        self._total_messages = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_time_ms = 0
        self._total_recall_time_ms = 0
        self._total_store_time_ms = 0
        self._total_memory_entities = 0
        self._total_memory_episodes = 0
        self._sessions_count = 0
    
    def new_session(self, user_id: str = "user") -> None:
        """Inicia nova sessão - limpa histórico da sessão, mas mantém memória."""
        self._session_history = []
        self._session_start = datetime.now()
        self._current_user = user_id
        self._sessions_count += 1
    
    def _recall_memory(
        self, 
        query: str,
    ) -> tuple[str, int, int, int, float]:
        """
        Busca memórias relevantes no Cortex.
        
        Args:
            query: Query de busca
        
        Returns:
            (context_text, num_entities, num_episodes, num_relations, time_ms)
        """
        start_time = time.time()
        
        try:
            # Chama recall
            result = self.cortex.recall(
                query=query,
                who=[self._current_user] if self._current_user else None,
                where=self.namespace,
                limit=10,
            )
            
            recall_time = (time.time() - start_time) * 1000
            
            # A nova API não retorna "success", retorna diretamente os dados
            entities = result.get("entities", [])
            episodes = result.get("episodes", [])
            
            # Não há relations no novo modelo, use contagem zero
            relations_count = result.get("relations_found", 0)
            
            # Formata contexto para o prompt
            context_parts = []
            
            if entities:
                context_parts.append("📋 ENTIDADES CONHECIDAS:")
                for e in entities[:5]:
                    context_parts.append(f"  • {e.get('name', '?')} ({e.get('type', 'unknown')})")
            
            if episodes:
                context_parts.append("\n📝 HISTÓRICO RELEVANTE:")
                for ep in episodes[:5]:
                    action = ep.get("action", "unknown")
                    outcome = ep.get("outcome", "")
                    context_parts.append(f"  • {action}: {outcome}" if outcome else f"  • {action}")
            
            # Usa prompt_context se disponível (mais conciso)
            prompt_ctx = result.get("prompt_context", "")
            if prompt_ctx and prompt_ctx.strip():
                context_text = prompt_ctx
            elif context_parts:
                context_text = "\n".join(context_parts)
            else:
                context_text = "Nenhuma memória relevante encontrada."
            
            return context_text, len(entities), len(episodes), relations_count, recall_time
            
        except Exception as e:
            recall_time = (time.time() - start_time) * 1000
            return f"[Erro ao buscar memória: {e}]", 0, 0, 0, recall_time
    
    def _store_memory(self, message: str, response: str, verbose: bool = False) -> tuple[float, dict]:
        """
        Armazena a interação no Cortex usando prompt YAML otimizado.
        
        Prompt simplificado para modelos pequenos:
        - Formato YAML (30% menos tokens que JSON)
        - Poucas regras, mais exemplos
        - Foco no modelo W5H
        
        Returns:
            (time_ms, extracted_data)
        """
        start_time = time.time()
        extracted_data = {}
        
        try:
            # Prompt OTIMIZADO: curto, YAML, poucos exemplos
            extract_prompt = f"""Extract memory from this conversation. Reply ONLY in YAML format.

USER: {message[:200]}
ASSISTANT: {response[:200]}

Reply with this YAML structure (no markdown, no explanation):
who:
  - name_of_person_or_entity
what: action_verb_object
why: reason_or_context
how: result_or_outcome
topics:
  - topic1
  - topic2

Example:
who:
  - Maria
  - FastAPI
what: asked_about_authentication
why: building_web_api
how: explained_jwt_tokens
topics:
  - JWT
  - security
  - Python"""

            extract_response = call_llm_with_retry(
                model=f"ollama_chat/{self.model}",
                messages=[{"role": "user", "content": extract_prompt}],
                api_base=self.ollama_url,
                max_retries=3,
                initial_wait=5.0,
            )
            
            content = extract_response.choices[0].message.content
            
            # Remove markdown se houver
            content = re.sub(r'```ya?ml\s*|\s*```', '', content).strip()
            
            # Parse YAML
            try:
                extracted = yaml.safe_load(content)
                if not isinstance(extracted, dict):
                    raise ValueError("YAML não retornou dict")
            except Exception:
                # Fallback: tenta extrair manualmente
                extracted = self._parse_yaml_fallback(content)
            
            extracted_data = extracted or {}
            
            # Extrai campos
            who_list = extracted.get("who", [])
            if isinstance(who_list, str):
                who_list = [who_list]
            who_list = [w for w in who_list if w and str(w).lower() not in ["user", "assistant", "none"]]
            
            what = extracted.get("what", "conversed")
            why = extracted.get("why", "")
            how = extracted.get("how", "")
            topics = extracted.get("topics", [])
            
            # Adiciona tópicos como entidades "who"
            if topics and isinstance(topics, list):
                who_list.extend([t for t in topics if t and isinstance(t, str)])
            
            # Remove duplicatas e limpa
            who_list = list(set([str(w).strip() for w in who_list if w]))[:5]
            
            # Adiciona usuário atual
            if self._current_user and self._current_user not in who_list:
                who_list.insert(0, self._current_user)
            
            # Salva no Cortex (com namespace isolado)
            self.cortex.remember(
                who=who_list if who_list else [self._current_user],
                what=str(what)[:100] if what else "conversed",
                why=str(why)[:100] if why else "",
                how=str(how)[:150] if how else "",
                where=self.namespace,  # Isola por domínio
            )
            
            if verbose:
                print(f"\n   📝 Store: who={who_list}, what={what}")
                print(f"      why={why}, how={how[:50]}...")
            
        except Exception as e:
            if verbose:
                print(f"\n   ⚠️ Store fallback: {e}")
            # Fallback: salva versão minimalista
            self.cortex.remember(
                who=[self._current_user],
                what="interaction",
                how=response[:100] if response else "completed",
                where=self.namespace,  # Isola por domínio
            )
            extracted_data = {"error": str(e)}
        
        return (time.time() - start_time) * 1000, extracted_data
    
    def _parse_yaml_fallback(self, content: str) -> dict:
        """Parse YAML manualmente quando yaml.safe_load falha."""
        import re
        
        result = {"who": [], "what": "", "why": "", "how": "", "topics": []}
        
        # Extrai campos com regex
        who_match = re.search(r'who:\s*\n((?:\s*-\s*.+\n?)+)', content)
        if who_match:
            items = re.findall(r'-\s*(.+)', who_match.group(1))
            result["who"] = [i.strip() for i in items if i.strip()]
        
        what_match = re.search(r'what:\s*(.+)', content)
        if what_match:
            result["what"] = what_match.group(1).strip()
        
        why_match = re.search(r'why:\s*(.+)', content)
        if why_match:
            result["why"] = why_match.group(1).strip()
        
        how_match = re.search(r'how:\s*(.+)', content)
        if how_match:
            result["how"] = how_match.group(1).strip()
        
        topics_match = re.search(r'topics:\s*\n((?:\s*-\s*.+\n?)+)', content)
        if topics_match:
            items = re.findall(r'-\s*(.+)', topics_match.group(1))
            result["topics"] = [i.strip() for i in items if i.strip()]
        
        return result
    
    def process_message(self, message: str, user_context: dict | None = None) -> AgentResponse:
        """
        Processa mensagem usando Ollama COM memória Cortex.
        
        1. RECALL - Busca memórias relevantes
        2. GENERATE - Gera resposta com contexto
        3. STORE - Armazena a interação
        """
        total_start = time.time()
        
        # Atualiza usuário se fornecido
        if user_context and "user_id" in user_context:
            self._current_user = user_context["user_id"]
        
        # 1. RECALL - Busca memórias
        memory_context, num_entities, num_episodes, num_relations, recall_time = self._recall_memory(message)
        
        # Adiciona mensagem ao histórico da sessão
        self._session_history.append({
            "role": "user",
            "content": message,
        })
        
        # Monta contexto (últimas N mensagens)
        context_messages = self._session_history[-self.context_window_size:]
        
        # Prepara system prompt com memória
        if memory_context and "Nenhuma memória" not in memory_context:
            memory_section = f"MEMÓRIAS RELEVANTES:\n{memory_context}"
        else:
            memory_section = "Nenhuma memória prévia encontrada sobre este assunto."
        
        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(memory_section=memory_section)
        
        # Prepara mensagens para o LLM
        messages = [
            {"role": "system", "content": system_prompt},
            *context_messages
        ]
        
        # 2. GENERATE - Chama Ollama (com retry para rate limit)
        llm_start = time.time()
        try:
            response = call_llm_with_retry(
                model=f"ollama_chat/{self.model}",
                messages=messages,
                api_base=self.ollama_url,
            )
            
            answer = response.choices[0].message.content
            
            # Extrai métricas de tokens
            usage = response.usage
            prompt_tokens = usage.prompt_tokens if usage else 0
            completion_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0
            
        except Exception as e:
            answer = f"[Erro ao processar: {e}]"
            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
        
        llm_time = (time.time() - llm_start) * 1000
        
        # Adiciona resposta ao histórico
        self._session_history.append({
            "role": "assistant",
            "content": answer,
        })
        
        # 3. STORE - Armazena a interação
        store_time, extracted_data = self._store_memory(message, answer, verbose=False)
        
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
            content=answer,
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
            model=self.model,
            has_memory=True,
            session_messages=len(self._session_history),
        )
    
    def get_stats(self) -> dict:
        """Retorna estatísticas acumuladas."""
        return {
            "type": "cortex",
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
            "avg_recall_time_ms": (
                self._total_recall_time_ms / self._total_messages
                if self._total_messages > 0 else 0
            ),
            "avg_store_time_ms": (
                self._total_store_time_ms / self._total_messages
                if self._total_messages > 0 else 0
            ),
        }
    
    def test_connection(self) -> bool:
        """Testa se Ollama e Cortex estão acessíveis."""
        try:
            # Testa Ollama
            litellm.completion(
                model=f"ollama_chat/{self.model}",
                messages=[{"role": "user", "content": "test"}],
                api_base=self.ollama_url,
                max_tokens=1,
            )
            
            # Testa Cortex (método correto é stats, não get_stats)
            self.cortex.stats()
            
            return True
        except Exception:
            return False
    
    def recall(
        self,
        query: str,
        conversation_id: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        """Recall público para lightweight benchmark."""
        try:
            return self.cortex.recall(
                query=query,
                who=[self._current_user] if self._current_user else None,
                where=self.namespace,
                limit=10,
            )
        except Exception as e:
            return {
                "entities_found": 0,
                "episodes_found": 0,
                "prompt_context": "Nenhuma memória encontrada.",
                "entities": [],
                "episodes": [],
                "error": str(e),
            }
    
    def store(
        self,
        user_message: str,
        assistant_response: str,
        conversation_id: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        """Store público para lightweight benchmark."""
        return self._store_memory(user_message, assistant_response)
    
    def set_namespace(self, namespace: str) -> None:
        """Atualiza o namespace e recria o cliente Cortex."""
        if self.namespace != namespace:
            self.namespace = namespace
            # Recria cliente com novo namespace (header atualizado)
            self.cortex = CortexClient(base_url=self._cortex_url, namespace=namespace)
    
    def clear_namespace(self) -> bool:
        """Limpa o namespace de benchmark no Cortex."""
        try:
            result = self.cortex.clear()
            return result.get("success", False)
        except Exception:
            return False


def test_agents():
    """Teste básico dos agentes."""
    print("=" * 60)
    print("TESTE DOS AGENTES COM OLLAMA REAL")
    print("=" * 60)
    
    # Verifica Ollama (com retry)
    print("\n🔍 Verificando Ollama...")
    try:
        response = call_llm_with_retry(
            model="ollama_chat/ministral-3:3b",
            messages=[{"role": "user", "content": "Oi, responda apenas 'ok'"}],
            api_base="http://localhost:11434",
        )
        print("✅ Ollama funcionando!")
        print(f"   Resposta: {response.choices[0].message.content[:50]}")
    except Exception as e:
        print(f"❌ Ollama não disponível: {e}")
        return
    
    # Teste Baseline
    print("\n" + "=" * 40)
    print("BASELINE AGENT (sem memória)")
    print("=" * 40)
    
    baseline = BaselineAgent(model="ministral-3:3b")
    
    # Sessão 1
    baseline.new_session()
    print("\n--- Sessão 1 ---")
    
    messages_s1 = [
        "Olá! Meu nome é João e sou desenvolvedor Python.",
        "Preciso de ajuda com FastAPI.",
    ]
    
    for msg in messages_s1:
        print(f"\n👤 User: {msg}")
        resp = baseline.process_message(msg)
        print(f"🤖 Bot: {resp.content[:200]}...")
        print(f"   [tokens: {resp.total_tokens}, tempo: {resp.response_time_ms:.0f}ms]")
    
    # Sessão 2 - Nova sessão, sem memória
    baseline.new_session()
    print("\n\n--- Sessão 2 (sem memória) ---")
    
    messages_s2 = [
        "Oi, você lembra de mim?",
        "Qual era meu nome mesmo?",
    ]
    
    for msg in messages_s2:
        print(f"\n👤 User: {msg}")
        resp = baseline.process_message(msg)
        print(f"🤖 Bot: {resp.content[:200]}...")
        print(f"   [tokens: {resp.total_tokens}, tempo: {resp.response_time_ms:.0f}ms]")
    
    # Estatísticas
    print("\n\n📊 ESTATÍSTICAS BASELINE:")
    stats = baseline.get_stats()
    for k, v in stats.items():
        print(f"   {k}: {v}")
    
    # Teste Cortex Agent
    print("\n" + "=" * 40)
    print("CORTEX AGENT (com memória)")
    print("=" * 40)
    
    # Verifica Cortex API
    print("\n🔍 Verificando Cortex API...")
    cortex_agent = CortexAgent(
        model="ministral-3:3b",
        namespace="benchmark_test",
    )
    
    try:
        health = cortex_agent.cortex.health_check()
        if health.get("status") != "healthy":
            print("❌ Cortex API não disponível!")
            print("   Execute: cortex-api")
            return
        print("✅ Cortex API funcionando!")
    except Exception as e:
        print(f"❌ Cortex API não disponível: {e}")
        print("   Execute: cortex-api")
        return
    
    # Limpa namespace de teste
    cortex_agent.clear_namespace()
    
    # Sessão 1
    cortex_agent.new_session(user_id="joao")
    print("\n--- Sessão 1 ---")
    
    for msg in messages_s1:
        print(f"\n👤 User: {msg}")
        resp = cortex_agent.process_message(msg)
        print(f"🤖 Bot: {resp.content[:200]}...")
        print(f"   [tokens: {resp.total_tokens}, tempo: {resp.response_time_ms:.0f}ms, recall: {resp.recall_time_ms:.0f}ms]")
        if resp.memory_entities or resp.memory_episodes:
            print(f"   [memória: {resp.memory_entities} entidades, {resp.memory_episodes} episódios]")
    
    # Sessão 2 - Nova sessão COM memória
    cortex_agent.new_session(user_id="joao")
    print("\n\n--- Sessão 2 (COM memória) ---")
    
    for msg in messages_s2:
        print(f"\n👤 User: {msg}")
        resp = cortex_agent.process_message(msg)
        print(f"🤖 Bot: {resp.content[:200]}...")
        print(f"   [tokens: {resp.total_tokens}, tempo: {resp.response_time_ms:.0f}ms, recall: {resp.recall_time_ms:.0f}ms]")
        if resp.memory_entities or resp.memory_episodes:
            print(f"   [memória: {resp.memory_entities} entidades, {resp.memory_episodes} episódios]")
        if resp.context_from_memory and "Nenhuma" not in resp.context_from_memory:
            print(f"   [contexto recuperado: {resp.context_from_memory[:100]}...]")
    
    # Estatísticas
    print("\n\n📊 ESTATÍSTICAS CORTEX:")
    stats = cortex_agent.get_stats()
    for k, v in stats.items():
        print(f"   {k}: {v}")
    
    # Limpa namespace de teste
    cortex_agent.clear_namespace()
    print("\n✅ Teste completo!")


if __name__ == "__main__":
    test_agents()
