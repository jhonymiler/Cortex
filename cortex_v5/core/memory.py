"""
Memory — W5H (Who/What/Why/When/Where/How) memory unit.

Internationalized: the SCHEMA is universal; the VALUES can be in any
natural language. Detection of language is done at the query level
(by Extractor), not stored with the memory.

Complies with 5-element detector:
  E1. Discrete alphabet (entity, memory, relation types)
  E2. Syntax (W5H enforced via __post_init__)
  E3. Separable mapping with external referent (who points to real entities)
  E4. Independent interpreter (Extractor handles this, not Memory)
  E5. Functional semantics (semantic-functional fields, role differentiation)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4


# W5H required fields (the 'what' is the content; rest are optional but recommended)
_REQUIRED_FIELDS = ("what",)


@dataclass
class Memory:
    """
    A single memory unit, structured as W5H.

    The schema is fixed (W5H) but the VALUES can be in any language.
    A `what` of "liked pizza" (EN) and "gostou de pizza" (PT) are
    structurally equivalent; the meaning comparison (if needed) is the
    Extractor's job, not Memory's.

    Attributes:
        who: list of participants (entity IDs, names, or both)
        what: the action/fact (REQUIRED — this is the content)
        why: cause/motivation
        when: timestamp of the event
        where: namespace or spatial context
        how: outcome or method
        importance: 0.0-1.0, base importance
        access_count: how many times this memory was accessed
        last_accessed: timestamp of last access
        created_at: timestamp of creation
    """

    # W5H fields
    who: list[str] = field(default_factory=list)
    what: str = ""
    why: str = ""
    when: datetime = field(default_factory=datetime.now)
    where: str = "default"
    how: str = ""

    # Identifiers and metadata
    id: str = field(default_factory=lambda: str(uuid4()))
    importance: float = 0.5
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    # Custom metadata (extensible per use case)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Language tag (informational; the schema is universal but values
    # are in a specific language. Used for tokenization hints and
    # cross-language debug, NOT for retrieval decisions.)
    lang: str | None = None

    def __post_init__(self) -> None:
        """Enforce minimal schema (E2 — syntax)."""
        # Strip whitespace and validate required fields
        self.what = (self.what or "").strip()
        if not self.what:
            raise ValueError(
                "Memory 'what' field is required and cannot be empty "
                "(this is the content of the memory)"
            )

        # Normalize who to list of stripped strings
        if self.who:
            self.who = [str(w).strip() for w in self.who if w and str(w).strip()]

        # Default where
        if not self.where:
            self.where = "default"

        # Validate importance range
        if not 0.0 <= self.importance <= 1.0:
            raise ValueError(f"importance must be in [0.0, 1.0], got {self.importance}")

    # === Core operations ===

    def touch(self) -> None:
        """Mark memory as accessed. Increments counter and updates timestamp."""
        self.access_count += 1
        self.last_accessed = datetime.now()

    def is_about(self, who: str) -> bool:
        """Check if memory is about a given entity (case-insensitive)."""
        who_lower = who.lower()
        return any(w.lower() == who_lower or who_lower in w.lower() for w in self.who)

    def matches_text(self, text: str) -> float:
        """
        Score how well memory matches a text (0.0-1.0).

        Uses token Jaccard on what + why + how. Language-agnostic.
        For semantic跨语 matching, use embedding-based extractor.
        """
        if not text or not text.strip():
            return 0.0
        text_tokens = _tokenize(text)
        if not text_tokens:
            return 0.0
        mem_tokens = _tokenize(self.what) | _tokenize(self.why) | _tokenize(self.how)
        if not mem_tokens:
            return 0.0
        return len(text_tokens & mem_tokens) / len(text_tokens | mem_tokens)

    # === Serialization ===

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "who": self.who,
            "what": self.what,
            "why": self.why,
            "when": self.when.isoformat(),
            "where": self.where,
            "how": self.how,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Memory":
        return cls(
            id=data.get("id", str(uuid4())),
            who=data.get("who", []),
            what=data.get("what", ""),
            why=data.get("why", ""),
            when=datetime.fromisoformat(data["when"]) if data.get("when") else datetime.now(),
            where=data.get("where", "default"),
            how=data.get("how", ""),
            importance=data.get("importance", 0.5),
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            metadata=data.get("metadata", {}),
            lang=data.get("lang"),
        )

    @classmethod
    def from_text(
        cls,
        text: str,
        similar_to: Optional["Memory"] = None,
        importance: float = 0.5,
    ) -> "Memory":
        """
        Create a Memory from free text, optionally inheriting structure from
        a similar existing memory.

        This is the FLEXIBLE ENTRY POINT for noisy/short/informal input
        (typos, abbreviations, slang, mixed-language). Schema validation
        in __post_init__ still enforces non-empty `what`.

        Args:
            text: the content (becomes `what`)
            similar_to: optional reference memory; its `where`, `lang`, and
                       scaled `importance` are inherited
            importance: explicit importance if similar_to is None

        Returns:
            Memory with at minimum {what: text}, optionally with inherited structure
        """
        if similar_to is not None:
            return cls(
                what=text.strip(),
                where=similar_to.where,
                how=similar_to.how,  # inherit "how" as default context
                importance=similar_to.importance * 0.8,  # slight decay
                lang=similar_to.lang,
            )
        return cls(what=text.strip(), importance=importance)

    def __repr__(self) -> str:
        who_str = ",".join(self.who[:2]) if self.who else "?"
        what_short = self.what[:40] + "..." if len(self.what) > 40 else self.what
        return f"Memory(who=[{who_str}], what={what_short!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Memory):
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


# === Module-level helpers ===

_STOPWORDS_PT = {"o", "a", "os", "as", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
                 "é", "foi", "são", "e", "ou", "que", "para", "por", "com", "sem", "um", "uma"}
_STOPWORDS_EN = {"the", "a", "an", "of", "in", "on", "at", "is", "was", "were", "are", "and", "or", "that", "for", "by", "with", "to"}
_STOPWORDS = _STOPWORDS_PT | _STOPWORDS_EN


def _tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase words, removing stopwords and short tokens."""
    if not text:
        return set()
    # Split on non-alphanumeric
    raw_tokens = re.findall(r"\w+", text.lower())
    # Filter: length > 2, not stopword
    return {t for t in raw_tokens if len(t) > 2 and t not in _STOPWORDS}
