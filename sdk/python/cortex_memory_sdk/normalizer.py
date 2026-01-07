"""
Normalizer - Converte Action para W5H.

Executado LOCALMENTE no SDK antes de enviar ao serviço.
100% DETERMINÍSTICO.
"""

import re
from datetime import datetime

from .contracts import Action, W5H


def normalize_term(term: str) -> str:
    """
    Normaliza termo para formato padrão.
    
    - Lowercase
    - Remove acentos (se unidecode disponível)
    - Substitui espaços/pontuação por _
    """
    if not term:
        return ""
    
    try:
        from unidecode import unidecode
        term = unidecode(term)
    except ImportError:
        pass
    
    term = term.lower().strip()
    term = re.sub(r'[^a-z0-9_]', '_', term)
    term = re.sub(r'_+', '_', term)
    return term.strip('_')


def action_to_w5h(
    action: Action,
    namespace: str = "default",
    reason: str | None = None,
) -> W5H:
    """
    Converte Action para W5H.
    
    Regras FIXAS:
        who   ← subject
        what  ← verb + "_" + object
        how   ← modifiers.join("_")
        when  ← now()
        where ← namespace
        why   ← somente se explícito
    """
    who = normalize_term(action.subject) if action.subject else ""
    
    what_parts = [action.verb]
    if action.object:
        what_parts.append(action.object)
    what = "_".join(normalize_term(p) for p in what_parts if p)
    
    how = ""
    if action.modifiers:
        how = "_".join(normalize_term(m) for m in action.modifiers if m)
    
    when = datetime.now().isoformat()
    where = normalize_term(namespace) if namespace else "default"
    why = normalize_term(reason) if reason else ""
    
    return W5H(
        who=who,
        what=what,
        when=when,
        where=where,
        how=how,
        why=why,
    )

