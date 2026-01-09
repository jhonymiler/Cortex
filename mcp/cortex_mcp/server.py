"""
Cortex MCP Server - Model Context Protocol para Cortex Memory

Servidor MCP com contrato W5H (Who, What, Why, When, Where, How) para LLMs.

"Cortex, porque agentes inteligentes precisam de memória inteligente"

=== FERRAMENTAS ===

store_memory(what, why, how?, who?, where?, visibility?, importance?)
    Armazena memória estruturada no formato W5H.
    
    Formatos aceitos:
    - W5H direto: what="solicitou_reembolso", why="produto_defeito"
    - Action: what="[verbo]_[objeto]" → normalizado automaticamente
    - Texto: what="cliente pediu reembolso" → normalizado

recall_memory(query, limit?, who?, where?)
    Busca semântica híbrida com suporte a sinônimos.
    Use ANTES de responder para contexto personalizado.

get_current_context()
    Retorna namespace atual (team:project:user).

=== MODELO W5H ===

| Campo | Pergunta        | Exemplo                          |
|-------|-----------------|----------------------------------|
| what  | O que aconteceu | "solicitou_reembolso"            |
| why   | Por quê         | "produto_com_defeito"            |
| how   | Como resolveu   | "aprovado_credito_loja"          |
| who   | Quem participou | "cliente_joao, atendente_maria"  |
| where | Onde/contexto   | "suporte:ticket_123"             |

=== VISIBILIDADE ===

- personal: Só você (preferências, notas)
- shared: Time do projeto (decisões, bugs)
- learned: Toda organização (aprendizados)

=== NORMALIZAÇÃO ===

Termos são normalizados automaticamente:
- Lowercase, sem acentos, underscores
- "Solicitou Reembolso" → "solicitou_reembolso"
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
    instructions="""Sistema de memória cognitiva W5H para agentes de IA.

QUANDO USAR:
- recall_memory: ANTES de responder — busca contexto, preferências, histórico
- store_memory: APÓS interações importantes — decisões, preferências, bugs, resoluções

FORMATO W5H (Who, What, Why, When, Where, How):
- what: verbo_objeto (ex: "solicitou_reembolso")
- why: causa/motivação (ex: "produto_defeito")
- how: resultado/método (ex: "aprovado")
- who: participantes (ex: "cliente_joao, atendente")
- where: contexto (ex: "suporte:ticket_123")

VISIBILIDADE:
- personal: só você vê
- shared: time do projeto
- learned: toda organização

