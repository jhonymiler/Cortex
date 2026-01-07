"""
RAGAgent - Baseline usando RAG com embeddings para comparação com Cortex.

Este agente implementa RAG (Retrieval Augmented Generation) tradicional:
- Armazena mensagens + respostas com embeddings
- Busca por similaridade vetorial
- Sem consolidação, sem decaimento, sem W5H

Usado como baseline para comparar com Cortex no paper.
"""

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Tenta importar chromadb, se não tiver disponível usa mock
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None

from benchmark.agents import call_llm_with_retry


@dataclass
class RAGDocument:
    """Documento armazenado no RAG."""
    
    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RAGResponse:
    """Resposta do RAG agent."""
    
    content: str
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    context_from_rag: str = ""
    documents_retrieved: int = 0


class SimpleRAGMemory:
    """
    Implementação simples de RAG para ambientes sem ChromaDB.
    
    Usa TF-IDF básico para similaridade (sem embeddings reais).
    """
    
    def __init__(self, namespace: str = "default"):
        self.namespace = namespace
        self._documents: list[RAGDocument] = []
    
    def add_document(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Adiciona documento ao RAG."""
        doc_id = f"doc_{len(self._documents)}_{self.namespace}"
        doc = RAGDocument(
            id=doc_id,
            content=content,
            metadata=metadata or {},
        )
        self._documents.append(doc)
        return doc_id
    
    def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[tuple[RAGDocument, float]]:
        """Busca documentos por similaridade (TF-IDF simples)."""
        if not self._documents:
            return []
        
        query_words = set(query.lower().split())
        
        scored = []
        for doc in self._documents:
            doc_words = set(doc.content.lower().split())
            
            # Jaccard similarity
            intersection = len(query_words & doc_words)
            union = len(query_words | doc_words)
            score = intersection / union if union > 0 else 0
            
            if score > 0:
                scored.append((doc, score))
        
        # Ordena por score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return scored[:limit]
    
    def clear(self) -> None:
        """Limpa todos os documentos."""
        self._documents.clear()


class ChromaRAGMemory:
    """
    Implementação de RAG usando ChromaDB com embeddings reais.
    """
    
    def __init__(self, namespace: str = "default", persist_dir: str | None = None):
        self.namespace = namespace
        
        if not CHROMADB_AVAILABLE:
            raise ImportError("chromadb não está instalado. Use: pip install chromadb")
        
        # Inicializa ChromaDB
        if persist_dir:
            self._client = chromadb.PersistentClient(path=persist_dir)
        else:
            self._client = chromadb.Client()
        
        # Cria ou obtém collection
        self._collection = self._client.get_or_create_collection(
            name=f"rag_{namespace}",
            metadata={"hnsw:space": "cosine"},
        )
    
    def add_document(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Adiciona documento com embedding."""
        doc_id = f"doc_{self._collection.count()}_{datetime.now().timestamp()}"
        
        self._collection.add(
            documents=[content],
            ids=[doc_id],
            metadatas=[metadata or {}],
        )
        
        return doc_id
    
    def search(
        self,
        query: str,
        limit: int = 5,
    ) -> list[tuple[dict, float]]:
        """Busca por similaridade vetorial."""
        results = self._collection.query(
            query_texts=[query],
            n_results=limit,
        )
        
        documents = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                score = 1 - results["distances"][0][i] if results["distances"] else 0.5
                documents.append((
                    {"content": doc, "id": results["ids"][0][i]},
                    score,
                ))
        
        return documents
    
    def clear(self) -> None:
        """Limpa collection."""
        self._client.delete_collection(f"rag_{self.namespace}")
        self._collection = self._client.get_or_create_collection(
            name=f"rag_{self.namespace}",
        )


class RAGAgent:
    """
    Agente LLM com memória RAG tradicional.
    
    Implementa o padrão RAG:
    1. Recebe query do usuário
    2. Busca documentos similares no vectordb
    3. Injeta documentos no prompt
    4. Gera resposta
    5. Armazena interação no vectordb
    
    Diferenças vs Cortex:
    - Sem W5H estruturado
    - Sem consolidação
    - Sem decaimento
    - Busca por embedding (custo de tokens)
    - Sem distinção personal/shared
    """
    
    SYSTEM_PROMPT_TEMPLATE = """Você é um assistente útil e amigável com acesso a uma base de conhecimento.

{rag_context}

INSTRUÇÕES:
- Use as informações relevantes da base de conhecimento para responder.
- Se não houver informações relevantes, responda normalmente.
- Seja consistente com informações anteriores.
"""
    
    def __init__(
        self,
        model: str = "ministral-3:3b",
        ollama_url: str = "http://localhost:11434",
        namespace: str = "rag_benchmark",
        use_chromadb: bool = False,
        persist_dir: str | None = None,
    ):
        self.model = model
        self.ollama_url = ollama_url
        self.namespace = namespace
        
        # Seleciona implementação de RAG
        if use_chromadb and CHROMADB_AVAILABLE:
            self._rag = ChromaRAGMemory(namespace, persist_dir)
        else:
            self._rag = SimpleRAGMemory(namespace)
        
        # Estado da sessão
        self._current_user: str | None = None
        self._session_history: list[dict] = []
        self._context_window_size = 10
        
        # Métricas
        self._total_messages = 0
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_rag_time_ms = 0.0
    
    def new_session(self, user_id: str | None = None) -> None:
        """Inicia nova sessão."""
        self._current_user = user_id
        self._session_history = []
    
    def process_message(
        self,
        user_message: str,
        verbose: bool = False,
    ) -> RAGResponse:
        """
        Processa uma mensagem do usuário.
        
        1. Busca documentos similares
        2. Gera resposta com contexto
        3. Armazena interação
        """
        start_time = time.time()
        
        # 1. RAG Retrieval
        rag_start = time.time()
        similar_docs = self._rag.search(user_message, limit=3)
        rag_time = (time.time() - rag_start) * 1000
        
        # Formata contexto RAG
        if similar_docs:
            context_parts = ["[Informações Relevantes]"]
            for doc, score in similar_docs[:3]:
                content = doc.content if hasattr(doc, 'content') else doc.get('content', '')
                context_parts.append(f"- {content[:200]}")
            rag_context = "\n".join(context_parts)
        else:
            rag_context = ""
        
        # 2. Gera resposta
        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(rag_context=rag_context)
        
        # Histórico da sessão
        messages = [{"role": "system", "content": system_prompt}]
        for msg in self._session_history[-self._context_window_size:]:
            messages.append(msg)
        messages.append({"role": "user", "content": user_message})
        
        # Chama LLM
        response = call_llm_with_retry(
            model=f"ollama_chat/{self.model}",
            messages=messages,
            api_base=self.ollama_url,
            max_retries=3,
            initial_wait=5.0,
        )
        
        assistant_response = response.choices[0].message.content
        
        # 3. Armazena interação no RAG
        store_start = time.time()
        self._rag.add_document(
            content=f"User: {user_message}\nAssistant: {assistant_response}",
            metadata={
                "user_id": self._current_user,
                "timestamp": datetime.now().isoformat(),
            },
        )
        store_time = (time.time() - store_start) * 1000
        
        # Atualiza histórico da sessão
        self._session_history.append({"role": "user", "content": user_message})
        self._session_history.append({"role": "assistant", "content": assistant_response})
        
        # Métricas
        total_time = (time.time() - start_time) * 1000
        prompt_tokens = response.usage.prompt_tokens if response.usage else 0
        completion_tokens = response.usage.completion_tokens if response.usage else 0
        
        self._total_messages += 1
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens
        self._total_rag_time_ms += rag_time + store_time
        
        if verbose:
            print(f"    RAG: {len(similar_docs)} docs, {rag_time:.0f}ms retrieve, {store_time:.0f}ms store")
        
        return RAGResponse(
            content=assistant_response,
            total_tokens=prompt_tokens + completion_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=total_time,
            context_from_rag=rag_context,
            documents_retrieved=len(similar_docs),
        )
    
    def clear_memory(self) -> None:
        """Limpa toda a memória RAG."""
        self._rag.clear()
    
    def get_stats(self) -> dict[str, Any]:
        """Retorna estatísticas do agente."""
        return {
            "type": "rag",
            "model": self.model,
            "has_memory": True,
            "memory_type": "vector_similarity",
            "namespace": self.namespace,
            "total_messages": self._total_messages,
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_completion_tokens": self._total_completion_tokens,
            "total_tokens": self._total_prompt_tokens + self._total_completion_tokens,
            "total_rag_time_ms": self._total_rag_time_ms,
            "uses_embeddings": isinstance(self._rag, ChromaRAGMemory),
        }


# Para testes rápidos
if __name__ == "__main__":
    print("🔬 Testando RAGAgent...")
    
    agent = RAGAgent(
        model="ministral-3:3b",
        namespace="rag_test",
    )
    
    # Sessão 1
    agent.new_session(user_id="test_user")
    
    response1 = agent.process_message(
        "Olá, meu nome é João e trabalho com Python.",
        verbose=True,
    )
    print(f"Response 1: {response1.content[:100]}...")
    
    response2 = agent.process_message(
        "Qual linguagem eu uso?",
        verbose=True,
    )
    print(f"Response 2: {response2.content[:100]}...")
    
    # Nova sessão
    agent.new_session(user_id="test_user")
    
    response3 = agent.process_message(
        "Você lembra do meu nome?",
        verbose=True,
    )
    print(f"Response 3 (nova sessão): {response3.content[:100]}...")
    
    print("\n📊 Stats:")
    for k, v in agent.get_stats().items():
        print(f"   {k}: {v}")
    
    # Limpa
    agent.clear_memory()
    print("\n✅ Teste completo!")

