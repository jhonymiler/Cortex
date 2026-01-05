"""
Entity - Representa qualquer "coisa" no sistema de memória.

Entidades são agnósticas de domínio:
- Dev: arquivos, erros, projetos
- Roleplay: personagens, lugares, objetos
- Chatbot: clientes, produtos, pedidos
- Assistente: pessoas, tarefas, eventos
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass
class Entity:
    """
    Uma entidade é qualquer "coisa" que pode ser mencionada e lembrada.
    
    Attributes:
        id: Identificador único (UUID)
        type: Tipo livre definido pelo cliente (person, file, character, product...)
        name: Nome legível para humanos
        identifiers: Lista de formas de reconhecer esta entidade
                    (email, hash, path, apelido, etc.)
        attributes: Metadados livres sobre a entidade
        created_at: Quando foi criada
        updated_at: Última atualização
        access_count: Quantas vezes foi acessada/mencionada
        last_accessed: Último acesso
    
    Examples:
        # Dev
        Entity(type="file", name="apache.log", identifiers=["sha256:abc", "/var/log/apache.log"])
        
        # Roleplay
        Entity(type="character", name="Elena", identifiers=["protagonist", "vampire_queen"])
        
        # Chatbot
        Entity(type="customer", name="Maria Silva", identifiers=["maria@email.com", "cust_123"])
    """
    
    type: str
    name: str
    identifiers: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: datetime | None = None
    
    def touch(self) -> None:
        """Marca a entidade como acessada."""
        self.access_count += 1
        self.last_accessed = datetime.now()
        self.updated_at = datetime.now()
    
    def add_identifier(self, identifier: str) -> None:
        """Adiciona um novo identificador se não existir."""
        if identifier not in self.identifiers:
            self.identifiers.append(identifier)
            self.updated_at = datetime.now()
    
    def matches(self, query: str) -> bool:
        """
        Verifica se a entidade corresponde a uma busca.
        
        Busca por:
        - ID exato
        - Nome (case-insensitive, parcial)
        - Qualquer identificador (case-insensitive, parcial)
        """
        query_lower = query.lower()
        
        # Match exato por ID
        if query == self.id:
            return True
        
        # Match por nome
        if query_lower in self.name.lower():
            return True
        
        # Match por identificadores
        for identifier in self.identifiers:
            if query_lower in identifier.lower():
                return True
        
        return False
    
    def similarity_score(self, query: str, context: dict[str, Any] | None = None) -> float:
        """
        Calcula um score de similaridade (0.0 - 1.0) entre a entidade e uma query.
        
        Considera:
        - Match exato: 1.0
        - Match por nome: 0.8
        - Match por identificador: 0.7
        - Match por atributos: 0.5
        - Contexto compatível: +0.2
        """
        score = 0.0
        query_lower = query.lower()
        
        # Match exato por ID ou nome
        if query == self.id or query_lower == self.name.lower():
            score = 1.0
        # Match parcial por nome
        elif query_lower in self.name.lower():
            score = 0.8
        # Match por identificador
        elif any(query_lower in ident.lower() for ident in self.identifiers):
            score = 0.7
        # Match por tipo
        elif query_lower == self.type.lower():
            score = 0.3
        
        # Bonus por contexto
        if context and score > 0:
            # Se o tipo da entidade está no contexto
            if context.get("entity_types") and self.type in context["entity_types"]:
                score = min(1.0, score + 0.1)
            # Se há entidades relacionadas no contexto
            if context.get("related_entities"):
                for related in context["related_entities"]:
                    if self.matches(related):
                        score = min(1.0, score + 0.1)
                        break
        
        return score
    
    def to_dict(self) -> dict[str, Any]:
        """Serializa para dicionário."""
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "identifiers": self.identifiers,
            "attributes": self.attributes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entity":
        """Deserializa de dicionário."""
        return cls(
            id=data["id"],
            type=data["type"],
            name=data["name"],
            identifiers=data.get("identifiers", []),
            attributes=data.get("attributes", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
        )
    
    def __repr__(self) -> str:
        return f"Entity(type={self.type!r}, name={self.name!r}, id={self.id[:8]}...)"
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        return hash(self.id)
