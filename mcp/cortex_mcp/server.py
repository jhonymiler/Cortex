"""
Cortex MCP Server - Model Context Protocol para Cortex Memory

Servidor MCP que expõe as funcionalidades do Cortex para Claude Desktop
e outros clientes MCP compatíveis.

"Cortex, porque agentes inteligentes precisam de memória inteligente"

Hierarquia de Namespace:
    {team}:{project}:{user}
    
    - team: Organização/time (fixo via env)
    - project: Projeto/sala/contexto (dinâmico, detectado automaticamente)
    - user: Usuário atual (fixo via env)

Exemplos:
    - IDE: dev_team:cortex:jhony → dev_team:outro_projeto:jhony
    - Suporte: suporte:financeiro:maria → suporte:tecnico:maria
    - Multi-agentes: agents:sales_crew:bot_1

4 Dimensões de Valor:
- 🧠 Cognição Biológica (50%) - Decay, consolidação, hubs
- 👥 Memória Coletiva (75%) - Herança hierárquica, isolamento
- 🎯 Valor Semântico (100%) - Sinônimos, threshold adaptativo
- ⚡ Eficiência (100%) - 16ms latência, tokens compactos
"""

import os
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests
from mcp.server.fastmcp import FastMCP

# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

CORTEX_API_URL = os.getenv("CORTEX_API_URL", "http://localhost:8000")

# Namespace hierárquico: {team}:{project}:{user}
CORTEX_TEAM = os.getenv("CORTEX_TEAM", "default_team")
CORTEX_USER = os.getenv("CORTEX_USER", os.getenv("USER", "anonymous"))
CORTEX_PROJECT = os.getenv("CORTEX_PROJECT", "")  # Se vazio, detecta automaticamente

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cortex-mcp")


# =============================================================================
# DETECÇÃO AUTOMÁTICA DE PROJETO
# =============================================================================

def detect_project_from_cwd() -> str:
    """
    Detecta o nome do projeto baseado no diretório atual.
    
    Estratégia de detecção (em ordem):
    1. Variável CORTEX_PROJECT (se definida)
    2. Nome em pyproject.toml
    3. Nome em package.json
    4. Nome em .git (nome do repo)
    5. Nome do diretório atual
    """
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
                    # name = "cortex-memory" → cortex-memory
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
    
    # Tenta .git
    git_dir = cwd / ".git"
    if git_dir.exists():
        # Pega o nome do remote origin ou do diretório
        try:
            config = (git_dir / "config").read_text()
            for line in config.split("\n"):
                if "url = " in line:
                    # git@github.com:user/repo.git → repo
                    url = line.split("=")[1].strip()
                    name = url.split("/")[-1].replace(".git", "")
                    return _normalize_name(name)
        except Exception:
            pass
    
    # Fallback: nome do diretório
    return _normalize_name(cwd.name)


def _normalize_name(name: str) -> str:
    """Normaliza nome para uso em namespace."""
    # Remove caracteres especiais, mantém letras, números, underscore
    normalized = "".join(c if c.isalnum() or c == "_" else "_" for c in name.lower())
    # Remove underscores duplicados
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized.strip("_")


def get_full_namespace(project_override: Optional[str] = None) -> str:
    """
    Retorna o namespace completo: {team}:{project}:{user}
    
    Níveis de memória coletiva:
    - team level: Memória compartilhada de todo o time
    - project level: Memória do projeto específico
    - user level: Memória pessoal do usuário
    """
    project = project_override or detect_project_from_cwd()
    return f"{CORTEX_TEAM}:{project}:{CORTEX_USER}"


def get_team_namespace() -> str:
    """Namespace do time (memória coletiva máxima)."""
    return CORTEX_TEAM


def get_project_namespace(project_override: Optional[str] = None) -> str:
    """Namespace do projeto (memória coletiva do projeto)."""
    project = project_override or detect_project_from_cwd()
    return f"{CORTEX_TEAM}:{project}"


# =============================================================================
# CONTEXTO ATUAL (para resources)
# =============================================================================

_current_project: Optional[str] = None

def set_current_project(project: str):
    """Define o projeto atual manualmente."""
    global _current_project
    _current_project = project
    logger.info(f"Projeto alterado para: {project}")

def get_current_project() -> str:
    """Retorna o projeto atual."""
    return _current_project or detect_project_from_cwd()


