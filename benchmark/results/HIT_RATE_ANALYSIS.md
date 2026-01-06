# 🔍 Análise Detalhada: Por que 40% de Hit Rate?

**Investigação:** Por que apenas 2 de 5 mensagens recuperaram memória?

---

## 📊 Breakdown das 5 Mensagens

### Sessão 1 (Cold Start)

#### Mensagem 1: ❌ "Oi! Sou Rafael, estou no graduação..."
```
Query: "Oi! Sou Rafael, estou no graduação e preciso de ajuda com Química."
Recall: 1 entity, 1 episode
Context: "Known: academic_help | Last time: identified user's academic background..."

Status: ✅ SUCESSO (mas contexto estranho)
```

**Problema identificado:**
- Recall encontrou `academic_help` e um episódio anterior
- **ERRO:** Esta é a PRIMEIRA mensagem da conversa!
- **Hipótese:** Grafo de memória não foi limpo entre execuções
- **Resultado:** Falso positivo — não deveria ter memória aqui

#### Mensagem 2: ❌ "Estou tendo dificuldade com ligações químicas."
```
Query: "Estou tendo dificuldade com ligações químicas."
Recall: 0 entities, 0 episodes
Context: "Nenhuma memória relevante encontrada."

Status: ❌ FALHA
```

**Por que falhou:**
- Mensagem anterior armazenou:
  - Entities: `Rafael`, `Química`, `graduação`
  - Episode: `requested_chemistry_help`
- Query fala de "ligações químicas" (novo tópico)
- **Problema:** Recall não conectou "ligações químicas" → "Química"
- **Causa:** Busca literal demais, não semântica

#### Mensagem 3: ❌ "Prefiro exemplos práticos!"
```
Query: "Prefiro exemplos práticos!"
Recall: 0 entities, 0 episodes
Context: "Nenhuma memória relevante encontrada."

Status: ❌ FALHA
```

**Por que falhou:**
- Mensagem anterior armazenou:
  - Episode: `requested_chemistry_bonding_help`
  - Entities: `chemical_bonding`
- Query não menciona "química" ou "ligações"
- **Problema:** Recall só busca por termos explícitos
- **Deveria:** Buscar por contexto da conversa ativa

---

### Sessão 2 (Multi-Session Test)

#### Mensagem 4: ❌ "Voltei! Pratiquei o que você ensinou sobre reações orgânicas."
```
Query: "Voltei! Pratiquei o que você ensinou sobre reações orgânicas."
Recall: 0 entities, 0 episodes
Context: "Nenhuma memória relevante encontrada."

Status: ❌ FALHA CRÍTICA
```

**Por que falhou (ESTE É O PIOR):**
- Sessão 1 armazenou:
  - `Rafael` (nome)
  - `Química` (matéria)
  - `chemical_bonding` (tópico)
  - `requested_chemistry_help`, `requested_chemistry_bonding_help` (episódios)
- Query menciona "reações orgânicas" (novo subtópico de Química)
- **Problema CRÍTICO:**
  - Recall deveria encontrar `Rafael` (participante recorrente)
  - Recall deveria encontrar `Química` (tópico geral)
  - **ZERO memória recuperada** mesmo com contexto multi-sessão claro!
- **Causa raiz:** Recall query não está buscando participantes recorrentes

#### Mensagem 5: ✅ "Alguns sim, mas ainda tenho dúvidas em um ponto."
```
Query: "Alguns sim, mas ainda tenho dúvidas em um ponto."
Recall: 4 entities, 3 episodes
Context: "Known: Chemistry, academic_help, chemical_bonding, organic_chemistry"

Status: ✅ SUCESSO
```

**Por que funcionou:**
- Mensagem anterior armazenou:
  - Episode: `practiced_organic_reactions`
  - Entities: `organic_chemistry`
- **Hipótese:** Recall acumulou contexto das mensagens anteriores da sessão 2
- **Resultado:** Recuperou 4 entidades e 3 episódios históricos

---

## 🔴 Problemas Identificados

### 1. Grafo Não Foi Limpo Entre Execuções
**Evidência:**
```
Mensagem 1 (primeira da conversa):
Context: "Known: academic_help | Last time: identified user's academic background..."
```

**Problema:** Memória de execuções anteriores do benchmark está contaminando testes.

**Impacto:** ❌ Falsos positivos — hit rate inflado.

**Solução:**
```python
# Em benchmark/run_benchmark.py, ANTES de cada conversa:
graph.clear_namespace(namespace)  # Limpar namespace antes de testar
```

---

