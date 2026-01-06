"""
Benchmark Framework - Executor e Avaliador de Benchmark

Executa conversas com ambos os agentes e coleta métricas reais.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Adiciona SDK ao path
sdk_path = Path(__file__).parent.parent / "sdk" / "python"
sys.path.insert(0, str(sdk_path))

# Imports condicionais para funcionar como script e como módulo
try:
    from .agents import BaselineAgent, CortexAgent, AgentResponse, call_llm_with_retry
    from .conversation_generator import (
        ConversationGenerator,
        Conversation,
        Session,
        Message,
    )
except ImportError:
    from agents import BaselineAgent, CortexAgent, AgentResponse, call_llm_with_retry
    from conversation_generator import (
        ConversationGenerator,
        Conversation,
        Session,
        Message,
    )


@dataclass
class MessageResult:
    """Resultado de uma mensagem processada."""
    message: str
    expected_recalls: list[str]  # O que deveria lembrar
    
    # Respostas
    baseline_response: str
    cortex_response: str
    
    # Métricas baseline
    baseline_tokens: int
    baseline_prompt_tokens: int
    baseline_time_ms: float
    
    # Métricas cortex
    cortex_tokens: int
    cortex_prompt_tokens: int
    cortex_time_ms: float
    cortex_recall_time_ms: float
    cortex_store_time_ms: float
    cortex_memory_entities: int
    cortex_memory_episodes: int
    cortex_context_used: str
    
    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "expected_recalls": self.expected_recalls,
            "baseline_response": self.baseline_response,
            "cortex_response": self.cortex_response,
            "baseline_tokens": self.baseline_tokens,
            "baseline_prompt_tokens": self.baseline_prompt_tokens,
            "baseline_time_ms": self.baseline_time_ms,
            "cortex_tokens": self.cortex_tokens,
            "cortex_prompt_tokens": self.cortex_prompt_tokens,
            "cortex_time_ms": self.cortex_time_ms,
            "cortex_recall_time_ms": self.cortex_recall_time_ms,
            "cortex_store_time_ms": self.cortex_store_time_ms,
            "cortex_memory_entities": self.cortex_memory_entities,
            "cortex_memory_episodes": self.cortex_memory_episodes,
            "cortex_context_used": self.cortex_context_used,
        }


@dataclass
class SessionResult:
    """Resultado de uma sessão."""
    session_index: int
    key_facts: list[str]
    expected_recalls: list[str]
    messages: list[MessageResult] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "session_index": self.session_index,
            "key_facts": self.key_facts,
            "expected_recalls": self.expected_recalls,
            "messages": [m.to_dict() for m in self.messages],
        }


@dataclass
class ConversationResult:
    """Resultado de uma conversa completa."""
    conversation_id: str
    domain: str
    user_profile: dict
    sessions: list[SessionResult] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "domain": self.domain,
            "user_profile": self.user_profile,
            "sessions": [s.to_dict() for s in self.sessions],
        }


@dataclass
class BenchmarkResult:
    """Resultado completo do benchmark."""
    started_at: datetime
    finished_at: datetime | None = None
    model: str = ""
    conversations: list[ConversationResult] = field(default_factory=list)
    baseline_stats: dict = field(default_factory=dict)
    cortex_stats: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": (
                (self.finished_at - self.started_at).total_seconds()
                if self.finished_at else None
            ),
            "model": self.model,
            "total_conversations": len(self.conversations),
            "total_sessions": sum(len(c.sessions) for c in self.conversations),
            "total_messages": sum(
                sum(len(s.messages) for s in c.sessions)
                for c in self.conversations
            ),
            "baseline_stats": self.baseline_stats,
            "cortex_stats": self.cortex_stats,
            "conversations": [c.to_dict() for c in self.conversations],
        }


class BenchmarkRunner:
    """Executor de benchmark."""
    
    def __init__(
        self,
        model: str = "deepseek-v3.1:671b-cloud",
        ollama_url: str = "http://localhost:11434",
        cortex_url: str = "http://localhost:8000",
        namespace: str = "benchmark",
        verbose: bool = True,
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.cortex_url = cortex_url
        self.namespace = namespace
        self.verbose = verbose
        
        # Inicializa agentes
        self.baseline = BaselineAgent(
            model=model,
            ollama_url=ollama_url,
        )
        
        self.cortex_agent = CortexAgent(
            model=model,
            ollama_url=ollama_url,
            cortex_url=cortex_url,
            namespace=namespace,
        )
    
    def _log(self, msg: str, end: str = "\n") -> None:
        if self.verbose:
            print(msg, end=end, flush=True)
    
    def verify_services(self) -> bool:
        """Verifica se Ollama e Cortex estão disponíveis."""
        self._log("🔍 Verificando serviços...")
        
        # Verifica Ollama (com retry para rate limit)
        try:
            response = call_llm_with_retry(
                model=f"ollama_chat/{self.model}",
                messages=[{"role": "user", "content": "ok"}],
                api_base=self.ollama_url,
            )
            self._log(f"   ✅ Ollama ({self.model}) funcionando")
        except Exception as e:
            self._log(f"   ❌ Ollama não disponível: {e}")
            return False
        
        # Verifica Cortex
        try:
            health = self.cortex_agent.cortex.health_check()
            if not health:
                self._log("   ❌ Cortex API não saudável")
                return False
            self._log(f"   ✅ Cortex API funcionando")
        except Exception as e:
            self._log(f"   ❌ Cortex API não disponível: {e}")
            return False
        
        return True
    
    def run_conversation(self, conversation: Conversation) -> ConversationResult:
        """Executa uma conversa com ambos os agentes."""
        user_id = conversation.user_profile.get("name", "user")
        user_id = user_id.lower().replace(" ", "_")
        
        result = ConversationResult(
            conversation_id=conversation.id,
            domain=conversation.domain,
            user_profile=conversation.user_profile,
        )
        
        self._log(f"\n📋 Conversa: {conversation.domain} - {user_id}")
        
        for session_idx, session in enumerate(conversation.sessions):
            self._log(f"   📅 Sessão {session_idx + 1}/{len(conversation.sessions)}", end="")
            
            # Inicia nova sessão em ambos os agentes
            self.baseline.new_session()
            self.cortex_agent.new_session(user_id=user_id)
            
            session_result = SessionResult(
                session_index=session_idx,
                key_facts=session.key_facts,
                expected_recalls=session.expected_recalls,
            )
            
            # Processa apenas mensagens do usuário
            user_messages = [m for m in session.messages if m.role == "user"]
            
            for msg in user_messages:
                # Processa com baseline
                baseline_resp = self.baseline.process_message(
                    msg.content,
                    user_context={"domain": conversation.domain},
                )
                
                # Processa com cortex
                cortex_resp = self.cortex_agent.process_message(
                    msg.content,
                    user_context={
                        "domain": conversation.domain,
                        "user_id": user_id,
                    },
                )
                
                msg_result = MessageResult(
                    message=msg.content,
                    expected_recalls=session.expected_recalls,
                    baseline_response=baseline_resp.content,
                    cortex_response=cortex_resp.content,
                    baseline_tokens=baseline_resp.total_tokens,
                    baseline_prompt_tokens=baseline_resp.prompt_tokens,
                    baseline_time_ms=baseline_resp.response_time_ms,
                    cortex_tokens=cortex_resp.total_tokens,
                    cortex_prompt_tokens=cortex_resp.prompt_tokens,
                    cortex_time_ms=cortex_resp.response_time_ms,
                    cortex_recall_time_ms=cortex_resp.recall_time_ms,
                    cortex_store_time_ms=cortex_resp.store_time_ms,
                    cortex_memory_entities=cortex_resp.memory_entities,
                    cortex_memory_episodes=cortex_resp.memory_episodes,
                    cortex_context_used=cortex_resp.context_from_memory,
                )
                
                session_result.messages.append(msg_result)
                self._log(".", end="")
            
            result.sessions.append(session_result)
            self._log(" ✓")
        
        return result
    
    def run_benchmark(
        self,
        conversations: list[Conversation],
        clear_memory_before: bool = True,
    ) -> BenchmarkResult:
        """
        Executa benchmark completo.
        
        Args:
            conversations: Lista de conversas para processar
            clear_memory_before: Se deve limpar a memória do Cortex antes
            
        Returns:
            BenchmarkResult com todas as métricas
        """
        result = BenchmarkResult(
            started_at=datetime.now(),
            model=self.model,
        )
        
        self._log("=" * 60)
        self._log("🚀 INICIANDO BENCHMARK")
        self._log(f"   Modelo: {self.model}")
        self._log(f"   Conversas: {len(conversations)}")
        self._log(f"   Sessões: {sum(len(c.sessions) for c in conversations)}")
        self._log("=" * 60)
        
        # Limpa memória se solicitado
        if clear_memory_before:
            self._log("\n🧹 Limpando memória do benchmark anterior...")
            self.cortex_agent.clear_namespace()
            self._log("   ✓ Memória limpa")
        
        # Processa cada conversa
        for idx, conv in enumerate(conversations):
            self._log(f"\n[{idx + 1}/{len(conversations)}]", end="")
            conv_result = self.run_conversation(conv)
            result.conversations.append(conv_result)
        
        # Coleta estatísticas finais
        result.baseline_stats = self.baseline.get_stats()
        result.cortex_stats = self.cortex_agent.get_stats()
        result.finished_at = datetime.now()
        
        self._log("\n" + "=" * 60)
        self._log("✅ BENCHMARK COMPLETO")
        self._log(f"   Duração: {(result.finished_at - result.started_at).total_seconds():.1f}s")
        self._log("=" * 60)
        
        return result
    
    def save_result(self, result: BenchmarkResult, filepath: Path | str) -> None:
        """Salva resultado em arquivo JSON."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        
        self._log(f"\n💾 Resultado salvo em: {filepath}")


