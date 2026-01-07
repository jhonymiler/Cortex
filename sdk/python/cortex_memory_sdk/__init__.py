"""
Cortex Memory SDK - Cliente para serviço Cortex.

O SDK faz preparo local (extração, normalização) e
comunica com a API Cortex remota.

Example:
    from cortex_memory_sdk import CortexMemorySDK
    
    sdk = CortexMemorySDK(namespace="customer_support:user_123")
    
    # Armazena
    sdk.remember({
        "verb": "solicitou",
        "subject": "carlos",
        "object": "reembolso",
    })
    
    # Busca
    result = sdk.recall("Carlos")
    print(result.to_prompt_context())
"""

from .client import CortexMemorySDK
from .contracts import Action, W5H, RecallResult
from .normalizer import action_to_w5h, normalize_term
from .extractor import extract_action, remove_memory_marker, has_memory_marker

__version__ = "0.1.0"

__all__ = [
    # Cliente principal
    "CortexMemorySDK",
    
    # Contratos
    "Action",
    "W5H",
    "RecallResult",
    
    # Utilitários
    "action_to_w5h",
    "normalize_term",
    "extract_action",
    "remove_memory_marker",
    "has_memory_marker",
]

