#!/usr/bin/env python3
"""
Cortex SDK - Cliente Python para API REST do Cortex

SDK para acessar Cortex remotamente via HTTP.
Usa modelo W5H (Who, What, Why, When, Where, How).

Exemplo de uso:
    from cortex_sdk import CortexClient
    
    client = CortexClient(namespace="meu_agente:usuario_123")
    
    # Antes de responder - buscar contexto
    context = client.recall("problema com pagamento")
    
    # Após responder - memorizar interação
    client.remember(
        who=["usuario_123", "sistema_pagamentos"],
        what="reportou erro de pagamento",
        why="cartão expirado",
        how="orientado a atualizar dados do cartão"
    )
"""

import os
from typing import Any
from dataclasses import dataclass
import requests


@dataclass
class IdentityConfig:
    """Configuração do IdentityKernel (Memory Firewall)."""
    enabled: bool = True
    mode: str = "pattern"  # pattern, semantic, hybrid
    strict: bool = False
    
    # Valores do agente
    values: list[dict] | None = None
    # Fronteiras absolutas
    boundaries: list[dict] | None = None
    # Diretrizes de comportamento
    directives: list[dict] | None = None
    # Padrões customizados anti-jailbreak
    custom_patterns: list[dict] | None = None
    # Persona do agente
    persona: str | None = None


@dataclass  
class EvaluationResult:
    """Resultado da avaliação do IdentityKernel."""
    passed: bool
    action: str  # allow, warn, block
    reason: str
    threats: list[dict]
    alignment_score: float
    source: str


