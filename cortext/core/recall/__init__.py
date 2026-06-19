"""
Recall subsystem: pluggable extractors + structural parser + pack.

Public API:
  - Extractor (Protocol)
  - QueryIntent (dataclass)
  - RegexExtractor (PT/EN/ES patterns)
  - HybridExtractor (regex + LLM fallback)
  - LLMExtractor (LLM-based, requires model_fn)
  - StructuralQueryParser (main recall entry point)
  - pack_for_context (compact prompt builder)
  - detect_lang (language detection)
"""

from cortext.core.recall.extractor import (
    Extractor,
    QueryIntent,
    detect_lang,
)
from cortext.core.recall.extractors.regex_lang import (
    RegexExtractor,
    HybridExtractor,
    LLMExtractor,
)
from cortext.core.recall.parser import StructuralQueryParser
from cortext.core.recall.pack import pack_for_context, rough_token_count

__all__ = [
    "Extractor",
    "QueryIntent",
    "detect_lang",
    "RegexExtractor",
    "HybridExtractor",
    "LLMExtractor",
    "StructuralQueryParser",
    "pack_for_context",
    "rough_token_count",
]
