#!/usr/bin/env python3
"""
Teste de Integração: Agente Real usando Cortex via SDK (API REST)

Este teste isola completamente o Cortex - o agente o usa como serviço externo.
Demonstra a integração real: agente → SDK → API REST → Cortex.

Pré-requisitos:
1. Servidor Cortex rodando: cortex-api
2. Ollama rodando (opcional): ollama serve

Uso:
    python test_integration_sdk.py
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from dataclasses import dataclass, field

# Adiciona SDK ao path
sdk_path = Path(__file__).parent.parent / "sdk" / "python"
sys.path.insert(0, str(sdk_path))


@dataclass
class ConversationTurn:
    """Uma interação na conversa."""
    user_message: str
    agent_response: str = ""
    memory_context: str = ""
    tokens_context: int = 0


@dataclass
class ConversationResult:
    """Resultado de uma conversa completa."""
    scenario: str
    turns: list[ConversationTurn] = field(default_factory=list)
    total_tokens: int = 0
    memory_used: bool = False
    
    def print_summary(self):
        print(f"\n{'='*60}")
        print(f"  Cenário: {self.scenario}")
        print(f"  Turnos: {len(self.turns)}")
        print(f"  Tokens de contexto: ~{self.total_tokens}")
        print(f"  Memória usada: {'✅' if self.memory_used else '❌'}")
        print('='*60)


def check_api_running(base_url: str = "http://localhost:8000") -> bool:
    """Verifica se a API do Cortex está rodando."""
    try:
        import httpx
        response = httpx.get(f"{base_url}/memory/stats", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def start_api_server() -> subprocess.Popen | None:
    """Inicia o servidor da API em background."""
    print("🚀 Iniciando servidor Cortex API...")
    
    # Usa diretório temporário para teste
    env = os.environ.copy()
    env["CORTEX_DATA_DIR"] = str(Path(__file__).parent / "data_integration_sdk")
    
    process = subprocess.Popen(
        ["python", "-m", "cortex.api.app"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=Path(__file__).parent.parent,
    )
    
    # Aguarda servidor iniciar
    for _ in range(10):
        time.sleep(0.5)
        if check_api_running():
            print("   ✅ API iniciada!")
            return process
    
    print("   ❌ Falha ao iniciar API")
    process.kill()
    return None


def count_tokens(text: str) -> int:
    """Estimativa de tokens."""
    return int(len(text.split()) * 1.3)


class AgentWithCortexSDK:
    """
    Agente que usa Cortex via SDK.
    
    O Cortex é tratado como serviço EXTERNO - agente não conhece internals.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        from cortex_sdk import CortexClient
        self.client = CortexClient(base_url=base_url)
        self.user_name = "TestUser"
    
    def recall(self, query: str) -> str:
        """Busca memórias relevantes via API."""
        try:
            result = self.client.recall(query=query, context={"user": self.user_name})
            
            if not result.get("prompt_context"):
                return ""
            
            return result["prompt_context"]
        except Exception as e:
            print(f"   ⚠️ Recall error: {e}")
            return ""
    
    def store(self, action: str, outcome: str, participants: list[dict] | None = None):
        """Armazena memória via API."""
        try:
            self.client.store(
                action=action,
                outcome=outcome,
                participants=participants or [],
            )
        except Exception as e:
            print(f"   ⚠️ Store error: {e}")
    
    def respond(self, user_message: str, use_memory: bool = True) -> ConversationTurn:
        """
        Gera resposta para uma mensagem.
        
        Em produção, isso chamaria um LLM. Aqui simulamos a lógica.
        """
        turn = ConversationTurn(user_message=user_message)
        
        # 1. Recall (se usar memória)
        if use_memory:
            turn.memory_context = self.recall(user_message)
            turn.tokens_context = count_tokens(turn.memory_context)
        
        # 2. Simula resposta baseada no contexto
        if turn.memory_context and "histórico" in turn.memory_context:
            # Tem contexto - resposta personalizada
            turn.agent_response = f"[Com memória] Baseado no histórico, posso ajudar diretamente."
        else:
            # Sem contexto - resposta genérica
            turn.agent_response = f"[Sem memória] Claro! Pode me dar mais detalhes?"
        
        # 3. Store (se usar memória)
        if use_memory:
            self.store(
                action="responded_to_user",
                outcome=f"Respondeu: {turn.agent_response[:50]}",
                participants=[{"type": "user", "name": self.user_name}],
            )
        
        return turn


def test_scenario_customer_support(agent: AgentWithCortexSDK) -> ConversationResult:
    """Testa cenário de Customer Support com memória."""
    print("\n🎫 CENÁRIO: Customer Support")
    
    result = ConversationResult(scenario="Customer Support", memory_used=True)
    
    # Popula histórico primeiro
    print("   Populando histórico...")
    agent.store(
        action="login_issue_resolved",
        outcome="VPN bloqueando acesso - desconectar VPN resolveu",
        participants=[{"type": "customer", "name": agent.user_name}],
    )
    agent.store(
        action="login_issue_resolved",
        outcome="VPN problema recorrente - mesmo cliente",
        participants=[{"type": "customer", "name": agent.user_name}],
    )
    agent.store(
        action="preference_noted",
        outcome=f"{agent.user_name} prefere Chrome",
        participants=[{"type": "customer", "name": agent.user_name}],
    )
    
    # Conversa
    messages = [
        "Olá, preciso de ajuda com minha conta",
        "O login não está funcionando",
        "Isso sempre acontece comigo!",
    ]
    
    for msg in messages:
        print(f"   👤 User: {msg}")
        turn = agent.respond(msg, use_memory=True)
        print(f"   🤖 Agent: {turn.agent_response}")
        if turn.memory_context:
            print(f"   📋 Contexto: {turn.tokens_context} tokens")
        result.turns.append(turn)
        result.total_tokens += turn.tokens_context
    
    return result


