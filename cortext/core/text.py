"""
Text normalization shared by the index, recall, validation and decay.

One tokenizer for the whole system, so a token the index stores is exactly the
token a query looks up. Tokens are lowercased and accent-folded ("não" and
"nao" are the same token), split on non-word characters, and filtered of
stopwords and tokens of 2 characters or fewer.

``tokenize`` is memoized: the same strings (who names, places, repeated
phrases) are tokenized over and over on the hot path.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

_WORD = re.compile(r"\w+")

_STOPWORDS_RAW = {
    # pt
    "o", "a", "os", "as", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "é", "foi", "são", "e", "ou", "que", "para", "por", "com", "sem", "um", "uma",
    "uns", "umas", "ao", "aos", "pelo", "pela", "pelos", "pelas", "se", "seu", "sua",
    "isso", "isto", "este", "esta", "esse", "essa", "qual", "quais", "como", "mais",
    # en
    "the", "an", "of", "in", "on", "at", "is", "was", "were", "are", "and", "or",
    "that", "for", "by", "with", "to", "this", "these", "those", "it", "its", "be",
    "been", "has", "have", "had", "did", "does", "what", "who", "how",
    # es
    "el", "la", "los", "las", "del", "al", "un", "una", "y", "con", "es", "fue", "son",
}


def fold(text: str) -> str:
    """Lowercase and strip diacritics ("Ação" -> "acao")."""
    if not text:
        return ""
    if text.isascii():
        return text.lower()
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


STOPWORDS = frozenset(fold(w) for w in _STOPWORDS_RAW)


def stem(token: str) -> str:
    """Conservative plural folding (PT/EN/ES): "filas"->"fila", "migracoes"->"migracao".

    Only the plural ending is removed, and only on longer words, so distinct
    words don't collapse; "status", "analysis", "class" are left alone.
    """
    if len(token) > 4:
        if token.endswith("oes"):
            return token[:-3] + "ao"
        if token.endswith("s") and not token.endswith(("ss", "us", "is")):
            return token[:-1]
    return token


@lru_cache(maxsize=65536)
def tokenize(text: str) -> frozenset[str]:
    """Content tokens of ``text``: folded, plural-stemmed, length > 2, no stopwords."""
    if not text:
        return frozenset()
    return frozenset(
        stem(t) for t in _WORD.findall(fold(text)) if len(t) > 2 and t not in STOPWORDS
    )


def tokenize_all(*parts: str) -> frozenset[str]:
    """Union of ``tokenize`` over several fields."""
    out: set[str] = set()
    for p in parts:
        if p:
            out |= tokenize(p)
    return frozenset(out)
