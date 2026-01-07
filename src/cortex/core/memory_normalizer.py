"""
Memory Normalizer - Extração Inteligente de Núcleo Informacional

Usa spaCy para extrair verbo+objeto de frases verbosas.
Exemplo:
  "Pedro Costa solicitou o cancelamento de sua assinatura"
  → "Pedro_Costa:requested:cancellation_subscription"

Funciona com português e inglês.
"""
import re
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Lazy loading de spaCy para performance
_nlp_pt = None
_nlp_en = None


def _get_nlp_pt():
    """Carrega modelo português sob demanda."""
    global _nlp_pt
    if _nlp_pt is None:
        try:
            import spacy
            _nlp_pt = spacy.load('pt_core_news_sm')
            logger.debug("Modelo spaCy PT carregado")
        except Exception as e:
            logger.warning(f"Falha ao carregar spaCy PT: {e}")
            _nlp_pt = False  # Marca como indisponível
    return _nlp_pt if _nlp_pt else None


def _get_nlp_en():
    """Carrega modelo inglês sob demanda."""
    global _nlp_en
    if _nlp_en is None:
        try:
            import spacy
            _nlp_en = spacy.load('en_core_web_sm')
            logger.debug("Modelo spaCy EN carregado")
        except Exception as e:
            logger.warning(f"Falha ao carregar spaCy EN: {e}")
            _nlp_en = False  # Marca como indisponível
    return _nlp_en if _nlp_en else None


try:
    from unidecode import unidecode
except ImportError:
    def unidecode(text: str) -> str:
        return text


