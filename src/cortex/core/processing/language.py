"""
Language utilities - Centraliza todas as configurações dependentes de idioma.

Este módulo isola dependências de idioma para facilitar:
- Manutenção e atualização de stopwords
- Adição de novos idiomas
- Substituição por libs externas (spaCy, NLTK) no futuro

NOTA: Idealmente, usaríamos uma lib como `spacy` ou `nltk` para tokenização
robusta. Este módulo serve como camada de abstração para facilitar essa
migração futura.
"""

import re
from typing import Set

# =============================================================================
# STOPWORDS
# =============================================================================

# Stopwords comuns em Português
STOPWORDS_PT: Set[str] = {
    # Artigos
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    # Preposições
    "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas",
    "para", "por", "com", "sem", "sob", "sobre", "entre", "até",
    "ao", "aos", "à", "às",
    # Conjunções
    "e", "ou", "mas", "porém", "contudo", "porque", "pois", "que",
    "se", "quando", "enquanto", "embora", "como",
    # Pronomes
    "eu", "tu", "ele", "ela", "nós", "vós", "eles", "elas",
    "me", "te", "se", "nos", "vos", "lhe", "lhes",
    "meu", "minha", "meus", "minhas", "teu", "tua", "teus", "tuas",
    "seu", "sua", "seus", "suas", "nosso", "nossa", "nossos", "nossas",
    "este", "esta", "estes", "estas", "esse", "essa", "esses", "essas",
    "aquele", "aquela", "aqueles", "aquelas", "isto", "isso", "aquilo",
    # Verbos auxiliares comuns
    "é", "são", "foi", "foram", "ser", "estar", "ter", "haver",
    "está", "estou", "estamos", "estava", "tenho", "tem", "temos",
    # Advérbios
    "não", "sim", "já", "ainda", "também", "muito", "mais", "menos",
    "bem", "mal", "sempre", "nunca", "onde", "aqui", "ali", "lá",
    # Outros
    "só", "apenas", "mesmo", "próprio", "cada", "todo", "toda",
}

# Stopwords comuns em Inglês
STOPWORDS_EN: Set[str] = {
    # Articles
    "the", "a", "an",
    # Prepositions
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "again", "further",
    # Conjunctions
    "and", "but", "or", "nor", "so", "yet", "both", "either", "neither",
    "if", "because", "although", "while", "when", "where", "unless",
    # Pronouns
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
    "this", "that", "these", "those", "what", "which", "who", "whom",
    # Auxiliary verbs
    "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having", "do", "does", "did", "doing",
    "will", "would", "could", "should", "may", "might", "must",
    "shall", "can", "need", "dare",
    # Adverbs
    "not", "no", "yes", "very", "just", "only", "also", "already",
    "still", "even", "now", "then", "once", "here", "there",
    "more", "most", "less", "least", "too", "much", "many",
    # Others
    "all", "each", "few", "some", "any", "other", "such", "same",
    "own", "than",
}

# Combinação de todos os stopwords
STOPWORDS: Set[str] = STOPWORDS_PT | STOPWORDS_EN


# =============================================================================
# TOKENIZAÇÃO
# =============================================================================

# Padrão para split de tokens (caracteres não-alfanuméricos)
# Inclui caracteres acentuados do português
TOKEN_PATTERN = re.compile(r'[^a-záàâãéèêíìóòôõúùûç0-9]+', re.IGNORECASE)

# Tamanho mínimo de token (tokens menores são ignorados)
MIN_TOKEN_LENGTH = 2

# Limites para evitar textos enormes
MAX_TEXT_LENGTH = 500  # Caracteres máximos antes de truncar
MAX_TOKENS = 50        # Tokens máximos a retornar


def tokenize(text: str, remove_stopwords: bool = True, max_tokens: int | None = None) -> list[str]:
    """
    Tokeniza texto em termos normalizados.
    
    Args:
        text: Texto para tokenizar
        remove_stopwords: Se True, remove stopwords (default: True)
        max_tokens: Máximo de tokens a retornar (default: MAX_TOKENS)
    
    Returns:
        Lista de tokens normalizados (limitada a max_tokens)
    
    Examples:
        >>> tokenize("O cliente solicitou reembolso")
        ['cliente', 'solicitou', 'reembolso']
        
        >>> tokenize("The user requested help")
        ['user', 'requested', 'help']
    
    Note:
        Textos muito longos são truncados para evitar overhead.
    """
    if not text:
        return []
    
    # Limite de tokens
    limit = max_tokens if max_tokens is not None else MAX_TOKENS
    
    # Trunca textos muito longos ANTES de processar
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
    
    # Lowercase e split
    text_lower = text.lower()
    tokens = TOKEN_PATTERN.split(text_lower)
    
    # Filtra tokens curtos
    filtered = [t for t in tokens if t and len(t) >= MIN_TOKEN_LENGTH]
    
    # Remove stopwords se solicitado
    if remove_stopwords:
        filtered = [t for t in filtered if t not in STOPWORDS]
    
    # Limita quantidade de tokens
    return filtered[:limit]


