"""
Extractor - Extrai Action de texto livre.

Executado LOCALMENTE no SDK.
100% DETERMINÍSTICO. Sem LLM.
"""

import re
from typing import Optional

from .contracts import Action


def extract_action(text: str) -> Optional[Action]:
    """
    Tenta extrair Action de texto livre.
    
    Retorna None se não conseguir extrair.
    """
    if not text or not text.strip():
        return None
    
    # 1. Marcadores explícitos
    action = _extract_from_markers(text)
    if action:
        return action
    
    # 2. Regex patterns
    action = _extract_from_patterns(text)
    if action:
        return action
    
    return None


def _extract_from_markers(text: str) -> Optional[Action]:
    """Extrai de marcadores [MEM ...] ou [MEMORY]...[/MEMORY]."""
    
    # Pattern: [MEM verb="x" subject="y" object="z" /]
    pattern = r'\[MEM\s+verb="([^"]+)"(?:\s+subject="([^"]*)")?(?:\s+object="([^"]*)")?(?:\s+modifiers="([^"]*)")?\s*/?\]'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return Action(
            verb=match.group(1),
            subject=match.group(2) or "",
            object=match.group(3) or "",
            modifiers=tuple(m.strip() for m in (match.group(4) or "").split(",") if m.strip()),
        )
    
    # Pattern: [MEMORY]...[/MEMORY]
    memory_pattern = r'\[MEMORY\](.*?)\[/MEMORY\]'
    match = re.search(memory_pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        return _parse_memory_block(match.group(1))
    
    return None


def _parse_memory_block(block: str) -> Optional[Action]:
    """Parseia bloco [MEMORY]...[/MEMORY]."""
    lines = block.strip().split('\n')
    data = {}
    
    for line in lines:
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            data[key.strip().lower()] = value.strip()
    
    what = data.get("what", "")
    if not what:
        return None
    
    parts = what.split("_", 1)
    verb = parts[0]
    obj = parts[1] if len(parts) > 1 else ""
    
    modifiers = []
    if data.get("how"):
        modifiers.append(data["how"])
    if data.get("why"):
        modifiers.append(data["why"])
    
    return Action(
        verb=verb,
        subject=data.get("who", ""),
        object=obj,
        modifiers=tuple(modifiers),
    )


def _extract_from_patterns(text: str) -> Optional[Action]:
    """Extrai usando regex patterns comuns."""
    text_lower = text.lower()
    
    patterns = [
        (r'cliente\s+(\w+)\s+(?:pediu|solicitou)\s+(\w+)', 'solicitou'),
        (r'user\s+(\w+)\s+requested\s+(\w+)', 'requested'),
        (r'(\w+)\s+reportou\s+(.+?)(?:\.|$)', 'reportou'),
    ]
    
    for pattern, default_verb in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return Action(
                verb=default_verb,
                subject=match.group(1),
                object=match.group(2).split()[0],
            )
    
    return None


def remove_memory_marker(text: str) -> str:
    """Remove marcador de memória do texto."""
    text = re.sub(r'\[MEM\s+[^]]+/?\]', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\[MEMORY\].*?\[/MEMORY\]', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()


def has_memory_marker(text: str) -> bool:
    """Verifica se texto contém marcador de memória."""
    return bool(
        re.search(r'\[MEM\s', text, re.IGNORECASE) or
        re.search(r'\[MEMORY\]', text, re.IGNORECASE)
    )

