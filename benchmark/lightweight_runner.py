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
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from benchmark.agents import BaselineAgent, CortexAgent
from benchmark.conversation_generator import Conversation


class LightweightBenchmarkRunner:
    """
    Runner otimizado que apenas COLETA dados,
    sem fazer comparações ou análises que usem LLM.
    """
    
    def __init__(
        self,
        model: str,
        ollama_url: str = "http://localhost:11434",
        cortex_url: str = "http://localhost:8000",
        namespace: str = "benchmark",
        verbose: bool = True,
    ):
        self.model = model
        self.namespace = namespace
        self.verbose = verbose
        
        # Cria agentes
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
    
    def _log(self, message: str, end: str = "\n"):
        """Log condicional."""
        if self.verbose:
            print(message, end=end, flush=True)
    
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
        """
        self._log(f"\n📋 Conversa: {conversation.domain} - {conversation.user_profile.get('name', 'user')}")
        
        conv_result = {
            "conversation_id": conversation_id,
            "domain": conversation.domain,
            "user_profile": conversation.user_profile,
            "sessions": [],
        }
        
        # Processa cada sessão
        for session_idx, session in enumerate(conversation.sessions):
            self._log(f"   📅 Sessão {session_idx + 1}/{len(conversation.sessions)}.")
            
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
                
                # CORTEX: Recall + Responde + Store
                cortex_start = time.time()
                
                # Recall
                recall_start = time.time()
                recall_result = self.cortex_agent.recall(
                    query=user_message,
                    conversation_id=conversation_id,
                    session_id=session_id,
                )
                recall_time_ms = (time.time() - recall_start) * 1000
                
                # Responde (com contexto de memória)
                cortex_response = self.cortex_agent.process_message(
                    message=user_message,
                )
                
                # Store
                store_start = time.time()
                store_result = self.cortex_agent.store(
                    user_message=user_message,
                    assistant_response=cortex_response.content,
                    conversation_id=conversation_id,
                    session_id=session_id,
                )
                store_time_ms = (time.time() - store_start) * 1000
                
                cortex_time_ms = (time.time() - cortex_start) * 1000
                
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
                    "cortex_memory_entities": recall_result.get("entities_found", 0),
                    "cortex_memory_episodes": recall_result.get("episodes_found", 0),
                    "cortex_context_used": recall_result.get("prompt_context", ""),
                    
                    # Dados brutos de memória (para análise posterior)
                    "cortex_entities": recall_result.get("entities", []),
                    "cortex_episodes": recall_result.get("episodes", []),
                }
                
                session_result["messages"].append(message_result)
            
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
            
            # NÃO limpa entre conversas - memória acumula para análise posterior
            # A limpeza só ocorre no início do benchmark (clear_before=True)
            
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
