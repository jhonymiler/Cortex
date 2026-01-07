"""
CortexMemorySDK - Cliente para serviço Cortex.

O SDK faz:
1. Extração local (determinística)
2. Normalização local (Action → W5H)
3. Comunicação HTTP com API Cortex

O SDK NÃO:
- Chama LLM
- Infere dados
- Armazena localmente
"""

import os
from typing import Any

import requests

from .contracts import Action, W5H, RecallResult
from .normalizer import action_to_w5h
from .extractor import extract_action, remove_memory_marker


class CortexMemorySDK:
    """
    Cliente SDK para serviço Cortex Memory.
    
    Prepara dados localmente e comunica com API remota.
    
    Example:
        sdk = CortexMemorySDK(namespace="customer_support:user_123")
        
        # Opção A: explícita (recomendada)
        sdk.remember({
            "verb": "solicitou",
            "subject": "carlos",
            "object": "reembolso",
        })
        
        # Opção B: texto (best-effort)
        sdk.process("Cliente Carlos pediu reembolso")
        
        # Busca
        result = sdk.recall("Carlos")
        print(result.to_prompt_context())
    """
    
    def __init__(
        self,
        namespace: str = "default",
        api_url: str | None = None,
        api_key: str | None = None,
    ):
        """
        Inicializa SDK.
        
        Args:
            namespace: Identificador único (tenant:user, agent:session, etc)
            api_url: URL da API Cortex (env: CORTEX_API_URL)
            api_key: Chave de API (env: CORTEX_API_KEY)
        """
        self.namespace = namespace
        self.api_url = (api_url or os.getenv("CORTEX_API_URL", "http://localhost:8000")).rstrip('/')
        self.api_key = api_key or os.getenv("CORTEX_API_KEY", "")
        
        self._session = requests.Session()
        if self.api_key:
            self._session.headers["Authorization"] = f"Bearer {self.api_key}"
        self._session.headers["Content-Type"] = "application/json"
    
    # ==================== API PRINCIPAL ====================
    
    def remember(
        self,
        action: dict | Action,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """
        Armazena memória (Action → W5H → API).
        
        Args:
            action: { verb, subject?, object?, modifiers? }
            reason: Motivo explícito (opcional)
        
        Returns:
            Resposta da API
        
        Example:
            sdk.remember({
                "verb": "solicitou",
                "subject": "carlos",
                "object": "reembolso",
            })
        """
        # Converte para Action se dict
        if isinstance(action, dict):
            action = Action(
                verb=action.get("verb", ""),
                subject=action.get("subject", ""),
                object=action.get("object", ""),
                modifiers=tuple(action.get("modifiers", [])),
            )
        
        # Normaliza para W5H localmente
        w5h = action_to_w5h(action, namespace=self.namespace, reason=reason)
        
        # Envia para API
        return self._api_remember(w5h)
    
    def observe(self, text: str) -> dict[str, Any]:
        """
        Armazena observação (texto bruto).
        
        Não tenta extrair estrutura.
        
        Args:
            text: Texto livre
        
        Returns:
            Resposta da API
        """
        return self._api_observe(text)
    
    def process(self, text: str) -> tuple[dict[str, Any], str]:
        """
        Tenta extrair Action e armazena.
        
        Pipeline:
            1. Extrai Action (local)
            2. Se sucesso → remember()
            3. Se falha → observe()
        
        Args:
            text: Texto livre
        
        Returns:
            Tuple (resposta, tipo) onde tipo é "event" ou "observation"
        """
        action = extract_action(text)
        
        if action:
            response = self.remember(action)
            return response, "event"
        else:
            response = self.observe(text)
            return response, "observation"
    
    def recall(
        self,
        query: str = "",
        limit: int = 5,
    ) -> RecallResult:
        """
        Busca memórias relevantes.
        
        Args:
            query: Texto de busca
            limit: Máximo de resultados
        
        Returns:
            RecallResult com memórias
        """
        return self._api_recall(query, limit)
    
    def clean_response(self, text: str) -> str:
        """
        Remove marcadores de memória do texto.
        
        Útil para limpar resposta antes de enviar ao usuário.
        """
        return remove_memory_marker(text)
    
    # ==================== API HTTP ====================
    
    def _api_remember(self, w5h: W5H) -> dict[str, Any]:
        """Envia W5H para API."""
        payload = {
            "namespace": self.namespace,
            **w5h.to_dict(),
        }
        
        try:
            response = self._session.post(
                f"{self.api_url}/memory/remember",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e), "success": False}
    
    def _api_observe(self, text: str) -> dict[str, Any]:
        """Envia observação para API."""
        payload = {
            "namespace": self.namespace,
            "raw": text,
        }
        
        try:
            response = self._session.post(
                f"{self.api_url}/memory/observe",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e), "success": False}
    
    def _api_recall(self, query: str, limit: int) -> RecallResult:
        """Busca memórias na API."""
        payload = {
            "namespace": self.namespace,
            "query": query,
            "limit": limit,
        }
        
        try:
            response = self._session.post(
                f"{self.api_url}/memory/recall",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            
            memories = [W5H.from_dict(m) for m in data.get("memories", [])]
            return RecallResult(
                memories=memories,
                context_summary=data.get("context_summary", ""),
            )
        except requests.RequestException:
            return RecallResult()
    
    # ==================== UTILIDADES ====================
    
    def health(self) -> bool:
        """Verifica se API está online."""
        try:
            response = self._session.get(f"{self.api_url}/health")
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def stats(self) -> dict[str, Any]:
        """Retorna estatísticas do namespace."""
        try:
            response = self._session.get(
                f"{self.api_url}/memory/stats",
                params={"namespace": self.namespace},
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            return {"error": str(e)}
    
    def __repr__(self) -> str:
        return f"CortexMemorySDK(namespace={self.namespace!r}, api={self.api_url!r})"

