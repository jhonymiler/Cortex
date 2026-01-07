# W5H Memory Architecture Design

> **Documento de Design** - Redesenho do Cortex para modelo W5H
> Versão: 1.0 | Janeiro 2026

## 📚 Fundamentação Científica

### Pesquisa Realizada

#### 1. Curva de Esquecimento (Ebbinghaus, 1885)
**Fonte:** Wikipedia - Forgetting Curve

**Insights-chave:**
- Memórias decaem exponencialmente: `R = e^(-t/S)`
  - `R` = retrievability (facilidade de recuperar)
  - `S` = stability (durabilidade da memória)
  - `t` = tempo
- **Repetição espaçada** aplaina a curva - cada acesso aumenta `S`
- Memórias mais fortes (maior S) decaem mais lentamente
- **Flashbulb memories**: eventos marcantes resistem ao esquecimento

**Aplicação no Cortex:**
```python
# Decaimento exponencial com stability baseada em:
# 1. Quantas vezes foi acessada (access_count)
# 2. Quantos nós apontam para ela (hub centrality)
# 3. Importância declarada (importance)

stability = base_stability * (1 + log(access_count)) * (1 + centrality_score)
retrievability = exp(-time_since_access / stability)
```

#### 2. Consolidação de Memória
**Fonte:** Wikipedia - Memory Consolidation

**Insights-chave:**
- **Consolidação sináptica** (rápida, horas): estabiliza conexões
- **Consolidação de sistemas** (lenta, semanas-anos): torna memórias independentes
- **Reconsolidação**: memórias reativadas ficam lábeis novamente
- Memórias recentes são frágeis, antigas são estáveis

**Aplicação no Cortex:**
```python
# Episódios similares → consolidação automática
# Após consolidação, occurrence_count aumenta e importance sobe
# Memórias consolidadas decaem mais lentamente
```

#### 3. Centralidade em Grafos
**Fonte:** Wikipedia - Centrality

**Insights-chave:**
- **Degree centrality**: número de conexões diretas
- **Betweenness centrality**: quantos caminhos passam pelo nó
- **Hub nodes**: nós altamente conectados são mais "importantes"
- **Implicação**: nós que muitas memórias referenciam são cruciais

**Aplicação no Cortex:**
```python
# Quando várias memórias apontam para uma entidade:
# → Essa entidade é um "hub" (ponto central)
# → Sua importância aumenta automaticamente
# → Decaimento é mais lento
# → É priorizada em recalls

# Exemplo: "João" mencionado em 50 episódios
# → João é central para o usuário
# → Mesmo sem acessar, João decai mais lentamente
```

#### 4. CoALA - Cognitive Architectures for Language Agents
**Fonte:** arXiv:2309.02427

**Insights-chave:**
- Arquitetura Soar: working memory + long-term memory
- Long-term memory dividida em:
  - **Procedural**: regras de produção (como fazer)
  - **Semantic**: fatos (o que é)
  - **Episodic**: experiências passadas (o que aconteceu)
- Decision cycle: percepção → processamento → ação

**Aplicação no Cortex:**
- W5H unifica os três tipos em estrutura flexível
- WHO/WHAT = semantic (entidades)
- WHAT/HOW/WHY = episodic (ações/razões)
- Procedural emerge de episódios consolidados (padrões)

#### 5. Generative Agents (Stanford)
**Fonte:** arXiv:2304.03442

**Insights-chave:**
- Agentes guardam registro completo de experiências em linguagem natural
- Sintetizam memórias em reflexões de alto nível ao longo do tempo
- Recuperam dinamicamente para planejar comportamento
- Ablation mostrou: observation, planning, reflection são críticos

**Aplicação no Cortex:**
- Reflexões = episódios consolidados (is_consolidated=True)
- Observation = episódios recentes
- W5H permite estruturar para recuperação dinâmica

---

## 🎯 Modelo W5H

### Por que W5H?

| Modelo Tradicional | Problema | W5H |
|-------------------|----------|-----|
| semantic/episodic/procedural | Fronteiras confusas | Um modelo unificado |
| Entity/Episode/Relation | Não captura "por quê" | WHY como campo explícito |
| action/outcome | Falta contexto temporal/espacial | WHEN/WHERE explícitos |

