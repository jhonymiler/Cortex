"""
Agentes para Benchmark - Usando LLM Real (Ollama)

Dois agentes:
1. BaselineAgent - Usa Ollama SEM memória persistente
2. CortexAgent - Usa Ollama COM memória Cortex

Ambos coletam métricas reais: tokens, tempo de resposta, etc.
"""

import os
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import litellm

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
        model: Nome do modelo (ex: ollama_chat/deepseek-v3.1:671b-cloud)
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
        model: str = "deepseek-v3.1:671b-cloud",
        ollama_url: str = "http://localhost:11434",
        context_window_size: int = 10,  # Últimas N mensagens
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.context_window_size = context_window_size
        
        # Configura LiteLLM
        os.environ["OLLAMA_API_BASE"] = ollama_url
        
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
    
    SYSTEM_PROMPT_TEMPLATE = """Você é um assistente útil e amigável COM MEMÓRIA PERSISTENTE.

{memory_section}

INSTRUÇÕES:
- Use as memórias para dar respostas mais contextualizadas e personalizadas
- Se lembrar de algo sobre o usuário, mencione naturalmente
- Se não tiver memórias relevantes, responda normalmente
- Seja consistente com informações de sessões anteriores"""
    
    def __init__(
        self,
        model: str = "ministral-3:3b",
        ollama_url: str = "http://localhost:11434",
        cortex_url: str = "http://localhost:8000",
        context_window_size: int = 10,
        namespace: str = "benchmark",
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.cortex_url = cortex_url
        self.context_window_size = context_window_size
        self.namespace = namespace
        
        # Configura LiteLLM
        os.environ["OLLAMA_API_BASE"] = ollama_url
        
        # Cliente Cortex com namespace para isolamento
        self.cortex = CortexClient(base_url=cortex_url, namespace=namespace)
        
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
        conversation_id: str | None = None,
        session_id: str | None = None,
    ) -> tuple[str, int, int, int, float]:
        """
        Busca memórias relevantes no Cortex.
        
        Args:
            query: Query de busca
            conversation_id: ID da conversa ativa
            session_id: ID da sessão atual
        
        Returns:
            (context_text, num_entities, num_episodes, num_relations, time_ms)
        """
        start_time = time.time()
        
        try:
            # Chama recall com conversation_id e session_id
            result = self.cortex.recall(
                query=query,
                who=[self._current_user] if self._current_user else None,
                where=self.namespace,
                conversation_id=conversation_id,
                session_id=session_id,
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
    
    def _store_memory(self, message: str, response: str) -> float:
        """
        Armazena a interação no Cortex extraindo SIGNIFICADO SEMÂNTICO COMPLETO.
        
        Usa LLM para extrair:
        - action: verbo + objeto (ex: "requested_password_reset")
        - outcome: resultado conciso (ex: "reset link sent to email")
        - context: situação relevante (ex: "support_ticket_#123")
        - entities: entidades mencionadas na conversa
        - relations: relações semânticas descobertas
        
        Returns:
            time_ms
        """
        start_time = time.time()
        
        try:
            # Usa LLM para extrair significado ENRIQUECIDO
            extract_prompt = f"""Extraia o significado SEMÂNTICO COMPLETO desta interação em JSON:

USER: {message}
ASSISTANT: {response}

Retorne apenas JSON (sem markdown):
{{
  "action": "verbo_objeto",
  "outcome": "resultado_conciso",
  "context": "situação_relevante",
  "entities": [
    {{"type": "tipo", "name": "nome"}}
  ],
  "relations": [
    {{"from": "origem", "type": "relação", "to": "destino"}}
  ]
}}

Regras:
- action: verbo + objeto em snake_case (ex: "reported_login_issue")
- outcome: resultado em ~10 palavras
- context: contexto útil em ~5 palavras
- entities: TODOS conceitos, produtos, tecnologias, tópicos mencionados
  - types válidos: concept, product, technology, topic, feature, problem, solution
- relations: conexões semânticas descobertas (use nomes das entidades)
  - tipos de relação: interested_in, has_issue_with, requested, learned_about, 
    prefers, dislikes, works_with, needs, solved, caused_by, related_to
- Inclua o usuário nas relations quando relevante (use "{self._current_user}" como nome)
- SEM texto literal, MÁXIMO valor informacional

Exemplo extraído:
{{
  "action": "asked_about_fastapi",
  "outcome": "explained async routing and dependency injection",
  "context": "python_web_development",
  "entities": [
    {{"type": "technology", "name": "FastAPI"}},
    {{"type": "concept", "name": "async_routing"}},
    {{"type": "concept", "name": "dependency_injection"}}
  ],
  "relations": [
    {{"from": "{self._current_user}", "type": "interested_in", "to": "FastAPI"}},
    {{"from": "FastAPI", "type": "has_feature", "to": "async_routing"}}
  ]
}}"""

            extract_response = call_llm_with_retry(
                model=f"ollama_chat/{self.model}",
                messages=[{"role": "user", "content": extract_prompt}],
                api_base=self.ollama_url,
                max_retries=3,
                initial_wait=5.0,
            )
            
            # Parse JSON
            import json
            import re
            
            content = extract_response.choices[0].message.content
            # Remove markdown se houver
            content = re.sub(r'```json\s*|\s*```', '', content).strip()
            
            extracted = json.loads(content)
            
            # Extrai nomes das entidades para o campo 'who'
            entity_names = [
                e.get("name", "").strip() 
                for e in extracted.get("entities", []) 
                if e.get("name") and e.get("name", "").strip().lower() != self._current_user.lower()
            ]
            
            self.cortex.remember(
                who=[self._current_user] + entity_names,
                what=extracted.get("action", "conversed"),
                why=extracted.get("context", "session interaction"),
                how=extracted.get("outcome", "interaction completed"),
            )
            
        except Exception as e:
            # Fallback: salva versão minimalista manual
            self.cortex.remember(
                who=[self._current_user],
                what="interaction",
                how="user engaged with assistant",
            )
        
        return (time.time() - start_time) * 1000
    
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
        store_time = self._store_memory(message, answer)
        
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