class MetricsEvaluator:
    """Avaliador de métricas do benchmark."""
    
    def __init__(self, result: BenchmarkResult | dict):
        if isinstance(result, dict):
            self.data = result
        else:
            self.data = result.to_dict()
    
    def calculate_token_metrics(self) -> dict:
        """Calcula métricas de tokens."""
        baseline_tokens = 0
        cortex_tokens = 0
        baseline_prompt_tokens = 0
        cortex_prompt_tokens = 0
        message_count = 0
        
        for conv in self.data["conversations"]:
            for session in conv["sessions"]:
                for msg in session["messages"]:
                    baseline_tokens += msg["baseline_tokens"]
                    cortex_tokens += msg["cortex_tokens"]
                    baseline_prompt_tokens += msg["baseline_prompt_tokens"]
                    cortex_prompt_tokens += msg["cortex_prompt_tokens"]
                    message_count += 1
        
        # Economia de tokens (negativo = Cortex usou mais por causa do contexto de memória)
        token_diff = baseline_tokens - cortex_tokens
        token_diff_pct = (token_diff / baseline_tokens * 100) if baseline_tokens > 0 else 0
        
        return {
            "total_messages": message_count,
            "baseline": {
                "total_tokens": baseline_tokens,
                "total_prompt_tokens": baseline_prompt_tokens,
                "avg_tokens_per_message": baseline_tokens / message_count if message_count else 0,
            },
            "cortex": {
                "total_tokens": cortex_tokens,
                "total_prompt_tokens": cortex_prompt_tokens,
                "avg_tokens_per_message": cortex_tokens / message_count if message_count else 0,
            },
            "comparison": {
                "token_difference": token_diff,
                "token_difference_pct": token_diff_pct,
                "cortex_overhead": cortex_tokens - baseline_tokens,  # Overhead do contexto de memória
            },
        }
    
    def calculate_time_metrics(self) -> dict:
        """Calcula métricas de tempo."""
        baseline_time = 0
        cortex_time = 0
        cortex_recall_time = 0
        cortex_store_time = 0
        message_count = 0
        
        for conv in self.data["conversations"]:
            for session in conv["sessions"]:
                for msg in session["messages"]:
                    baseline_time += msg["baseline_time_ms"]
                    cortex_time += msg["cortex_time_ms"]
                    cortex_recall_time += msg["cortex_recall_time_ms"]
                    cortex_store_time += msg["cortex_store_time_ms"]
                    message_count += 1
        
        return {
            "total_messages": message_count,
            "baseline": {
                "total_time_ms": baseline_time,
                "avg_time_ms": baseline_time / message_count if message_count else 0,
            },
            "cortex": {
                "total_time_ms": cortex_time,
                "avg_time_ms": cortex_time / message_count if message_count else 0,
                "total_recall_time_ms": cortex_recall_time,
                "avg_recall_time_ms": cortex_recall_time / message_count if message_count else 0,
                "total_store_time_ms": cortex_store_time,
                "avg_store_time_ms": cortex_store_time / message_count if message_count else 0,
            },
            "comparison": {
                "time_difference_ms": baseline_time - cortex_time,
                "cortex_overhead_ms": cortex_time - baseline_time,  # Overhead total
                "memory_overhead_ms": cortex_recall_time + cortex_store_time,  # Overhead de memória
            },
        }
    
    def calculate_memory_metrics(self) -> dict:
        """Calcula métricas de uso de memória."""
        total_entities = 0
        total_episodes = 0
        messages_with_memory = 0
        messages_without_memory = 0
        
        for conv in self.data["conversations"]:
            for session in conv["sessions"]:
                for msg in session["messages"]:
                    entities = msg["cortex_memory_entities"]
                    episodes = msg["cortex_memory_episodes"]
                    total_entities += entities
                    total_episodes += episodes
                    
                    if entities > 0 or episodes > 0:
                        messages_with_memory += 1
                    else:
                        messages_without_memory += 1
        
        total_messages = messages_with_memory + messages_without_memory
        
        return {
            "total_entities_recalled": total_entities,
            "total_episodes_recalled": total_episodes,
            "messages_with_memory": messages_with_memory,
            "messages_without_memory": messages_without_memory,
            "memory_hit_rate": (
                messages_with_memory / total_messages * 100
                if total_messages else 0
            ),
            "avg_entities_per_message": total_entities / total_messages if total_messages else 0,
            "avg_episodes_per_message": total_episodes / total_messages if total_messages else 0,
        }
    
    def calculate_domain_metrics(self) -> dict:
        """Calcula métricas por domínio."""
        domains: dict[str, dict] = {}
        
        for conv in self.data["conversations"]:
            domain = conv["domain"]
            if domain not in domains:
                domains[domain] = {
                    "conversations": 0,
                    "sessions": 0,
                    "messages": 0,
                    "baseline_tokens": 0,
                    "cortex_tokens": 0,
                    "memory_hits": 0,
                }
            
            domains[domain]["conversations"] += 1
            domains[domain]["sessions"] += len(conv["sessions"])
            
            for session in conv["sessions"]:
                for msg in session["messages"]:
                    domains[domain]["messages"] += 1
                    domains[domain]["baseline_tokens"] += msg["baseline_tokens"]
                    domains[domain]["cortex_tokens"] += msg["cortex_tokens"]
                    if msg["cortex_memory_entities"] > 0 or msg["cortex_memory_episodes"] > 0:
                        domains[domain]["memory_hits"] += 1
        
        # Calcula médias
        for domain, stats in domains.items():
            msg_count = stats["messages"]
            stats["avg_baseline_tokens"] = stats["baseline_tokens"] / msg_count if msg_count else 0
            stats["avg_cortex_tokens"] = stats["cortex_tokens"] / msg_count if msg_count else 0
            stats["memory_hit_rate"] = stats["memory_hits"] / msg_count * 100 if msg_count else 0
        
        return domains
    
    def generate_summary(self) -> dict:
        """Gera resumo completo do benchmark."""
        return {
            "overview": {
                "model": self.data.get("model", "unknown"),
                "duration_seconds": self.data.get("duration_seconds"),
                "total_conversations": self.data.get("total_conversations"),
                "total_sessions": self.data.get("total_sessions"),
                "total_messages": self.data.get("total_messages"),
            },
            "token_metrics": self.calculate_token_metrics(),
            "time_metrics": self.calculate_time_metrics(),
            "memory_metrics": self.calculate_memory_metrics(),
            "domain_metrics": self.calculate_domain_metrics(),
            "agent_stats": {
                "baseline": self.data.get("baseline_stats", {}),
                "cortex": self.data.get("cortex_stats", {}),
            },
        }
    
    def print_summary(self) -> None:
        """Imprime resumo formatado."""
        summary = self.generate_summary()
        
        print("\n" + "=" * 70)
        print("📊 RESUMO DO BENCHMARK")
        print("=" * 70)
        
        # Overview
        ov = summary["overview"]
        print(f"\n🔧 Configuração:")
        print(f"   Modelo: {ov['model']}")
        print(f"   Duração: {ov['duration_seconds']:.1f}s")
        print(f"   Conversas: {ov['total_conversations']}")
        print(f"   Sessões: {ov['total_sessions']}")
        print(f"   Mensagens: {ov['total_messages']}")
        
        # Tokens
        tok = summary["token_metrics"]
        print(f"\n📝 Tokens:")
        print(f"   Baseline: {tok['baseline']['total_tokens']:,} total ({tok['baseline']['avg_tokens_per_message']:.1f} avg)")
        print(f"   Cortex:   {tok['cortex']['total_tokens']:,} total ({tok['cortex']['avg_tokens_per_message']:.1f} avg)")
        overhead = tok['comparison']['cortex_overhead']
        print(f"   Overhead: {overhead:+,} tokens ({overhead / tok['baseline']['total_tokens'] * 100:+.1f}%)")
        
        # Tempo
        tm = summary["time_metrics"]
        print(f"\n⏱️ Tempo:")
        print(f"   Baseline: {tm['baseline']['total_time_ms']/1000:.1f}s total ({tm['baseline']['avg_time_ms']:.0f}ms avg)")
        print(f"   Cortex:   {tm['cortex']['total_time_ms']/1000:.1f}s total ({tm['cortex']['avg_time_ms']:.0f}ms avg)")
        print(f"   Overhead memória: {tm['comparison']['memory_overhead_ms']:.0f}ms (recall: {tm['cortex']['total_recall_time_ms']:.0f}ms, store: {tm['cortex']['total_store_time_ms']:.0f}ms)")
        
        # Memória
        mem = summary["memory_metrics"]
        print(f"\n🧠 Memória Cortex:")
        print(f"   Entidades recuperadas: {mem['total_entities_recalled']}")
        print(f"   Episódios recuperados: {mem['total_episodes_recalled']}")
        print(f"   Taxa de hit: {mem['memory_hit_rate']:.1f}%")
        
        # Domínios
        print(f"\n📋 Por Domínio:")
        for domain, stats in summary["domain_metrics"].items():
            print(f"   {domain}:")
            print(f"      Mensagens: {stats['messages']}, Hit rate: {stats['memory_hit_rate']:.1f}%")
        
        print("\n" + "=" * 70)


