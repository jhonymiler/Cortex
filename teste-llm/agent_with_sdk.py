#!/usr/bin/env python3
"""
Agente com Cortex via SDK

Integração direta usando biblioteca específica do Cortex.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import litellm

# Carrega variáveis de ambiente
load_dotenv()

# Desabilita telemetria do LiteLLM
os.environ["LITELLM_TELEMETRY"] = "False"

# Adiciona SDK ao path
sdk_path = Path(__file__).parent.parent / "sdk" / "python"
sys.path.insert(0, str(sdk_path))

from cortex_sdk import CortexClient, make_participant


# Cliente Cortex (biblioteca específica)
cortex_client = CortexClient(base_url=os.getenv("CORTEX_API_URL", "http://localhost:8000"))


def recall_memory(query: str) -> str:
    """Busca memórias relevantes."""
    result = cortex_client.recall(query=query, context={})
    
    if not result.get("success"):
        return "Nenhuma memória encontrada."
    
    output = []
    for e in result.get("entities", [])[:3]:
        output.append(f"• {e['name']} ({e['type']})")
    for ep in result.get("episodes", [])[:3]:
        output.append(f"• {ep['action']}: {ep['outcome']}")
    
    return "\n".join(output) or "Nenhuma memória relevante."


def store_memory(action: str, outcome: str, participant: str = "") -> str:
    """Armazena uma memória."""
    participants = [make_participant("person", participant)] if participant else []
    result = cortex_client.store(action=action, outcome=outcome, participants=participants)
    
    return "✅ Memória salva" if result.get("success") else "❌ Erro ao salvar"


def chat_with_memory(
    message: str,
    model: str | None = None,
    ollama_url: str | None = None,
    user_name: str = "user"
) -> str:
    """
    Conversa com memória integrada ao Cortex.
    
    Args:
        message: Mensagem do usuário
        model: Modelo Ollama
        ollama_url: URL do Ollama
        user_name: Nome do usuário para armazenar memória
    
    Returns:
        Resposta do assistente
    """
    # Usa variáveis do .env ou valores padrão
    if model is None:
        model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    if ollama_url is None:
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    
    os.environ["OLLAMA_API_BASE"] = ollama_url
    
    try:
        # 1. RECALL - Busca memórias relevantes
        print("  [🧠 Buscando memórias...]", end="")
        memories = recall_memory(message)
        print(" ✓")
        
        # 2. Monta prompt com contexto
        system_prompt = f"""Você é um assistente útil com memória persistente.

MEMÓRIAS RELEVANTES:
{memories}

Use essas memórias para dar respostas mais contextualizadas."""
        
        # 3. Gera resposta
        print("  [💭 Pensando...]", end="")
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
        
        # 4. STORE - Armazena a interação
        print("  [💾 Salvando memória...]", end="")
        store_memory(
            action=f"conversed_about: {message[:50]}",
            outcome=answer[:100],
            participant=user_name
        )
        print(" ✓\n")
        
        return answer
    
    except Exception as e:
        raise RuntimeError(f"Erro ao processar mensagem: {e}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Agente + Cortex SDK")
    parser.add_argument("--model", default=None, help="Modelo Ollama (usa OLLAMA_MODEL do .env se não especificado)")
    parser.add_argument("--ollama-url", default=None, help="URL do Ollama")
    parser.add_argument("-i", "--interactive", action="store_true", help="Modo interativo")
    parser.add_argument("--user", default="user", help="Nome do usuário")
    parser.add_argument("--debug", action="store_true", help="Debug LiteLLM")
    parser.add_argument("message", nargs="*", help="Mensagem")
    
    args = parser.parse_args()
    
    if args.debug:
        litellm.set_verbose = True
    
    # Valida Cortex
    print("🔗 Verificando Cortex API...")
    health = cortex_client.health_check()
    if not health.get("status") == "healthy":
        print("❌ Cortex API não disponível!")
        print("   Certifique-se de que está rodando: cortex-api")
        return
    
    model_name = args.model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    print(f"✅ Cortex SDK conectado")
    print(f"🚀 Usando modelo {model_name}")
    print("✅ Pronto!\n")
    
    if args.interactive:
        print("💬 Modo interativo (Ctrl+C para sair)")
        print("   Memórias são buscadas e salvas automaticamente\n")
        
        while True:
            try:
                user_input = input("Você: ").strip()
                if not user_input:
                    continue
                if user_input == "/quit":
                    print("👋 Até logo!")
                    break
                
                print("\n🤖 Assistente:")
                response = chat_with_memory(
                    user_input,
                    model=args.model,
                    ollama_url=args.ollama_url,
                    user_name=args.user
                )
                print(f"{response}\n")
            
            except KeyboardInterrupt:
                print("\n\n👋 Até logo!")
                break
            except Exception as e:
                print(f"❌ Erro: {e}\n")
    
    elif args.message:
        message = " ".join(args.message)
        print(f"📨 Mensagem: {message}\n")
        print("🤖 Assistente:")
        response = chat_with_memory(
            message,
            model=args.model,
            ollama_url=args.ollama_url,
            user_name=args.user
        )
        print(f"{response}\n")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
