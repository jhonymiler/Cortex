"""
Cortex Memory - Core genérico para qualquer agente/framework.

Uso simples com 2 linhas:
    
    from cortex_memory import CortexMemory
    
    cortex = CortexMemory(namespace="meu_agente:usuario_123")
    
    def meu_agente(user_msg):
        context = cortex.before(user_msg)      # Busca memória + instrução
        
        response = llm.generate(context, user_msg)  # Seu LLM
        
        clean_response = cortex.after(user_msg, response)  # Extrai memória e limpa
        return clean_response

Funciona com qualquer framework: LangChain, CrewAI, LangGraph, custom, etc.
Para integrações plug-and-play, veja cortex.integrations.

NOVO: Extração automática via [MEMORY] block no output do LLM.
"""

import os
import re
import requests
from typing import Any, Callable
from dataclasses import dataclass, field


# ==================== CONSTANTS ====================

# Instrução injetada no prompt para extrair memória
MEMORY_INSTRUCTION = """

REGRA: Ao final de TODA resposta, adicione:

[MEMORY]
who: nome_participante
what: verbo_acao
why: motivo_breve
how: resultado_breve
[/MEMORY]"""

# Entidades genéricas que devem ser filtradas
GENERIC_ENTITIES = {
    "user", "usuario", "usuário", "cliente", "sistema", "system",
    "assistant", "assistente", "troubleshooting", "support", "suporte",
    "device", "dispositivo", "service", "serviço",
}


# ==================== DATA CLASSES ====================


@dataclass
class RecallResult:
    """Resultado do recall de memória."""
    context: str = ""
    entities_found: int = 0
    episodes_found: int = 0
    raw: dict = field(default_factory=dict)
    
    @property
    def has_memory(self) -> bool:
        return bool(self.context and len(self.context) > 10)


@dataclass 
class StoreResult:
    """Resultado do armazenamento."""
    success: bool = False
    memory_id: str | None = None
    extracted: dict = field(default_factory=dict)
    message: str = ""
    clean_response: str = ""  # Resposta sem bloco [MEMORY]


@dataclass
class ExtractedMemory:
    """Memória extraída do output do LLM."""
    who: str = ""
    what: str = ""
    why: str = ""
    how: str = ""
    raw_block: str = ""
    
    @property
    def is_valid(self) -> bool:
        """Verifica se a memória tem campos mínimos."""
        return bool(self.what and len(self.what) > 2)
    
    def to_dict(self) -> dict:
        return {
            "who": self.who,
            "what": self.what,
            "why": self.why,
            "how": self.how,
        }


# ==================== MEMORY EXTRACTOR ====================


class MemoryExtractor:
    """Extrai e normaliza memórias do output do LLM."""
    
    PATTERNS = [
        r'\[MEMORY\]\s*\n(.+?)\[/MEMORY\]',  # [MEMORY]...[/MEMORY]
        r'\[MEMORY\]\s*\n(.+?)$',  # [MEMORY]... (sem fechamento)
        r'\[MEMORY\](.+?)\[/MEMORY\]',  # Sem quebra de linha
        r'```memory\s*\n(.+?)```',  # Code block
    ]
    
    @classmethod
    def extract(cls, content: str) -> tuple[str, ExtractedMemory | None]:
        """
        Extrai memória do output e retorna resposta limpa.
        
        Args:
            content: Output bruto do LLM
            
        Returns:
            Tuple (resposta_limpa, memória_extraída ou None)
        """
        for pattern in cls.PATTERNS:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                # Remove o bloco da resposta
                clean = re.sub(pattern, '', content, flags=re.DOTALL | re.IGNORECASE).strip()
                
                # Parseia memória
                memory = cls._parse_block(match.group(1))
                
                if memory and memory.is_valid:
                    memory.raw_block = match.group(0)
                    return clean, memory
        
        return content, None
    
    @classmethod
    def _parse_block(cls, block: str) -> ExtractedMemory:
        """Parseia bloco de memória para ExtractedMemory."""
        memory = ExtractedMemory()
        
        for line in block.strip().split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key == 'who':
                    memory.who = cls._normalize_who(value)
                elif key == 'what':
                    memory.what = cls._normalize_what(value)
                elif key == 'why':
                    memory.why = value
                elif key == 'how':
                    memory.how = value
        
        return memory
    
    @classmethod
    def _normalize_who(cls, value: str) -> str:
        """Remove entidades genéricas do 'who'."""
        # Pode ser lista ou string
        if ',' in value:
            parts = [p.strip() for p in value.split(',')]
        elif '[' in value:
            # Lista como string
            parts = re.findall(r'"([^"]+)"', value) or [value.strip('[]')]
        else:
            parts = [value]
        
        # Filtra genéricos
        filtered = [p for p in parts if p.lower() not in GENERIC_ENTITIES]
        
        return ', '.join(filtered) if filtered else value
    
    @classmethod
    def _normalize_what(cls, value: str) -> str:
        """Normaliza 'what' para formato consistente."""
        # Remove prefixos comuns
        value = re.sub(r'^(o\s+)?(usuário|cliente|user)\s+', '', value, flags=re.IGNORECASE)
        
        # Converte para snake_case se tiver espaços
        if ' ' in value and '_' not in value:
            value = '_'.join(value.lower().split()[:3])  # Max 3 palavras
        
        return value.strip()


