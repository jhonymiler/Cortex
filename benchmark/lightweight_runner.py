"""
Lightweight Benchmark Runner - Sem comparações LLM em tempo real

Este runner executa o benchmark apenas coletando dados brutos:
- Respostas de baseline e cortex
- Memórias recuperadas
- Métricas de tokens e tempo

NÃO faz comparações semânticas (que gastam tokens).
Análise posterior pode ser feita com um script separado.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from benchmark.agents import BaselineAgent, evaluate_responses
from benchmark.cortex_agent import CortexAgent
from benchmark.conversation_generator import Conversation


class LightweightBenchmarkRunner:
    """
    Runner otimizado que apenas COLETA dados,
    sem fazer comparações ou análises que usem LLM.
    
    Usa CortexAgent com extração [MEMORY] inline.
    """
    
    def __init__(
        self,
        model: str | None = None,
        ollama_url: str | None = None,
        cortex_url: str | None = None,
        namespace: str | None = None,
        verbose: bool = True,
        evaluate_responses_llm: bool = False,
        detailed_logs: bool = False,
    ):
        # Usa variáveis de ambiente como fallback
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma3:4b")
        self.ollama_url = ollama_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        cortex_url = cortex_url or os.getenv("CORTEX_API_URL", "http://localhost:8000")
        self.namespace = namespace or os.getenv("CORTEX_NAMESPACE", "benchmark")
        self.verbose = verbose
        self.evaluate_responses_llm = evaluate_responses_llm
        self.detailed_logs = detailed_logs
        
        # Cria agentes
        self.baseline = BaselineAgent(
            model=self.model,
            ollama_url=self.ollama_url,
        )
        
        # CortexAgent com extração [MEMORY] inline
        self.cortex_agent = CortexAgent(
            model=self.model,
            ollama_url=self.ollama_url,
            cortex_url=cortex_url,
            namespace=self.namespace,
        )
    
    def _log(self, message: str, end: str = "\n"):
        """Log condicional."""
        if self.verbose:
            print(message, end=end, flush=True)
    
    def _print_wrapped(self, text: str, prefix: str = "", max_width: int = 70):
        """Imprime texto quebrado em múltiplas linhas."""
        import textwrap
        
        if not text:
            print(f"{prefix}(vazio)")
            return
        
        # Remove múltiplos espaços e quebras de linha excessivas
        text = " ".join(text.split())
        
        # Quebra em linhas
        lines = textwrap.wrap(text, width=max_width - len(prefix))
        
        for line in lines:
            print(f"{prefix}{line}")
    
    def verify_services(self) -> bool:
        """Verifica se Ollama e Cortex estão acessíveis."""
        self._log("\n🔍 Verificando serviços...")
        
        try:
            baseline_ok = self.baseline.test_connection()
            self._log(f"   {'✓' if baseline_ok else '✗'} Ollama ({self.model})")
            
            cortex_ok = self.cortex_agent.test_connection()
            self._log(f"   {'✓' if cortex_ok else '✗'} Cortex API")
            
            return baseline_ok and cortex_ok
        except Exception as e:
            self._log(f"   ✗ Erro: {e}")
            return False
    
    def clear_memory(self):
        """Limpa memória do namespace."""
        self._log(f"🧹 Limpando namespace '{self.namespace}'...")
        self.cortex_agent.clear_namespace()
        self._log("   ✓ Memória limpa")
    
    def run_conversation(
        self,
        conversation: Conversation,
        conversation_id: str,
    ) -> dict[str, Any]:
        """
        Executa UMA conversa em ambos agentes.
        
        Coleta apenas dados brutos, sem análises.
        
        IMPORTANTE: Cada conversa/usuário tem seu próprio namespace para evitar
        cross-contamination de memória entre diferentes usuários.
        """
        # Extrai identificador único do usuário
        user_name = conversation.user_profile.get('name', 'user')
        user_id = conversation.user_profile.get('id') or user_name.lower().replace(' ', '_')
        
        # Namespace hierárquico: {base}:{domain}:{user_id}
        # Isso garante isolamento completo por usuário
        user_namespace = f"{self.namespace}:{conversation.domain}:{user_id}"
        self.cortex_agent.set_namespace(user_namespace)
        
        self._log(f"\n📋 Conversa: {conversation.domain} - {user_name} (ns: {user_namespace})")
        
        conv_result = {
            "conversation_id": conversation_id,
            "domain": conversation.domain,
            "user_profile": conversation.user_profile,
            "sessions": [],
        }
        
        # Processa cada sessão
        for session_idx, session in enumerate(conversation.sessions):
            is_returning = session_idx > 0
            
            if self.verbose:
                print(f"\n   {'═' * 50}")
                print(f"   📅 SESSÃO {session_idx + 1}/{len(conversation.sessions)}")
                if is_returning:
                    print(f"   🔄 USUÁRIO RETORNANDO (teste de memória)")
                print(f"   {'═' * 50}")
            
            session_id = f"session_{session_idx}"
            session_result = {
                "session_index": session_idx,
                "session_id": session_id,
                "key_facts": session.key_facts,
                "expected_recalls": session.expected_recalls,
                "messages": [],
            }
            
            # Processa cada mensagem
            for msg_idx, msg in enumerate(session.messages):
                if msg.role != "user":
                    continue  # Só processa mensagens do usuário
                
                user_message = msg.content
                
                # BASELINE: Responde sem memória
                baseline_start = time.time()
                baseline_response = self.baseline.process_message(user_message)
                baseline_time_ms = (time.time() - baseline_start) * 1000
                
                # CORTEX V2: process_message faz recall + generate + store em 1 chamada
                cortex_start = time.time()
                
                cortex_response = self.cortex_agent.process_message(
                    message=user_message,
                )
                
                cortex_time_ms = (time.time() - cortex_start) * 1000
                
                # V2 retorna tempos internos
                recall_time_ms = cortex_response.recall_time_ms
                store_time_ms = cortex_response.store_time_ms
                
                # Coleta dados SEM análise
                # NOTA: expected_recalls está na SESSION, não na Message
                message_result = {
                    "message": user_message,
                    "message_index": msg_idx,
                    
                    # Baseline
                    "baseline_response": baseline_response.content,
                    "baseline_tokens": baseline_response.total_tokens,
                    "baseline_prompt_tokens": baseline_response.prompt_tokens,
                    "baseline_time_ms": baseline_time_ms,
                    
                    # Cortex
                    "cortex_response": cortex_response.content,
                    "cortex_tokens": cortex_response.total_tokens,
                    "cortex_prompt_tokens": cortex_response.prompt_tokens,
                    "cortex_time_ms": cortex_time_ms,
                    "cortex_recall_time_ms": recall_time_ms,
                    "cortex_store_time_ms": store_time_ms,
                    "cortex_memory_entities": cortex_response.memory_entities,
                    "cortex_memory_episodes": cortex_response.memory_episodes,
                    "cortex_context_used": cortex_response.context_from_memory or "",
                    
                    # V2: Memória extraída do [MEMORY] block
                    "cortex_memory_extracted": cortex_response.memory_extracted,
                    "cortex_extracted_memory": cortex_response.extracted_memory or {},
                }
                
                # Avaliação LLM (opcional)
                if self.evaluate_responses_llm:
                    eval_result = evaluate_responses(
                        model=f"ollama_chat/{self.model}",
                        api_base=self.ollama_url,
                        user_message=user_message,
                        baseline_response=baseline_response.content,
                        cortex_response=cortex_response.content,
                        memory_context=cortex_response.context_from_memory or "",
                    )
                    message_result["evaluation"] = eval_result
                    
                    if self.detailed_logs:
                        winner = eval_result.get("winner", "TIE")
                        self._log(f"\n      🏆 Winner: {winner} | B:{eval_result.get('baseline_score', 0):.1f} vs C:{eval_result.get('cortex_score', 0):.1f}")
                
                # Logs detalhados (igual ao full)
                if self.detailed_logs or self.verbose:
                    print(f"\n   ┌{'─' * 70}┐")
                    print(f"   │ 💬 MENSAGEM {msg_idx + 1}")
                    print(f"   └{'─' * 70}┘")
                    
                    # Mensagem do usuário COMPLETA
                    print(f"   │ 👤 USUÁRIO:")
                    self._print_wrapped(user_message, prefix="   │    ", max_width=70)
                    
                    print(f"   │")
                    print(f"   ├{'─' * 70}┤")
                    
                    # Baseline COMPLETO
                    print(f"   │ ⚪ BASELINE  │ 🎟️ {baseline_response.total_tokens:4d} tokens │ ⏱️ {baseline_time_ms:.0f}ms")
                    print(f"   │ 💭 Resposta:")
                    self._print_wrapped(baseline_response.content, prefix="   │    ", max_width=70)
                    
                    print(f"   │")
                    print(f"   ├{'─' * 70}┤")
                    
                    # Cortex COMPLETO
                    mems = cortex_response.memory_entities + cortex_response.memory_episodes
                    print(f"   │ 🟢 CORTEX    │ 🎟️ {cortex_response.total_tokens:4d} tokens │ ⏱️ {cortex_time_ms:.0f}ms │ 🧠 {mems} mems")
                    
                    # CONTEXTO DE MEMÓRIA RECUPERADO (COMPLETO)
                    if cortex_response.context_from_memory:
                        print(f"   │")
                        print(f"   │ 📋 CONTEXTO DE MEMÓRIA RECUPERADO:")
                        self._print_wrapped(cortex_response.context_from_memory, prefix="   │    ", max_width=70)
                    else:
                        print(f"   │ 📋 Contexto: (nenhuma memória recuperada)")
                    
                    print(f"   │")
                    print(f"   │ 💭 Resposta:")
                    self._print_wrapped(cortex_response.content, prefix="   │    ", max_width=70)
                    
                    # MEMÓRIA EXTRAÍDA E SALVA
                    print(f"   │")
                    if cortex_response.memory_extracted:
                        mem = cortex_response.extracted_memory or {}
                        print(f"   │ 💾 MEMÓRIA EXTRAÍDA E SALVA:")
                        print(f"   │    who: {mem.get('who', '?')}")
                        print(f"   │    what: {mem.get('what', '?')}")
                        print(f"   │    why: {mem.get('why', '')}")
                        print(f"   │    how: {mem.get('how', '')}")
                    else:
                        print(f"   │ 💾 Memória: (nenhuma memória extraída desta resposta)")
                    
                    print(f"   └{'─' * 70}┘")
                
                # Logs detalhados antigo (removido, agora usa o visual acima)
                if False and self.detailed_logs:
                    self._log(f"\n      📝 User: {user_message[:60]}...")
                    self._log(f"      🅰️ Baseline ({baseline_response.total_tokens}t): {baseline_response.content[:80]}...")
                    self._log(f"      🅱️ Cortex ({cortex_response.total_tokens}t): {cortex_response.content[:80]}...")
                    if cortex_response.context_from_memory:
                        self._log(f"      🧠 Memory: {cortex_response.context_from_memory[:100]}...")
                    if cortex_response.memory_extracted:
                        self._log(f"      💾 Extracted: {cortex_response.extracted_memory}")
                
                session_result["messages"].append(message_result)
            
            # Sumário da sessão
            if self.verbose:
                total_baseline_tokens = sum(m.get("baseline_tokens", 0) for m in session_result["messages"])
                total_cortex_tokens = sum(m.get("cortex_tokens", 0) for m in session_result["messages"])
                total_baseline_time = sum(m.get("baseline_time_ms", 0) for m in session_result["messages"])
                total_cortex_time = sum(m.get("cortex_time_ms", 0) for m in session_result["messages"])
                
                economy = ((total_baseline_tokens - total_cortex_tokens) / total_baseline_tokens * 100) if total_baseline_tokens > 0 else 0
                
                print(f"\n   ┌{'─' * 45}┐")
                print(f"   │ 📊 SUMÁRIO SESSÃO {session_idx + 1}")
                print(f"   ├{'─' * 45}┤")
                print(f"   │ ⚪ Baseline: {total_baseline_tokens:5d} tokens │ {total_baseline_time:7.0f}ms")
                print(f"   │ 🟢 Cortex:   {total_cortex_tokens:5d} tokens │ {total_cortex_time:7.0f}ms")
                print(f"   │ 💰 Economia: {economy:+.1f}%")
                print(f"   └{'─' * 45}┘")
            
            conv_result["sessions"].append(session_result)
        
        return conv_result
    
    def run_benchmark(
        self,
        conversations: list[Conversation],
        clear_before: bool = True,
        checkpoint_file: Path | str | None = None,
        resume_from: int = 0,
    ) -> dict[str, Any]:
        """
        Executa benchmark completo LEVE.
        
        Args:
            conversations: Lista de conversas
            clear_before: Limpar memória antes (ignorado se resumindo)
            checkpoint_file: Arquivo para salvar progresso (permite resume)
            resume_from: Índice da conversa para continuar (0 = início)
            
        Returns:
            Dict com dados brutos (JSON-serializável)
        """
        started_at = datetime.now()
        
        # Carrega checkpoint se existir e resume_from > 0
        conv_results = []
        if resume_from > 0 and checkpoint_file:
            checkpoint_path = Path(checkpoint_file)
            if checkpoint_path.exists():
                self._log(f"\n📂 Carregando checkpoint: {checkpoint_path}")
                with open(checkpoint_path, "r", encoding="utf-8") as f:
                    checkpoint_data = json.load(f)
                conv_results = checkpoint_data.get("conversations", [])
                self._log(f"   ✓ {len(conv_results)} conversas anteriores carregadas")
        
        self._log("\n" + "=" * 80)
        self._log("🚀 BENCHMARK LEVE (Sem comparações LLM)")
        self._log(f"   Modelo: {self.model}")
        self._log(f"   Namespace: {self.namespace}")
        self._log(f"   Conversas: {len(conversations)}")
        if resume_from > 0:
            self._log(f"   ⏩ Continuando da conversa {resume_from + 1}")
        self._log("=" * 80)
        
        # Limpa memória (só se não estiver resumindo)
        if clear_before and resume_from == 0:
            self.clear_memory()
        
        # Processa conversas
        for idx, conv in enumerate(conversations):
            # Pula conversas já processadas
            if idx < resume_from:
                continue
                
            self._log(f"\n[{idx + 1}/{len(conversations)}]", end="")
            
            conversation_id = f"conv_{idx}_{conv.domain}"
            
            # NOTA: O namespace por usuário é definido em run_conversation()
            # Cada usuário/conversa tem seu próprio namespace isolado
            
            try:
                conv_result = self.run_conversation(conv, conversation_id)
                conv_results.append(conv_result)
                
                # Salva checkpoint após cada conversa
                if checkpoint_file:
                    self._save_checkpoint(
                        checkpoint_file, 
                        conv_results, 
                        conversations,
                        idx + 1
                    )
            except Exception as e:
                self._log(f"\n❌ Erro na conversa {idx + 1}: {e}")
                self._log(f"   💾 Progresso salvo até conversa {idx}")
                if checkpoint_file:
                    self._save_checkpoint(
                        checkpoint_file,
                        conv_results,
                        conversations,
                        idx
                    )
                self._log(f"\n   ⏩ Para continuar, execute com --resume {idx}")
                raise
        
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        
        # Coleta stats finais
        baseline_stats = self.baseline.get_stats()
        cortex_stats = self.cortex_agent.get_stats()
        
        result = {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": duration,
            "model": self.model,
            "namespace": self.namespace,
            "total_conversations": len(conversations),
            "total_sessions": sum(len(c.sessions) for c in conversations),
            "total_messages": sum(
                sum(len(s.messages) for s in c.sessions)
                for c in conversations
            ),
            "baseline_stats": baseline_stats,
            "cortex_stats": cortex_stats,
            "conversations": conv_results,
        }
        
        self._log("\n" + "=" * 80)
        self._log("✅ BENCHMARK COMPLETO")
        self._log(f"   Duração: {duration:.1f}s")
        self._log(f"   Conversas: {len(conversations)}")
        self._log("=" * 80)
        
        return result
    
    def save_result(self, result: dict, filepath: Path | str):
        """Salva resultado em JSON."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        self._log(f"\n💾 Salvo em: {filepath}")
    
    def _save_checkpoint(
        self,
        filepath: Path | str,
        conv_results: list[dict],
        conversations: list[Conversation],
        last_completed: int,
    ):
        """Salva checkpoint para permitir resume."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        checkpoint = {
            "checkpoint": True,
            "last_completed": last_completed,
            "total_conversations": len(conversations),
            "model": self.model,
            "namespace": self.namespace,
            "saved_at": datetime.now().isoformat(),
            "conversations": conv_results,
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)
        
        self._log(f"   💾 Checkpoint salvo: {filepath}")