### Definição W5H

```
┌─────────────────────────────────────────────────────────────┐
│                         MEMORY                              │
├─────────────────────────────────────────────────────────────┤
│  WHO    │ Quem está envolvido (entidades)                   │
│  WHAT   │ O que aconteceu (ação/fato)                       │
│  WHY    │ Por quê (causa, motivação, razão)                 │
│  WHEN   │ Quando (timestamp + contexto temporal)            │
│  WHERE  │ Onde (namespace + contexto espacial)              │
│  HOW    │ Como (resultado, consequência, método)            │
└─────────────────────────────────────────────────────────────┘
```

### Mapeamento para Estrutura Atual

| W5H | Campo Atual | Localização |
|-----|-------------|-------------|
| WHO | participants + Entity lookup | Episode.participants → Entity |
| WHAT | action | Episode.action |
| WHY | *(novo)* cause | Episode.cause |
| WHEN | timestamp | Episode.timestamp |
| WHERE | *(novo)* namespace + location | Episode.namespace, Episode.location |
| HOW | outcome | Episode.outcome |

---

## 🏗️ Novo Schema

### Memory (unificação de Episode com W5H)

```python
@dataclass
class Memory:
    """
    Unidade fundamental de memória W5H.
    
    Substitui Episode com campos W5H explícitos.
    """
    id: str
    
    # WHO - Participantes
    who: list[str]  # Entity IDs ou nomes inline
    
    # WHAT - O que aconteceu
    what: str  # Ação/fato principal
    
    # WHY - Causa/motivação  
    why: str = ""  # Por que isso aconteceu
    
    # WHEN - Temporal
    when: datetime = field(default_factory=datetime.now)
    temporal_context: str = ""  # "durante a reunião", "após o deploy"
    
    # WHERE - Espacial/Namespace
    where: str = ""  # Namespace ou contexto espacial
    
    # HOW - Resultado/Método
    how: str = ""  # Outcome ou método usado
    
    # Metadados de gerenciamento
    importance: float = 0.5  # 0.0 - 1.0
    stability: float = 1.0   # Multiplicador de decaimento
    access_count: int = 0
    last_accessed: datetime | None = None
    occurrence_count: int = 1  # Para consolidação
    consolidated_from: list[str] = field(default_factory=list)
    
    # Decaimento
    @property
    def retrievability(self) -> float:
        """Calcula facilidade de recuperação baseada em decaimento."""
        if not self.last_accessed:
            self.last_accessed = self.when
        
        days_since = (datetime.now() - self.last_accessed).days
        # R = e^(-t/S) onde S = stability * (1 + log(access_count + 1))
        effective_stability = self.stability * (1 + math.log(self.access_count + 1))
        return math.exp(-days_since / max(effective_stability, 0.1))
    
    @property
    def is_consolidated(self) -> bool:
        return len(self.consolidated_from) > 0
```

### Entity (mantém, adiciona centrality)

```python
@dataclass
class Entity:
    """Entidade com tracking de centralidade."""
    # ... campos existentes ...
    
    # Novo: centralidade calculada
    centrality_score: float = 0.0  # Atualizado periodicamente
    
    def calculate_centrality(self, incoming_relations: int, total_memories_referencing: int) -> None:
        """Atualiza score de centralidade baseado em conexões."""
        self.centrality_score = math.log(1 + incoming_relations + total_memories_referencing)
```

### Relation (adiciona campos causais)

```python
@dataclass
class Relation:
    """Relação com suporte a causalidade explícita."""
    # ... campos existentes ...
    
    # Novo: tipo de causalidade
    causal_type: str = "associative"  # "causal", "temporal", "associative", "contradicts"
    confidence: float = 1.0  # Confiança na relação
```

---

## 🔄 Decaimento (Implementação)

### Algoritmo