# ==================== MAIN CLASS ====================


class CortexMemory:
    """
    Core genérico de memória Cortex.
    
    Funciona com qualquer agente/framework via hooks:
    - before(msg): Busca contexto + injeta instrução [MEMORY]
    - after(msg, response): Extrai memória, limpa resposta, armazena
    
    A extração é feita no CLIENTE via regex - rápido e sem custo extra.
    
    Attributes:
        namespace: Isolamento de memórias (ex: "agente:usuario")
        inject_memory_instruction: Se True, adiciona instrução [MEMORY] ao contexto
        auto_extract: Se True, extrai [MEMORY] do output automaticamente
    """
    
    DEFAULT_CONTEXT_TEMPLATE = """[MEMÓRIA DO CLIENTE]
{context}

Use a memória para dar continuidade natural à conversa."""
    
    def __init__(
        self,
        namespace: str | None = None,
        cortex_url: str | None = None,
        auto_inject: bool = True,
        inject_memory_instruction: bool = True,
        auto_extract: bool = True,
        context_template: str | None = None,
    ):
        """
        Inicializa memória Cortex.
        
        Args:
            namespace: Identificador único para isolamento (env: CORTEX_NAMESPACE)
            cortex_url: URL da API Cortex (env: CORTEX_API_URL)
            auto_inject: Se True, before() retorna contexto formatado
            inject_memory_instruction: Se True, adiciona instrução [MEMORY]
            auto_extract: Se True, after() extrai [MEMORY] do output
            context_template: Template customizado para contexto
        """
        self.namespace = namespace or os.getenv("CORTEX_NAMESPACE", "default")
        self.cortex_url = (cortex_url or os.getenv("CORTEX_API_URL", "http://localhost:8000")).rstrip("/")
        self.auto_inject = auto_inject
        self.inject_memory_instruction = inject_memory_instruction
        self.auto_extract = auto_extract
        self.context_template = context_template or self.DEFAULT_CONTEXT_TEMPLATE
        
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "X-Cortex-Namespace": namespace,
        })
        
        # Estatísticas
        self._recall_count = 0
        self._store_count = 0
        self._extract_success = 0
        self._extract_fail = 0
        self._last_context = ""
        self._last_memory: ExtractedMemory | None = None
    
    # ==================== CORE HOOKS ====================
    
    def before(self, user_message: str) -> str:
        """
        Hook ANTES de gerar resposta.
        
        Busca memórias relevantes e retorna contexto para o prompt.
        Se inject_memory_instruction=True, adiciona instrução [MEMORY].
        
        Args:
            user_message: Mensagem do usuário
            
        Returns:
            Contexto formatado + instrução de memória (se configurado)
        """
        result = self.recall(user_message)
        self._last_context = result.context
        
        context_parts = []
        
        # Adiciona memória se houver
        if result.has_memory and self.auto_inject:
            context_parts.append(self.context_template.format(context=result.context))
        
        # Adiciona instrução de memória
        if self.inject_memory_instruction:
            context_parts.append(MEMORY_INSTRUCTION)
        
        return "\n".join(context_parts)
    
    def after(
        self, 
        user_message: str, 
        assistant_response: str, 
        user_name: str = "user"
    ) -> str:
        """
        Hook DEPOIS de gerar resposta.
        
        Extrai [MEMORY] do output, remove o bloco, e armazena no Cortex.
        
        Args:
            user_message: Mensagem do usuário
            assistant_response: Resposta bruta do LLM (com [MEMORY])
            user_name: Nome do usuário (opcional)
            
        Returns:
            Resposta LIMPA (sem bloco [MEMORY]) para mostrar ao usuário
        """
        clean_response = assistant_response
        self._last_memory = None
        
        if self.auto_extract:
            clean_response, memory = MemoryExtractor.extract(assistant_response)
            self._last_memory = memory
            
            if memory and memory.is_valid:
                self._extract_success += 1
                
                # Armazena no Cortex
                who_list = [w.strip() for w in memory.who.split(',')] if memory.who else [user_name]
                self.store_w5h(
                    who=who_list,
                    what=memory.what,
                    why=memory.why,
                    how=memory.how,
                )
            else:
                self._extract_fail += 1
        
        return clean_response
    
    # ==================== API METHODS ====================
    
    def recall(self, query: str, limit: int = 5) -> RecallResult:
        """Busca memórias relevantes."""
        try:
            response = self._session.post(
                f"{self.cortex_url}/memory/recall",
                json={"query": query, "context": {}, "limit": limit},
            )
            self._recall_count += 1
            
            data = response.json()
            return RecallResult(
                context=data.get("prompt_context", ""),
                entities_found=data.get("entities_found", 0),
                episodes_found=data.get("episodes_found", 0),
                raw=data,
            )
        except Exception as e:
            return RecallResult(context="", raw={"error": str(e)})
    
    def store_w5h(
        self,
        who: list[str],
        what: str,
        why: str = "",
        how: str = "",
        importance: float = 0.5,
    ) -> StoreResult:
        """Armazena memória W5H no Cortex."""
        try:
            response = self._session.post(
                f"{self.cortex_url}/memory/remember",
                json={
                    "who": who,
                    "what": what,
                    "why": why,
                    "how": how,
                    "where": self.namespace,
                    "importance": importance,
                },
            )
            self._store_count += 1
            
            data = response.json()
            return StoreResult(
                success=data.get("success", False),
                memory_id=data.get("memory_id"),
                message="W5H armazenado",
            )
        except Exception as e:
            return StoreResult(success=False, message=str(e))
    
    # ==================== UTILITY METHODS ====================
    
    def clear(self) -> bool:
        """Limpa todas as memórias do namespace."""
        try:
            response = self._session.post(f"{self.cortex_url}/memory/clear")
            return response.json().get("success", False)
        except Exception:
            return False
    
    def stats(self) -> dict:
        """Retorna estatísticas do namespace."""
        try:
            response = self._session.get(f"{self.cortex_url}/memory/stats")
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def health(self) -> dict:
        """Retorna saúde da memória."""
        try:
            response = self._session.get(f"{self.cortex_url}/memory/health")
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    @property
    def usage_stats(self) -> dict:
        """Estatísticas de uso do cliente."""
        total_extracts = self._extract_success + self._extract_fail
        return {
            "namespace": self.namespace,
            "recall_count": self._recall_count,
            "store_count": self._store_count,
            "extract_success": self._extract_success,
            "extract_fail": self._extract_fail,
            "extract_rate": self._extract_success / total_extracts if total_extracts > 0 else 0,
            "last_context_length": len(self._last_context),
            "last_memory": self._last_memory.to_dict() if self._last_memory else None,
        }
    
    @property
    def memory_instruction(self) -> str:
        """Retorna a instrução de memória para injetar manualmente."""
        return MEMORY_INSTRUCTION
    
    # ==================== CONTEXT MANAGER ====================
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._session.close()


