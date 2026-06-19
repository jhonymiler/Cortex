"""
Regex-based extractors for multiple languages.

Each language has its own set of patterns. The extractor is FAST
(no LLM, no embedding) but limited to recognizing structured questions.
"""

from __future__ import annotations

import re
from typing import Callable

from cortext.core.recall.extractor import Extractor, QueryIntent, detect_lang


def _extract_identity(match: re.Match, lang: str = "pt") -> QueryIntent:
    who_raw = match.group(1).strip() if match.lastindex and match.lastindex >= 1 else ""
    return QueryIntent(
        who=[who_raw] if who_raw else [],
        query_type="identity",
        confidence=0.9,
        lang=lang,
    )


def _extract_action(match: re.Match, lang: str = "pt") -> QueryIntent:
    who_raw = match.group(1).strip() if match.lastindex and match.lastindex >= 1 else ""
    what_raw = match.group(2).strip() if match.lastindex and match.lastindex >= 2 else ""
    return QueryIntent(
        who=[who_raw] if who_raw else [],
        what=what_raw,
        query_type="action",
        confidence=0.85,
        lang=lang,
    )


def _extract_location(match: re.Match, lang: str = "pt") -> QueryIntent:
    """Onde X mora/trabalha/...?"""
    # Pattern A: 2 groups (who, what) — preferred
    # Pattern B: 1 group (where) — fallback
    if match.lastindex and match.lastindex >= 2:
        who_raw = match.group(1).strip() if match.lastindex >= 1 else ""
        what_raw = match.group(2).strip() if match.lastindex >= 2 else ""
        return QueryIntent(
            who=[who_raw] if who_raw else [],
            what=what_raw,
            query_type="location",
            confidence=0.8,
            lang=lang,
        )
    else:
        # Single group: it's a "where is X" pattern
        where_raw = match.group(1).strip() if match.lastindex and match.lastindex >= 1 else ""
        return QueryIntent(
            where=where_raw,
            query_type="location",
            confidence=0.8,
            lang=lang,
        )


def _extract_temporal(match: re.Match, lang: str = "pt") -> QueryIntent:
    what_raw = match.group(1).strip() if match.lastindex and match.lastindex >= 1 else ""
    return QueryIntent(
        what=what_raw,
        query_type="temporal",
        confidence=0.8,
        lang=lang,
    )


def _extract_temporal_who(match: re.Match, lang: str = "pt") -> QueryIntent:
    who_raw = match.group(1).strip() if match.lastindex and match.lastindex >= 1 else ""
    what_raw = match.group(2).strip() if match.lastindex and match.lastindex >= 2 else ""
    return QueryIntent(
        who=[who_raw] if who_raw else [],
        what=what_raw,
        query_type="temporal",
        confidence=0.75,
        lang=lang,
    )


def _extract_causal(match: re.Match, lang: str = "pt") -> QueryIntent:
    who_raw = match.group(1).strip() if match.lastindex and match.lastindex >= 1 else ""
    what_raw = match.group(2).strip() if match.lastindex and match.lastindex >= 2 else ""
    return QueryIntent(
        who=[who_raw] if who_raw else [],
        what=what_raw,
        query_type="causal",
        confidence=0.75,
        lang=lang,
    )


def _extract_general(match: re.Match, lang: str = "pt") -> QueryIntent:
    who_raw = match.group(1).strip() if match.lastindex and match.lastindex >= 1 else ""
    return QueryIntent(
        who=[who_raw] if who_raw else [],
        query_type="general",
        confidence=0.6,
        lang=lang,
    )


# ============================================================================
# Portuguese patterns
# ============================================================================

