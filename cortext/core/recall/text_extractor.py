"""
TextToMemory — extract W5H from free text using 3-level strategy.

1. Heuristic: regex for who (proper nouns), when (dates), where (keywords)
2. Embedding-similar: find similar memory in graph, copy its where/lang/importance
3. LLM extract (optional): only if heuristic fails or user explicitly requests

This is the ABSTRACTION layer the user wanted. The user passes natural
language text, not structured W5H.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from cortext.core.memory import Memory
    from cortext.core.graph import MemoryGraph


# Regex patterns for heuristic extraction
_WHO_PATTERN = re.compile(r"\b([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]{2,})\b")
_WHEN_PATTERNS = [
    re.compile(r"\b(hoje|ontem|anteontem|amanhã|agora)\b", re.IGNORECASE),
    re.compile(r"\b(segunda|terça|quarta|quinta|sexta|sábado|domingo)(-feira)?\b", re.IGNORECASE),
    re.compile(r"\b(\d{1,2}/\d{1,2}(/\d{2,4})?)\b"),  # 22/03/2026
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),  # ISO date
]
_WHERE_PATTERNS = [
    re.compile(r"\b(suporte|vendas|infra|dev|family|preferences|calendar|habits|trabalho|casa)\b", re.IGNORECASE),
]


def extract_who(text: str) -> list[str]:
    """Extract proper-noun-like names from text."""
    candidates = set()
    for match in _WHO_PATTERN.finditer(text):
        name = match.group(1)
        if name.lower() not in {"the", "que", "com", "para", "por", "uma", "não"}:
            candidates.add(name)
    return sorted(candidates)


def extract_when(text: str) -> str:
    """Extract temporal markers (returns first match or empty)."""
    for pat in _WHEN_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0)
    return ""


def extract_where(text: str) -> str:
    """Extract location/namespace hints."""
    for pat in _WHERE_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0).lower()
    return "default"


def extract_via_heuristic(text: str) -> dict[str, Any]:
    """Heuristic W5H extraction. Returns dict with who, what, when, where.

    Note: 'what' is not extracted by heuristic (it's the input itself).
    """
    return {
        "who": extract_who(text),
        "what": text,  # full text as what
        "why": "",
        "when": extract_when(text),
        "where": extract_where(text),
    }


def extract_via_embedding_similar(
    text: str, graph: "MemoryGraph", embedding_recall=None
) -> dict[str, Any]:
    """Find similar memory in graph; copy its where/lang/importance."""
    if embedding_recall is None or not embedding_recall.is_available():
        return {}

    # Try to find similar memory
    from cortext.core.memory import Memory
    results = embedding_recall.rank_memories(text, list(graph.iter_memories()), top_k=1)
    if not results:
        return {}
    similar_mem, score = results[0]
    return {
        "where": similar_mem.where,
        "lang": similar_mem.lang,
        "importance": similar_mem.importance * 0.8,  # decay
    }


def extract_via_llm(text: str, model_fn: Callable[[str], str]) -> dict[str, Any]:
    """LLM extraction (most accurate, most expensive).

    model_fn is a callable that takes a prompt and returns the response.
    Prompt asks for JSON with W5H fields.
    """
    prompt = (
        f"Extract from this text: \"{text}\"\n"
        "Return ONLY valid JSON with these fields: "
        '{"who": [list of names], "what": "action/fact (1 sentence)", '
        '"where": "namespace/place or empty", "when": "temporal marker or empty", '
        '"why": "cause or empty", "how": "method/result or empty"}'
    )
    try:
        response = model_fn(prompt)
        import json
        # Try to find JSON in response
        m = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if m:
            return json.loads(m.group(0))
    except Exception:
        pass
    return {}


class TextToMemory:
    """
    High-level extractor: turn free text into a Memory.

    Strategy:
      1. Heuristic (always): regex for who, when, where
      2. Embedding-similar (optional): copy structure from similar memory
      3. LLM extract (optional): for ambiguous cases

    The user can choose which levels to use via constructor flags.
    """

    def __init__(
        self,
        enable_embedding: bool = True,
        llm_fn: Optional[Callable[[str], str]] = None,
    ) -> None:
        """
        Args:
            enable_embedding: if True, use embedding-similar to inherit structure
            llm_fn: optional callable for LLM extraction. If None, no LLM.
        """
        self.enable_embedding = enable_embedding
        self.llm_fn = llm_fn
        self._embedding_recall = None
        if enable_embedding:
            from cortext.core.recall.embedding import EmbeddingRecall
            self._embedding_recall = EmbeddingRecall()

    def extract(
        self, text: str, graph: Optional["MemoryGraph"] = None
    ) -> dict[str, Any]:
        """
        Extract W5H from text.

        Args:
            text: free text
            graph: optional graph for embedding-similar inheritance

        Returns:
            dict with keys: who, what, why, when, where, how, lang
        """
        # Level 1: heuristic (always)
        result = extract_via_heuristic(text)
        result.setdefault("how", "")

        # Level 2: embedding-similar (if enabled and graph has memories)
        if self.enable_embedding and graph is not None and self._embedding_recall:
            similar = extract_via_embedding_similar(text, graph, self._embedding_recall)
            # Fill in missing fields
            if not result.get("where") or result["where"] == "default":
                if "where" in similar:
                    result["where"] = similar["where"]
            if not result.get("lang") and "lang" in similar:
                result["lang"] = similar["lang"]
            if "importance" in similar:
                result["importance"] = similar["importance"]

        # Level 3: LLM extract (only if what is still empty or explicitly requested)
        if self.llm_fn is not None and not result.get("what"):
            llm_result = extract_via_llm(text, self.llm_fn)
            for key in llm_result:
                if llm_result[key]:
                    result[key] = llm_result[key]

        # Set defaults
        result.setdefault("lang", None)
        result.setdefault("importance", 0.5)

        return result

    def to_memory(
        self, text: str, graph: Optional["MemoryGraph"] = None
    ) -> "Memory":
        """
        Direct text → Memory. Returns a fully-formed Memory.
        """
        from cortext.core.memory import Memory
        data = self.extract(text, graph)
        return Memory(
            who=data.get("who", []),
            what=data.get("what", text),
            why=data.get("why", ""),
            when=data.get("when", "") or None,  # if empty, use default datetime.now
            where=data.get("where", "default"),
            how=data.get("how", ""),
            importance=data.get("importance", 0.5),
            lang=data.get("lang"),
        )


def default_extractor(llm_fn: Optional[Callable[[str], str]] = None) -> TextToMemory:
    """Create a TextToMemory with sensible defaults (heuristic + embedding)."""
    return TextToMemory(enable_embedding=True, llm_fn=llm_fn)


def heuristic_only_extractor() -> TextToMemory:
    """Create a TextToMemory with ONLY heuristic (no embedding, no LLM)."""
    return TextToMemory(enable_embedding=False, llm_fn=None)


def full_extractor(llm_fn: Callable[[str], str]) -> TextToMemory:
    """Create a TextToMemory with all 3 levels (heuristic + embedding + LLM)."""
    return TextToMemory(enable_embedding=True, llm_fn=llm_fn)