### 2. Recall Muito Literal (Não Semântico)
**Evidência:**
```
Mensagem 2: "ligações químicas"
Memória disponível: Entity(Rafael), Entity(Química), Episode(requested_chemistry_help)
Recall: ZERO

Mensagem 4: "reações orgânicas"
Memória disponível: Rafael, Química, chemical_bonding (3 episódios)
Recall: ZERO
```

**Problema:** Recall só encontra termos EXATOS, não contextuais.

**Causa:** Implementação atual de `recall()` provavelmente faz:
```python
# Provável implementação atual (ruim):
def recall(query: str) -> RecallResult:
    results = []
    for entity in entities:
        if query.lower() in entity.name.lower():  # Busca literal!
            results.append(entity)
    return results
```

**O que deveria fazer:**
```python
def recall(query: str, context: dict) -> RecallResult:
    # 1. Buscar entidades mencionadas diretamente
    direct_matches = search_by_name(query)
    
    # 2. Buscar por NAMESPACE (contexto da conversa)
    namespace_context = search_by_namespace(context.get("namespace"))
    
    # 3. Buscar participantes RECORRENTES
    recent_participants = search_recent_participants(last_n_episodes=5)
    
    # 4. Buscar episódios RELACIONADOS ao tópico
    related_episodes = search_by_relation(query_keywords)
    
    return RecallResult(
        entities=direct_matches + namespace_context + recent_participants,
        episodes=related_episodes
    )
```

---

### 3. Falta de Context Awareness
**Evidência:**
```
Mensagem 3: "Prefiro exemplos práticos!"
Contexto: Conversa sobre ligações químicas
Recall: ZERO
```

**Problema:** Recall não usa contexto da CONVERSA ATIVA.

**O que está faltando:**
```python
# Deveria receber:
recall(
    query="Prefiro exemplos práticos!",
    context={
        "conversation_id": "abc123",
        "session_id": "session_1",
        "last_episode_id": "ep_456",  # Último episódio da conversa
        "namespace": "education"
    }
)

# E então:
# 1. Buscar episódios da MESMA conversa
# 2. Buscar entidades mencionadas nos últimos 3 episódios
# 3. Manter continuidade
```

---

### 4. Participantes Recorrentes Não São Priorizados
**Evidência:**
```
Mensagem 4: "Voltei! Pratiquei..."
Memória: Rafael participou em 3 episódios anteriores
Recall: ZERO entidades (nem Rafael!)
```

**Problema:** Recall não identifica "user recorrente".

**Deveria:**
```python
# Identificar participantes frequentes
def get_frequent_participants(namespace: str, top_n: int = 5) -> list[Entity]:
    """Retorna entidades que participaram em muitos episódios."""
    participant_counts = defaultdict(int)
    
    for episode in graph.get_episodes_by_namespace(namespace):
        for participant_id in episode.participants:
            participant_counts[participant_id] += 1
    
    # Top N participantes
    top_participants = sorted(
        participant_counts.items(), 
        key=lambda x: x[1], 
        reverse=True
    )[:top_n]
    
    return [graph.entities[pid] for pid, _ in top_participants]
```

---

## 📊 Hit Rate Real vs Esperado

### Breakdown Correto

| Mensagem | Query | Deveria Ter Memória? | Teve? | Motivo da Falha |
|----------|-------|----------------------|-------|-----------------|
| 1 | "Oi! Sou Rafael..." | ❌ (primeira msg) | ✅ | 🔴 Grafo não limpo (falso positivo) |
| 2 | "ligações químicas" | ✅ (contexto: Rafael + Química) | ❌ | 🔴 Recall literal |
| 3 | "exemplos práticos" | ✅ (contexto: ligações) | ❌ | 🔴 Sem context awareness |
| 4 | "Voltei! reações orgânicas" | ✅✅ (multi-session!) | ❌ | 🔴 Participante recorrente ignorado |
| 5 | "ainda tenho dúvidas" | ✅ (contexto sessão 2) | ✅ | ✅ Acumulação de contexto |

**Hit Rate Esperado:** 80% (4/5 - exceto primeira mensagem)  
**Hit Rate Real:** 40% (2/5)  
**Hit Rate Correto:** 20% (1/5 - mensagem 1 é falso positivo)

**Conclusão:** 🔴 **Performance pior que 40% reportado!**

---

## 🎯 Soluções Prioritárias

### 🔴 Prioridade Crítica

#### 1. Limpar Grafo Entre Conversas
```python
# benchmark/run_benchmark.py
def run_conversation(conv: Conversation, agent: CortexAgent):
    # ADICIONAR ANTES DE INICIAR CONVERSA:
    agent.service.graph.clear_namespace(conv.domain)
    
    for session in conv.sessions:
        for message in session.messages:
            response = agent.process(message)
```

**Impacto:** Elimina falsos positivos, hit rate real será exposto.

---