_PATTERNS_PT: list[tuple[re.Pattern, Callable]] = [
    # IDENTITY: "quem é/são X?"
    (re.compile(r"quem\s+(?:é|são|foi|era)\s+(?:o|a|os|as)?\s*([\w\s\-]+?)\s*\??\s*$", re.IGNORECASE), _extract_identity),
    # ACTION: "o que X fez/faz/disse/...?"
    (re.compile(r"o\s+que\s+(?:o|a|os|as)?\s*([\w\-]+)\s+(fez|faz|disse|diz|pediu|pede|comprou|compra|vendeu|vende|gostou|gosta|reclamou|reclama|quis|quer|precisa|fez|fazia|disse|tinha|tem)\s*\??\s*$", re.IGNORECASE), _extract_action),
    (re.compile(r"o\s+que\s+(?:aconteceu|ocorreu|rolou)\s+com\s+(?:o|a|os|as)?\s*([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_action),
    # LOCATION: "onde X mora/trabalha/...?"
    (re.compile(r"onde\s+(?:o|a|os|as)?\s*([\w\-]+)\s+(mora|morou|morava|trabalha|trabalhou|trabalha|está|estava|fica|ficou|fica|vai|foi)\s*\??\s*$", re.IGNORECASE), _extract_location),
    (re.compile(r"onde\s+(?:é|fica|aconteceu|ocorreu)\s+(?:a|o|os|as)?\s*([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_location),
    # TEMPORAL: "quando aconteceu/foi/é X?" / "quando X fez Y?"
    (re.compile(r"quando\s+(?:foi|aconteceu|ocorreu|é|será|era)\s+(?:a|o|os|as)?\s*([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_temporal),
    (re.compile(r"quando\s+(?:o|a|os|as)?\s*([\w]+)\s+(fez|faz|disse|pediu|comprou|vendeu|gostou|reclamou)\s*(?:.*)$", re.IGNORECASE), _extract_temporal_who),
    # CAUSAL: "por que X?"
    (re.compile(r"por\s+que\s+(?:o|a|os|as)?\s*([\w\-]+)\s+([\w\-]+)\s*\??\s*$", re.IGNORECASE), _extract_causal),
    (re.compile(r"por\s+que\s+(?:aconteceu|ocorreu|reclamou|pediu|fez)", re.IGNORECASE), _extract_causal),
    # GENERAL: "o que você sabe sobre X?"
    (re.compile(r"o\s+que\s+(?:você|tu|vc)\s+(?:sabe|conhece)\s+sobre\s+(?:o|a|os|as)?\s*([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_general),
    (re.compile(r"fale\s+sobre\s+(?:o|a|os|as)?\s*([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_general),
    (re.compile(r"conte\s+sobre\s+(?:o|a|os|as)?\s*([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_general),
]


# ============================================================================
# English patterns
# ============================================================================

_PATTERNS_EN: list[tuple[re.Pattern, Callable]] = [
    # IDENTITY: "who is X?"
    (re.compile(r"who\s+is\s+(?:the\s+)?([\w\s\-]+?)\s*\??\s*$", re.IGNORECASE), _extract_identity),
    (re.compile(r"what\s+is\s+([\w\s\-]+?)\s*\??\s*$", re.IGNORECASE), _extract_identity),
    (re.compile(r"tell\s+me\s+about\s+([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_identity),
    # ACTION: "what did X do?" / "what does X want?"
    (re.compile(r"what\s+(?:did|does|is|are)\s+(?:the\s+)?([\w]+)\s+(do|eat|buy|sell|want|say|tell|have|need|like|love|hate|know|see|ask|find|get|make|take|give|show|use|try|go|come|leave|bring|send|write|read|call|start|stop|begin|finish|complete|reach|hold|keep|put|set|turn|move|run|walk|talk|play)\s*\??\s*$", re.IGNORECASE), _extract_action),
    (re.compile(r"what\s+happened\s+(?:to|with)\s+(?:the\s+)?([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_action),
    # LOCATION: "where does X live?"
    (re.compile(r"where\s+(?:does|did|is|are)\s+(?:the\s+)?([\w]+)\s+(live|work|stay|go|come|be)\s*\??\s*$", re.IGNORECASE), _extract_location),
    (re.compile(r"where\s+(?:is|are|was|were)\s+(?:the\s+)?([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_location),
    # TEMPORAL: "when did X happen?" / "when did X do Y?"
    (re.compile(r"when\s+(?:did|is|was|were)\s+(?:the\s+)?([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_temporal),
    (re.compile(r"when\s+(?:did|does)\s+(?:the\s+)?([\w]+)\s+(do|eat|buy|sell|say|go|come)\s*(?:.*)$", re.IGNORECASE), _extract_temporal_who),
    # CAUSAL: "why did X happen?" / "why is X?"
    (re.compile(r"why\s+(?:did|does|is|are)\s+(?:the\s+)?([\w\-]+)\s+([\w\-]+)\s*\??\s*$", re.IGNORECASE), _extract_causal),
    (re.compile(r"why\s+(?:did|does|is|are|happened)", re.IGNORECASE), _extract_causal),
    # GENERAL
    (re.compile(r"what\s+(?:do\s+you|can\s+you)\s+(?:know|tell\s+me)\s+about\s+(?:the\s+)?([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_general),
    (re.compile(r"tell\s+me\s+(?:about|everything\s+about)\s+([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_general),
]


# ============================================================================
# Spanish patterns
# ============================================================================

_PATTERNS_ES: list[tuple[re.Pattern, Callable]] = [
    # IDENTITY: "¿quién es X?"
    (re.compile(r"¿?quién\s+(?:es|son|fue|era)\s+(?:el|la|los|las)?\s*([\w\s\-]+?)\s*\??\s*$", re.IGNORECASE), _extract_identity),
    # ACTION: "¿qué hizo X?" / "¿qué quiere X?"
    (re.compile(r"¿?qué\s+(?:hizo|hace|dijo|dice|pidió|pide|compró|compra|vendió|vende|quiere|necesita|le\s+gusta|odia|sabe)\s+(?:el|la|los|las)?\s*([\w]+)\s*\??\s*$", re.IGNORECASE), _extract_action),
    (re.compile(r"¿?qué\s+(?:pasó|sucedió|ocurrió)\s+con\s+(?:el|la|los|las)?\s*([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_action),
    # LOCATION: "¿dónde vive X?"
    (re.compile(r"¿?dónde\s+(?:vive|vivió|trabaja|trabajó|está|estuvo|queda|quedó|va|fue)\s+(?:el|la|los|las)?\s*([\w\-]+)\s*\??\s*$", re.IGNORECASE), _extract_location),
    (re.compile(r"¿?dónde\s+(?:es|está|queda|quedó|ocurrió)\s+(?:el|la|los|las)?\s*([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_location),
    # TEMPORAL: "¿cuándo pasó X?"
    (re.compile(r"¿?cuándo\s+(?:pasó|sucedió|ocurrió|fue|será|era)\s+(?:el|la|los|las)?\s*([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_temporal),
    (re.compile(r"¿?cuándo\s+(?:el|la|los|las)?\s*([\w]+)\s+(hizo|hizo|dijo|compró)\s*(?:.*)$", re.IGNORECASE), _extract_temporal_who),
    # CAUSAL: "¿por qué X?"
    (re.compile(r"¿?por\s+qué\s+(?:el|la|los|las)?\s*([\w\-]+)\s+([\w\-]+)\s*\??\s*$", re.IGNORECASE), _extract_causal),
    # GENERAL
    (re.compile(r"¿?qué\s+(?:sabes|conoces)\s+sobre\s+(?:el|la|los|las)?\s*([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_general),
    (re.compile(r"¿?háblame\s+de\s+(?:el|la|los|las)?\s*([\w\s]+?)\s*\??\s*$", re.IGNORECASE), _extract_general),
]


_PATTERNS_BY_LANG = {
    "pt": _PATTERNS_PT,
    "en": _PATTERNS_EN,
    "es": _PATTERNS_ES,
}


class RegexExtractor:
    """
    Regex-based extractor. Fast (no LLM, no embedding).

    Supports Portuguese, English, Spanish. Falls back to Portuguese
    for unknown languages.
    """

    def __init__(self, default_lang: str = "auto") -> None:
        """
        Args:
            default_lang: default language if detection fails
                           ("pt", "en", "es", "auto")
        """
        self.default_lang = default_lang
        self._patterns_by_lang = _PATTERNS_BY_LANG

    @property
    def supported_langs(self) -> list[str]:
        return list(self._patterns_by_lang.keys())

    def extract(self, query: str, lang: str = "auto") -> QueryIntent:
        """Extract W5H from query using language-specific regex patterns."""
        if not query or not query.strip():
            return QueryIntent(raw_query=query, lang=lang, confidence=0.0)

        # Resolve language
        if lang == "auto":
            lang = detect_lang(query)
        if lang not in self._patterns_by_lang:
            lang = "pt"  # fallback

        patterns = self._patterns_by_lang[lang]
        query_lower = query.strip().lower()

        # Try each pattern
        for pattern, extractor_fn in patterns:
            m = pattern.search(query_lower)
            if m:
                intent = extractor_fn(m, lang=lang)
                intent.raw_query = query
                return intent

        # No match
        return QueryIntent(
            raw_query=query,
            query_type="unknown",
            confidence=0.0,
            lang=lang,
        )


class HybridExtractor:
    """
    Tries a primary extractor first; falls back to secondary if confidence < threshold.

    Use case: RegexExtractor (fast, free) → LLMExtractor (slow, costs)
    """

    def __init__(self, primary: Extractor, fallback: Extractor, threshold: float = 0.5) -> None:
        self.primary = primary
        self.fallback = fallback
        self.threshold = threshold

    @property
    def supported_langs(self) -> list[str]:
        langs = set(self.primary.supported_langs)
        langs.update(self.fallback.supported_langs)
        return sorted(langs)

    def extract(self, query: str, lang: str = "auto") -> QueryIntent:
        intent = self.primary.extract(query, lang=lang)
        if intent.confidence >= self.threshold:
            return intent
        return self.fallback.extract(query, lang=lang)


class LLMExtractor:
    """
    Placeholder for LLM-based extraction. Returns low-confidence result
    because there's no actual LLM call here — the user provides their
    own model_fn (e.g., lambda q: my_llm.generate(q)).

    In production, users wire this to Ollama, OpenAI, etc.
    """

    def __init__(self, model_fn=None, default_lang: str = "auto") -> None:
        """
        Args:
            model_fn: callable(query) -> response_text. If None, returns
                     unparsed intent with confidence 0.
            default_lang: default language hint
        """
        self.model_fn = model_fn
        self.default_lang = default_lang

    @property
    def supported_langs(self) -> list[str]:
        # LLM is theoretically universal
        return ["pt", "en", "es", "fr", "de", "zh", "ja", "auto"]

    def extract(self, query: str, lang: str = "auto") -> QueryIntent:
        if not self.model_fn:
            return QueryIntent(raw_query=query, query_type="unknown", confidence=0.0, lang=lang)

        # Prompt for W5H JSON extraction
        prompt = (
            f"Extract from this query: \"{query}\"\n"
            "Return JSON with fields: who (list), what (str), where (str), "
            "when (str), why (str), how (str). Use empty/blank for missing."
        )

        try:
            response = self.model_fn(prompt)
            return self._parse_json_response(response, query, lang)
        except Exception:
            return QueryIntent(raw_query=query, query_type="unknown", confidence=0.0, lang=lang)

    def _parse_json_response(self, response: str, query: str, lang: str) -> QueryIntent:
        """Parse LLM JSON response into QueryIntent."""
        import json
        import re

        # Try to extract JSON from response
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if not json_match:
            return QueryIntent(raw_query=query, query_type="general", confidence=0.5, lang=lang)

        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return QueryIntent(raw_query=query, query_type="general", confidence=0.5, lang=lang)

        return QueryIntent(
            who=data.get("who", []) or [],
            what=data.get("what", "") or "",
            where=data.get("where", "") or "",
            when=data.get("when", "") or "",
            why=data.get("why", "") or "",
            how=data.get("how", "") or "",
            query_type="general",
            confidence=0.7,  # LLM extraction has higher base confidence
            raw_query=query,
            lang=lang,
        )
