#!/usr/bin/env python3
"""
Cortex SDK - Cliente Python para API REST do Cortex

SDK simples para acessar Cortex remotamente via HTTP.
Permite testes isolados sem dependência direta do código do Cortex.
"""

from typing import Any
import requests


class CortexClient:
    """Cliente HTTP para comunicação com API Cortex."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Inicializa cliente Cortex.
        
        Args:
            base_url: URL base da API Cortex (padrão: http://localhost:8000)
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json"
        })

    def recall(self, query: str, context: dict | None = None) -> dict[str, Any]:
        """
        Busca memórias relevantes para uma query.
        
        Args:
            query: Texto para buscar
            context: Contexto adicional (opcional)
            
        Returns:
            Dict com entities, episodes, relations
            
        Raises:
            requests.HTTPError: Se API retornar erro
        """
        url = f"{self.base_url}/memory/recall"
        payload = {
            "query": query,
            "context": context or {}
        }
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        return response.json()

    def store(
        self,
        action: str,
        outcome: str,
        participants: list[dict] | None = None,
        context: str = "",
        relations: list[dict] | None = None
    ) -> dict[str, Any]:
        """
        Armazena um episódio.
        
        Args:
            action: O que foi feito (verbo: "conversed", "analyzed", etc.)
            outcome: O resultado
            participants: Lista de participantes (entidades)
            context: Contexto da ação (opcional)
            relations: Lista de relações para criar (opcional)
            
        Returns:
            Dict com IDs criados e status
            
        Raises:
            requests.HTTPError: Se API retornar erro
        """
        url = f"{self.base_url}/memory/store"
        payload = {
            "action": action,
            "outcome": outcome,
            "participants": participants or [],
            "context": context,
            "relations": relations or []
        }
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        
        return response.json()

    def stats(self) -> dict[str, Any]:
        """
        Obtém estatísticas do grafo de memória.
        
        Returns:
            Dict com contagens de entities, episodes, relations, etc.
            
        Raises:
            requests.HTTPError: Se API retornar erro
        """
        url = f"{self.base_url}/memory/stats"
        
        response = self.session.get(url)
        response.raise_for_status()
        
        return response.json()

    def clear(self) -> dict[str, Any]:
        """
        Limpa toda a memória (CUIDADO!).
        
        Returns:
            Dict com status da operação
            
        Raises:
            requests.HTTPError: Se API retornar erro
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
        except:
            return False


# Helpers para construção de payloads

def make_participant(
    type: str,
    name: str,
    identifiers: list[str] | None = None
) -> dict:
    """
    Cria payload de participante (entidade).
    
    Args:
        type: Tipo da entidade (livre: "user", "file", "character", etc.)
        name: Nome da entidade
        identifiers: IDs alternativos (opcional)
        
    Returns:
        Dict formatado para API
    """
    return {
        "type": type,
        "name": name,
        "identifiers": identifiers or []
    }


def make_relation(
    from_name: str,
    relation_type: str,
    to_name: str
) -> dict:
    """
    Cria payload de relação.
    
    Args:
        from_name: Nome da entidade origem
        relation_type: Tipo da relação (livre: "caused_by", "loves", etc.)
        to_name: Nome da entidade destino
        
    Returns:
        Dict formatado para API
    """
    return {
        "from": from_name,
        "type": relation_type,
        "to": to_name
    }


if __name__ == "__main__":
    # Teste rápido do SDK
    import sys
    
    print("🧪 Testando Cortex SDK...\n")
    
    client = CortexClient()
    
    # 1. Health check
    print("1. Verificando se API está online...")
    if not client.health_check():
        print("❌ API Cortex não está respondendo em http://localhost:8000")
        print("   Execute: uvicorn cortex.api.app:app --reload")
        sys.exit(1)
    print("✓ API online!\n")
    
    # 2. Stats inicial
    print("2. Estatísticas iniciais:")
    stats = client.stats()
    print(f"   Entidades: {stats.get('entity_count', 0)}")
    print(f"   Episódios: {stats.get('episode_count', 0)}\n")
    
    # 3. Store
    print("3. Armazenando teste...")
    result = client.store(
        action="tested_sdk",
        outcome="SDK funcionando corretamente",
        participants=[
            make_participant("user", "test_sdk", identifiers=["sdk_test_001"])
        ]
    )
    print(f"✓ Armazenado! Episode ID: {result.get('episode_id', 'N/A')[:8]}...\n")
    
    # 4. Recall
    print("4. Buscando memória...")
    memories = client.recall("teste SDK")
    print(f"✓ Encontradas {len(memories.get('episodes', []))} episódios\n")
    
    # 5. Stats final
    print("5. Estatísticas finais:")
    stats = client.stats()
    print(f"   Entidades: {stats.get('entity_count', 0)}")
    print(f"   Episódios: {stats.get('episode_count', 0)}\n")
    
    print("✅ SDK funcionando corretamente!")