# =============================================================================
# API CLIENT
# =============================================================================

def _api_call(method: str, endpoint: str, **kwargs) -> dict:
    """Faz chamada à API do Cortex."""
    url = f"{CORTEX_API_URL}{endpoint}"
    try:
        response = requests.request(method, url, timeout=30, **kwargs)
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
    instructions="Sistema de memória cognitiva para agentes LLM. "
                 "Namespace hierárquico: {team}:{project}:{user}. "
                 "Use recall_memory antes de responder e store_memory após interações importantes."
)


# =============================================================================
# TOOLS - Gerenciamento de Contexto
# =============================================================================

@mcp.tool()
def switch_project(project: str) -> dict:
    """
    Muda o projeto/contexto atual.
    
    Use quando precisar trabalhar em outro projeto sem mudar de diretório.
    O projeto é o nível intermediário do namespace: {team}:{project}:{user}
    
    Args:
        project: Nome do projeto (ex: "cortex", "outro_projeto", "sales_crew")
    
    Returns:
        Novo namespace ativo
    
    Examples:
        - switch_project("cortex")
        - switch_project("cliente_xyz")
        - switch_project("sales_bot")
    """
    set_current_project(project)
    return {
        "success": True,
        "namespace": get_full_namespace(project),
        "team": CORTEX_TEAM,
        "project": project,
        "user": CORTEX_USER,
        "message": f"Contexto alterado para projeto '{project}'"
    }


@mcp.tool()
def get_current_context() -> dict:
    """
    Retorna o contexto atual (team, project, user).
    
    Útil para verificar em qual namespace você está operando.
    
    Returns:
        Informações do contexto atual
    """
    project = get_current_project()
    return {
        "team": CORTEX_TEAM,
        "project": project,
        "user": CORTEX_USER,
        "namespace_user": get_full_namespace(project),
        "namespace_project": get_project_namespace(project),
        "namespace_team": get_team_namespace(),
        "detected_from": "env" if CORTEX_PROJECT else "cwd",
        "cwd": str(Path.cwd())
    }


# =============================================================================
# TOOLS - Operações de Memória
# =============================================================================

@mcp.tool()
def store_memory(
    content: str,
    visibility: str = "personal",
    importance: float = 0.5,
    project: Optional[str] = None
) -> dict:
    """
    Armazena uma memória no Cortex.
    
    O namespace é construído automaticamente: {team}:{project}:{user}
    
    Níveis de visibilidade determinam quem pode ver:
    - personal: Só você (usuário)
    - shared: Todo o projeto (todos os usuários do projeto)
    - learned: Todo o time (padrões aprendidos, anonimizados)
    
    Args:
        content: Texto descrevendo o acontecimento/informação
        visibility: "personal", "shared" ou "learned"
        importance: 0.0 a 1.0 (afeta decay)
        project: Override do projeto (se None, usa atual)
    
    Returns:
        Resultado da operação
    
    Examples:
        - store_memory("Descobri que o bug era no pool de conexões")
        - store_memory("Padrão: sempre verificar logs antes de debug", visibility="shared")
        - store_memory("Este cliente prefere comunicação formal", visibility="personal")
    """
    namespace = get_full_namespace(project)
    
    payload = {
        "content": content,
        "namespace": namespace,
        "visibility": visibility,
        "importance": importance
    }
    
    result = _api_call("POST", "/memory/store", json=payload)
    result["namespace_used"] = namespace
    return result


@mcp.tool()
def recall_memory(
    query: str,
    scope: str = "all",
    limit: int = 5,
    project: Optional[str] = None
) -> dict:
    """
    Recupera memórias relevantes para uma query.
    
    O scope determina de onde buscar:
    - "personal": Só suas memórias pessoais
    - "project": Suas + compartilhadas do projeto
    - "team": Todas (incluindo aprendizados do time)
    - "all": Equivalente a "team" (default)
    
    Args:
        query: Texto da busca (linguagem natural, sinônimos funcionam)
        scope: "personal", "project", "team" ou "all"
        limit: Máximo de resultados
        project: Override do projeto (se None, usa atual)
    
    Returns:
        Lista de memórias relevantes
    
    Examples:
        - recall_memory("como resolver erro de conexão")
        - recall_memory("preferências do cliente", scope="personal")
        - recall_memory("padrões de debug", scope="team")
    """
    proj = project or get_current_project()
    
    # Define namespace baseado no scope
    if scope == "personal":
        namespace = get_full_namespace(proj)
        include_shared = False
    elif scope == "project":
        namespace = get_full_namespace(proj)
        include_shared = True
    else:  # team ou all
        namespace = get_full_namespace(proj)
        include_shared = True
    
    params = {
        "query": query,
        "namespace": namespace,
        "limit": limit,
        "include_shared": include_shared
    }
    
    result = _api_call("GET", "/memory/recall", params=params)
    result["scope_used"] = scope
    result["namespace_used"] = namespace
    return result


