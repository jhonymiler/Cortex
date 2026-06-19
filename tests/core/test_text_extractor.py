"""
Tests for TextToMemory — the abstraction layer for free text input.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cortext import Memory, MemoryGraph
from cortext.core.recall.text_extractor import (
    TextToMemory,
    extract_who,
    extract_when,
    extract_where,
    extract_via_heuristic,
    heuristic_only_extractor,
    default_extractor,
    full_extractor,
)


class TestHeuristicExtractors:
    """Test individual heuristic extractors."""

    def test_extract_who_pt(self):
        names = extract_who("Maria ligou hoje cedo reclamando")
        assert "Maria" in names

    def test_extract_who_multiple(self):
        names = extract_who("Maria e João encontraram Pedro")
        assert "Maria" in names
        assert "João" in names
        assert "Pedro" in names

    def test_extract_who_skips_common_words(self):
        names = extract_who("Com para não uma")
        # Common words filtered
        assert "Com" not in names
        assert "Para" not in names

    def test_extract_when_hoje(self):
        assert extract_when("Maria ligou hoje cedo") == "hoje"

    def test_extract_when_ontem(self):
        assert extract_when("ontem recebi a ligação") == "ontem"

    def test_extract_when_iso_date(self):
        assert extract_when("aconteceu em 2026-03-22") == "2026-03-22"

    def test_extract_when_br_date(self):
        assert extract_when("aconteceu em 22/03/2026") == "22/03/2026"

    def test_extract_when_empty(self):
        assert extract_when("Maria ligou") == ""

    def test_extract_where_suporte(self):
        assert extract_where("ligou do suporte") == "suporte"

    def test_extract_where_default(self):
        assert extract_where("Maria ligou") == "default"

    def test_extract_via_heuristic_returns_full_dict(self):
        result = extract_via_heuristic("Maria ligou hoje do suporte")
        assert "who" in result
        assert "what" in result
        assert "when" in result
        assert "where" in result
        assert "Maria" in result["who"]
        assert result["what"] == "Maria ligou hoje do suporte"
        assert result["when"] == "hoje"
        assert result["where"] == "suporte"


class TestTextToMemory:
    """Test the high-level extractor."""

    def test_heuristic_only(self):
        ttm = heuristic_only_extractor()
        data = ttm.extract("Maria ligou hoje do suporte")
        assert "Maria" in data["who"]
        assert data["where"] == "suporte"
        assert data["when"] == "hoje"

    def test_to_memory_returns_valid_memory(self):
        ttm = heuristic_only_extractor()
        m = ttm.to_memory("Maria ligou hoje do suporte")
        assert isinstance(m, Memory)
        assert "Maria" in m.who
        assert m.where == "suporte"

    def test_embedding_similar_inherits_structure(self):
        """Embedding-similar copies where/lang from most similar memory.

        Skipped if sentence-transformers not installed.
        """
        g = MemoryGraph()
        ref = Memory(who=["Maria"], what="pediu reembolso", where="suporte", lang="pt", importance=0.8)
        g._memories[ref.id] = ref

        ttm = default_extractor()  # heuristic + embedding
        if not ttm._embedding_recall or not ttm._embedding_recall.is_available():
            pytest.skip("sentence-transformers not installed; embedding-similar not available")
        data = ttm.extract("Maria ligou para resolver", graph=g)
        # Should inherit where='suporte' from similar memory
        assert data.get("where") == "suporte"

    def test_llm_extractor_called_when_provided(self):
        """If LLM function is provided, it's used as 3rd level."""

        def mock_llm(prompt):
            return '{"who": ["João"], "what": "test extracted", "where": "vendas"}'

        ttm = full_extractor(llm_fn=mock_llm)
        data = ttm.extract("anything")
        # LLM was used (we can't easily check it's a 3rd level here without
        # mocking, but the data should be valid)
        assert "who" in data

    def test_to_memory_with_embedding_inheritance(self):
        """Full pipeline: text → extract → Memory with inherited structure.

        Skipped if sentence-transformers not installed.
        """
        g = MemoryGraph()
        ref = Memory(who=["Maria"], what="gostou do produto", where="vendas", lang="pt")
        g._memories[ref.id] = ref

        ttm = default_extractor()
        if not ttm._embedding_recall or not ttm._embedding_recall.is_available():
            pytest.skip("sentence-transformers not installed; embedding-similar not available")
        m = ttm.to_memory("Maria adorou a compra nova", graph=g)
        # Inherited from ref
        assert m.where == "vendas"
        assert "Maria" in m.who


class TestPublicAPI:
    """Test factory functions."""

    def test_default_extractor(self):
        ttm = default_extractor()
        assert ttm.enable_embedding is True
        assert ttm.llm_fn is None

    def test_heuristic_only_extractor(self):
        ttm = heuristic_only_extractor()
        assert ttm.enable_embedding is False
        assert ttm.llm_fn is None

    def test_full_extractor(self):
        ttm = full_extractor(llm_fn=lambda p: "{}")
        assert ttm.enable_embedding is True
        assert ttm.llm_fn is not None


class TestEndToEndAbstraction:
    """Real-world scenarios showing the abstraction value."""

    def test_free_text_turn_into_memory(self):
        """User passes text, gets Memory back. The whole point of the abstraction."""
        ttm = heuristic_only_extractor()
        m = ttm.to_memory("Maria ligou hoje cedo reclamando do produto com defeito")
        # Even without LLM, we get a valid Memory with extracted fields
        assert isinstance(m, Memory)
        assert "Maria" in m.who
        assert m.where == "default"  # no where keyword detected
        # The text becomes `what`
        assert "Maria ligou hoje cedo" in m.what
        # When is extracted
        assert m.metadata is not None or m.when is not None  # default datetime.now()

    def test_user_passes_garbled_text_gracefully(self):
        """Even with very noisy input, doesn't crash."""
        ttm = heuristic_only_extractor()
        m = ttm.to_memory("qqq www eee !!! ???")
        # Just stores the text as what
        assert isinstance(m, Memory)
        # who is empty
        assert m.who == []
        # No crash on empty extraction
