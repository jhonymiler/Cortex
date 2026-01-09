"""
Cortex MCP Server - Model Context Protocol para Cortex Memory

Servidor MCP minimalista com apenas as ferramentas essenciais.

"Cortex, porque agentes inteligentes precisam de memória inteligente"

Ferramentas disponíveis:
- store_memory: Armazena uma memória
- recall_memory: Recupera memórias relevantes
- get_current_context: Mostra o contexto atual
"""

import os
import logging
import json
from pathlib import Path
from typing import Optional

import requests
from mcp.server.fastmcp import FastMCP

# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

CORTEX_API_URL = os.getenv("CORTEX_API_URL", "http://localhost:8000")
CORTEX_TEAM = os.getenv("CORTEX_TEAM", "default_team")
CORTEX_USER = os.getenv("CORTEX_USER", os.getenv("USER", "anonymous"))
CORTEX_PROJECT = os.getenv("CORTEX_PROJECT", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cortex-mcp")


# =============================================================================
# DETECÇÃO AUTOMÁTICA DE PROJETO
# =============================================================================

def detect_project_from_cwd() -> str:
    """Detecta o nome do projeto baseado no diretório atual."""
    if CORTEX_PROJECT:
        return CORTEX_PROJECT
    
    cwd = Path.cwd()
    
    # Tenta pyproject.toml
    pyproject = cwd / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text()
            for line in content.split("\n"):
                if line.strip().startswith("name"):
                    name = line.split("=")[1].strip().strip('"').strip("'")
                    return _normalize_name(name)
        except Exception:
            pass
    
    # Tenta package.json
    package_json = cwd / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text())
            if "name" in data:
                return _normalize_name(data["name"])
        except Exception:
            pass
    
    # Fallback: nome do diretório
    return _normalize_name(cwd.name)


def _normalize_name(name: str) -> str:
    """Normaliza nome para uso em namespace."""
    normalized = "".join(c if c.isalnum() or c == "_" else "_" for c in name.lower())
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def get_full_namespace(project_override: Optional[str] = None) -> str:
    """Retorna o namespace completo: {team}:{project}:{user}"""
    project = project_override or detect_project_from_cwd()
    return f"{CORTEX_TEAM}:{project}:{CORTEX_USER}"


# =============================================================================
# API CLIENT
# =============================================================================

def _api_call(method: str, endpoint: str, namespace: str = None, **kwargs) -> dict:
    """Faz chamada à API do Cortex."""
    url = f"{CORTEX_API_URL}{endpoint}"
    
    headers = kwargs.pop("headers", {})
    headers["Content-Type"] = "application/json"
    if namespace:
        headers["X-Cortex-Namespace"] = namespace
    
    try:
        response = requests.request(method, url, timeout=30, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API error: {e}")
        return {"error": str(e)}


# =============================================================================
# SERVIDOR MCP
# =============================================================================

mcp = FastMCP(
    name="Cortex Memory",
    instructions="Sistema de memória cognitiva. Use recall_memory antes de responder e store_memory após interações importantes."
)


# =============================================================================
# TOOLS (apenas 3 essenciais)
# =============================================================================

@mcp.tool()
def get_current_context() -> dict:
    """
    Retorna o contexto atual (team, project, user).
    
    Returns:
        Informações do contexto atual
    """
    project = detect_project_from_cwd()
    return {
        "team": CORTEX_TEAM,
        "project": project,
        "user": CORTEX_USER,
        "namespace": get_full_namespace(project),
        "cwd": str(Path.cwd())
    }


@mcp.tool()
def store_memory(
    content: str,
    visibility: str = "personal",
    importance: float = 0.5
) -> dict:
    """
    Armazena uma memória no Cortex.
    
    Args:
        content: Texto descrevendo o acontecimento/informação
        visibility: "personal" (só você), "shared" (projeto) ou "learned" (time)
        importance: 0.0 a 1.0 (afeta retenção)
    
    Returns:
        Resultado da operação
    
    Examples:
        - store_memory("O cliente João prefere contato por email")
        - store_memory("Bug resolvido: pool de conexões", visibility="shared")
    """
    namespace = get_full_namespace()
    
    payload = {
        "who": [CORTEX_USER],
        "what": content,
        "why": "mcp_store",
        "how": content,
        "where": namespace,
        "visibility": visibility,
        "importance": importance,
        "owner_id": CORTEX_USER
    }
    
    result = _api_call("POST", "/memory/remember", namespace=namespace, json=payload)
    result["namespace_used"] = namespace
    return result


@mcp.tool()
def recall_memory(
    query: str,
    limit: int = 5
) -> dict:
    """
    Recupera memórias relevantes para uma query.
    
    Args:
        query: Texto da busca (linguagem natural, sinônimos funcionam)
        limit: Máximo de resultados
    
    Returns:
        Lista de memórias relevantes com contexto formatado
    
    Examples:
        - recall_memory("preferências do cliente")
        - recall_memory("como resolver erro de conexão")
    """
    namespace = get_full_namespace()
    
    payload = {
        "query": query,
        "limit": limit,
        "context": {
            "who": [CORTEX_USER]
        }
    }
    
    result = _api_call("POST", "/memory/recall", namespace=namespace, json=payload)
    result["namespace_used"] = namespace
    return result


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Inicia o servidor MCP."""
    project = detect_project_from_cwd()
    
    logger.info("🧠 Cortex MCP Server (minimal)")
    logger.info(f"   API: {CORTEX_API_URL}")
    logger.info(f"   Namespace: {get_full_namespace()}")
    
    mcp.run()


if __name__ == "__main__":
    main()