@mcp.tool()
def share_with_team(
    content: str,
    importance: float = 0.7
) -> dict:
    """
    Compartilha conhecimento com todo o time.
    
    Use para padrões, soluções e aprendizados que beneficiam todos.
    A memória é armazenada no nível do time com visibility="learned".
    
    Args:
        content: Conhecimento a compartilhar
        importance: 0.0 a 1.0 (default 0.7 - conhecimento importante)
    
    Returns:
        Resultado da operação
    
    Examples:
        - share_with_team("Padrão: sempre usar connection pool em produção")
        - share_with_team("Bug comum: timeout de 30s não é suficiente para relatórios")
    """
    # Armazena no nível do time
    payload = {
        "content": content,
        "namespace": get_team_namespace(),
        "visibility": "learned",
        "importance": importance
    }
    
    result = _api_call("POST", "/memory/store", json=payload)
    result["shared_with"] = "team"
    result["namespace_used"] = get_team_namespace()
    return result


@mcp.tool()
def share_with_project(
    content: str,
    importance: float = 0.6,
    project: Optional[str] = None
) -> dict:
    """
    Compartilha conhecimento com todo o projeto.
    
    Use para informações específicas do projeto que todos os
    colaboradores devem saber.
    
    Args:
        content: Conhecimento a compartilhar
        importance: 0.0 a 1.0
        project: Override do projeto
    
    Returns:
        Resultado da operação
    
    Examples:
        - share_with_project("Este projeto usa PostgreSQL 15 com pgvector")
        - share_with_project("Cliente prefere deploy às sextas após 18h")
    """
    proj = project or get_current_project()
    
    payload = {
        "content": content,
        "namespace": get_project_namespace(proj),
        "visibility": "shared",
        "importance": importance
    }
    
    result = _api_call("POST", "/memory/store", json=payload)
    result["shared_with"] = "project"
    result["namespace_used"] = get_project_namespace(proj)
    return result


@mcp.tool()
def get_entity(
    name: str,
    project: Optional[str] = None
) -> dict:
    """
    Recupera informações sobre uma entidade.
    
    Entidades são "coisas" (pessoas, conceitos, objetos) que
    aparecem nas memórias.
    
    Args:
        name: Nome da entidade
        project: Override do projeto
    
    Returns:
        Dados da entidade
    """
    namespace = get_full_namespace(project)
    params = {"namespace": namespace}
    return _api_call("GET", f"/entity/{name}", params=params)


@mcp.tool()
def list_entities(
    entity_type: Optional[str] = None,
    limit: int = 20,
    project: Optional[str] = None
) -> dict:
    """
    Lista entidades conhecidas.
    
    Args:
        entity_type: Filtrar por tipo ("person", "concept", etc.)
        limit: Máximo de resultados
        project: Override do projeto
    
    Returns:
        Lista de entidades
    """
    namespace = get_full_namespace(project)
    params = {"namespace": namespace, "limit": limit}
    if entity_type:
        params["type"] = entity_type
    return _api_call("GET", "/entities", params=params)


@mcp.tool()
def consolidate_memories(
    scope: str = "project",
    similarity_threshold: float = 0.85,
    project: Optional[str] = None
) -> dict:
    """
    Consolida memórias similares (DreamAgent).
    
    Args:
        scope: "personal", "project" ou "team"
        similarity_threshold: Quão similares devem ser (0.85 = 85%)
        project: Override do projeto
    
    Returns:
        Resultado da consolidação
    """
    if scope == "personal":
        namespace = get_full_namespace(project)
    elif scope == "project":
        namespace = get_project_namespace(project)
    else:
        namespace = get_team_namespace()
    
    payload = {
        "namespace": namespace,
        "similarity_threshold": similarity_threshold
    }
    return _api_call("POST", "/memory/consolidate", json=payload)