```python
class DecayManager:
    """Gerencia decaimento de memórias."""
    
    DECAY_RATE = 0.95  # 5% por dia sem acesso
    CONSOLIDATION_BONUS = 2.0  # Memórias consolidadas decaem 2x mais lento
    HUB_BONUS = 1.5  # Hubs decaem mais lentamente
    IMPORTANCE_THRESHOLD = 0.1  # Abaixo disso, memória é "esquecida"
    
    def apply_decay(self, memory: Memory, graph: MemoryGraph) -> None:
        """Aplica decaimento a uma memória."""
        days_since = (datetime.now() - memory.last_accessed).days
        
        if days_since == 0:
            return  # Acessada hoje, sem decaimento
        
        # Calcula multiplicadores
        consolidation_mult = self.CONSOLIDATION_BONUS if memory.is_consolidated else 1.0
        hub_mult = self.HUB_BONUS if self._is_hub(memory, graph) else 1.0
        
        # Aplica decaimento
        effective_decay = self.DECAY_RATE ** days_since
        effective_decay *= consolidation_mult * hub_mult
        
        memory.importance *= effective_decay
        
        # Marca como "esquecida" se abaixo do threshold
        if memory.importance < self.IMPORTANCE_THRESHOLD:
            memory.metadata["forgotten"] = True
    
    def _is_hub(self, memory: Memory, graph: MemoryGraph) -> bool:
        """Verifica se a memória é referenciada por muitas outras."""
        incoming = graph.count_relations_to(memory.id)
        return incoming >= 5  # 5+ referências = hub
    
    def touch(self, memory: Memory) -> None:
        """Acessa memória, aumentando stability e resetando decaimento."""
        memory.access_count += 1
        memory.last_accessed = datetime.now()
        
        # Spaced repetition: cada acesso aumenta stability
        memory.stability = min(10.0, memory.stability * 1.2)
```

### Significado de Hub Memories

**Quando várias memórias apontam para uma única memória, isso significa:**

1. **Centralidade semântica**: essa memória é um conceito-chave
2. **Maior retenção**: hubs são "protegidos" contra esquecimento
3. **Prioridade em recall**: aparecem primeiro nas buscas
4. **Indicador de importância**: o grafo emergente revela o que importa

**Exemplo prático:**
```
Memory: "João é gerente de projetos"
├── Referenced by: "João aprovou o orçamento"
├── Referenced by: "João delegou tarefa para Maria"
├── Referenced by: "João conduziu a reunião de sprint"
├── Referenced by: "João resolveu conflito com cliente"
└── Referenced by: "João mentor do estagiário"

→ 5 referências = HUB
→ João é claramente central para o contexto
→ Essa memória decai mais lentamente
→ Aparece em mais recalls
```

---

## 🔧 MCP Tools Refatorados

### cortex_remember (substituí cortex_store)

```python
@mcp.tool()
def cortex_remember(
    who: list[str],           # Quem está envolvido
    what: str,                # O que aconteceu
    why: str = "",            # Por quê
    how: str = "",            # Resultado/método
    where: str = "default",   # Namespace
    importance: float = 0.5,  # Importância inicial
) -> dict:
    """
    Armazena uma memória no Cortex.
    
    Use APÓS responder ao usuário para lembrar o que aconteceu.
    
    Args:
        who: Lista de participantes (nomes, IDs)
        what: Descrição da ação/fato principal
        why: Razão/causa (opcional)
        how: Resultado ou método (opcional)
        where: Namespace para organização (opcional)
        importance: Importância de 0.0 a 1.0 (opcional)
    
    Returns:
        {"success": True, "memory_id": "..."}
    """
```

### cortex_recall (mantém, adiciona filtros W5H)

```python
@mcp.tool()
def cortex_recall(
    query: str,
    who: list[str] | None = None,  # Filtrar por participantes
    where: str | None = None,       # Filtrar por namespace
    min_importance: float = 0.0,    # Filtrar por importância
    include_forgotten: bool = False, # Incluir memórias esquecidas
    limit: int = 10,
) -> dict:
    """
    Busca memórias relevantes.
    
    Use ANTES de responder ao usuário para ter contexto.
    """
```

### cortex_forget (novo)

```python
@mcp.tool()
def cortex_forget(
    memory_id: str,
    reason: str = "",
) -> dict:
    """
    Esquece uma memória explicitamente.
    
    Use quando o usuário pede para esquecer algo ou
    quando uma memória é corrigida.
    """
```

