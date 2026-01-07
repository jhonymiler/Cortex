# 🗺️ Posicionamento Competitivo

> Onde o Cortex se encaixa no ecossistema de memória para IA.

---

## Mapa de Posicionamento

```
                        FIDELIDADE DE MEMÓRIA
                               ▲
                               │
                           Alta│
                               │
      Fine-tuning ●            │            ● CORTEX
      (custo alto,             │            (custo zero,
       irreversível,           │             reversível,
       batch learning)         │             real-time)
                               │
                               │
    ───────────────────────────┼───────────────────────────►
    Custo Alto                 │                 Custo Zero
                               │                 POR INFERÊNCIA
                               │
      VectorDB ●               │
      (custo por busca,        │
       texto não estruturado)  │            ● Context Window
                               │            (custo por token,
      RAG ●                    │             sem persistência,
      (embeddings + busca,     │             limite de tamanho)
       similaridade)           │
                               │
                          Baixa│
                               │
```

---

## Comparativo Detalhado

### Cortex vs Context Window

| Aspecto | Context Window | Cortex |
|---------|----------------|--------|
| **Persistência** | ❌ Sessão apenas | ✅ Permanente |
| **Custo** | Alto (todos os tokens) | Zero por recall |
| **Limite** | 128K tokens | Ilimitado |
| **Estrutura** | Texto bruto | Grafo semântico |
| **Escalabilidade** | Linear ($$) | Constante |

**Quando usar Context Window**: Conversas curtas, sem necessidade de persistência.

**Quando usar Cortex**: Qualquer caso com múltiplas sessões ou contexto rico.

---

### Cortex vs RAG (Retrieval Augmented Generation)

| Aspecto | RAG | Cortex |
|---------|-----|--------|
| **Custo por busca** | ~$0.001 (embedding) | **$0** |
| **Estrutura** | Chunks de texto | W5H estruturado |
| **Relevância** | Similaridade vetorial | Grafo + índices |
| **Consolidação** | ❌ Não consolida | ✅ Automática |
| **Decaimento** | ❌ Estático | ✅ Ebbinghaus |
| **Setup** | Complexo (embeddings, vector store) | Simples (pip install) |

**Quando usar RAG**: Busca em documentos existentes (knowledge base estática).

**Quando usar Cortex**: Memória de interações (experiências, contexto dinâmico).

---

### Cortex vs VectorDB (Pinecone, Weaviate, etc.)

| Aspecto | VectorDB | Cortex |
|---------|----------|--------|
| **Modelo de dados** | Vetores | Grafo |
| **Busca** | Similaridade ~O(log n) | Índice O(1) |
| **Custo** | Por busca + storage | Apenas storage |
| **Relações** | Implícitas | Explícitas |
| **Tipagem** | Texto livre | W5H estruturado |
| **Vendor** | Cloud (lock-in) | Self-hosted |

**Quando usar VectorDB**: Busca semântica em grandes volumes de texto não estruturado.

**Quando usar Cortex**: Memória estruturada com relações explícitas.

---

### Cortex vs Fine-tuning

| Aspecto | Fine-tuning | Cortex |
|---------|-------------|--------|
| **Custo inicial** | $100-10.000 | $0 |
| **Tempo de setup** | Horas-dias | Minutos |
| **Reversibilidade** | ❌ Irreversível | ✅ Totalmente |
| **Atualização** | Re-treino completo | Real-time |
| **Personalização** | Por modelo | Por usuário |
| **Debugging** | Caixa preta | Grafo inspecionável |

**Quando usar Fine-tuning**: Ajustar comportamento fundamental do modelo.

**Quando usar Cortex**: Personalização por usuário/sessão sem alterar modelo.

---

### Cortex vs Mem0

| Aspecto | Mem0 | Cortex |
|---------|------|--------|
| **Modelo** | Salience extraction | W5H estruturado |
| **Consolidação** | Básica | Hierárquica |
| **Decaimento** | ❌ Sem | ✅ Ebbinghaus |
| **Hub detection** | ❌ Não | ✅ Automático |
| **Shared memory** | Limitado | Full (personal/shared/learned) |
| **Open source** | Parcial | 100% MIT |

