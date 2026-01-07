"""
Memory - Unidade fundamental de memória W5H.

O modelo W5H substitui Episode com campos explícitos:
- WHO: Quem está envolvido
- WHAT: O que aconteceu
- WHY: Por quê (causa/motivação)
- WHEN: Quando (timestamp + contexto temporal)
- WHERE: Onde (namespace + contexto espacial)
- HOW: Como (resultado/método)

Baseado em:
- Curva de Esquecimento de Ebbinghaus (1885)
- CoALA: Cognitive Architectures for Language Agents
- Generative Agents (Stanford)
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class Memory:
    """
    Unidade fundamental de memória W5H.
    
    Cada memória responde às 5 perguntas fundamentais + How:
    - WHO: Quem participou
    - WHAT: O que aconteceu
    - WHY: Por que aconteceu
    - WHEN: Quando aconteceu
    - WHERE: Onde aconteceu (namespace/contexto)
    - HOW: Como foi resolvido/resultado
    
    Inclui suporte a:
    - Decaimento baseado em Ebbinghaus (retrievability)
    - Consolidação automática (occurrence_count)
    - Centralidade (calculada externamente)
    
    Attributes:
        id: Identificador único
        who: Lista de participantes (Entity IDs ou nomes inline)
        what: Descrição da ação/fato principal
        why: Causa/motivação (opcional)
        when: Timestamp do evento
        temporal_context: Contexto temporal ("durante a reunião")
        where: Namespace ou contexto espacial
        how: Resultado ou método utilizado
        importance: Importância base (0.0 - 1.0)
        stability: Multiplicador de retenção (aumenta com acesso)
        access_count: Quantas vezes foi acessada
        last_accessed: Último acesso
        occurrence_count: Quantas vezes padrão similar ocorreu
        consolidated_from: IDs de memórias consolidadas nesta
        metadata: Dados adicionais livres
        
    Examples:
        # Suporte técnico
        Memory(
            who=["maria@email.com", "sistema_pagamentos"],
            what="reportou erro de pagamento",
            why="cartão expirado",
            how="orientada a atualizar dados do cartão",
            where="suporte_cliente"
        )
        
        # Desenvolvimento
        Memory(
            who=["dev_joao", "api_vendas"],
            what="debugou timeout",
            why="conexão não fechada corretamente",
            how="adicionou connection pooling",
            where="projeto_ecommerce"
        )
        
        # Roleplay
        Memory(
            who=["elena", "marcus"],
            what="confessaram sentimentos",
            why="momento de vulnerabilidade após batalha",
            how="decidiram ficar juntos",
            where="campanha_vampiros"
        )
    """
    
    # WHO - Participantes
    who: list[str] = field(default_factory=list)
    
    # WHAT - Ação/Fato principal (obrigatório)
    what: str = ""
    
    # WHY - Causa/Motivação
    why: str = ""
    
    # WHEN - Temporal
    when: datetime = field(default_factory=datetime.now)
    temporal_context: str = ""  # "durante a reunião", "após o deploy"
    
    # WHERE - Namespace/Espacial
    where: str = "default"
    
    # HOW - Resultado/Método
    how: str = ""
    
    # Identificação
    id: str = field(default_factory=lambda: str(uuid4()))
    
    # Gerenciamento de memória
    importance: float = 0.5
    stability: float = 1.0  # Base stability para decaimento
    access_count: int = 0
    last_accessed: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)
    
    # Consolidação
    occurrence_count: int = 1
    consolidated_from: list[str] = field(default_factory=list)  # IDs consolidadas NESTA memória
    consolidated_into: str | None = None  # ID da memória pai (se foi consolidada)
    is_summary: bool = False  # True se for uma memória de consolidação/resumo
    
    # Metadados
    metadata: dict[str, Any] = field(default_factory=dict)
    
    # Cache de centralidade (atualizado externamente)
    _centrality_score: float = field(default=0.0, repr=False)
    
    # Constante de decaimento para memórias já consolidadas
    CONSOLIDATED_DECAY_MULTIPLIER: float = field(default=0.3, repr=False)
    
    @property
    def is_consolidated(self) -> bool:
        """Retorna True se esta memória é resultado de consolidação (memória pai/resumo)."""
        return len(self.consolidated_from) > 0 or self.is_summary
    
    @property
    def was_consolidated(self) -> bool:
        """Retorna True se esta memória FOI consolidada em outra (memória filha/granular)."""
        return self.consolidated_into is not None
    
    @property
    def decay_multiplier(self) -> float:
        """
        Multiplicador de decaimento para memórias já consolidadas.
        
        Memórias que foram consolidadas em um resumo decaem 3x mais rápido,
        pois seu conteúdo já está representado na memória pai.
        
        Returns:
            0.3 se foi consolidada (decai rápido)
            1.0 se ainda não foi consolidada (decai normal)
        """
        if self.was_consolidated:
            return self.CONSOLIDATED_DECAY_MULTIPLIER  # 0.3
        return 1.0
    
    @property
    def is_forgotten(self) -> bool:
        """Retorna True se a memória está marcada como esquecida."""
        return self.metadata.get("forgotten", False)
    
    @property
    def retrievability(self) -> float:
        """
        Calcula facilidade de recuperação baseada em decaimento.
        
        Baseado na curva de Ebbinghaus: R = e^(-t/S)
        
        Onde:
            R = retrievability (0.0 - 1.0)
            t = tempo desde último acesso (em dias)
            S = stability * modificadores
        
        Modificadores de stability:
            - access_count: mais acessos = mais estável
            - centrality: hubs são mais estáveis
            - is_consolidated (resumo): memórias resumo são mais estáveis
            - was_consolidated (granular): memórias granulares já consolidadas decaem RÁPIDO
        
        Returns:
            float entre 0.0 (esquecida) e 1.0 (fresca na memória)
        """
        reference_time = self.last_accessed or self.when
        days_since = (datetime.now() - reference_time).total_seconds() / 86400
        
        if days_since < 0:
            days_since = 0
        
        # Calcula stability efetiva
        # Base: stability * (1 + log(access_count + 1))
        access_modifier = 1 + math.log(self.access_count + 1)
        
        # Bonus para memórias RESUMO (consolidação pai)
        summary_modifier = 2.0 if self.is_consolidated else 1.0
        
        # PENALIDADE para memórias granulares JÁ consolidadas
        # Elas decaem 3x mais rápido (decay_multiplier = 0.3)
        granular_modifier = self.decay_multiplier
        
        # Bonus para hubs (centralidade)
        centrality_modifier = 1 + (self._centrality_score * 0.5)
        
        effective_stability = (
            self.stability 
            * access_modifier 
            * summary_modifier 
            * granular_modifier  # 0.3 se já consolidada
            * centrality_modifier
        )
        
        # Evita divisão por zero
        effective_stability = max(effective_stability, 0.1)
        
        # Fórmula de Ebbinghaus: R = e^(-t/S)
        return math.exp(-days_since / effective_stability)
    
    def touch(self) -> None:
        """
        Marca a memória como acessada.
        
        Efeitos:
        - Incrementa access_count
        - Atualiza last_accessed
        - Aumenta stability (spaced repetition)
        - Remove flag "forgotten" se existir
        """
        self.access_count += 1
        self.last_accessed = datetime.now()
        
        # Spaced repetition: cada acesso aumenta stability
        # Limite de 10.0 para evitar memórias "imortais"
        self.stability = min(10.0, self.stability * 1.2)
        
        # Se estava esquecida, revive
        if self.metadata.get("forgotten"):
            del self.metadata["forgotten"]
    
    def forget(self) -> None:
        """Marca a memória como esquecida."""
        self.metadata["forgotten"] = True
    
    def set_centrality(self, score: float) -> None:
        """Define o score de centralidade (calculado externamente)."""
        self._centrality_score = max(0.0, score)
    
    def similarity_to(self, other: "Memory") -> float:
        """
        Calcula similaridade com outra memória para consolidação.
        
        Considera:
        - WHO: participantes em comum
        - WHAT: ação similar
        - WHERE: mesmo namespace
        
        Returns:
            float entre 0.0 (diferentes) e 1.0 (idênticas)
        """
        score = 0.0
        
        # WHO: Jaccard similarity
        if self.who and other.who:
            who_set = set(self.who)
            other_who_set = set(other.who)
            intersection = len(who_set & other_who_set)
            union = len(who_set | other_who_set)
            if union > 0:
                score += 0.4 * (intersection / union)
        
        # WHAT: igualdade exata (pode melhorar com fuzzy matching)
        if self.what.lower().strip() == other.what.lower().strip():
            score += 0.4
        
        # WHERE: mesmo namespace
        if self.where == other.where:
            score += 0.2
        
        return score
    
    def to_summary(self) -> str:
        """Gera resumo legível da memória."""
        parts = []
        
        # WHO
        if self.who:
            participants = ", ".join(self.who[:3])
            if len(self.who) > 3:
                participants += f" +{len(self.who) - 3}"
            parts.append(participants)
        
        # WHAT
        parts.append(self.what)
        
        # HOW (se existir)
        if self.how:
            parts.append(f"→ {self.how}")
        
        # Consolidation marker
        if self.is_consolidated:
            parts.insert(0, f"[{self.occurrence_count}x]")
        
        return " ".join(parts)
    
    def to_w5h_dict(self) -> dict[str, Any]:
        """Retorna representação W5H da memória."""
        return {
            "who": self.who,
            "what": self.what,
            "why": self.why,
            "when": self.when.isoformat(),
            "where": self.where,
            "how": self.how,
        }
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa memória para persistência."""
        return {
            "id": self.id,
            "who": self.who,
            "what": self.what,
            "why": self.why,
            "when": self.when.isoformat(),
            "temporal_context": self.temporal_context,
            "where": self.where,
            "how": self.how,
            "importance": self.importance,
            "stability": self.stability,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "created_at": self.created_at.isoformat(),
            "occurrence_count": self.occurrence_count,
            "consolidated_from": self.consolidated_from,
            "consolidated_into": self.consolidated_into,
            "is_summary": self.is_summary,
            "metadata": self.metadata,
            "centrality_score": self._centrality_score,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Memory":
        """Deserializa memória de persistência."""
        memory = cls(
            id=data.get("id", str(uuid4())),
            who=data.get("who", []),
            what=data.get("what", ""),
            why=data.get("why", ""),
            when=datetime.fromisoformat(data["when"]) if data.get("when") else datetime.now(),
            temporal_context=data.get("temporal_context", ""),
            where=data.get("where", "default"),
            how=data.get("how", ""),
            importance=data.get("importance", 0.5),
            stability=data.get("stability", 1.0),
            access_count=data.get("access_count", 0),
            occurrence_count=data.get("occurrence_count", 1),
            consolidated_from=data.get("consolidated_from", []),
            consolidated_into=data.get("consolidated_into"),
            is_summary=data.get("is_summary", False),
            metadata=data.get("metadata", {}),
        )
        
        if data.get("last_accessed"):
            memory.last_accessed = datetime.fromisoformat(data["last_accessed"])
        
        if data.get("created_at"):
            memory.created_at = datetime.fromisoformat(data["created_at"])
        
        if data.get("centrality_score"):
            memory._centrality_score = data["centrality_score"]
        
        return memory


# Compatibilidade: Episode é alias para Memory (deprecated)
Episode = Memory