### cortex_contradict (mantém)

```python
@mcp.tool()
def cortex_contradict(
    memory_id: str,
    new_fact: str,
    resolution: str = "ask_user",  # "keep_old", "keep_new", "ask_user"
) -> dict:
    """
    Marca uma memória como contraditória.
    
    Use quando descobrir informação que contradiz memória existente.
    """
```

---

## 📊 Métricas do Grafo

### Novas Métricas

```python
@dataclass
class GraphMetrics:
    """Métricas do grafo de memória."""
    
    total_memories: int
    total_entities: int
    total_relations: int
    
    # Decaimento
    active_memories: int  # retrievability > 0.5
    fading_memories: int  # 0.1 < retrievability <= 0.5
    forgotten_memories: int  # retrievability <= 0.1
    
    # Centralidade
    hub_entities: list[str]  # Entidades com alta centralidade
    hub_memories: list[str]  # Memórias muito referenciadas
    
    # Consolidação
    consolidated_count: int
    consolidation_ratio: float  # % de memórias consolidadas
    
    # Contradições
    pending_contradictions: int
    resolved_contradictions: int
```

---

## 🚀 Plano de Implementação

### Fase 1: Core Schema ✅
1. [x] Criar `Memory` dataclass com campos W5H (`src/cortex/core/memory.py`)
2. [x] Adicionar `centrality_score` a Entity (`src/cortex/core/entity.py`)
3. [x] Migrar Episode → Memory (alias para retrocompatibilidade)
4. [x] Atualizar MemoryGraph para novo schema

### Fase 2: Decaimento ✅
1. [x] Implementar `DecayManager` (`src/cortex/core/decay.py`)
2. [x] Adicionar `retrievability` calculation (propriedade em Memory)
3. [x] Implementar `apply_decay()` com spaced repetition
4. [x] Adicionar threshold para "forgotten"
5. [x] Hub protection (memórias centrais decaem mais lentamente)

### Fase 3: Centralidade ✅
1. [x] Implementar cálculo de degree centrality
2. [x] Atualizar centrality em cada store/recall
3. [x] Ajustar decaimento baseado em centrality
4. [x] Adicionar hub detection (>5 referências)

### Fase 4: MCP Tools ✅
1. [x] Refatorar `cortex_store` → `cortex_remember` com W5H
2. [x] Atualizar `cortex_recall` com filtros W5H
3. [x] Implementar `cortex_forget`
4. [x] Testar com Claude Desktop

### Fase 5: Shared Memory ✅
1. [x] Implementar `SharedMemoryManager` (`src/cortex/core/shared_memory.py`)
2. [x] Três níveis: personal, shared, learned
3. [x] Isolamento entre usuários
4. [x] Benchmark de shared memory

### Fase 6: Dashboard (Prioridade Baixa)
1. [x] Visualizar grafo de memória (Streamlit)
2. [ ] Visualizar retrievability
3. [ ] Mostrar hubs
4. [ ] Gráfico de decaimento ao longo do tempo

---

## 🔑 Decisões de Design

### Por que unificar Episode → Memory?
- Episode já tinha action + outcome + context
- W5H adiciona WHY + WHERE explícitos
- Evita confusão semântica
- Um modelo mental mais simples

### Por que usar Ebbinghaus para decaimento?
- Bem estudado (100+ anos de pesquisa)
- Fórmula simples: `R = e^(-t/S)`
- Permite ajustar S baseado em acesso e importância
- Intuitivo: memórias menos usadas são esquecidas

### Por que centralidade afeta decaimento?
- Insight do grafo: hubs são importantes
- Se muitas memórias referenciam X, X é central
- Central = deve ser lembrado mais tempo
- Emergente, não declarado

### Por que não usar embeddings?
- Cortex é O(1) lookup, não similaridade vetorial
- Embeddings custam tokens
- W5H permite busca estruturada sem ML
- Diferencial em relação a RAG/VectorDB

---

*Documento criado em: 06 de Janeiro de 2026*
*Baseado em pesquisa de: Ebbinghaus, CoALA, Generative Agents, Centrality*