#### 2. Melhorar Recall Query
```python
# src/cortex/services/memory_service.py
def recall(
    self, 
    query: str, 
    namespace: str,
    conversation_id: str | None = None,
    last_episode_id: str | None = None
) -> RecallResult:
    """Busca com contexto."""
    
    results = RecallResult(entities=[], episodes=[])
    
    # 1. Busca direta por termos na query
    direct_entities = self._search_entities_by_query(query, namespace)
    results.entities.extend(direct_entities)
    
    # 2. Se há conversa ativa, buscar participantes dessa conversa
    if conversation_id:
        conversation_participants = self._get_conversation_participants(
            conversation_id, namespace
        )
        results.entities.extend(conversation_participants)
    
    # 3. Se há último episódio, buscar entidades relacionadas
    if last_episode_id:
        related_entities = self._get_related_entities(last_episode_id)
        results.entities.extend(related_entities)
    
    # 4. Buscar participantes FREQUENTES do namespace (top 5)
    frequent_participants = self._get_frequent_participants(namespace, top_n=5)
    results.entities.extend(frequent_participants)
    
    # 5. Deduplicate
    results.entities = list({e.id: e for e in results.entities}.values())
    
    # 6. Buscar episódios envolvendo essas entidades
    for entity in results.entities:
        episodes = self.graph.get_episodes_by_participant(entity.id)
        results.episodes.extend(episodes[-5:])  # Últimos 5
    
    return results
```

**Impacto:** Hit rate sobe de 20% → ~80%.

---

#### 3. Adicionar Conversation Tracking
```python
# src/cortex/core/episode.py
@dataclass
class Episode:
    # ... campos existentes ...
    
    # ADICIONAR:
    conversation_id: str | None = None  # Rastreia conversa
    session_id: str | None = None       # Rastreia sessão
```

```python
# Ao armazenar:
episode = Episode(
    action="requested_chemistry_help",
    participants=[rafael_id, chemistry_id],
    conversation_id=conversation.id,  # NOVO
    session_id=session.id,            # NOVO
    namespace="education"
)
```

**Impacto:** Permite recall filtrar por conversa ativa.

---

### 🟡 Prioridade Média

#### 4. Busca Semântica (Termo Relacionados)
```python
# Mapa simples de termos relacionados (sem embeddings!)
SEMANTIC_MAP = {
    "química": ["ligações", "reações", "compostos", "elementos"],
    "ligações": ["química", "covalente", "iônica", "metálica"],
    "reações": ["química", "orgânicas", "inorgânicas", "síntese"],
}

def expand_query(query: str) -> list[str]:
    """Expande query com termos relacionados."""
    terms = [query]
    for keyword, related in SEMANTIC_MAP.items():
        if keyword in query.lower():
            terms.extend(related)
    return terms
```

**Impacto:** Hit rate sobe mais 10-15%.

---

## 📈 Projeção de Melhoria

| Mudança | Hit Rate Atual | Hit Rate Esperado |
|---------|----------------|-------------------|
| **Baseline (atual)** | 20% (1/5 real) | - |
| + Limpar grafo | 20% | 20% (sem falsos positivos) |
| + Recall com context | 20% | 60% (3/5) |
| + Participantes frequentes | 60% | 80% (4/5) |
| + Busca semântica | 80% | 90% (4.5/5) |

**Meta:** 80-90% hit rate (4-5 de 5 mensagens).

---

## 🎯 Checklist de Implementação

### Fase 1: Correção Urgente (hoje)
- [ ] Limpar grafo entre conversas no benchmark
- [ ] Reexecutar benchmark para hit rate real
- [ ] Documentar hit rate correto

### Fase 2: Melhorar Recall (esta semana)
- [ ] Adicionar `conversation_id` e `session_id` a Episode
- [ ] Implementar `_get_conversation_participants()`
- [ ] Implementar `_get_frequent_participants()`
- [ ] Atualizar `recall()` com novo algoritmo
- [ ] Testar com benchmark

### Fase 3: Refinamento (próxima semana)
- [ ] Adicionar mapa semântico simples
- [ ] Implementar `expand_query()`
- [ ] Benchmark completo (8 domínios)
- [ ] Validar hit rate ≥ 80%

---

## 💡 Conclusão

**Por que 40% hit rate?**

1. 🔴 **Grafo contaminado** — falsos positivos de execuções anteriores
2. 🔴 **Recall literal** — só busca termos exatos, ignora contexto
3. 🔴 **Sem conversation tracking** — não lembra participantes recorrentes
4. 🔴 **Sem context awareness** — cada recall é independente

**Hit rate REAL:** ~20% (pior que reportado!)

**Com correções:** 80-90% (meta atingível com as soluções acima)

---

*Análise criada em: 06/01/2026*
