#!/usr/bin/env python3
"""
Agente simples com Ollama

Agente genérico usando Ollama via LiteLLM diretamente.
Não conhece Cortex - é completamente agnóstico.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import litellm

# Carrega variáveis de ambiente do .env
load_dotenv()

# Desabilita telemetria do LiteLLM
os.environ["LITELLM_TELEMETRY"] = "False"


def chat(
    message: str,
    model: str | None = None,
    ollama_url: str | None = None
) -> str:
    """
    Envia mensagem para o modelo Ollama.
    
    Args:
        message: Mensagem para enviar
        model: Modelo Ollama (usa OLLAMA_MODEL do .env se None)
        ollama_url: URL do servidor Ollama (usa OLLAMA_URL do .env se None)
    
    Returns:
        Resposta do modelo
    """
    # Usa variáveis do .env ou valores padrão
    if model is None:
        model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    if ollama_url is None:
        ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    
    # Configura LiteLLM para usar Ollama
    os.environ["OLLAMA_API_BASE"] = ollama_url
    
    try:
        # Chama modelo via LiteLLM
        response = litellm.completion(
            model=f"ollama_chat/{model}",
            messages=[{"role": "user", "content": message}],
            api_base=ollama_url
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        raise RuntimeError(f"Erro ao chamar Ollama: {e}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Agente ADK + Ollama")
    parser.add_argument("--ollama-url", default=None, help="URL do Ollama (usa OLLAMA_URL do .env se não especificado)")
    parser.add_argument("--model", default=None, help="Modelo Ollama (usa OLLAMA_MODEL do .env se não especificado)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Modo interativo")
    parser.add_argument("--debug", action="store_true", help="Debug LiteLLM")
    parser.add_argument("message", nargs="*", help="Mensagem")
    
    args = parser.parse_args()
    
    # Debug
    if args.debug:
        litellm.set_verbose = True
    
    # Configuração do modelo
    model_name = args.model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    print(f"🚀 Usando modelo {model_name}...")
    print("✅ Pronto!\n")
    
    if args.interactive:
        print("💬 Modo interativo (Ctrl+C para sair)\n")
        
        while True:
            try:
                user_input = input("Você: ").strip()
                if not user_input:
                    continue
                
                if user_input == "/quit":
                    print("👋 Até logo!")
                    break
                
                print("\n🤖 Assistente:")
                response = chat(user_input, model=args.model, ollama_url=args.ollama_url)
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
        response = chat(message, model=args.model, ollama_url=args.ollama_url)
        print(f"{response}\n")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
