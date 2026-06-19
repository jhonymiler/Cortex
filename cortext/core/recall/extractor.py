"""
Extractor interface — pluggable W5H extraction from natural-language queries.

The W5H schema is universal. The EXTRACTION of W5H values from text
is language-specific. Extractor abstracts this so we can:
  - Have fast regex extractors per language (PT, EN, ES)
  - Have a slow but universal LLM-based extractor (fallback)
  - Have a hybrid that tries regex first, falls back to LLM
"""

from __future__ import annotations

from typing import Protocol
from dataclasses import dataclass, field


@dataclass
class QueryIntent:
    """
    W5H skeleton extracted from a natural-language query.

    Schema is universal (Who/What/Why/When/Where/How). Values can be
    in any language. `lang` records which language was detected/used
    during extraction (informational, not enforced).

    Fields:
        who: list of participants mentioned
        what: action or claim
        why: cause or motivation
        when: temporal marker (text form)
        where: location marker
        how: method or result
        query_type: identity | action | location | temporal | causal | general | unknown
        confidence: 0.0-1.0, how confident the parser is
        raw_query: the original input (preserved)
        lang: detected or specified language code (pt, en, es, auto, etc)
    """

    who: list[str] = field(default_factory=list)
    what: str = ""
    why: str = ""
    when: str = ""
    where: str = ""
    how: str = ""
    query_type: str = "unknown"
    confidence: float = 0.0
    raw_query: str = ""
    lang: str = "auto"

    def is_structured(self) -> bool:
        """True if extractor found a structured pattern with non-trivial confidence."""
        return self.confidence >= 0.5 and (
            bool(self.who) or bool(self.what) or bool(self.where) or bool(self.when)
        )

    def to_dict(self) -> dict:
        return {
            "who": self.who,
            "what": self.what,
            "why": self.why,
            "when": self.when,
            "where": self.where,
            "how": self.how,
            "query_type": self.query_type,
            "confidence": self.confidence,
            "raw_query": self.raw_query,
            "lang": self.lang,
        }

    def __repr__(self) -> str:
        parts = []
        if self.who:
            parts.append(f"who={self.who}")
        if self.what:
            parts.append(f"what={self.what!r}")
        return f"QueryIntent(type={self.query_type}, lang={self.lang}, conf={self.confidence:.2f}, " + ", ".join(parts) + ")"


class Extractor(Protocol):
    """Interface for query extractors. Implementations extract W5H from text."""

    def extract(self, query: str, lang: str = "auto") -> QueryIntent:
        """
        Extract W5H intent from a query.

        Args:
            query: natural-language query
            lang: language hint (pt, en, es, auto=detect)

        Returns:
            QueryIntent with extracted W5H fields
        """
        ...

    @property
    def supported_langs(self) -> list[str]:
        """List of language codes this extractor supports."""
        ...


def detect_lang(text: str) -> str:
    """
    Detect language from text using common-word heuristics.

    Returns: "pt" | "en" | "es" | "unknown"
    """
    if not text or not text.strip():
        return "unknown"

    # Strip punctuation (¿, ¡, ?, !, ., ,) for word matching
    import re
    text_clean = re.sub(r"[¿¡!?.,;:]", " ", text.lower())
    words = set(text_clean.split())

    # Common words per language
    pt_signals = {"não", "que", "para", "com", "uma", "como", "foi", "são", "quem", "onde", "quando", "por"}
    en_signals = {"the", "what", "where", "when", "who", "why", "how", "is", "did", "are", "with", "for", "does"}
    es_signals = {"qué", "quién", "dónde", "cuándo", "cómo", "es", "fue", "con", "para", "pide", "pides", "hace", "vive", "sabe", "vive"}

    pt_count = len(words & pt_signals)
    en_count = len(words & en_signals)
    es_count = len(words & es_signals)

    if max(pt_count, en_count, es_count) == 0:
        return "unknown"
    if en_count > pt_count and en_count > es_count:
        return "en"
    if es_count > pt_count and es_count > en_count:
        return "es"
    if pt_count > 0:
        return "pt"
    return "unknown"