**Quando usar Mem0**: Projetos simples com necessidades básicas.

**Quando usar Cortex**: Sistemas complexos com múltiplos usuários e consolidação.

---

## Matriz de Decisão

```
┌─────────────────────────────────────────────────────────────┐
│                    ESCOLHA SUA SOLUÇÃO                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Você precisa de...                     → Use              │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  Buscar em docs existentes              → RAG              │
│  Busca semântica em escala              → VectorDB         │
│  Mudar comportamento do modelo          → Fine-tuning      │
│                                                             │
│  Memória entre sessões                  → CORTEX ✅        │
│  Personalização por usuário             → CORTEX ✅        │
│  Multi-tenant com isolamento            → CORTEX ✅        │
│  Consolidação automática                → CORTEX ✅        │
│  Zero custo por recall                  → CORTEX ✅        │
│  Decaimento cognitivo                   → CORTEX ✅        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Arquitetura Complementar

Cortex não substitui — **complementa**:

```
┌─────────────────────────────────────────────────────────────┐
│                      SEU AGENTE LLM                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐   │
│  │    CORTEX     │  │     RAG       │  │    TOOLS      │   │
│  │   (memória    │  │  (knowledge   │  │   (ações,     │   │
│  │  de sessões)  │  │    base)      │  │    APIs)      │   │
│  └───────────────┘  └───────────────┘  └───────────────┘   │
│         │                  │                  │             │
│         └──────────────────┴──────────────────┘             │
│                            │                                │
│                      CONTEXT WINDOW                         │
│                     (working memory)                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Exemplo de Stack Completo

```python
# RAG para documentação
docs_rag = RAGPipeline(vectordb=pinecone, embeddings=openai)

# Cortex para memória de usuário
cortex = CortexMemory(namespace="meu_agente")

# Combinar no agente
def meu_agente(user_msg):
    # 1. Memória do usuário (Cortex)
    user_context = cortex.before(user_msg)
    
    # 2. Conhecimento base (RAG)
    docs_context = docs_rag.search(user_msg)
    
    # 3. Gerar resposta
    response = llm.generate(
        context=f"{user_context}\n\n{docs_context}",
        message=user_msg
    )
    
    # 4. Armazenar memória
    cortex.after(user_msg, response)
    
    return response
```

---

## Por Que Escolher Cortex?

### 1. Zero Custo por Recall

Enquanto RAG cobra por embedding e busca, Cortex usa **índices O(1)**.

```
10.000 recalls/mês:
├── RAG: 10.000 × $0.001 = $10
└── Cortex: $0
```

### 2. Memória que Pensa

Não é apenas storage — é **cognição**:
- Consolida experiências repetidas
- Esquece o irrelevante (Ebbinghaus)
- Detecta hubs automaticamente

### 3. Estrutura > Texto

W5H fornece **semântica**, não apenas palavras:

```python
# RAG retorna:
"O cliente João reclamou do login ontem"

# Cortex retorna:
Memory(
    who=["João", "sistema_auth"],
    what="reclamou_login",
    why="vpn_bloqueando",
    how="resolvido_desconectando_vpn",
    when="2026-01-06"
)
```

### 4. Multi-Tenant Nativo

Isolamento por design, não por gambiarra:

```python
# Personal: só do usuário
# Shared: visível a todos
# Learned: padrões anonimizados
```

### 5. Open Source, Self-Hosted

- Sem vendor lock-in
- Sem custo por assento
- Seus dados, seu controle

---

## Próximos Passos

| Convencido? | Ação |
|-------------|------|
| Sim | [Quick Start](../getting-started/quickstart.md) |
| Quase | [Benchmarks](../research/benchmarks.md) |
| Curioso | [Arquitetura](../architecture/overview.md) |

---

*Posicionamento Competitivo — Última atualização: Janeiro 2026*

