"""
Full Comparison Benchmark - Cortex vs RAG vs Mem0 vs Baseline

Executa benchmark completo comparando:
1. Baseline (sem memória)
2. RAG (TF-IDF / ChromaDB)
3. Mem0 (salience extraction)
4. Cortex (W5H + Decay + Consolidation)

Inclui:
- Múltiplas sessões por domínio
- Volta de usuários (test returning users)
- DreamAgent entre sessões (consolidação)
- Métricas científicas (Precision@K, Recall@K, MRR)

Uso:
    python full_comparison_benchmark.py --quick   # Rápido (1 conv/domínio)
    python full_comparison_benchmark.py --full    # Completo (3 conv/domínio)
    python full_comparison_benchmark.py --with-chromadb  # Usa ChromaDB real
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Silencia logs verbosos do LiteLLM
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Força flush imediato para ver output em tempo real
import functools
print = functools.partial(print, flush=True)

# Adiciona paths
benchmark_path = Path(__file__).parent
project_root = benchmark_path.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(benchmark_path))
sdk_path = project_root / "sdk" / "python"
sys.path.insert(0, str(sdk_path))

# Imports locais
from agents import BaselineAgent
from cortex_agent import CortexAgent
from rag_agent import RAGAgent
from mem0_agent import Mem0Agent
from conversation_generator import ConversationGenerator

# Import DreamAgent
try:
    from src.cortex.workers.dream_agent import DreamAgent
    DREAM_AGENT_AVAILABLE = True
except ImportError:
    DREAM_AGENT_AVAILABLE = False


@dataclass
class AgentResult:
    """Resultado de um agente em uma mensagem."""
    response: str
    tokens: int
    latency_ms: float
    context_used: str = ""
    memories_retrieved: int = 0


@dataclass
class SessionResult:
    """Resultado de uma sessão."""
    session_id: int
    messages: list[dict] = field(default_factory=list)
    total_tokens: dict[str, int] = field(default_factory=dict)
    total_latency: dict[str, float] = field(default_factory=dict)
    is_returning_user: bool = False


@dataclass
class ConversationResult:
    """Resultado de uma conversa completa."""
    domain: str
    user_id: str
    sessions: list[SessionResult] = field(default_factory=list)
    consolidated: bool = False


@dataclass 
class BenchmarkResults:
    """Resultados completos do benchmark."""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    config: dict = field(default_factory=dict)
    conversations: list[ConversationResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "timestamp": self.timestamp,
            "config": self.config,
            "conversations": [
                {
                    "domain": c.domain,
                    "user_id": c.user_id,
                    "consolidated": c.consolidated,
                    "sessions": [
                        {
                            "session_id": s.session_id,
                            "is_returning_user": s.is_returning_user,
                            "messages": s.messages,
                            "total_tokens": s.total_tokens,
                            "total_latency": s.total_latency,
                        }
                        for s in c.sessions
                    ],
                }
                for c in self.conversations
            ],
            "summary": self.summary,
        }


class FullComparisonBenchmark:
    """
    Benchmark completo comparando todos os sistemas de memória.
    """
    
    AGENTS = ["baseline", "rag", "mem0", "cortex"]
    
    def __init__(
        self,
        ollama_url: str = None,
        model: str = None,
        cortex_url: str = None,
        use_chromadb: bool = False,
        verbose: bool = True,
    ):
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma3:4b")
        self.cortex_url = cortex_url or os.getenv("CORTEX_API_URL", "http://localhost:8000")
        self.use_chromadb = use_chromadb
        self.verbose = verbose
        
        # Inicializa agentes
        self._agents = {}
        self._init_agents()
        
        # Gerador de conversas
        self._conversation_gen = ConversationGenerator()
        
        # Resultados
        self.results = BenchmarkResults()
    
    def _init_agents(self):
        """Inicializa todos os agentes."""
        print(f"🔧 Inicializando agentes...")
        print(f"   Ollama URL: {self.ollama_url}")
        print(f"   Model: {self.model}")
        print(f"   Cortex URL: {self.cortex_url}")
        
        # Baseline (sem memória)
        self._agents["baseline"] = BaselineAgent(
            model=self.model,
            ollama_url=self.ollama_url,
        )
        print("   ✅ Baseline")
        
        # RAG
        self._agents["rag"] = RAGAgent(
            model=self.model,
            ollama_url=self.ollama_url,
            use_chromadb=self.use_chromadb,
        )
        print(f"   ✅ RAG {'(ChromaDB)' if self.use_chromadb else '(TF-IDF)'}")
        
        # Mem0
        self._agents["mem0"] = Mem0Agent(
            model=self.model,
            ollama_url=self.ollama_url,
            use_real_mem0=False,  # Usa simples para velocidade
        )
        print("   ✅ Mem0")
        
        # Cortex
        self._agents["cortex"] = CortexAgent(
            model=self.model,
            ollama_url=self.ollama_url,
            cortex_url=self.cortex_url,
        )
        print("   ✅ Cortex")
    
    def _clear_all_memories(self, namespace: str):
        """Limpa memórias de todos os agentes."""
        # RAG
        self._agents["rag"].clear_memory()
        
        # Mem0
        self._agents["mem0"].clear_memory()
        
        # Cortex
        self._agents["cortex"].clear_namespace()
    
    def _set_namespace(self, namespace: str):
        """Define namespace para todos os agentes."""
        self._agents["rag"].namespace = namespace
        self._agents["mem0"].set_namespace(namespace)
        self._agents["cortex"].set_namespace(namespace)
    
    def _run_dream_agent(self, namespace: str) -> dict:
        """Executa DreamAgent para consolidar memórias."""
        if not DREAM_AGENT_AVAILABLE:
            return {"success": False, "error": "DreamAgent not available"}
        
        try:
            agent = DreamAgent(
                cortex_url=self.cortex_url,
                llm_url=self.ollama_url,
                llm_model=self.model,
            )
            result = agent.dream(namespace=namespace)
            return {
                "success": result.success,
                "analyzed": result.memories_analyzed,
                "refined": result.memories_refined,
                "entities": result.entities_extracted,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _process_message(
        self,
        agent_name: str,
        user_message: str,
    ) -> AgentResult:
        """Processa uma mensagem com um agente específico."""
        agent = self._agents[agent_name]
        
        start_time = time.time()
        
        if agent_name == "baseline":
            response = agent.process_message(user_message)
            return AgentResult(
                response=response.content,
                tokens=response.total_tokens,
                latency_ms=response.response_time_ms,
            )
        
        elif agent_name == "rag":
            response = agent.process_message(user_message)
            return AgentResult(
                response=response.content,
                tokens=response.total_tokens,
                latency_ms=response.latency_ms,
                context_used=response.context_from_rag,
                memories_retrieved=response.documents_retrieved,
            )
        
        elif agent_name == "mem0":
            response = agent.process_message(user_message)
            return AgentResult(
                response=response.content,
                tokens=response.total_tokens,
                latency_ms=response.latency_ms,
                context_used=response.context_from_memory,
                memories_retrieved=response.memories_retrieved,
            )
        
        elif agent_name == "cortex":
            response = agent.process_message(user_message)
            return AgentResult(
                response=response.content,
                tokens=response.total_tokens,
                latency_ms=response.response_time_ms,
                context_used=response.context_from_memory or "",
                memories_retrieved=response.memory_entities + response.memory_episodes,
            )
    
    def run_conversation(
        self,
        domain: str,
        num_sessions: int = 2,
        consolidate_between_sessions: bool = True,
    ) -> ConversationResult:
        """
        Executa uma conversa completa com múltiplas sessões.
        
        Args:
            domain: Domínio do cenário
            num_sessions: Número de sessões (2+ para testar volta de usuário)
            consolidate_between_sessions: Se deve rodar DreamAgent entre sessões
        """
        namespace = f"bench_{domain}_{datetime.now().strftime('%H%M%S')}"
        user_id = f"user_{domain}"
        
        # PRIMEIRO configura o novo namespace, DEPOIS limpa
        # (cada namespace é único, então não há dados para limpar)
        self._set_namespace(namespace)
        # Limpa apenas RAG e Mem0 (namespace novo do Cortex já está vazio)
        self._agents["rag"].clear_memory()
        self._agents["mem0"].clear_memory()
        
        conversation = ConversationResult(
            domain=domain,
            user_id=user_id,
        )
        
        # Gera mensagens para o domínio
        conversations = self._conversation_gen.generate_domain(domain, count=1, sessions=num_sessions)
        
        # Extrai mensagens de todas as sessões
        messages = []
        if conversations:
            for session in conversations[0].sessions:
                for msg in session.messages:
                    messages.append({"role": msg.role, "content": msg.content})
        
        for session_idx in range(num_sessions):
            is_returning = session_idx > 0
            
            if self.verbose:
                print(f"\n{'═' * 60}")
                print(f"📍 {domain.upper()} - SESSÃO {session_idx + 1}/{num_sessions}")
                if is_returning:
                    print(f"   🔄 USUÁRIO RETORNANDO (teste de memória)")
                print(f"{'═' * 60}")
            
            # Nova sessão para cada agente
            for agent_name, agent in self._agents.items():
                if hasattr(agent, 'new_session'):
                    try:
                        agent.new_session(user_id=user_id)
                    except TypeError:
                        # BaselineAgent não aceita user_id
                        agent.new_session()
            
            session = SessionResult(
                session_id=session_idx,
                is_returning_user=is_returning,
            )
            
            # Seleciona mensagens para esta sessão
            session_messages = messages[session_idx * 3:(session_idx + 1) * 3] if len(messages) > 3 else messages
            
            if is_returning:
                # Adiciona pergunta de contexto para testar memória
                session_messages = [
                    {"role": "user", "content": "Olá, sou eu de novo. Você lembra de mim?"},
                    *session_messages[:2],
                ]
            
            for msg_idx, msg in enumerate(session_messages):
                user_message = msg.get("content", msg) if isinstance(msg, dict) else msg
                
                if self.verbose:
                    print(f"\n   ┌{'─' * 56}┐")
                    print(f"   │ 💬 MENSAGEM {msg_idx + 1}/{len(session_messages)}")
                    print(f"   └{'─' * 56}┘")
                    # Mostra mensagem completa (quebra em linhas se muito longa)
                    for i in range(0, len(user_message), 70):
                        prefix = "   │ 👤 " if i == 0 else "   │    "
                        print(f"{prefix}{user_message[i:i+70]}")
                
                msg_result = {"user_message": user_message}
                
                for agent_name in self.AGENTS:
                    try:
                        result = self._process_message(agent_name, user_message)
                        msg_result[f"{agent_name}_response"] = result.response[:200]
                        msg_result[f"{agent_name}_tokens"] = result.tokens
                        msg_result[f"{agent_name}_latency_ms"] = result.latency_ms
                        msg_result[f"{agent_name}_memories"] = result.memories_retrieved
                        
                        session.total_tokens[agent_name] = session.total_tokens.get(agent_name, 0) + result.tokens
                        session.total_latency[agent_name] = session.total_latency.get(agent_name, 0) + result.latency_ms
                        
                        if self.verbose:
                            # Emoji por agente
                            agent_emoji = {"baseline": "⚪", "rag": "🔵", "mem0": "🟣", "cortex": "🟢"}.get(agent_name, "⚫")
                            print(f"   │")
                            print(f"   │ {agent_emoji} {agent_name.upper():10s} │ 🎟️ {result.tokens:4d} tokens │ ⏱️ {result.latency_ms:.0f}ms │ 🧠 {result.memories_retrieved} mems")
                            
                            # Contexto usado (se houver)
                            if result.context_used and agent_name != "baseline":
                                ctx_preview = result.context_used[:100].replace('\n', ' ')
                                print(f"   │   📋 Contexto: {ctx_preview}...")
                            
                            # Resposta (primeiras linhas)
                            response_preview = result.response[:150].replace('\n', ' ')
                            print(f"   │   💭 {response_preview}...")
                        
                    except Exception as e:
                        msg_result[f"{agent_name}_error"] = str(e)
                        print(f"   │ ❌ {agent_name}: {e}")
                
                session.messages.append(msg_result)
                
                if self.verbose:
                    print(f"   └{'─' * 56}┘")
            
            # Sumário da sessão
            if self.verbose:
                print(f"\n   ┌{'─' * 50}┐")
                print(f"   │ 📊 SUMÁRIO SESSÃO {session_idx + 1}")
                print(f"   ├{'─' * 50}┤")
                for agent in self.AGENTS:
                    tokens = session.total_tokens.get(agent, 0)
                    latency = session.total_latency.get(agent, 0)
                    agent_emoji = {"baseline": "⚪", "rag": "🔵", "mem0": "🟣", "cortex": "🟢"}.get(agent, "⚫")
                    print(f"   │ {agent_emoji} {agent:10s}: {tokens:5d} tokens │ {latency:7.0f}ms")
                print(f"   └{'─' * 50}┘")
            
            conversation.sessions.append(session)
            
            # Consolidação entre sessões
            if consolidate_between_sessions and session_idx < num_sessions - 1:
                if self.verbose:
                    print(f"\n   ┌{'─' * 40}┐")
                    print(f"   │ 💭 CONSOLIDAÇÃO (DreamAgent)         │")
                    print(f"   └{'─' * 40}┘")
                
                refine_result = self._run_dream_agent(namespace)
                
                if refine_result.get("success"):
                    if self.verbose:
                        print(f"   │ ✅ Analisadas: {refine_result.get('analyzed', 0)}")
                        print(f"   │ ✅ Refinadas: {refine_result.get('refined', 0)}")
                        print(f"   │ ✅ Entidades: {refine_result.get('entities', 0)}")
                    conversation.consolidated = True
                else:
                    if self.verbose:
                        print(f"   │ ⚠️ Erro: {refine_result.get('error', 'Unknown')}")
        
        return conversation
    
    def run_benchmark(
        self,
        domains: list[str] | None = None,
        conversations_per_domain: int = 1,
        sessions_per_conversation: int = 2,
        consolidate: bool = True,
    ) -> BenchmarkResults:
        """
        Executa benchmark completo.
        
        Args:
            domains: Lista de domínios (None = todos)
            conversations_per_domain: Conversas por domínio
            sessions_per_conversation: Sessões por conversa (2+ testa volta)
            consolidate: Se deve consolidar entre sessões
        """
        domains = domains or list(ConversationGenerator.GENERATORS.keys())
        
        self.results.config = {
            "domains": domains,
            "conversations_per_domain": conversations_per_domain,
            "sessions_per_conversation": sessions_per_conversation,
            "consolidate": consolidate,
            "model": self.model,
            "ollama_url": self.ollama_url,
            "cortex_url": self.cortex_url,
            "use_chromadb": self.use_chromadb,
        }
        
        print("\n" + "=" * 60)
        print(" 🧠 FULL COMPARISON BENCHMARK")
        print("=" * 60)
        print(f"\n📊 Configuração:")
        print(f"   Domínios: {len(domains)}")
        print(f"   Conversas/domínio: {conversations_per_domain}")
        print(f"   Sessões/conversa: {sessions_per_conversation}")
        print(f"   Consolidação: {'✅' if consolidate else '❌'}")
        print(f"   Agentes: {', '.join(self.AGENTS)}")
        
        total_conversations = len(domains) * conversations_per_domain
        
        checkpoint_dir = benchmark_path / "results"
        checkpoint_dir.mkdir(exist_ok=True)
        checkpoint_file = checkpoint_dir / f"full_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.checkpoint.json"
        
        for domain_idx, domain in enumerate(domains):
            print(f"\n{'─' * 40}")
            print(f"📂 Domínio: {domain} ({domain_idx + 1}/{len(domains)})")
            
            for conv_idx in range(conversations_per_domain):
                conversation = self.run_conversation(
                    domain=domain,
                    num_sessions=sessions_per_conversation,
                    consolidate_between_sessions=consolidate,
                )
                self.results.conversations.append(conversation)
            
            # Checkpoint após cada domínio (evita perda de dados)
            self._calculate_summary()
            with open(checkpoint_file, "w") as f:
                json.dump(self.results.to_dict(), f, indent=2, ensure_ascii=False)
            if self.verbose:
                print(f"   💾 Checkpoint salvo ({len(self.results.conversations)} conversas)")
        
        # Calcula sumário final
        self._calculate_summary()
        
        return self.results
    
    def _calculate_summary(self):
        """Calcula sumário dos resultados."""
        summary = {
            "total_conversations": len(self.results.conversations),
            "total_sessions": sum(len(c.sessions) for c in self.results.conversations),
            "total_messages": sum(
                len(s.messages) for c in self.results.conversations for s in c.sessions
            ),
            "consolidated_conversations": sum(1 for c in self.results.conversations if c.consolidated),
        }
        
        # Tokens por agente
        for agent in self.AGENTS:
            total_tokens = sum(
                s.total_tokens.get(agent, 0)
                for c in self.results.conversations
                for s in c.sessions
            )
            summary[f"{agent}_total_tokens"] = total_tokens
        
        # Comparações
        baseline_tokens = summary["baseline_total_tokens"]
        if baseline_tokens > 0:
            for agent in ["rag", "mem0", "cortex"]:
                agent_tokens = summary[f"{agent}_total_tokens"]
                diff_pct = ((agent_tokens - baseline_tokens) / baseline_tokens) * 100
                summary[f"{agent}_vs_baseline_pct"] = round(diff_pct, 2)
        
        # Memórias recuperadas (só para agentes com memória)
        for agent in ["rag", "mem0", "cortex"]:
            total_memories = sum(
                msg.get(f"{agent}_memories", 0)
                for c in self.results.conversations
                for s in c.sessions
                for msg in s.messages
            )
            summary[f"{agent}_total_memories_retrieved"] = total_memories
        
        self.results.summary = summary
    
    def save_results(self, output_path: str | None = None) -> str:
        """Salva resultados em JSON."""
        if output_path is None:
            output_dir = benchmark_path / "results"
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / f"full_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(output_path, "w") as f:
            json.dump(self.results.to_dict(), f, indent=2, ensure_ascii=False)
        
        return str(output_path)
    
    def print_summary(self):
        """Imprime sumário dos resultados."""
        summary = self.results.summary
        
        print("\n" + "=" * 60)
        print(" 📊 SUMÁRIO DO BENCHMARK")
        print("=" * 60)
        
        print(f"\n📈 Métricas Gerais:")
        print(f"   Conversas: {summary.get('total_conversations', 0)}")
        print(f"   Sessões: {summary.get('total_sessions', 0)}")
        print(f"   Mensagens: {summary.get('total_messages', 0)}")
        print(f"   Consolidadas: {summary.get('consolidated_conversations', 0)}")
        
        print(f"\n💰 Tokens por Agente:")
        for agent in self.AGENTS:
            tokens = summary.get(f"{agent}_total_tokens", 0)
            print(f"   {agent:10s}: {tokens:,}")
        
        print(f"\n📊 Comparação vs Baseline:")
        for agent in ["rag", "mem0", "cortex"]:
            diff = summary.get(f"{agent}_vs_baseline_pct", 0)
            emoji = "✅" if diff < 0 else "⚠️" if diff < 10 else "❌"
            sign = "+" if diff > 0 else ""
            print(f"   {emoji} {agent:10s}: {sign}{diff:.1f}%")
        
        print(f"\n🧠 Memórias Recuperadas:")
        for agent in ["rag", "mem0", "cortex"]:
            memories = summary.get(f"{agent}_total_memories_retrieved", 0)
            print(f"   {agent:10s}: {memories:,}")


def main():
    parser = argparse.ArgumentParser(description="Full Comparison Benchmark")
    parser.add_argument("--quick", action="store_true", help="Modo rápido (1 conv/domínio, 2 sessões)")
    parser.add_argument("--full", action="store_true", help="Modo completo (3 conv/domínio, 5 sessões)")
    parser.add_argument("--domains", nargs="+", help="Domínios específicos")
    parser.add_argument("--conversations", type=int, default=1, help="Conversas por domínio")
    parser.add_argument("--sessions", type=int, default=2, help="Sessões por conversa")
    parser.add_argument("--no-consolidate", action="store_true", help="Não consolidar entre sessões")
    parser.add_argument("--with-chromadb", action="store_true", help="Usar ChromaDB para RAG")
    parser.add_argument("-y", "--yes", action="store_true", help="Pular confirmação")
    args = parser.parse_args()
    
    # Configuração
    if args.quick:
        conversations = 1
        sessions = 2
    elif args.full:
        conversations = 3
        sessions = 5
    else:
        conversations = args.conversations
        sessions = args.sessions
    
    domains = args.domains
    consolidate = not args.no_consolidate
    
    # Confirmação
    if not args.yes:
        total_calls = (len(domains or ConversationGenerator.GENERATORS) * conversations * sessions * 
                      len(FullComparisonBenchmark.AGENTS) * 3)  # ~3 msgs/sessão
        print(f"\n⚠️ Este benchmark fará aproximadamente {total_calls} chamadas LLM.")
        response = input("Continuar? (s/N): ")
        if response.lower() not in ["s", "sim", "y", "yes"]:
            print("Cancelado.")
            return
    
    # Executa benchmark
    benchmark = FullComparisonBenchmark(
        use_chromadb=args.with_chromadb,
        verbose=True,
    )
    
    benchmark.run_benchmark(
        domains=domains,
        conversations_per_domain=conversations,
        sessions_per_conversation=sessions,
        consolidate=consolidate,
    )
    
    # Salva e mostra resultados
    output_path = benchmark.save_results()
    print(f"\n📁 Resultados salvos em: {output_path}")
    
    benchmark.print_summary()
    
    # Verificação final de integridade
    print("\n" + "=" * 60)
    print(" 🔍 VERIFICAÇÃO DE INTEGRIDADE")
    print("=" * 60)
    
    # Verifica grafos salvos
    data_dir = Path(__file__).parent.parent / "data"
    saved_graphs = list(data_dir.glob("bench_*/memory_graph.json"))
    valid_graphs = [g for g in saved_graphs if g.stat().st_size > 100]
    
    print(f"\n📊 Grafos de Memória:")
    print(f"   Total de pastas: {len(list(data_dir.glob('bench_*')))}")
    print(f"   Com dados: {len(valid_graphs)}")
    
    if len(valid_graphs) == 0:
        print("   ⚠️  ALERTA: Nenhum grafo com dados! Verifique bug de persistência.")
    else:
        print(f"   ✅ Grafos salvos corretamente")
    
    # Verifica JSON de resultado
    if Path(output_path).exists():
        size = Path(output_path).stat().st_size
        print(f"\n📄 Arquivo de Resultado:")
        print(f"   Tamanho: {size:,} bytes")
        print(f"   ✅ Salvo com sucesso")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()