@mcp.tool()
def get_memory_stats(
    scope: str = "project",
    project: Optional[str] = None
) -> dict:
    """
    Retorna estatísticas do grafo de memória.
    
    Args:
        scope: "personal", "project" ou "team"
        project: Override do projeto
    
    Returns:
        Estatísticas
    """
    if scope == "personal":
        namespace = get_full_namespace(project)
    elif scope == "project":
        namespace = get_project_namespace(project)
    else:
        namespace = get_team_namespace()
    
    params = {"namespace": namespace}
    return _api_call("GET", "/memory/stats", params=params)


# =============================================================================
# RESOURCES
# =============================================================================

@mcp.resource("cortex://context")
def current_context() -> str:
    """Contexto atual (team, project, user)."""
    ctx = get_current_context()
    return f"""
# Contexto Atual

- **Team**: {ctx['team']}
- **Project**: {ctx['project']}
- **User**: {ctx['user']}

## Namespaces

| Scope | Namespace |
|-------|-----------|
| User (personal) | `{ctx['namespace_user']}` |
| Project (shared) | `{ctx['namespace_project']}` |
| Team (learned) | `{ctx['namespace_team']}` |

Detectado de: {ctx['detected_from']}
CWD: {ctx['cwd']}
"""


@mcp.resource("cortex://health")
def health_check() -> str:
    """Status de saúde do servidor Cortex."""
    result = _api_call("GET", "/health")
    if "error" in result:
        return f"❌ Cortex offline: {result['error']}"
    return "✅ Cortex online e saudável"


@mcp.resource("cortex://about")
def about() -> str:
    """Informações sobre o Cortex Memory."""
    return """
# 🧠 Cortex Memory

> "Cortex, porque agentes inteligentes precisam de memória inteligente"

## Hierarquia de Namespace

```
{team}:{project}:{user}
  │        │        └── Memória pessoal
  │        └── Memória do projeto (shared)
  └── Memória do time (learned)
```

## 4 Dimensões de Valor

| Dimensão | Score | Exclusivo? |
|----------|-------|------------|
| 🧠 Cognição Biológica | 50% | ✅ |
| 👥 Memória Coletiva | 75% | ✅ |
| 🎯 Valor Semântico | 100% | Empata |
| ⚡ Eficiência | 100% | ✅ |

**Score Total: 83%** (vs 40% das alternativas)

## Scopes de Memória

| Scope | Quem vê | Uso |
|-------|---------|-----|
| personal | Só você | Preferências, notas pessoais |
| project | Time do projeto | Decisões, padrões do projeto |
| team | Toda organização | Aprendizados gerais |
"""


# =============================================================================
# PROMPTS
# =============================================================================

@mcp.prompt()
def remember_context() -> str:
    """Prompt para usar memória no contexto."""
    ctx = get_current_context()
    return f"""
Você tem acesso ao Cortex Memory. Contexto atual:
- Team: {ctx['team']}
- Project: {ctx['project']}
- User: {ctx['user']}

Antes de responder:
1. Use `recall_memory` para buscar contexto relevante
2. Considere histórico e preferências

Após interações importantes:
1. Use `store_memory` para dados pessoais
2. Use `share_with_project` para conhecimento do projeto
3. Use `share_with_team` para padrões universais

Sinônimos funcionam! Se não encontrar, tente variações.
"""


@mcp.prompt()
def new_project_context(project_name: str) -> str:
    """Prompt para iniciar contexto em novo projeto."""
    return f"""
Iniciando contexto no projeto: {project_name}

Execute: switch_project("{project_name}")

Depois busque contexto existente:
1. recall_memory("visão geral do projeto", scope="project")
2. recall_memory("padrões e decisões", scope="project")
3. recall_memory("stack e tecnologias", scope="project")
"""


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Inicia o servidor MCP."""
    project = get_current_project()
    
    logger.info("🧠 Iniciando Cortex MCP Server...")
    logger.info(f"   API URL: {CORTEX_API_URL}")
    logger.info(f"   Team: {CORTEX_TEAM}")
    logger.info(f"   Project: {project} (detected)")
    logger.info(f"   User: {CORTEX_USER}")
    logger.info(f"   Full namespace: {get_full_namespace()}")
    
    mcp.run()


if __name__ == "__main__":
    main()

