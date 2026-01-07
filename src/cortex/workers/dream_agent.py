"""
Dream Agent - Consolida e refina memórias em background.

Inspirado no processo de consolidação de memória durante o sono:
1. Analisa memórias brutas
2. Extrai entidades e relações
3. Cria resumos consolidados
4. Salva memórias refinadas

Uso:
    from cortex.workers import DreamAgent
    
    agent = DreamAgent(
        cortex_url="http://localhost:8000",
        llm_url="http://localhost:11434",  # Ollama
        llm_model="gemma3:4b",
    )
    
    result = agent.dream(namespace="meu_agente")
    print(f"Refinadas: {result.memories_refined}")
"""

import os
import re
import requests
from dataclasses import dataclass, field


@dataclass
class DreamResult:
    """Resultado do sonho/consolidação."""
    success: bool = False
    memories_analyzed: int = 0
    memories_refined: int = 0
    entities_extracted: list[str] = field(default_factory=list)
    patterns_found: list[str] = field(default_factory=list)
    consolidated_summary: str = ""
    error: str = ""


class DreamAgent:
    """
    Refina e consolida memórias usando LLM.
    
    Este worker simula o processo de consolidação de memória
    que ocorre durante o sono no cérebro humano.
    
    Attributes:
        cortex_url: URL da API Cortex
        llm_url: URL do servidor LLM (Ollama)
        llm_model: Modelo LLM a usar
    """
    
    REFINEMENT_PROMPT = """Você é um sistema de consolidação de memória.

Analise estas memórias brutas de um atendimento:

{context}

Sua tarefa:
1. Identifique PADRÕES e agrupe memórias similares
2. Extraia ENTIDADES importantes (pessoas, produtos, problemas)
3. Crie RELAÇÕES entre entidades
4. Gere um RESUMO consolidado

Responda EXATAMENTE neste formato YAML:

```yaml
entidades:
  - nome: "Nome da Entidade"
    tipo: "cliente|equipamento|problema|local"
    atributos:
      chave: "valor"

padroes:
  - what: "verbo_acao_padrao"
    ocorrencias: 1
    resumo: "Descrição do padrão"

relacoes:
  - de: "Entidade1"
    tipo: "possui|reportou|resolveu"
    para: "Entidade2"

resumo_consolidado: |
  Resumo em 2-3 frases do que aconteceu.
```
"""
    
    def __init__(
        self,
        cortex_url: str | None = None,
        llm_url: str | None = None,
        llm_model: str | None = None,
    ):
        # Usa variáveis de ambiente como fallback
        self.cortex_url = (cortex_url or os.getenv("CORTEX_API_URL", "http://localhost:8000")).rstrip("/")
        self.llm_url = (llm_url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.llm_model = llm_model or os.getenv("OLLAMA_MODEL", "gemma3:4b")
        
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})
    
    def dream(self, namespace: str, query: str = "") -> DreamResult:
        """
        Executa consolidação de memórias para um namespace.
        
        Similar ao processo de sonho que consolida memórias no cérebro.
        
        Args:
            namespace: Namespace a processar
            query: Query opcional para filtrar memórias (default: busca ampla)
        
        Returns:
            DreamResult com detalhes do refinamento
        """
        result = DreamResult()
        
        try:
            # 1. Busca memórias brutas
            self._session.headers["X-Cortex-Namespace"] = namespace
            
            recall_query = query or "cliente problema solução atendimento"
            recall_resp = self._session.post(
                f"{self.cortex_url}/memory/recall",
                json={"query": recall_query, "context": {}, "limit": 50},
            )
            
            recall_data = recall_resp.json()
            context = recall_data.get("prompt_context", "")
            result.memories_analyzed = recall_data.get("episodes_found", 0)
            
            if not context or len(context) < 50:
                result.error = "Poucas memórias para refinar"
                return result
            
            # 2. Envia para LLM refinar
            prompt = self.REFINEMENT_PROMPT.format(context=context)
            
            llm_resp = requests.post(
                f"{self.llm_url}/api/chat",
                json={
                    "model": self.llm_model,
                    "messages": [
                        {"role": "system", "content": "Responda apenas em YAML."},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                },
                timeout=120,
            )
            
            llm_content = llm_resp.json().get("message", {}).get("content", "")
            
            # 3. Parseia resultado
            yaml_match = re.search(r'```yaml\s*\n(.+?)```', llm_content, re.DOTALL)
            if not yaml_match:
                result.error = "LLM não retornou YAML válido"
                return result
            
            yaml_content = yaml_match.group(1)
            
            # Extrai entidades
            entidades = re.findall(r'nome:\s*"([^"]+)"', yaml_content)
            result.entities_extracted = entidades
            
            # Extrai padrões
            padroes = re.findall(r'what:\s*"([^"]+)"', yaml_content)
            result.patterns_found = padroes
            
            # Extrai resumo consolidado
            resumo_match = re.search(
                r'resumo_consolidado:\s*\|?\s*\n(.+?)(?=\n\w|\Z)', 
                yaml_content, 
                re.DOTALL
            )
            if resumo_match:
                result.consolidated_summary = resumo_match.group(1).strip()
            
            # 4. Salva memória consolidada
            if result.consolidated_summary:
                store_resp = self._session.post(
                    f"{self.cortex_url}/memory/remember",
                    json={
                        "who": entidades[:3] if entidades else ["sistema"],
                        "what": "consolidacao_memoria",
                        "why": "dream_consolidation",
                        "how": result.consolidated_summary[:200],
                        "where": namespace,
                        "importance": 0.9,
                        "is_summary": True,  # Marca como resumo de consolidação
                    },
                )
                
                store_data = store_resp.json()
                if store_data.get("success"):
                    result.memories_refined = 1
                    summary_id = store_data.get("memory_id")
                    
                    # 5. Marca memórias originais como consolidadas
                    if summary_id:
                        self._mark_originals_as_consolidated(
                            namespace=namespace,
                            summary_id=summary_id,
                            patterns=padroes,
                        )
            
            result.success = True
            
        except Exception as e:
            result.error = str(e)
        
        return result
    
    def _mark_originals_as_consolidated(
        self,
        namespace: str,
        summary_id: str,
        patterns: list[str],
    ) -> int:
        """
        Marca memórias originais como consolidadas.
        
        Define consolidated_into para apontar para o resumo.
        Isso faz as memórias originais decairem mais rápido.
        
        Returns:
            Número de memórias marcadas
        """
        marked = 0
        
        try:
            # Busca memórias com padrões similares
            for pattern in patterns[:5]:  # Limita para evitar muitas chamadas
                recall_resp = self._session.post(
                    f"{self.cortex_url}/memory/recall",
                    json={"query": pattern, "context": {}, "limit": 20},
                )
                
                episodes = recall_resp.json().get("episodes", [])
                
                for ep in episodes:
                    ep_id = ep.get("id")
                    # Não marca o próprio resumo
                    if ep_id and ep_id != summary_id:
                        # Atualiza memória para apontar para o resumo
                        update_resp = self._session.patch(
                            f"{self.cortex_url}/memory/episode/{ep_id}",
                            json={"consolidated_into": summary_id},
                        )
                        if update_resp.status_code == 200:
                            marked += 1
        except Exception:
            pass  # Silently fail - não é crítico
        
        return marked
    
    def dream_all_namespaces(self) -> dict[str, DreamResult]:
        """
        Executa consolidação em todos os namespaces.
        
        Returns:
            Dict de namespace -> DreamResult
        """
        results = {}
        
        try:
            # Lista namespaces
            resp = self._session.get(f"{self.cortex_url}/namespaces")
            namespaces = resp.json().get("namespaces", [])
            
            for ns in namespaces:
                results[ns] = self.dream(ns)
                
        except Exception as e:
            results["_error"] = DreamResult(error=str(e))
        
        return results
