"""Pluggable extractors (regex per language, LLM fallback, hybrid)."""

from cortex_v5.core.recall.extractors.regex_lang import (
    RegexExtractor,
    HybridExtractor,
    LLMExtractor,
    _PATTERNS_PT,
    _PATTERNS_EN,
    _PATTERNS_ES,
)

__all__ = ["RegexExtractor", "HybridExtractor", "LLMExtractor"]