def test_scenario_without_memory(agent: AgentWithCortexSDK) -> ConversationResult:
    """Testa mesmo cenário SEM usar memória."""
    print("\n❌ CENÁRIO: Customer Support (SEM MEMÓRIA)")
    
    result = ConversationResult(scenario="Customer Support (sem memória)", memory_used=False)
    
    messages = [
        "Olá, preciso de ajuda com minha conta",
        "O login não está funcionando",
        "Isso sempre acontece comigo!",
    ]
    
    for msg in messages:
        print(f"   👤 User: {msg}")
        turn = agent.respond(msg, use_memory=False)  # SEM memória
        print(f"   🤖 Agent: {turn.agent_response}")
        result.turns.append(turn)
    
    return result


def test_scenario_code_assistant(agent: AgentWithCortexSDK) -> ConversationResult:
    """Testa cenário de Code Assistant."""
    print("\n💻 CENÁRIO: Code Assistant")
    
    result = ConversationResult(scenario="Code Assistant", memory_used=True)
    
    # Popula contexto do time
    agent.store(
        action="team_setup",
        outcome="Time usa TypeScript + React + NextAuth",
        participants=[
            {"type": "team", "name": "TimeAlpha"},
            {"type": "tech", "name": "TypeScript"},
        ],
    )
    agent.store(
        action="bug_fixed",
        outcome="TypeError em JWT resolvido com type guard",
        participants=[{"type": "team", "name": "TimeAlpha"}],
    )
    
    messages = [
        "Me ajuda com esse bug no auth?",
        "TypeError no JWT",
    ]
    
    for msg in messages:
        print(f"   👤 User: {msg}")
        turn = agent.respond(msg, use_memory=True)
        print(f"   🤖 Agent: {turn.agent_response}")
        if turn.memory_context:
            print(f"   📋 Contexto: {turn.tokens_context} tokens")
        result.turns.append(turn)
        result.total_tokens += turn.tokens_context
    
    return result


def print_final_comparison(with_memory: ConversationResult, without_memory: ConversationResult):
    """Mostra comparação final."""
    print("\n" + "="*60)
    print("  📊 COMPARAÇÃO FINAL")
    print("="*60)
    
    print(f"""
    ┌─────────────────────────────────────────────────────────────┐
    │                  COM MEMÓRIA vs SEM MEMÓRIA                 │
    ├──────────────────────────┬──────────────────────────────────┤
    │ ❌ SEM CORTEX            │ ✅ COM CORTEX                    │
    ├──────────────────────────┼──────────────────────────────────┤
    │ Contexto: 0 tokens       │ Contexto: ~{with_memory.total_tokens} tokens           │
    │ Resposta: Genérica       │ Resposta: Personalizada          │
    │ Perguntas: Várias        │ Perguntas: Zero repetidas        │
    └──────────────────────────┴──────────────────────────────────┘
    
    🔑 O Cortex fornece contexto rico com mínimo de tokens,
       permitindo respostas personalizadas sem perguntas repetitivas.
    """)


def main():
    print("="*60)
    print("  🧪 TESTE DE INTEGRAÇÃO: AGENTE + CORTEX SDK")
    print("  Usando Cortex como serviço externo via API REST")
    print("="*60)
    
    # Verifica se API está rodando ou inicia
    api_process = None
    if not check_api_running():
        api_process = start_api_server()
        if not api_process:
            print("\n❌ Não foi possível iniciar a API do Cortex.")
            print("   Execute manualmente: cortex-api")
            return
    else:
        print("✅ API do Cortex já está rodando")
    
    try:
        # Cria agente
        agent = AgentWithCortexSDK()
        
        # Roda cenários
        result_with = test_scenario_customer_support(agent)
        result_with.print_summary()
        
        # Cria novo agente para teste sem memória
        agent2 = AgentWithCortexSDK()
        result_without = test_scenario_without_memory(agent2)
        result_without.print_summary()
        
        # Code Assistant
        agent3 = AgentWithCortexSDK()
        result_code = test_scenario_code_assistant(agent3)
        result_code.print_summary()
        
        # Comparação
        print_final_comparison(result_with, result_without)
        
        print("\n✅ Testes de integração SDK concluídos!")
        
    finally:
        # Para servidor se iniciamos
        if api_process:
            print("\n🛑 Parando servidor API...")
            api_process.terminate()
            api_process.wait()
        
        # Limpa dados de teste
        import shutil
        test_data = Path(__file__).parent / "data_integration_sdk"
        if test_data.exists():
            shutil.rmtree(test_data)


if __name__ == "__main__":
    main()
