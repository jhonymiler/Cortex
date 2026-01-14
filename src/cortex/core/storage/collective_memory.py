"""
Coleta e Promoção de Memória Coletiva (LEARNED).

Este módulo implementa a lógica para identificar memórias pessoais que
devem ser promovidas para conhecimento coletivo.

Princípio: Conhecimento coletivo NÃO é o que a IA "acha" que é útil.
           Conhecimento coletivo É padrões que se repetem entre usuários diferentes.

Tipos de Conhecimento Coletivo:
1. Dúvidas Comuns: N usuários → mesma dúvida → mesma resolução
2. Procedimentos: N usuários → passos similares → mesma resolução

Arquitetura em Duas Etapas:
1. Seleção de Candidatos: Top N por (acesso + conexões + procedimentos)
2. Análise de Promoção: Verificar se padrão repete em 3+ usuários do tenant
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TYPE_CHECKING
from pathlib import Path
import hashlib
import re

if TYPE_CHECKING:
    from cortex.core.graph import MemoryGraph
    from cortex.core.primitives import Episode


@dataclass
class CandidateMemory:
    """Memória candidata à promoção para LEARNED."""
    
    episode_id: str
    namespace: str  # Namespace de origem (ex: tenant:domain:user)
    tenant: str     # Tenant extraído (ex: tenant)
    
    # Métricas de seleção
    access_count: int = 0
    occurrence_count: int = 0
    connection_count: int = 0  # Quantas relações/participantes
    importance: float = 0.5
    
    # Classificação
    is_procedure: bool = False
    procedure_steps: list[str] = field(default_factory=list)
    
    # Conteúdo normalizado para comparação
    pattern_hash: str = ""  # Hash do padrão (what + outcome normalizado)
    what_normalized: str = ""
    outcome_normalized: str = ""
    
    # Score calculado
    candidate_score: float = 0.0
    
    def calculate_score(self) -> float:
        """
        Calcula score de candidatura para promoção.
        
        Score = (access_count * 0.3) + (occurrence_count * 0.3) + 
                (connection_count * 0.2) + (importance * 0.2) +
                (is_procedure * 0.5)  # Bonus para procedimentos
        """
        score = 0.0
        
        # Normaliza access_count (0-10 → 0-1)
        score += min(self.access_count / 10, 1.0) * 0.3
        
        # Normaliza occurrence_count (1-5 → 0-1)
        score += min(self.occurrence_count / 5, 1.0) * 0.3
        
        # Normaliza connection_count (0-10 → 0-1)
        score += min(self.connection_count / 10, 1.0) * 0.2
        
        # Importance já é 0-1
        score += self.importance * 0.2
        
        # Bonus para procedimentos
        if self.is_procedure:
            score += 0.5
        
        self.candidate_score = score
        return score


@dataclass
class PatternCluster:
    """Agrupamento de padrões similares entre usuários."""
    
    pattern_hash: str
    tenant: str
    
    # Usuários que têm este padrão
    user_namespaces: set[str] = field(default_factory=set)
    episode_ids: list[str] = field(default_factory=list)
    
    # Conteúdo representativo
    what: str = ""
    outcome: str = ""
    is_procedure: bool = False
    procedure_steps: list[str] = field(default_factory=list)
    
    @property
    def user_count(self) -> int:
        return len(self.user_namespaces)
    
    @property
    def should_promote(self) -> bool:
        """Retorna True se deve ser promovido para LEARNED."""
        return self.user_count >= 3  # Threshold configurável


class CollectiveMemoryCollector:
    """
    Coleta e identifica memórias para promoção a LEARNED.
    
    Fluxo:
    1. Escaneia namespaces de um tenant
    2. Seleciona candidatos (alto acesso + conexões + procedimentos)
    3. Agrupa por padrão similar
    4. Identifica padrões com 3+ usuários → candidatos a LEARNED
    """
    
    def __init__(
        self,
        base_path: Path | str,
        promotion_threshold: int = 3,
    ):
        """
        Args:
            base_path: Diretório base onde ficam os dados dos namespaces
            promotion_threshold: Mínimo de usuários para promover (default: 3)
        """
        self.base_path = Path(base_path) if isinstance(base_path, str) else base_path
        self.promotion_threshold = promotion_threshold
        
        # Cache de candidatos por tenant
        self._candidates: dict[str, list[CandidateMemory]] = {}
        
        # Clusters de padrões
        self._clusters: dict[str, PatternCluster] = {}
    
    def _extract_tenant(self, namespace: str) -> str:
        """
        Extrai o tenant do namespace.
        
        Ex: "minha_empresa:customer_support:user_123" → "minha_empresa"
        """
        parts = namespace.split(":")
        return parts[0] if parts else namespace
    
    def _normalize_text(self, text: str) -> str:
        """Normaliza texto para comparação de padrões."""
        if not text:
            return ""
        
        # Lowercase
        text = text.lower()
        
        # Remove pontuação
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Remove múltiplos espaços
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove stopwords comuns
        stopwords = {'o', 'a', 'os', 'as', 'um', 'uma', 'de', 'da', 'do', 'para', 
                     'com', 'em', 'que', 'e', 'é', 'foi', 'ser', 'está', 'são'}
        words = [w for w in text.split() if w not in stopwords]
        
        return ' '.join(words)
    
    def _generate_pattern_hash(self, what: str, outcome: str) -> str:
        """Gera hash único para um padrão (what + outcome normalizados)."""
        what_norm = self._normalize_text(what)
        outcome_norm = self._normalize_text(outcome)
        
        combined = f"{what_norm}|{outcome_norm}"
        return hashlib.md5(combined.encode()).hexdigest()[:12]
    
    def _detect_procedure(self, episode: "Episode") -> tuple[bool, list[str]]:
        """
        Detecta se o episódio representa um procedimento.
        
        Indicadores:
        - Outcome contém lista numerada (1. 2. 3.)
        - Outcome contém "→" ou "então" ou "depois"
        - Outcome contém verbos de ação em sequência
        
        Returns:
            (is_procedure, steps)
        """
        outcome = episode.outcome or ""
        
        # Padrão 1: Lista numerada
        numbered_pattern = re.findall(r'(\d+[.)]\s*[^0-9]+)', outcome)
        if len(numbered_pattern) >= 2:
            return True, [step.strip() for step in numbered_pattern]
        
        # Padrão 2: Sequência com →
        if '→' in outcome or ' -> ' in outcome:
            steps = re.split(r'\s*[→\->]\s*', outcome)
            if len(steps) >= 2:
                return True, [step.strip() for step in steps if step.strip()]
        
        # Padrão 3: Sequência com "então", "depois", "em seguida"
        sequence_words = ['então', 'depois', 'em seguida', 'por fim', 'finalmente']
        for word in sequence_words:
            if word in outcome.lower():
                # Divide por palavras de sequência
                steps = re.split(r'\s*(?:então|depois|em seguida|por fim|finalmente)\s*', 
                                outcome, flags=re.IGNORECASE)
                if len(steps) >= 2:
                    return True, [step.strip() for step in steps if step.strip()]
        
        return False, []
    
    def collect_candidates_from_namespace(
        self,
        namespace: str,
        graph: "MemoryGraph",
        limit: int = 50,
    ) -> list[CandidateMemory]:
        """
        Coleta candidatos de um namespace específico.
        
        Args:
            namespace: Namespace a escanear
            graph: MemoryGraph carregado
            limit: Máximo de candidatos
            
        Returns:
            Lista de CandidateMemory ordenada por score
        """
        tenant = self._extract_tenant(namespace)
        candidates = []
        
        # Pega todos os episódios
        for episode_id, episode in graph._episodes.items():
            # Ignora episódios já esquecidos ou de baixa importância
            if episode.metadata.get("forgotten"):
                continue
            
            if episode.importance < 0.3:
                continue
            
            # Calcula conexões (participantes + relações relacionadas)
            connection_count = len(episode.participants)
            for rel in graph._relations.values():
                if episode_id in [rel.from_id, rel.to_id]:
                    connection_count += 1
            
            # Detecta se é procedimento
            is_procedure, procedure_steps = self._detect_procedure(episode)
            
            # Normaliza e gera hash
            what_norm = self._normalize_text(episode.action)
            outcome_norm = self._normalize_text(episode.outcome)
            pattern_hash = self._generate_pattern_hash(episode.action, episode.outcome)
            
            candidate = CandidateMemory(
                episode_id=episode_id,
                namespace=namespace,
                tenant=tenant,
                access_count=episode.metadata.get("access_count", 0),
                occurrence_count=episode.occurrence_count,
                connection_count=connection_count,
                importance=episode.importance,
                is_procedure=is_procedure,
                procedure_steps=procedure_steps,
                pattern_hash=pattern_hash,
                what_normalized=what_norm,
                outcome_normalized=outcome_norm,
            )
            
            candidate.calculate_score()
            candidates.append(candidate)
        
        # Ordena por score descendente
        candidates.sort(key=lambda c: c.candidate_score, reverse=True)
        
        return candidates[:limit]
    
    def collect_candidates_from_tenant(
        self,
        tenant: str,
        limit_per_namespace: int = 20,
    ) -> list[CandidateMemory]:
        """
        Coleta candidatos de todos os namespaces de um tenant.
        
        Args:
            tenant: Identificador do tenant
            limit_per_namespace: Máximo por namespace
            
        Returns:
            Lista consolidada de candidatos
        """
        from cortex.core.graph import MemoryGraph
        
        all_candidates = []
        
        # Encontra todos os diretórios do tenant
        tenant_prefix = tenant.replace(":", "__")
        
        for ns_dir in self.base_path.iterdir():
            if not ns_dir.is_dir():
                continue
            
            dir_name = ns_dir.name
            
            # Verifica se pertence ao tenant
            if not dir_name.startswith(tenant_prefix):
                continue
            
            # Reconstrói namespace do nome do diretório
            namespace = dir_name.replace("__", ":")
            
            # Carrega o grafo
            try:
                graph = MemoryGraph(storage_path=ns_dir)
                candidates = self.collect_candidates_from_namespace(
                    namespace=namespace,
                    graph=graph,
                    limit=limit_per_namespace,
                )
                all_candidates.extend(candidates)
            except Exception:
                continue
        
        # Cache
        self._candidates[tenant] = all_candidates
        
        return all_candidates
    
    def cluster_by_pattern(
        self,
        candidates: list[CandidateMemory],
    ) -> dict[str, PatternCluster]:
        """
        Agrupa candidatos por padrão similar.
        
        Candidatos com mesmo pattern_hash são agrupados.
        Se 3+ usuários têm o mesmo padrão → candidato a LEARNED.
        
        Returns:
            Dict de pattern_hash → PatternCluster
        """
        clusters: dict[str, PatternCluster] = {}
        
        for candidate in candidates:
            ph = candidate.pattern_hash
            
            if ph not in clusters:
                clusters[ph] = PatternCluster(
                    pattern_hash=ph,
                    tenant=candidate.tenant,
                    what=candidate.what_normalized,
                    outcome=candidate.outcome_normalized,
                    is_procedure=candidate.is_procedure,
                    procedure_steps=candidate.procedure_steps,
                )
            
            cluster = clusters[ph]
            cluster.user_namespaces.add(candidate.namespace)
            cluster.episode_ids.append(candidate.episode_id)
            
            # Atualiza se for procedimento
            if candidate.is_procedure and not cluster.is_procedure:
                cluster.is_procedure = True
                cluster.procedure_steps = candidate.procedure_steps
        
        self._clusters = clusters
        return clusters
    
    def get_promotion_candidates(
        self,
        tenant: str,
    ) -> list[PatternCluster]:
        """
        Retorna clusters que devem ser promovidos para LEARNED.
        
        Um cluster é promovido se:
        - Tem 3+ usuários diferentes com o mesmo padrão
        
        Returns:
            Lista de PatternCluster que devem ser promovidos
        """
        # Coleta candidatos se ainda não fez
        if tenant not in self._candidates:
            self.collect_candidates_from_tenant(tenant)
        
        candidates = self._candidates.get(tenant, [])
        
        # Agrupa por padrão
        clusters = self.cluster_by_pattern(candidates)
        
        # Filtra os que devem ser promovidos
        to_promote = [
            cluster for cluster in clusters.values()
            if cluster.user_count >= self.promotion_threshold
        ]
        
        # Ordena por número de usuários (mais comum primeiro)
        to_promote.sort(key=lambda c: c.user_count, reverse=True)
        
        return to_promote
    
    def generate_learned_memory(
        self,
        cluster: PatternCluster,
        target_namespace: str,
    ) -> dict[str, Any]:
        """
        Gera o payload para criar uma memória LEARNED.
        
        Args:
            cluster: Cluster a promover
            target_namespace: Namespace pai onde salvar (ex: "tenant:domain")
            
        Returns:
            Dict no formato do RememberRequest
        """
        # Gera descrição do padrão
        what = cluster.what if cluster.what else "padrão_comum"
        how = cluster.outcome if cluster.outcome else "resolução_padrão"
        
        # Se é procedimento, formata os passos
        if cluster.is_procedure and cluster.procedure_steps:
            how = " → ".join(cluster.procedure_steps)
        
        return {
            "who": ["sistema"],  # Anônimo
            "what": what,
            "why": "collective_pattern",
            "how": how,
            "where": target_namespace,
            "importance": 0.8,
            "visibility": "learned",
            "owner_id": "system",
            "metadata": {
                "pattern_hash": cluster.pattern_hash,
                "user_count": cluster.user_count,
                "is_procedure": cluster.is_procedure,
                "source_episodes": cluster.episode_ids[:10],  # Limita para não explodir
            },
        }


# ==================== FUNÇÕES UTILITÁRIAS ====================


def scan_and_promote(
    base_path: Path | str,
    tenant: str,
    cortex_url: str = "http://localhost:8000",
    dry_run: bool = True,
) -> dict[str, Any]:
    """
    Escaneia um tenant e promove padrões comuns para LEARNED.
    
    Args:
        base_path: Diretório base dos dados
        tenant: Tenant a escanear
        cortex_url: URL da API Cortex
        dry_run: Se True, não salva (apenas mostra o que faria)
        
    Returns:
        Resultado da operação
    """
    import requests
    
    collector = CollectiveMemoryCollector(base_path=base_path)
    
    # Encontra candidatos à promoção
    to_promote = collector.get_promotion_candidates(tenant)
    
    result = {
        "tenant": tenant,
        "candidates_found": len(collector._candidates.get(tenant, [])),
        "clusters_found": len(collector._clusters),
        "to_promote": len(to_promote),
        "promoted": [],
        "dry_run": dry_run,
    }
    
    if dry_run:
        result["would_promote"] = [
            {
                "pattern": c.what,
                "outcome": c.outcome,
                "users": c.user_count,
                "is_procedure": c.is_procedure,
            }
            for c in to_promote
        ]
        return result
    
    # Promove cada cluster
    target_namespace = tenant  # Salva no namespace raiz do tenant
    
    for cluster in to_promote:
        payload = collector.generate_learned_memory(cluster, target_namespace)
        
        try:
            resp = requests.post(
                f"{cortex_url}/memory/remember",
                json=payload,
                headers={"X-Cortex-Namespace": target_namespace},
            )
            
            if resp.status_code == 200:
                data = resp.json()
                result["promoted"].append({
                    "pattern": cluster.what,
                    "memory_id": data.get("memory_id"),
                    "users": cluster.user_count,
                })
        except Exception as e:
            result["errors"] = result.get("errors", [])
            result["errors"].append(str(e))
    
    return result