def tokenize_to_set(text: str, remove_stopwords: bool = True) -> set[str]:
    """
    Tokeniza texto retornando um set (sem duplicatas).
    
    Útil para cálculo de overlap/interseção.
    """
    return set(tokenize(text, remove_stopwords))


def extract_key_terms(text: str, max_terms: int = 10) -> list[str]:
    """
    Extrai termos-chave de um texto.
    
    Prioriza:
    - Termos mais longos (mais específicos)
    - Termos únicos (não repetidos)
    
    Args:
        text: Texto para extrair termos
        max_terms: Máximo de termos a retornar
    
    Returns:
        Lista de termos-chave ordenados por especificidade
    """
    tokens = tokenize(text)
    
    # Remove duplicatas mantendo ordem
    unique = list(dict.fromkeys(tokens))
    
    # Ordena por tamanho (mais longos = mais específicos)
    sorted_by_length = sorted(unique, key=len, reverse=True)
    
    return sorted_by_length[:max_terms]


def calculate_overlap(text1: str, text2: str) -> float:
    """
    Calcula overlap de termos entre dois textos.
    
    Returns:
        Float entre 0.0 e 1.0 representando a proporção de overlap
    """
    tokens1 = tokenize_to_set(text1)
    tokens2 = tokenize_to_set(text2)
    
    if not tokens1 or not tokens2:
        return 0.0
    
    intersection = len(tokens1 & tokens2)
    # Usamos o menor conjunto como referência
    return intersection / min(len(tokens1), len(tokens2))


def is_stopword(word: str) -> bool:
    """Verifica se uma palavra é stopword."""
    return word.lower() in STOPWORDS


def truncate_for_memory(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """
    Trunca texto inteligentemente para armazenamento em memória.
    
    Diferente de text[:max_length], tenta:
    1. Cortar em um ponto final (.) se possível
    2. Cortar em uma vírgula (,) se possível
    3. Cortar em um espaço se possível
    4. Fallback: corta no limite exato
    
    Args:
        text: Texto para truncar
        max_length: Comprimento máximo (default: MAX_TEXT_LENGTH)
    
    Returns:
        Texto truncado inteligentemente
    """
    if not text or len(text) <= max_length:
        return text
    
    # Tenta encontrar um ponto final antes do limite
    truncated = text[:max_length]
    
    # Tenta cortar em ponto final
    last_period = truncated.rfind('.')
    if last_period > max_length * 0.5:  # Pelo menos 50% do texto
        return truncated[:last_period + 1]
    
    # Tenta cortar em vírgula
    last_comma = truncated.rfind(',')
    if last_comma > max_length * 0.5:
        return truncated[:last_comma]
    
    # Tenta cortar em espaço
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.7:
        return truncated[:last_space]
    
    # Fallback: corta no limite
    return truncated


def is_text_too_long(text: str) -> bool:
    """Verifica se um texto excede o limite recomendado."""
    return len(text) > MAX_TEXT_LENGTH


# =============================================================================
# NORMALIZAÇÃO
# =============================================================================

def normalize_text(text: str) -> str:
    """
    Normaliza texto removendo acentos e caracteres especiais.
    
    Usa unidecode se disponível, fallback para remoção manual.
    """
    try:
        from unidecode import unidecode
        return unidecode(text.lower())
    except ImportError:
        # Fallback simples
        replacements = {
            'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a',
            'é': 'e', 'è': 'e', 'ê': 'e',
            'í': 'i', 'ì': 'i',
            'ó': 'o', 'ò': 'o', 'ô': 'o', 'õ': 'o',
            'ú': 'u', 'ù': 'u', 'û': 'u',
            'ç': 'c',
        }
        result = text.lower()
        for src, dst in replacements.items():
            result = result.replace(src, dst)
        return result

