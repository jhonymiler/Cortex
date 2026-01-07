"""
Contracts - Contratos do SDK CortexMemory.

Estes são os formatos aceitos pelo SDK.
O SDK prepara os dados localmente antes de enviar ao serviço.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class Action:
    """
    Ação estruturada - entrada válida para memória.
    
    Attributes:
        verb: Ação realizada (obrigatório)
        subject: Quem realizou (opcional)
        object: O que foi afetado (opcional)
        modifiers: Contexto adicional (opcional)
    """
    verb: str
    subject: str = ""
    object: str = ""
    modifiers: tuple[str, ...] = field(default_factory=tuple)
    
    def __post_init__(self):
        if not self.verb:
            raise ValueError("Action.verb é obrigatório")
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "verb": self.verb,
            "subject": self.subject,
            "object": self.object,
            "modifiers": list(self.modifiers),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Action":
        return cls(
            verb=data["verb"],
            subject=data.get("subject", ""),
            object=data.get("object", ""),
            modifiers=tuple(data.get("modifiers", [])),
        )


@dataclass
class W5H:
    """
    Memória normalizada - formato W5H.
    
    Campos:
        who   ← subject
        what  ← verb + "_" + object
        when  ← timestamp
        where ← namespace
        how   ← modifiers
        why   ← somente se explícito
    """
    who: str = ""
    what: str = ""
    when: str = ""
    where: str = ""
    how: str = ""
    why: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "who": self.who,
            "what": self.what,
            "when": self.when,
            "where": self.where,
            "how": self.how,
            "why": self.why,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "W5H":
        return cls(
            who=data.get("who", ""),
            what=data.get("what", ""),
            when=data.get("when", ""),
            where=data.get("where", ""),
            how=data.get("how", ""),
            why=data.get("why", ""),
        )


@dataclass
class RecallResult:
    """Resultado de uma busca de memória."""
    memories: list[W5H] = field(default_factory=list)
    context_summary: str = ""
    
    def to_prompt_context(self) -> str:
        """Gera contexto para injeção em prompt."""
        if not self.memories:
            return ""
        
        lines = []
        for w5h in self.memories[:3]:
            parts = []
            if w5h.who:
                parts.append(f"who:{w5h.who}")
            if w5h.what:
                parts.append(f"what:{w5h.what}")
            if w5h.how:
                parts.append(f"how:{w5h.how}")
            if parts:
                lines.append(" ".join(parts))
        
        return "\n".join(lines)
    
    def __len__(self) -> int:
        return len(self.memories)
    
    def __bool__(self) -> bool:
        return len(self.memories) > 0