def main():
    """Executa benchmark de demonstração."""
    # Gera conversas
    print("🔄 Gerando conversas de teste...")
    generator = ConversationGenerator()
    conversations = generator.generate_all(
        conversations_per_domain=1,  # 1 conversa por domínio para teste rápido
        sessions_per_conversation=3,  # 3 sessões por conversa
    )
    
    print(f"   ✅ {len(conversations)} conversas geradas")
    
    # Cria runner
    runner = BenchmarkRunner(
        model=os.getenv("OLLAMA_MODEL", "deepseek-v3.1:671b-cloud"),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        cortex_url=os.getenv("CORTEX_API_URL", "http://localhost:8000"),
    )
    
    # Verifica serviços
    if not runner.verify_services():
        print("\n❌ Serviços não disponíveis. Certifique-se de que:")
        print("   1. Ollama está rodando: ollama serve")
        print("   2. Cortex API está rodando: cortex-api")
        return
    
    # Executa benchmark
    result = runner.run_benchmark(conversations)
    
    # Salva resultado
    output_path = Path(__file__).parent / "results" / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    runner.save_result(result, output_path)
    
    # Avalia e imprime resumo
    evaluator = MetricsEvaluator(result)
    evaluator.print_summary()
    
    # Salva resumo
    summary_path = output_path.with_suffix(".summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(evaluator.generate_summary(), f, ensure_ascii=False, indent=2)
    print(f"\n📊 Resumo salvo em: {summary_path}")


if __name__ == "__main__":
    main()