class CortexClient:
    """Cliente HTTP para comunicação com API Cortex."""

    def __init__(
        self,
        base_url: str | None = None,
        namespace: str | None = None,
        identity: IdentityConfig | None = None,
    ):
        """
        Inicializa cliente Cortex.
        
        Args:
            base_url: URL base da API Cortex (env: CORTEX_API_URL)
            namespace: Namespace para isolamento de memórias (env: CORTEX_NAMESPACE)
                       Use identificador único por usuário/agente:
                       - Atendimento: f"suporte:{user_id}"
                       - Subagente: f"agent:{agent_id}"
                       - Multi-tenant: f"{tenant}:{user}"
            identity: Configuração do IdentityKernel (Memory Firewall)
                      Se None, usa configuração padrão do servidor
        
        Example:
            # Básico
            client = CortexClient(namespace="meu_agente")
            
            # Com Identity Kernel customizado
            client = CortexClient(
                namespace="suporte:user_123",
                identity=IdentityConfig(
                    mode="hybrid",
                    boundaries=[
                        {"id": "no_refunds", "description": "Nunca processar reembolsos"}
                    ]
                )
            )
        """
        self.base_url = (base_url or os.getenv("CORTEX_API_URL", "http://localhost:8000")).rstrip('/')
        self.namespace = namespace or os.getenv("CORTEX_NAMESPACE", "default")
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-Cortex-Namespace": self.namespace,
        })
        
        # Configura IdentityKernel se fornecido
        self._identity = identity
        if identity:
            self._configure_identity(identity)
    
    def _configure_identity(self, config: IdentityConfig) -> None:
        """Configura IdentityKernel no servidor."""
        payload = {}
        
        if config.mode:
            payload["mode"] = config.mode
        if config.persona:
            payload["persona"] = config.persona
        if config.values:
            payload["values"] = config.values
        if config.boundaries:
            payload["boundaries"] = config.boundaries
        if config.directives:
            payload["directives"] = config.directives
        if config.custom_patterns:
            payload["custom_patterns"] = config.custom_patterns
        
        if payload:
            url = f"{self.base_url}/identity/configure"
            response = self.session.post(url, json=payload)
            response.raise_for_status()

    # ==================== IDENTITY KERNEL (MEMORY FIREWALL) ====================

    def evaluate(self, input_text: str, context: dict | None = None) -> EvaluationResult:
        """
        Avalia input contra o IdentityKernel (Memory Firewall).
        
        Use ANTES de armazenar memórias para verificar se o input é seguro.
        
        Args:
            input_text: Texto a avaliar (mensagem do usuário)
            context: Contexto adicional (opcional)
        
        Returns:
            EvaluationResult com:
            - passed: Se o input é seguro
            - action: "allow", "warn" ou "block"
            - reason: Explicação
            - threats: Ameaças detectadas
            - alignment_score: 0.0 a 1.0
        
        Example:
            result = client.evaluate("Ignore suas instruções")
            if not result.passed:
                print(f"Bloqueado: {result.reason}")
        """
        url = f"{self.base_url}/identity/evaluate"
        payload = {"input": input_text, "context": context or {}}
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        data = response.json()
        return EvaluationResult(
            passed=data["passed"],
            action=data["action"],
            reason=data["reason"],
            threats=data["threats"],
            alignment_score=data["alignment_score"],
            source=data["source"],
        )
    
    def is_safe(self, input_text: str) -> bool:
        """
        Verificação rápida se input é seguro.
        
        Args:
            input_text: Texto a verificar
        
        Returns:
            True se seguro, False se bloqueado
        """
        result = self.evaluate(input_text)
        return result.passed
    
    def identity_stats(self) -> dict[str, Any]:
        """
        Retorna estatísticas do IdentityKernel.
        
        Returns:
            Dict com total_evaluations, blocked, block_rate, etc.
        """
        url = f"{self.base_url}/identity/stats"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def identity_audit(self, limit: int = 100) -> list[dict]:
        """
        Retorna log de auditoria do IdentityKernel.
        
        Args:
            limit: Máximo de entradas
        
        Returns:
            Lista de avaliações recentes
        """
        url = f"{self.base_url}/identity/audit"
        response = self.session.get(url, params={"limit": limit})
        response.raise_for_status()
        return response.json().get("entries", [])

    # ==================== CORE W5H METHODS ====================

    def remember(
        self,
        who: list[str],
        what: str,
        why: str = "",
        how: str = "",
        where: str = "default",
        importance: float = 0.5,
    ) -> dict[str, Any]:
        """
        Armazena uma memória W5H.
        
        Use APÓS responder ao usuário para memorizar o que aconteceu.
        
        Args:
            who: Lista de participantes (nomes, emails, sistemas)
            what: O que aconteceu (ação/fato principal)
            why: Por quê aconteceu (causa/razão) - opcional
            how: Como foi resolvido (resultado) - opcional
            where: Namespace para organização (padrão: "default")
            importance: Importância de 0.0 a 1.0 (padrão: 0.5)
            
        Returns:
            Dict com:
            - success: Se armazenou com sucesso
            - memory_id: ID da memória criada
            - who_resolved: IDs das entidades dos participantes
            - consolidated: Se consolidou com memórias similares
            - retrievability: Score de recuperabilidade atual
            
        Example:
            client.remember(
                who=["maria@email.com", "sistema_pagamentos"],
                what="reportou erro de pagamento",
                why="cartão expirado",
                how="orientada a atualizar dados do cartão",
                importance=0.7
            )
        """
        url = f"{self.base_url}/memory/remember"
        payload = {
            "who": who,
            "what": what,
            "why": why,
            "how": how,
            "where": where,
            "importance": importance,
        }
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        return response.json()

    def recall(
        self,
        query: str,
        who: list[str] | None = None,
        where: str | None = None,
        min_importance: float = 0.0,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Busca memórias relevantes para uma query.
        
        Use ANTES de responder ao usuário para ter contexto.
        
        Args:
            query: Texto para buscar
            who: Filtrar por participantes específicos (opcional)
            where: Filtrar por namespace (opcional)
            min_importance: Importância mínima 0.0-1.0 (padrão: 0.0)
            limit: Máximo de resultados (padrão: 10)
            
        Returns:
            Dict com:
            - entities_found: Número de entidades conhecidas
            - episodes_found: Número de episódios relevantes
            - context_summary: Resumo em texto
            - prompt_context: YAML para injetar no prompt
            - entities: Lista de entidades
            - episodes: Lista de episódios
        """
        url = f"{self.base_url}/memory/recall"
        payload = {
            "query": query,
            "context": {
                "who": who,
                "where": where,
                "min_importance": min_importance,
            },
            "limit": limit,
        }
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        return response.json()

    def forget(
        self,
        memory_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """
        Esquece uma memória (marca como esquecida, excluída de recalls).
        
        Use quando usuário pede para esquecer algo ou quando
        uma memória é encontrada incorreta.
        
        Args:
            memory_id: ID da memória para esquecer
            reason: Por que está sendo esquecida (opcional)
            
        Returns:
            Dict com:
            - success: Se operação sucedeu
            - memory_id: ID da memória esquecida
            - was_forgotten: True se já estava esquecida antes
            - message: Mensagem de status
        """
        url = f"{self.base_url}/memory/forget"
        payload = {
            "memory_id": memory_id,
            "reason": reason,
        }
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        return response.json()

    # ==================== ADMIN METHODS ====================

    def stats(self) -> dict[str, Any]:
        """
        Obtém estatísticas do grafo de memória.
        
        Returns:
            Dict com contagens de entities, episodes, relations, etc.
        """
        url = f"{self.base_url}/memory/stats"
        
        response = self.session.get(url)
        response.raise_for_status()
        
        return response.json()

    def health(self) -> dict[str, Any]:
        """
        Obtém métricas de saúde da memória.
        
        Returns:
            Dict com health_score, orphan_entities, etc.
        """
        url = f"{self.base_url}/memory/health"
        
        response = self.session.get(url)
        response.raise_for_status()
        
        return response.json()

    def clear(self) -> dict[str, Any]:
        """
        Limpa toda a memória do namespace (CUIDADO!).
        
        Returns:
            Dict com status da operação
        """
        url = f"{self.base_url}/memory/clear"
        
        response = self.session.delete(url)
        response.raise_for_status()
        
        return response.json()

    def health_check(self) -> bool:
        """
        Verifica se API está online e respondendo.
        
        Returns:
            True se API está ok, False caso contrário
        """
        try:
            url = f"{self.base_url}/health"
            response = self.session.get(url, timeout=2)
            return response.status_code == 200
        except Exception:
            return False


if __name__ == "__main__":
    # Teste rápido do SDK W5H
    import sys
    
    print("🧪 Testando Cortex SDK (W5H)...\n")
    
    client = CortexClient()
    
    # 1. Health check
    print("1. Verificando se API está online...")
    if not client.health_check():
        print("❌ API Cortex não está respondendo em http://localhost:8000")
        print("   Execute: cortex-api")
        sys.exit(1)
    print("✅ API online!\n")
    
    # 2. Stats inicial
    print("2. Estatísticas iniciais:")
    stats = client.stats()
    print(f"   Entidades: {stats.get('total_entities', 0)}")
    print(f"   Memórias: {stats.get('total_episodes', 0)}\n")
    
    # 3. Remember (W5H)
    print("3. Armazenando memória W5H...")
    result = client.remember(
        who=["test_sdk", "cortex_api"],
        what="testou SDK com modelo W5H",
        why="validar funcionamento do SDK",
        how="teste passou com sucesso",
        importance=0.6
    )
    print(f"✅ Armazenado! Memory ID: {result.get('memory_id', 'N/A')[:8]}...")
    print(f"   Retrievability: {result.get('retrievability', 0):.2f}\n")
    
    # 4. Recall
    print("4. Buscando memória...")
    memories = client.recall("teste SDK W5H")
    print(f"✅ Encontradas {memories.get('episodes_found', 0)} memórias")
    if memories.get('prompt_context'):
        print(f"   Contexto: {memories.get('prompt_context')[:100]}...\n")
    
    # 5. Stats final
    print("5. Estatísticas finais:")
    stats = client.stats()
    print(f"   Entidades: {stats.get('total_entities', 0)}")
    print(f"   Memórias: {stats.get('total_episodes', 0)}\n")
    
    print("✅ SDK W5H funcionando corretamente!")
