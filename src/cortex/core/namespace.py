"""
Gerenciador de Memórias com Isolamento por Namespace.

Permite que múltiplos clientes/agentes usem o Cortex sem
que suas memórias se misturem.

Exemplos de namespace:
- "agent_001:user_123" - Agente específico para usuário específico
- "support_bot:cliente_acme" - Bot de suporte para cliente ACME
- "dev_assistant:projeto_alpha" - Assistente de dev para projeto

O namespace é definido pelo usuário do Cortex - total flexibilidade.
"""

from pathlib import Path
from typing import Any

from cortex.core.memory_graph import MemoryGraph


class NamespacedMemoryManager:
    """
    Gerencia múltiplos grafos de memória isolados por namespace.
    
    Cada namespace tem seu próprio grafo e arquivo de persistência.
    Zero vazamento entre namespaces.
    
    Usage:
        manager = NamespacedMemoryManager(base_path="/data/cortex")
        
        # Agente A com usuário 123
        graph_a = manager.get_graph("agent_a:user_123")
        graph_a.store(...)
        
        # Agente A com usuário 456 (isolado!)
        graph_b = manager.get_graph("agent_a:user_456")
        graph_b.store(...)
        
        # Agente B com usuário 123 (também isolado!)
        graph_c = manager.get_graph("agent_b:user_123")
    """
    
    def __init__(self, base_path: Path | str | None = None):
        """
        Inicializa o gerenciador.
        
        Args:
            base_path: Diretório base para persistência.
                       Cada namespace cria subpasta própria.
        """
        self.base_path = Path(base_path) if base_path else None
        self._graphs: dict[str, MemoryGraph] = {}
    
    def get_graph(self, namespace: str) -> MemoryGraph:
        """
        Obtém ou cria grafo para um namespace.
        
        Args:
            namespace: Identificador único (ex: "agent:user", "bot:client")
        
        Returns:
            MemoryGraph isolado para esse namespace
        """
        if namespace not in self._graphs:
            self._graphs[namespace] = self._create_graph(namespace)
        
        return self._graphs[namespace]
    
    def _create_graph(self, namespace: str) -> MemoryGraph:
        """Cria novo grafo com persistência isolada."""
        if self.base_path:
            # Sanitiza namespace para nome de pasta
            safe_name = self._sanitize_namespace(namespace)
            storage_path = self.base_path / safe_name
            return MemoryGraph(storage_path=storage_path)
        
        return MemoryGraph(storage_path=None)
    
    def _sanitize_namespace(self, namespace: str) -> str:
        """
        Converte namespace para nome de pasta seguro.
        
        "agent:user_123" → "agent__user_123"
        "support/bot:client" → "support_bot__client"
        """
        # Remove caracteres problemáticos
        safe = namespace.replace(":", "__").replace("/", "_").replace("\\", "_")
        # Remove caracteres especiais
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in safe)
        return safe
    
    def list_namespaces(self) -> list[str]:
        """Lista todos os namespaces em memória."""
        return list(self._graphs.keys())
    
    def list_persisted_namespaces(self) -> list[str]:
        """Lista namespaces com dados persistidos."""
        if not self.base_path or not self.base_path.exists():
            return []
        
        namespaces = []
        for path in self.base_path.iterdir():
            if path.is_dir() and (path / "memory_graph.json").exists():
                # Reverte sanitização (aproximado)
                ns = path.name.replace("__", ":")
                namespaces.append(ns)
        
        return namespaces
    
    def delete_namespace(self, namespace: str) -> bool:
        """
        Remove um namespace e todos seus dados.
        
        Returns:
            True se removido, False se não existia
        """
        # Remove da memória
        if namespace in self._graphs:
            del self._graphs[namespace]
        
        # Remove do disco
        if self.base_path:
            safe_name = self._sanitize_namespace(namespace)
            storage_path = self.base_path / safe_name
            if storage_path.exists():
                import shutil
                shutil.rmtree(storage_path)
                return True
        
        return False
    
    def get_stats(self) -> dict[str, Any]:
        """Estatísticas de todos os namespaces."""
        stats = {
            "total_namespaces": len(self._graphs),
            "persisted_namespaces": len(self.list_persisted_namespaces()),
            "namespaces": {},
        }
        
        for ns, graph in self._graphs.items():
            stats["namespaces"][ns] = graph.stats()
        
        return stats
    
    def clear_all(self) -> int:
        """
        Remove TODOS os namespaces. Use com cuidado!
        
        Returns:
            Número de namespaces removidos
        """
        count = len(self._graphs)
        
        for namespace in list(self._graphs.keys()):
            self.delete_namespace(namespace)
        
        return count


# Singleton global para fácil acesso
_global_manager: NamespacedMemoryManager | None = None


def get_memory_manager(base_path: Path | str | None = None) -> NamespacedMemoryManager:
    """
    Obtém o gerenciador global de memórias.
    
    Na primeira chamada, cria o gerenciador com o base_path fornecido.
    Chamadas subsequentes retornam o mesmo gerenciador.
    """
    global _global_manager
    
    if _global_manager is None:
        _global_manager = NamespacedMemoryManager(base_path=base_path)
    
    return _global_manager


def reset_memory_manager() -> None:
    """Reseta o gerenciador global (para testes)."""
    global _global_manager
    _global_manager = None