class MemoryNormalizer:
    """
    Normaliza memórias extraindo verbo+objeto usando spaCy.
    
    Transforma texto verboso em núcleo informacional:
    - Usa POS tagging para identificar verbos (VERB) e substantivos (NOUN, PROPN)
    - Extrai padrão: verbo_substantivo1_substantivo2
    - Remove acentos e normaliza para formato compacto
    """
    
    def __init__(self, max_nouns: int = 3, use_lemma: bool = False):
        """
        Args:
            max_nouns: Máximo de substantivos a incluir
            use_lemma: Se True, usa forma base do verbo (solicitar).
                      Se False, mantém conjugação (solicitou).
        """
        self.max_nouns = max_nouns
        self.use_lemma = use_lemma
    
    def extract_core(self, text: str, lang: str = "auto") -> str:
        """
        Extrai núcleo informacional: verbo + substantivos principais.
        
        Args:
            text: Texto original
            lang: "pt", "en" ou "auto" (detecta automaticamente)
            
        Returns:
            Formato compacto: "verbo_subst1_subst2"
        """
        if not text or not text.strip():
            return ""
        
        # Detecta idioma
        if lang == "auto":
            lang = self._detect_language(text)
        
        # Obtém modelo NLP
        nlp = _get_nlp_pt() if lang == "pt" else _get_nlp_en()
        
        if not nlp:
            # Fallback sem spaCy
            return self._fallback_normalize(text)
        
        # Processa com spaCy
        doc = nlp(text)
        
        verbs = []
        nouns = []
        proper_nouns = []
        
        for token in doc:
            # Ignora tokens muito curtos (artigos, preposições)
            if len(token.text) <= 2:
                continue
                
            # Verbo
            if token.pos_ == "VERB":
                if self.use_lemma:
                    verbs.append(token.lemma_.lower())
                else:
                    verbs.append(token.text.lower())
            
            # Substantivo comum
            elif token.pos_ == "NOUN":
                nouns.append(token.text.lower())
            
            # Nome próprio
            elif token.pos_ == "PROPN":
                proper_nouns.append(token.text)
        
        # Monta resultado
        parts = []
        
        # Nomes próprios primeiro (entidades)
        if proper_nouns:
            entity = "_".join(proper_nouns[:2])
            parts.append(entity)
        
        # Verbo principal
        if verbs:
            parts.append(verbs[0])
        
        # Substantivos (objetos)
        if nouns:
            parts.extend(nouns[:self.max_nouns])
        
        # Gera formato compacto
        result = "_".join(parts)
        result = unidecode(result)  # Remove acentos
        result = re.sub(r'_+', '_', result)  # Remove underscores duplicados
        result = result.strip('_')
        
        # Limite de tamanho
        if len(result) > 60:
            result = result[:60].rsplit('_', 1)[0]
        
        return result.lower()
    
    def normalize(self, text: str) -> str:
        """Alias para extract_core - mantém compatibilidade."""
        return self.extract_core(text)
    
    def normalize_w5h(
        self,
        who: list[str] | str | None = None,
        what: str | None = None,
        why: str | None = None,
        how: str | None = None,
    ) -> dict:
        """
        Normaliza campos W5H individualmente.
        
        Returns:
            Dict com campos normalizados
        """
        result = {}
        
        # WHO: mantém nomes próprios, apenas limpa
        if who:
            if isinstance(who, list):
                result["who"] = [self._normalize_entity(w) for w in who]
            else:
                result["who"] = [self._normalize_entity(who)]
        
        # WHAT: extrai verbo+objeto
        if what:
            result["what"] = self.extract_core(what)
        
        # WHY: extrai substantivos principais
        if why:
            result["why"] = self._extract_nouns_only(why)
        
        # HOW: extrai resultado/estado
        if how:
            result["how"] = self._extract_nouns_only(how)
        
        return result
    
    def _detect_language(self, text: str) -> str:
        """Detecta idioma baseado em padrões."""
        # Caracteres típicos do português
        if re.search(r'[áéíóúãõâêôç]', text.lower()):
            return "pt"
        
        # Palavras comuns em português
        pt_words = {'de', 'da', 'do', 'para', 'com', 'que', 'não', 'está', 'foi'}
        words = set(text.lower().split())
        if len(words & pt_words) >= 2:
            return "pt"
        
        return "en"
    
    def _normalize_entity(self, entity: str) -> str:
        """Normaliza nome de entidade."""
        entity = re.sub(r'\s+', '_', entity.strip())
        entity = re.sub(r'[^\w_]', '', entity)
        return unidecode(entity)
    
    def _extract_nouns_only(self, text: str) -> str:
        """Extrai apenas substantivos (para why/how)."""
        lang = self._detect_language(text)
        nlp = _get_nlp_pt() if lang == "pt" else _get_nlp_en()
        
        if not nlp:
            return self._fallback_normalize(text)
        
        doc = nlp(text)
        nouns = [
            token.text.lower() 
            for token in doc 
            if token.pos_ in ["NOUN", "PROPN"] and len(token.text) > 2
        ]
        
        result = "_".join(nouns[:self.max_nouns])
        return unidecode(result).lower()
    
    def _fallback_normalize(self, text: str) -> str:
        """Fallback quando spaCy não está disponível."""
        # Remove pontuação
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Stopwords básicas
        stopwords = {
            'o', 'a', 'os', 'as', 'um', 'uma', 'de', 'da', 'do', 'em', 'na', 'no',
            'para', 'com', 'por', 'que', 'e', 'ou', 'se', 'seu', 'sua',
            'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        }
        
        words = [w for w in text.lower().split() if w not in stopwords and len(w) > 2]
        
        result = "_".join(words[:5])
        return unidecode(result)


# Instância global para uso direto
_normalizer = MemoryNormalizer(max_nouns=3, use_lemma=False)


def normalize_memory(text: str) -> str:
    """Função de conveniência para normalizar memória."""
    return _normalizer.normalize(text)


def extract_core(text: str, lang: str = "auto") -> str:
    """Extrai núcleo informacional de texto."""
    return _normalizer.extract_core(text, lang)


def normalize_w5h(**kwargs) -> dict:
    """Função de conveniência para normalizar W5H."""
    return _normalizer.normalize_w5h(**kwargs)


# Testes
if __name__ == "__main__":
    normalizer = MemoryNormalizer()
    
    tests_pt = [
        "Pedro Costa solicitou o cancelamento de sua assinatura",
        "O usuário está tendo problemas com o login",
        "Cliente reportou erro de pagamento no sistema",
        "Ana perguntou sobre o prazo de entrega do pedido",
        "Técnico resolveu o bug de timeout na aplicação",
        "Maria quer fazer upgrade para o plano premium",
    ]
    
    tests_en = [
        "Customer requested subscription cancellation",
        "User reported payment error in the system",
        "Support resolved the connection issue",
        "John wants to upgrade his plan",
    ]
    
    print("=" * 70)
    print("🧪 TESTE DE EXTRAÇÃO DE NÚCLEO INFORMACIONAL")
    print("=" * 70)
    
    print("\n🇧🇷 PORTUGUÊS:")
    for test in tests_pt:
        core = normalizer.extract_core(test, lang="pt")
        print(f"\n  📝 \"{test}\"")
        print(f"     → {core}")
    
    print("\n🇺🇸 INGLÊS:")
    for test in tests_en:
        core = normalizer.extract_core(test, lang="en")
        print(f"\n  📝 \"{test}\"")
        print(f"     → {core}")
    
    print("\n" + "=" * 70)
    print("🔧 TESTE W5H:")
    print("=" * 70)
    
    w5h_result = normalizer.normalize_w5h(
        who="Pedro Costa",
        what="solicitou o cancelamento da assinatura",
        why="insatisfação com o serviço",
        how="ticket resolvido com reembolso"
    )
    print(f"\n  Input:")
    print(f"    who: Pedro Costa")
    print(f"    what: solicitou o cancelamento da assinatura")
    print(f"    why: insatisfação com o serviço")
    print(f"    how: ticket resolvido com reembolso")
    print(f"\n  Output: {w5h_result}")
