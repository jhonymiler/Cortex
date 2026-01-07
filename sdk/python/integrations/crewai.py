"""
Cortex CrewAI Integration - Memória de longo prazo para CrewAI.

Uso:
    from cortex.integrations import CortexCrewAIMemory
    from crewai import Crew, Agent, Task
    
    # Cria memória Cortex
    memory = CortexCrewAIMemory(namespace="minha_crew")
    
    # Usa com CrewAI
    crew = Crew(
        agents=[...],
        tasks=[...],
        memory=True,
        long_term_memory=memory,  # Plug and play!
    )

Compatível com:
- CrewAI >= 0.30.0
"""

from typing import Any, Dict, List, Optional
import sys
import os

# Adiciona path do SDK
sdk_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if sdk_path not in sys.path:
    sys.path.insert(0, sdk_path)

from cortex_memory import CortexMemory


class CortexCrewAIMemory:
    """
    Memória Cortex para CrewAI.
    
    Implementa interface compatível com long_term_memory do CrewAI.
    
    Nota: Esta é uma implementação preliminar.
    A API do CrewAI pode mudar entre versões.
    
    Attributes:
        namespace: Identificador para isolamento
    """
    
    def __init__(
        self,
        namespace: str | None = None,
        cortex_url: str | None = None,
    ):
        # Usa variáveis de ambiente como fallback
        self.namespace = namespace or os.getenv("CORTEX_NAMESPACE", "crewai")
        cortex_url = cortex_url or os.getenv("CORTEX_API_URL", "http://localhost:8000")
        self._cortex = CortexMemory(
            namespace=self.namespace,
            cortex_url=cortex_url,
        )
    
    def save(
        self,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        agent: Optional[str] = None,
    ) -> None:
        """
        Salva memória de longo prazo.
        
        Chamado pelo CrewAI após execução de tarefas.
        
        Args:
            value: Conteúdo a ser armazenado
            metadata: Metadados adicionais
            agent: Nome do agente que gerou
        """
        metadata = metadata or {}
        
        # Extrai W5H do value e metadata
        who = [agent] if agent else ["crew"]
        what = str(value)[:100] if value else "task_completed"
        why = metadata.get("task", "")
        how = metadata.get("result", str(value)[:200] if value else "")
        
        self._cortex.store_w5h(
            who=who,
            what=what,
            why=why,
            how=how,
            importance=metadata.get("importance", 0.5),
        )
    
    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        Busca memórias relevantes.
        
        Chamado pelo CrewAI antes de executar tarefas.
        
        Args:
            query: Texto para buscar
            limit: Máximo de resultados
            score_threshold: Score mínimo (não usado, Cortex não usa embeddings)
            
        Returns:
            Lista de memórias encontradas
        """
        result = self._cortex.recall(query, limit=limit)
        
        # Formata para CrewAI
        memories = []
        
        for episode in result.raw.get("episodes", []):
            memories.append({
                "content": f"{episode.get('action', '')}: {episode.get('outcome', '')}",
                "metadata": {
                    "id": episode.get("id", ""),
                    "action": episode.get("action", ""),
                    "outcome": episode.get("outcome", ""),
                },
                "score": 1.0,  # Cortex não usa score de similaridade
            })
        
        return memories
    
    def reset(self) -> None:
        """Limpa toda a memória."""
        self._cortex.clear()
    
    @property
    def cortex(self) -> CortexMemory:
        """Acesso ao cliente Cortex subjacente."""
        return self._cortex