# ==================== DECORATOR HELPER ====================


def with_memory(
    namespace: str | None = None,
    cortex_url: str | None = None,
    inject_memory_instruction: bool = True,
    auto_extract: bool = True,
):
    """
    Decorator que adiciona memória a qualquer função de agente.
    
    A função decorada deve ter assinatura:
        fn(user_message: str, context: str = "") -> str
    
    O decorator:
    1. Injeta contexto + instrução [MEMORY] no prompt
    2. Extrai [MEMORY] do output
    3. Remove o bloco antes de retornar
    4. Armazena a memória no Cortex
    
    Example:
        @with_memory(namespace="meu_agente")
        def meu_agente(user_message: str, context: str = "") -> str:
            # context já contém memória + instrução [MEMORY]
            return llm.generate(context + user_message)
        
        # Uso
        response = meu_agente("Olá!")  # Retorna resposta LIMPA
    """
    memory = CortexMemory(
        namespace=namespace, 
        cortex_url=cortex_url,
        inject_memory_instruction=inject_memory_instruction,
        auto_extract=auto_extract,
    )
    
    def decorator(fn: Callable[[str, str], str]):
        def wrapper(user_message: str, **kwargs) -> str:
            # Before: recall + instrução
            context = memory.before(user_message)
            
            # Call agent
            raw_response = fn(user_message, context=context, **kwargs)
            
            # After: extrai memória e limpa resposta
            clean_response = memory.after(user_message, raw_response)
            
            return clean_response
        
        wrapper._cortex_memory = memory  # Expõe para debug
        return wrapper
    
    return decorator