DICA: Sinônimos funcionam na busca! "erro login" encontra "problema autenticação"."""
)


# =============================================================================
# TOOLS (apenas 3 essenciais)
# =============================================================================

@mcp.tool()
def get_current_context() -> dict:
    """
    Retorna o contexto atual do Cortex.
    
    Use antes de armazenar memórias para verificar o namespace ativo.
    O namespace determina quem pode ver as memórias.
    
    Returns:
        team: Organização/time (fixo via CORTEX_TEAM)
        project: Projeto atual (detectado automaticamente ou via CORTEX_PROJECT)
        user: Usuário atual (fixo via CORTEX_USER)
        namespace: Namespace completo no formato {team}:{project}:{user}
        cwd: Diretório de trabalho atual
    
    Hierarquia de namespace:
        {team}:{project}:{user}
          │        │        └── Memória pessoal (visibility: personal)
          │        └── Memória do projeto (visibility: shared)
          └── Memória do time (visibility: learned)
    
    Example:
        get_current_context()
        # Retorna:
        # {
        #   "team": "dev_team",
        #   "project": "cortex",
        #   "user": "jhony",
        #   "namespace": "dev_team:cortex:jhony",
        #   "cwd": "/home/jhony/projetos/Cortex"
        # }
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
    what: str,
    why: str,
    how: str = "",
    who: str = "",
    where: str = "",
    visibility: str = "personal",
    importance: float = 0.5
) -> dict:
    """
    Armazena uma memória no Cortex usando o contrato W5H.
    
    O modelo W5H estrutura memórias de forma compacta (~36 tokens vs 200+ texto livre).
    Memórias são normalizadas automaticamente: lowercase, sem acentos, underscores.
    
    FORMATOS ACEITOS:
    
    1. W5H Direto (recomendado):
       what="solicitou_reembolso", why="produto_defeito", how="aprovado"
    
    2. Estilo Action (verbo + objeto):
       what="[verbo]_[objeto]" → what="solicitou_reembolso"
    
    3. Texto descritivo curto:
       what="cliente pediu reembolso" → normalizado para "cliente_pediu_reembolso"
    
    Args:
        what: O QUE aconteceu? Ação ou fato principal.
              
              Formato ideal: verbo_objeto (normalizado automaticamente)
              
              Exemplos por domínio:
              - Customer Support: "solicitou_reembolso", "reportou_problema"
              - Desenvolvimento: "corrigiu_bug", "implementou_feature"
              - Roleplay/Games: "confessou_sentimentos", "descobriu_segredo"
              - Healthcare: "relatou_sintomas", "prescreveu_medicamento"
        
        why: POR QUE aconteceu? Causa, motivação ou razão.
             
             Captura o contexto causal — essencial para aprendizado.
             
             Exemplos:
             - "vpn_bloqueando_conexao" (causa técnica)
             - "produto_com_defeito" (motivo do cliente)
             - "conexao_nao_fechada" (root cause)
             - "medo_perder_chance" (motivação emocional)
        
        how: COMO foi resolvido? Resultado, consequência ou método.
             
             Opcional, mas importante para padrões de resolução.
             
             Exemplos:
             - "orientado_desconectar_vpn" (ação tomada)
             - "aprovado_credito_loja" (resolução)
             - "adicionou_connection_pool" (fix técnico)
             - "reciprocidade_confirmada" (outcome)
        
        who: QUEM participou? Nomes ou identificadores.
             
             Formato: nomes separados por vírgula.
             O usuário atual é incluído automaticamente.
             
             Exemplos:
             - "maria@email.com, sistema_auth"
             - "cliente_vip, atendente_joao"
             - "elena, marcus" (personagens)
        
        where: ONDE aconteceu? Contexto, arquivo ou módulo.
               
               Se não informado, usa o namespace atual.
               
               Exemplos:
               - "suporte_cliente:ticket_123"
               - "src/auth/login.py"
               - "fantasia:capitulo_5"
               - "clinica:consulta_2026_01"
        
        visibility: Quem pode ver esta memória?
                   - "personal": Só você (padrão) — preferências, notas
                   - "shared": Time do projeto — decisões, padrões, bugs
                   - "learned": Toda organização — aprendizados gerais
        
        importance: 0.0 a 1.0. Afeta retenção (decaimento de Ebbinghaus).
                   - 0.1-0.3: Baixa (notas temporárias)
                   - 0.4-0.6: Normal (interações comuns)
                   - 0.7-0.9: Alta (bugs críticos, decisões)
                   - 1.0: Máxima (nunca esquecer)
    
    Returns:
        memory_id: ID único da memória
        consolidated: True se foi mesclada com memória similar existente
        retrievability: Score 0.0-1.0 de probabilidade de recuperação
        namespace_used: Namespace onde foi armazenada
    
    Examples:
        # Customer Support
        store_memory(
            what="solicitou_reembolso",
            why="produto_com_defeito",
            how="aprovado_credito_loja",
            who="cliente_vip, atendente_maria",
            where="atendimento:ticket_123",
            visibility="shared"
        )
        
        # Desenvolvimento (bug crítico)
        store_memory(
            what="corrigiu_bug_timeout",
            why="conexao_nao_fechada",
            how="adicionou_connection_pool",
            who="dev_joao, modulo_auth",
            where="src/db/pool.py",
            visibility="shared",
            importance=0.8
        )
        
        # Preferência pessoal
        store_memory(
            what="prefere_contato_email",
            why="responde_mais_rapido",
            who="cliente_carlos"
        )
        
        # Roleplay/Game
        store_memory(
            what="confessou_sentimentos",
            why="medo_perder_chance",
            how="reciprocidade_confirmada",
            who="elena, marcus",
            where="fantasia:capitulo_5"
        )
        
        # Healthcare
        store_memory(
            what="relatou_sintomas_gastrite",
            why="estresse_trabalho",
            how="prescrito_omeprazol",
            who="paciente_carlos, dr_silva",
            where="clinica:consulta_jan",
            visibility="personal"
        )
    """
    namespace = get_full_namespace()
    
    # Monta lista de envolvidos
    who_list = [CORTEX_USER]
    if who:
        who_list.extend([w.strip() for w in who.split(",") if w.strip()])
    
    payload = {
        "who": who_list,
        "what": what,
        "why": why,
        "how": how or what,
        "where": where or namespace,
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
    limit: int = 5,
    who: str = "",
    where: str = ""
) -> dict:
    """
    Recupera memórias relevantes usando busca semântica híbrida.
    
    IMPORTANTE: Use ANTES de responder ao usuário para contexto personalizado.
    
    BUSCA SEMÂNTICA:
    - Sinônimos funcionam: "erro de login" → encontra "problema de autenticação"
    - Linguagem natural: "o que o cliente pediu?" funciona
    - Campos W5H indexados: busca rápida por who, what, where
    
    HIERARQUIA DE VISIBILIDADE (automática):
    - Memórias pessoais (suas)
    - Memórias do projeto (shared)  
    - Memórias do time (learned)
    
    Args:
        query: O QUE buscar? Pergunta ou palavras-chave em linguagem natural.
               
               Tipos de query efetivos:
               - Perguntas: "como resolver erro de conexão?"
               - Contexto: "histórico do cliente João"
               - Padrões: "bugs resolvidos no módulo auth"
               - Preferências: "como o usuário prefere ser contatado?"
               
               Exemplos por domínio:
               - Customer Support: "reclamações do cliente", "última interação"
               - Desenvolvimento: "decisões de arquitetura", "bugs do sprint"
               - Roleplay: "relacionamento entre Elena e Marcus"
               - Healthcare: "histórico de sintomas do paciente"
        
        limit: Máximo de resultados (1-100, padrão: 5).
               
               Recomendações:
               - 1-3: Contexto rápido para resposta
               - 5-10: Análise de histórico
               - 10+: Investigação completa
        
        who: Filtrar por QUEM participou.
             
             Nomes separados por vírgula. Você é incluído automaticamente.
             
             Exemplos:
             - "cliente_joao" (pessoa específica)
             - "dev_maria, tech_lead" (múltiplas pessoas)
             - "sistema_auth" (sistema/módulo)
        
        where: Filtrar por ONDE aconteceu.
               
               Contexto espacial: arquivo, módulo, sistema, local.
               
               Exemplos:
               - "src/db/" (diretório)
               - "suporte_cliente" (departamento)
               - "fantasia:capitulo_5" (contexto narrativo)
    
    Returns:
        memories: Lista de memórias, cada uma com:
            - what: Ação/fato principal
            - why: Causa/motivação
            - how: Resultado/resolução
            - who: Participantes
            - when: Timestamp
            - relevance: Score 0.0-1.0
        
        Formato para injeção em prompt (exemplo):
            who:carlos what:solicitou_reembolso how:aprovado
            who:maria what:reportou_bug how:corrigido
        
        namespace_used: Namespace onde buscou
    
    Examples:
        # Contexto antes de responder
        recall_memory(query="preferências do cliente")
        
        # Investigar bugs por módulo
        recall_memory(
            query="erros de timeout",
            where="src/db/",
            limit=10
        )
        
        # Histórico de pessoa específica
        recall_memory(
            query="decisões e preferências",
            who="tech_lead",
            limit=5
        )
        
        # Última interação com cliente
        recall_memory(
            query="última solicitação",
            who="cliente_joao",
            limit=1
        )
        
        # Padrões de resolução
        recall_memory(
            query="como foram resolvidos bugs de conexão",
            limit=10
        )
        
        # Contexto narrativo (roleplay)
        recall_memory(
            query="relacionamento entre personagens",
            where="fantasia:capitulo_5"
        )
    """
    namespace = get_full_namespace()
    
    # Monta contexto de busca
    context = {"who": [CORTEX_USER]}
    if who:
        context["who"].extend([w.strip() for w in who.split(",") if w.strip()])
    if where:
        context["where"] = where
    
    payload = {
        "query": query,
        "limit": limit,
        "context": context
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
