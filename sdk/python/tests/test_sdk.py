"""
Testes unitários do CortexMemorySDK.

Testa:
- Contratos (Action, W5H)
- Extractor (determinístico)
- Normalizer (Action → W5H)
- Client (mock HTTP)
"""

import pytest
import sys
import os

# Adiciona path do SDK
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cortex_memory_sdk import (
    Action, W5H, RecallResult,
    action_to_w5h, normalize_term,
    extract_action, remove_memory_marker, has_memory_marker,
)


class TestAction:
    """Testes para contrato Action."""
    
    def test_action_creation(self):
        action = Action(verb="solicitou", subject="carlos", object="reembolso")
        assert action.verb == "solicitou"
        assert action.subject == "carlos"
        assert action.object == "reembolso"
    
    def test_action_requires_verb(self):
        with pytest.raises(ValueError):
            Action(verb="")
    
    def test_action_to_dict(self):
        action = Action(verb="solicitou", subject="carlos", modifiers=("urgente",))
        d = action.to_dict()
        assert d["verb"] == "solicitou"
        assert d["subject"] == "carlos"
        assert d["modifiers"] == ["urgente"]
    
    def test_action_from_dict(self):
        d = {"verb": "reportou", "subject": "maria", "object": "bug"}
        action = Action.from_dict(d)
        assert action.verb == "reportou"
        assert action.subject == "maria"


class TestW5H:
    """Testes para contrato W5H."""
    
    def test_w5h_creation(self):
        w5h = W5H(who="carlos", what="solicitou_reembolso")
        assert w5h.who == "carlos"
        assert w5h.what == "solicitou_reembolso"
    
    def test_w5h_to_dict(self):
        w5h = W5H(who="carlos", what="pediu", how="urgente")
        d = w5h.to_dict()
        assert d["who"] == "carlos"
        assert d["what"] == "pediu"
        assert d["how"] == "urgente"


class TestNormalizer:
    """Testes para normalização."""
    
    def test_normalize_term_lowercase(self):
        assert normalize_term("Carlos") == "carlos"
    
    def test_normalize_term_spaces(self):
        assert normalize_term("produto defeituoso") == "produto_defeituoso"
    
    def test_normalize_term_special_chars(self):
        assert normalize_term("olá, mundo!") == "ola_mundo"
    
    def test_action_to_w5h_basic(self):
        action = Action(verb="solicitou", subject="carlos", object="reembolso")
        w5h = action_to_w5h(action, namespace="support")
        
        assert w5h.who == "carlos"
        assert w5h.what == "solicitou_reembolso"
        assert w5h.where == "support"
    
    def test_action_to_w5h_with_modifiers(self):
        action = Action(
            verb="reportou",
            subject="maria",
            object="bug",
            modifiers=("crítico", "urgente"),
        )
        w5h = action_to_w5h(action, namespace="dev")
        
        assert w5h.who == "maria"
        assert w5h.what == "reportou_bug"
        assert w5h.how == "critico_urgente"
    
    def test_action_to_w5h_with_reason(self):
        action = Action(verb="cancelou", subject="joao", object="pedido")
        w5h = action_to_w5h(action, reason="mudou de ideia")
        
        assert w5h.why == "mudou_de_ideia"


class TestExtractor:
    """Testes para extração determinística."""
    
    def test_extract_from_mem_marker(self):
        text = '[MEM verb="solicitou" subject="carlos" object="reembolso" /]'
        action = extract_action(text)
        
        assert action is not None
        assert action.verb == "solicitou"
        assert action.subject == "carlos"
        assert action.object == "reembolso"
    
    def test_extract_from_memory_block(self):
        text = """
        Resposta do agente.
        
        [MEMORY]
        who: Carlos
        what: solicitou_reembolso
        why: produto_defeituoso
        [/MEMORY]
        """
        action = extract_action(text)
        
        assert action is not None
        assert action.verb == "solicitou"
        assert action.subject == "Carlos"
        assert action.object == "reembolso"
    
    def test_extract_from_pattern_pt(self):
        text = "O cliente Carlos pediu reembolso do produto"
        action = extract_action(text)
        
        assert action is not None
        assert action.subject == "carlos"
        assert action.object == "reembolso"
    
    def test_extract_fails_gracefully(self):
        text = "Texto genérico sem estrutura clara"
        action = extract_action(text)
        
        assert action is None
    
    def test_remove_memory_marker(self):
        text = "Resposta [MEM verb='x' /] limpa"
        clean = remove_memory_marker(text)
        
        assert "[MEM" not in clean
        assert "Resposta" in clean
        assert "limpa" in clean
    
    def test_has_memory_marker(self):
        assert has_memory_marker("[MEMORY]teste[/MEMORY]")
        assert has_memory_marker('[MEM verb="x" /]')
        assert not has_memory_marker("texto normal")


class TestRecallResult:
    """Testes para RecallResult."""
    
    def test_recall_result_empty(self):
        result = RecallResult()
        assert len(result) == 0
        assert not result
    
    def test_recall_result_with_memories(self):
        memories = [
            W5H(who="carlos", what="pediu_reembolso"),
            W5H(who="maria", what="cancelou_pedido"),
        ]
        result = RecallResult(memories=memories)
        
        assert len(result) == 2
        assert result
    
    def test_recall_result_to_prompt_context(self):
        memories = [W5H(who="carlos", what="pediu_reembolso", how="urgente")]
        result = RecallResult(memories=memories)
        
        context = result.to_prompt_context()
        assert "who:carlos" in context
        assert "what:pediu_reembolso" in context
        assert "how:urgente" in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


