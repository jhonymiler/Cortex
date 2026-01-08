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
from pathlib import Path

from cortex.core.memory_normalizer import MemoryNormalizer
from cortex.core.collective_memory import CollectiveMemoryCollector


@dataclass
class DreamResult:
    """Resultado do sonho/consolidação."""
    success: bool = False
    memories_analyzed: int = 0
    memories_refined: int = 0  # Consolidações pessoais
    procedural_extracted: int = 0  # Conhecimentos LEARNED extraídos para coletivo
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

    # Prompt para extração de conhecimento procedural compartilhável
    PROCEDURAL_EXTRACTION_PROMPT = """Você é um sistema de extração de conhecimento.

Analise estas memórias consolidadas e identifique CONHECIMENTO PROCEDURAL que pode ajudar OUTROS usuários com problemas similares.

Memórias:
{context}

REGRAS IMPORTANTES:
1. Extraia APENAS soluções genéricas de problemas (procedimentos, passos, dicas)
2. REMOVA todos os dados pessoais (nomes, emails, telefones, endereços, CPF, cartões)
3. Não inclua detalhes específicos de um único caso
4. O conhecimento deve ser REUTILIZÁVEL para outros casos similares
5. Responda "NENHUM" se não houver conhecimento procedural genérico útil

Exemplos de conhecimento procedural válido:
- "Para resolver timeout em API: verificar connection pooling e aumentar timeout"
- "Cliente com pagamento recusado: verificar validade do cartão e limite"
- "Erro de login: limpar cache do navegador e redefinir senha"

Responda EXATAMENTE neste formato YAML:

```yaml
conhecimentos_procedurais:
  - problema: "Descrição genérica do problema"
    solucao: "Passos ou dicas para resolver"
    aplicabilidade: "alta|media|baixa"  # Quão genérico/reutilizável é
    contem_pii: false  # true se ainda contém dados pessoais (NÃO INCLUIR SE TRUE)

quantidade_validos: 0  # Número de conhecimentos com aplicabilidade alta/media e sem PII
```

Se não houver conhecimento procedural útil, responda:
```yaml
conhecimentos_procedurais: []
quantidade_validos: 0
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
        
        # Normalizador para compactar memórias
        self._normalizer = MemoryNormalizer(max_nouns=3, use_lemma=False)
    
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
            
            # Extrai padrões e NORMALIZA com spaCy
            padroes_raw = re.findall(r'what:\s*"([^"]+)"', yaml_content)
            padroes = [self._normalizer.extract_core(p) for p in padroes_raw]
            result.patterns_found = padroes
            
            # Extrai resumo consolidado e NORMALIZA
            resumo_match = re.search(
                r'resumo_consolidado:\s*\|?\s*\n(.+?)(?=\n\w|\Z)', 
                yaml_content, 
                re.DOTALL
            )
            if resumo_match:
                resumo_raw = resumo_match.group(1).strip()
                # Normaliza resumo para formato compacto
                result.consolidated_summary = self._normalizer.extract_core(resumo_raw)
            
            # 4. Salva memória consolidada NO MESMO NAMESPACE (permanece PERSONAL)
            # Consolidação é apenas compactação, NÃO muda visibilidade
            if result.consolidated_summary:
                # Extrai o padrão principal dos patterns para usar como what
                what_consolidated = padroes[0] if padroes else "consolidacao_memoria"
                
                store_resp = self._session.post(
                    f"{self.cortex_url}/memory/remember",
                    json={
                        "who": entidades[:3] if entidades else ["sistema"],
                        "what": what_consolidated,  # Já normalizado
                        "why": "dream_consolidation",
                        "how": result.consolidated_summary,  # Já normalizado
                        "where": namespace,  # MESMO namespace - permanece personal
                        "importance": 0.9,
                        "visibility": "personal",  # Consolidação NÃO é compartilhada automaticamente
                        "owner_id": "system",
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
            
            # 6. EXTRAÇÃO DE CONHECIMENTO PROCEDURAL (fase separada)
            # Usa LLM para identificar conhecimento genérico útil para outros usuários
            procedural_count = self._extract_and_store_procedural_knowledge(
                namespace=namespace,
                context=context,
            )
            
            result.procedural_extracted = procedural_count
            if procedural_count > 0:
                result.patterns_found.append(f"{procedural_count} conhecimentos procedurais extraídos para memória coletiva")
            
            result.success = True
            
        except Exception as e:
            result.error = str(e)
        
        return result
    
    def _get_parent_namespace(self, namespace: str) -> str | None:
        """
        Extrai o namespace pai de um namespace hierárquico.
        
        Args:
            namespace: Namespace hierárquico (ex: "support:customer_support:user_123")
            
        Returns:
            Namespace pai ou None se for raiz
            
        Examples:
            "support:customer_support:user_123" -> "support:customer_support"
            "support:customer_support" -> "support"
            "support" -> None
        """
        parts = namespace.split(":")
        if len(parts) > 1:
            return ":".join(parts[:-1])
        return None
    
    def _extract_and_store_procedural_knowledge(
        self,
        namespace: str,
        context: str,
    ) -> int:
        """
        Usa LLM para extrair conhecimento procedural genérico.
        
        Este é o coração da geração de memória coletiva:
        1. LLM analisa memórias e extrai padrões de resolução
        2. Remove PII/PCI automaticamente
        3. Valida se o conhecimento é genérico o suficiente
        4. Salva como LEARNED no namespace pai
        
        Args:
            namespace: Namespace atual do usuário
            context: Contexto de memórias para analisar
            
        Returns:
            Número de conhecimentos procedurais extraídos e salvos
        """
        stored_count = 0
        
        try:
            # 1. Envia para LLM extrair conhecimento procedural
            prompt = self.PROCEDURAL_EXTRACTION_PROMPT.format(context=context)
            
            llm_resp = requests.post(
                f"{self.llm_url}/api/chat",
                json={
                    "model": self.llm_model,
                    "messages": [
                        {
                            "role": "system", 
                            "content": "Você extrai conhecimento procedural útil. "
                                       "Responda apenas em YAML. "
                                       "NUNCA inclua dados pessoais (nomes, emails, etc)."
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                },
                timeout=120,
            )
            
            llm_content = llm_resp.json().get("message", {}).get("content", "")
            
            # 2. Parseia resposta YAML
            yaml_match = re.search(r'```yaml\s*\n(.+?)```', llm_content, re.DOTALL)
            if not yaml_match:
                return 0
            
            yaml_content = yaml_match.group(1)
            
            # Verifica se há conhecimentos válidos
            quant_match = re.search(r'quantidade_validos:\s*(\d+)', yaml_content)
            if not quant_match or int(quant_match.group(1)) == 0:
                return 0
            
            # 3. Extrai conhecimentos procedurais
            # Padrão para capturar cada bloco de conhecimento
            conhecimentos = re.findall(
                r'- problema:\s*"([^"]+)"\s*\n\s*solucao:\s*"([^"]+)"\s*\n\s*aplicabilidade:\s*"?(alta|media)"?',
                yaml_content,
                re.MULTILINE
            )
            
            if not conhecimentos:
                return 0
            
            # 4. Determina namespace pai para salvar conhecimento coletivo
            parent_namespace = self._get_parent_namespace(namespace)
            target_namespace = parent_namespace or namespace
            
            # 5. Salva cada conhecimento procedural como LEARNED
            for problema, solucao, aplicabilidade in conhecimentos:
                # Normaliza com spaCy
                problema_norm = self._normalizer.extract_core(problema)
                solucao_norm = self._normalizer.extract_core(solucao)
                
                # Salva como memória LEARNED no namespace pai
                store_resp = self._session.post(
                    f"{self.cortex_url}/memory/remember",
                    json={
                        "who": ["sistema"],  # Anônimo - conhecimento coletivo
                        "what": problema_norm,
                        "why": "procedural_knowledge",
                        "how": solucao_norm,
                        "where": target_namespace,
                        "importance": 0.85 if aplicabilidade == "alta" else 0.7,
                        "visibility": "learned",  # LEARNED = compartilhável e anônimo
                        "owner_id": "system",
                    },
                )
                
                if store_resp.status_code == 200:
                    data = store_resp.json()
                    if data.get("success"):
                        stored_count += 1
            
        except Exception as e:
            # Log error but don't fail the main dream process
            pass
        
        return stored_count
    
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
    
    # ==================== MEMÓRIA COLETIVA (NOVA ABORDAGEM) ====================
    
    def promote_collective_knowledge(
        self,
        tenant: str,
        data_path: Path | str | None = None,
        dry_run: bool = False,
    ) -> dict:
        """
        Promove memória coletiva baseada em CONTAGEM de padrões repetidos.
        
        NOVA ABORDAGEM: Não depende de "intuição da IA".
        Conhecimento coletivo = padrões que se repetem em 3+ usuários diferentes.
        
        Fluxo:
        1. Escaneia todos os namespaces do tenant
        2. Coleta candidatos (memórias com alto acesso, conexões, procedimentos)
        3. Agrupa por padrão similar (hash de what+outcome normalizado)
        4. Promove para LEARNED se 3+ usuários têm o mesmo padrão
        
        Args:
            tenant: Identificador do tenant (ex: "minha_empresa")
            data_path: Diretório base dos dados (default: ./data)
            dry_run: Se True, não salva (apenas mostra o que faria)
            
        Returns:
            Resultado da operação com detalhes de promoção
        """
        # Define path dos dados
        if data_path is None:
            data_path = Path(os.getenv("CORTEX_DATA_DIR", "./data"))
        else:
            data_path = Path(data_path)
        
        # Usa o collector para encontrar candidatos
        collector = CollectiveMemoryCollector(
            base_path=data_path,
            promotion_threshold=3,  # Mínimo 3 usuários
        )
        
        # Encontra padrões que devem ser promovidos
        to_promote = collector.get_promotion_candidates(tenant)
        
        result = {
            "tenant": tenant,
            "candidates_analyzed": len(collector._candidates.get(tenant, [])),
            "patterns_found": len(collector._clusters),
            "patterns_to_promote": len(to_promote),
            "promoted": [],
            "dry_run": dry_run,
        }
        
        if dry_run:
            result["would_promote"] = [
                {
                    "pattern": c.what,
                    "outcome": c.outcome[:50] + "..." if len(c.outcome) > 50 else c.outcome,
                    "users": c.user_count,
                    "is_procedure": c.is_procedure,
                }
                for c in to_promote
            ]
            return result
        
        # Determina namespace de destino (raiz do tenant)
        target_namespace = tenant
        
        # Promove cada cluster
        for cluster in to_promote:
            payload = collector.generate_learned_memory(cluster, target_namespace)
            
            try:
                resp = self._session.post(
                    f"{self.cortex_url}/memory/remember",
                    json=payload,
                    headers={"X-Cortex-Namespace": target_namespace},
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        result["promoted"].append({
                            "pattern": cluster.what,
                            "memory_id": data.get("memory_id"),
                            "users": cluster.user_count,
                            "is_procedure": cluster.is_procedure,
                        })
            except Exception as e:
                if "errors" not in result:
                    result["errors"] = []
                result["errors"].append(str(e))
        
        return result
    
    def scan_tenant_for_collective(
        self,
        tenant: str,
        data_path: Path | str | None = None,
    ) -> dict:
        """
        Escaneia um tenant e retorna candidatos a memória coletiva.
        
        Útil para debug e relatórios.
        
        Returns:
            Dict com candidatos, clusters e padrões comuns
        """
        if data_path is None:
            data_path = Path(os.getenv("CORTEX_DATA_DIR", "./data"))
        else:
            data_path = Path(data_path)
        
        collector = CollectiveMemoryCollector(base_path=data_path)
        
        candidates = collector.collect_candidates_from_tenant(tenant)
        clusters = collector.cluster_by_pattern(candidates)
        
        return {
            "tenant": tenant,
            "total_candidates": len(candidates),
            "total_clusters": len(clusters),
            "candidates_summary": [
                {
                    "namespace": c.namespace,
                    "pattern": c.what_normalized[:30],
                    "score": round(c.candidate_score, 2),
                    "is_procedure": c.is_procedure,
                }
                for c in candidates[:20]  # Top 20
            ],
            "clusters_summary": [
                {
                    "pattern": c.what[:30],
                    "users": c.user_count,
                    "should_promote": c.should_promote,
                    "is_procedure": c.is_procedure,
                }
                for c in sorted(clusters.values(), key=lambda x: x.user_count, reverse=True)[:10]
            ],
        }
