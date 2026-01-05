#!/usr/bin/env python3
"""
Agente com Cortex via MCP

Integração REAL via Model Context Protocol - cliente MCP Python direto.
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv
import litellm
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Carrega variáveis de ambiente
load_dotenv()

# Desabilita telemetria
os.environ["LITELLM_TELEMETRY"] = "False"


async def chat_with_mcp(
    message: str,
    model: str | None = None,
    ollama_url: str | None = None,
    user_name: str = "user",
    namespace: str | None = None,
) -> str:
    """
    Conversa usando MCP REAL para memória Cortex.
    
    Args:
        message: Mensagem do usuário
        model: Modelo Ollama (usa OLLAMA_MODEL do .env se None)
        ollama_url: URL do Ollama (usa OLLAMA_URL do .env se None)
        user_name: Nome do usuário
        namespace: Namespace para isolamento (usa CORTEX_NAMESPACE do .env se None)
    
    Returns:
        Resposta do assistente
    """
    # Usa variáveis do .env ou valores padrão
    if model is None:
        model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    if ollama_url is None:
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    
    os.environ["OLLAMA_API_BASE"] = ollama_url
    
    # Herda ambiente atual e adiciona config do Cortex
    mcp_env = os.environ.copy()
    mcp_env["CORTEX_DATA_DIR"] = os.getenv("CORTEX_DATA_DIR", str(Path.home() / ".cortex"))
    
    # Define namespace para isolamento de memórias
    # Pode ser: "agent:user", "bot:cliente", "projeto:contexto", etc.
    if namespace is None:
        namespace = os.getenv("CORTEX_NAMESPACE", "default")
    mcp_env["CORTEX_NAMESPACE"] = namespace
    
    # Parâmetros do servidor MCP Cortex
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "cortex.mcp.server"],
        env=mcp_env
    )
    
    try:
        # Conecta ao servidor MCP
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Inicializa sessão MCP
                await session.initialize()
                
                # 1. RECALL - Busca memórias via MCP
                print("  [🧠 MCP recall...]", end="", flush=True)
                recall_result = await session.call_tool("cortex_recall", {"query": message, "limit": 5})
                print(" ✓")
                
                # Extrai conteúdo do recall
                memories_text = "Nenhuma memória relevante"
                if recall_result.content:
                    for content in recall_result.content:
                        if hasattr(content, 'text'):
                            memories_text = content.text
                
                # 2. Monta prompt com memórias
                system_prompt = f"""Você é um assistente útil com memória persistente via MCP.

MEMÓRIAS RELEVANTES:
{memories_text}

Use essas memórias para contextualizar sua resposta."""
                
                # 3. Gera resposta
                print("  [💭 Pensando...]", end="", flush=True)
                response = litellm.completion(
                    model=f"ollama_chat/{model}",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": message}
                    ],
                    api_base=ollama_url
                )
                answer = response.choices[0].message.content
                print(" ✓")
                
                # 4. STORE - Salva via MCP
                print("  [💾 MCP store...]", end="", flush=True)
                await session.call_tool(
                    "cortex_store",
                    {
                        "action": f"conversed_about: {message[:50]}",
                        "outcome": answer[:100],
                        "participants": [
                            {"type": "person", "name": user_name}
                        ] if user_name else []
                    }
                )
                print(" ✓\n")
                
                return answer
    
    except Exception as e:
        raise RuntimeError(f"Erro MCP: {e}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Agente + Cortex MCP (cliente MCP real)",
        epilog="Usa protocolo MCP via stdio para conectar ao cortex-mcp server"
    )
    parser.add_argument("--model", default=None, help="Modelo Ollama (usa OLLAMA_MODEL do .env se não especificado)")
    parser.add_argument("--ollama-url", default=None, help="URL do Ollama (usa OLLAMA_URL do .env se não especificado)")
    parser.add_argument("-i", "--interactive", action="store_true", help="Modo interativo")
    parser.add_argument("--user", default="user", help="Nome do usuário")
    parser.add_argument("--namespace", default=None, help="Namespace para isolamento (ex: 'agent:user', usa CORTEX_NAMESPACE do .env se não especificado)")
    parser.add_argument("--debug", action="store_true", help="Debug LiteLLM")
    parser.add_argument("message", nargs="*", help="Mensagem")
    
    args = parser.parse_args()
    
    if args.debug:
        litellm.set_verbose = True
    
    model_name = args.model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    namespace = args.namespace or os.getenv("CORTEX_NAMESPACE", "default")
    
    print("🔌 Agente com MCP REAL (cliente MCP Python)")
    print(f"🚀 Usando modelo {model_name}")
    print(f"📦 Namespace: {namespace}")
    print("✅ Pronto!\n")
    
    async def interactive_loop():
        """Loop interativo assíncrono."""
        print("💬 Modo interativo (Ctrl+C para sair)")
        print("   Memórias via protocolo MCP\n")
        
        while True:
            try:
                user_input = input("Você: ").strip()
                if not user_input:
                    continue
                if user_input == "/quit":
                    print("👋 Até logo!")
                    break
                
                print("\n🤖 Assistente:")
                response = await chat_with_mcp(
                    user_input,
                    model=args.model,
                    ollama_url=args.ollama_url,
                    user_name=args.user,
                    namespace=args.namespace,
                )
                print(f"{response}\n")
            
            except KeyboardInterrupt:
                print("\n\n👋 Até logo!")
                break
            except Exception as e:
                print(f"❌ Erro: {e}\n")
                if args.debug:
                    import traceback
                    traceback.print_exc()
    
    async def single_message():
        """Processa uma única mensagem."""
        message = " ".join(args.message)
        print(f"📨 Mensagem: {message}\n")
        print("🤖 Assistente:")
        response = await chat_with_mcp(
            message,
            model=args.model,
            ollama_url=args.ollama_url,
            user_name=args.user,
            namespace=args.namespace,
        )
        print(f"{response}\n")
    
    # Executa modo apropriado
    if args.interactive:
        asyncio.run(interactive_loop())
    elif args.message:
        asyncio.run(single_message())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
