# 🔒 Aprendizado Coletivo com Privacidade
*(Memória Compartilhada com Isolamento)*

> **A dor:** Conhecimento fica preso em silos — cada atendente resolve o mesmo problema do zero.
> **A solução:** Cortex compartilha padrões aprendidos enquanto isola dados pessoais por design.
> **O resultado:** Resolva um problema uma vez, beneficie todos os usuários. LGPD/GDPR compliant.

*Documento Canônico — fonte única de verdade sobre memória compartilhada.*

---

## Por Que Isso Importa

A **Memória Coletiva** é uma das [5 dimensões de valor](../research/benchmarks.md) do Cortex:

| Dimensão | Score | Cortex é Único? |
|----------|-------|-----------------|
| 🧠 Cognição Biológica | 100% | ✅ Exclusivo |
| 👥 **Memória Coletiva** | **75%** | ✅ **Exclusivo** |
| 🎯 Valor Semântico | 100% | Empata |
| ⚡ Eficiência | 100% | ✅ Exclusivo |
| 🔒 Segurança | 100% | ✅ Exclusivo |

**Nenhum concorrente** (Baseline, RAG, Mem0) oferece memória coletiva com isolamento.

---

## O Problema

Agentes que atendem **múltiplos usuários** enfrentam um dilema:

| Necessidade | Risco |
|-------------|-------|
| Aprender com todos os atendimentos | Vazar dados de um cliente para outro |
| Compartilhar conhecimento comum | Misturar informações pessoais |
| Escalar aprendizado | Violar privacidade (LGPD, GDPR) |

---

## A Solução: Três Níveis de Visibilidade

```
┌─────────────────────────────────────────────────────────────┐
│                    NAMESPACE: agente_suporte                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PERSONAL (isolado por usuário)                            │
│  ═══════════════════════════════                           │
│  user:123 → "João pediu pedido #456"                       │
│  user:456 → "Maria mora em São Paulo"                      │
│  user:789 → "Carlos tem modem TP-Link"                     │
│                                                             │
│  ⚠️ NUNCA cruza entre usuários                             │
│  ⚠️ PII/PCI permanece aqui                                 │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  SHARED (visível a todos do namespace)                     │
│  ═════════════════════════════════════                     │
│  "Política de devolução: 30 dias"                          │
│  "Horário de atendimento: 8h-18h"                          │
│  "Promoção atual: frete grátis acima de R$100"             │
│                                                             │
│  ✅ Conhecimento institucional                              │
│  ✅ Configurável pelo admin                                 │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  LEARNED (padrões aprendidos, anonimizados)                │
│  ═══════════════════════════════════════════               │
│  "Padrão: clientes perguntam muito sobre prazos"           │
│  "Insight: modem X tem problema recorrente de luz vermelha"│
│  "Tendência: dúvidas sobre PIX aumentaram 40%"             │
│                                                             │
│  ✅ Extraído de PERSONAL após anonimização                  │
│  ✅ Melhora atendimento de todos                            │
│  ❌ Nunca contém PII/PCI                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## SharedMemoryManager

### Uso Básico

```python
from cortex.core import SharedMemoryManager

manager = SharedMemoryManager()

# Namespace pessoal do usuário
personal_ns = manager.get_personal_namespace("user_123")
# → "user:user_123"

# Para recall, combina personal + shared + learned
namespaces = manager.get_recall_namespaces("user_123")
# → ["user:user_123", "shared", "learned"]

# Para store, determina onde salvar
target_ns = manager.get_store_namespace(
    user_id="user_123",
    memory_type="personal"  # ou "shared", "learned"
)
```

### Regras de Isolamento

```python
# ❌ NUNCA acontece:
recall(user="user_123", namespaces=["user:user_456"])

# ✅ Sempre acontece:
recall(user="user_123", namespaces=[
    "user:user_123",  # Próprio
    "shared",         # Comum
    "learned"         # Padrões
])
```

---

## Fluxo de Dados

### Store (Armazenar)

```
┌───────────────────┐
│  Memória Nova     │
│  "João pediu #456"│
└─────────┬─────────┘
          │
          ▼
┌─────────────────────────────────────────┐
│  Classificação                          │
│  ├─ Contém PII/PCI? → PERSONAL          │
│  ├─ É política/regra? → SHARED          │
│  └─ É padrão anonimizado? → LEARNED     │
└─────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────┐
│  Armazenamento                          │
│  namespace = "user:user_123" (PERSONAL) │
└─────────────────────────────────────────┘
```

### Recall (Recuperar)

```
┌───────────────────┐
│  Query:           │
│  "prazo devolução"│
│  user: user_123   │
└─────────┬─────────┘
          │
          ▼
┌─────────────────────────────────────────┐
│  Busca em:                              │
│  1. user:user_123 (PERSONAL)            │
│  2. shared (SHARED)                     │
│  3. learned (LEARNED)                   │
└─────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────┐
│  Resultados mesclados                   │
│  ├─ "João pediu #456" (personal)        │
│  ├─ "Devolução: 30 dias" (shared)       │
│  └─ "Clientes perguntam prazos" (learned)│
└─────────────────────────────────────────┘
```

---

## Promoção: Personal → Learned

### Princípio Fundamental

> **Conhecimento coletivo NÃO é o que a IA "acha" que é útil.**
> **Conhecimento coletivo É padrões que se repetem entre usuários diferentes.**

### Definição de Conhecimento Coletivo

| Tipo | Critério | Exemplo |
|------|----------|---------|
| **Dúvidas Comuns** | N usuários → mesma dúvida → mesma resolução | "Como resetar senha?" → "/forgot-password" |
| **Procedimentos** | N usuários → passos similares → mesma resolução | Deploy → build → test → push |

### Arquitetura de Promoção (Duas Etapas)

O DreamAgent **não processa todas as memórias de uma vez** — com milhões de lembranças, isso seria inviável.

**Etapa 1: Seleção de Candidatos** (Batch/Scheduled)

Por tenant, seleciona memórias baseado em:

```python
candidatos = selecionar_por_tenant(
    # Critério 1: Memórias mais acessadas
    ordem_por=["access_count DESC"],
    
    # Critério 2: Memórias com mais conexões (hub centrality)
    minimo_conexoes=3,
    
    # Critério 3: Memórias marcadas como procedimento
    tipo=["procedimento", "resolucao"],
    
    limite=100  # Top 100 candidatos por tenant
)
```

**Etapa 2: Análise e Promoção** (DreamAgent)

```python
for candidato in candidatos:
    # Verifica se é padrão repetido entre usuários
    usuarios_similares = contar_usuarios_com_padrao_similar(candidato)
    
    if usuarios_similares >= 3:  # Threshold configurável
        # Anonimiza e promove
        promover_para_learned(candidato)
```

### Marcação de Procedimentos

Durante a consolidação normal, o DreamAgent marca memórias que são **procedimentos**:

```python
# Na consolidação:
if detectar_sequencia_de_passos(memoria):
    memoria.metadata["tipo"] = "procedimento"
    memoria.metadata["passos"] = extrair_passos(memoria)
```

Isso facilita a seleção posterior:

```python
# Na seleção de candidatos:
procedimentos = buscar(tipo="procedimento", importancia__gte=0.7)
```

### Evolução por Consolidação

Procedimentos podem **evoluir** quando múltiplos usuários executam passos similares:

```
User A: Deploy → build → test → push → notify
User B: Deploy → build → push → notify (sem test)
User C: Deploy → build → test → push → notify

→ Consolida: Deploy → build → test → push → notify (melhor prática)
→ Promove para LEARNED: "Procedimento de Deploy"
```

### Exemplo Completo

```python
# DreamAgent detecta padrão comum entre 3+ usuários
pattern = consolidate([
    "user:123 → problema com modem X → atualizar firmware",
    "user:456 → problema com modem X → atualizar firmware",
    "user:789 → problema com modem X → atualizar firmware",
])

# Anonimiza e promove para LEARNED
promoted = Memory(
    who=["cliente_generico", "modem_X"],
    what="problema_recorrente_luz_vermelha",
    why="firmware_desatualizado",
    how="atualizar_firmware_resolve",
    where="learned"  # ← Promovido!
)

# Remove PII antes de promover
assert "João" not in str(promoted)
assert "@email.com" not in str(promoted)
```

### Decaimento de LEARNED

| Tipo | Decaimento |
|------|------------|
| **PERSONAL** | Curva de Ebbinghaus normal |
| **LEARNED** | **Fixo** (sem decay por enquanto) |

**Futuro**: LEARNED pode ter decay baseado em uso agregado, gerando relatórios de "conhecimentos que podem estar desatualizados" para review do cliente.

---

## Casos de Uso

### 1. Customer Support

```python
# Atendente atendeu 100 clientes
# Cada um tem namespace isolado

# Após consolidação:
learned_memories = [
    "Modem X tem bug de luz vermelha → atualizar firmware",
    "Clientes VIP preferem chat sobre telefone",
    "Problema de pagamento geralmente é cartão expirado"
]
# Todos atendentes se beneficiam
```

### 2. Dev Team

```python
# Time de 5 devs compartilha workspace

# PERSONAL (cada dev):
"João prefere TypeScript"
"Maria usa VSCode com vim bindings"

# SHARED (time):
"Convenção: camelCase para variáveis"
"Deploy: sempre via CI/CD"

# LEARNED (emergente):
"Bugs de timeout geralmente são conexões não fechadas"
"Erros de import são 80% das vezes path errado"
```

### 3. Healthcare (HIPAA Compliance)

```python
# PERSONAL (paciente, ultra-isolado):
"Carlos tem diabetes tipo 2"  # NUNCA sai daqui

# SHARED (clínica):
"Horário: 8h-18h"
"Aceita convênio X"

# LEARNED (padrões médicos):
"Pacientes com sintoma X geralmente têm condição Y"
# 100% anonimizado, validado por médico
```

---

## Configuração

```bash
# .env
CORTEX_MEMORY_MODE=hybrid  # individual | shared | hybrid

# Modos:
# individual: Só PERSONAL, sem compartilhamento
# shared: Tudo em SHARED (cuidado com PII!)
# hybrid: PERSONAL + SHARED + LEARNED (recomendado)
```

---

## API

### Store com Nível

```bash
POST /memory/remember
X-Cortex-Namespace: meu_agente
X-Cortex-User: user_123
Content-Type: application/json

{
    "who": ["João"],
    "what": "pediu_reembolso",
    "memory_level": "personal"  # ou "shared", "learned"
}
```

### Recall com Isolamento

```bash
POST /memory/recall
X-Cortex-Namespace: meu_agente
X-Cortex-User: user_123
Content-Type: application/json

{
    "query": "política de devolução"
}

# Automaticamente busca em:
# - user:user_123 (personal)
# - shared
# - learned
```

---

## Proteção de PII/PCI

### Regra Fundamental

> **PII (Personally Identifiable Information) e PCI (Payment Card Industry) NUNCA saem de PERSONAL.**

### Detecção Automática

```python
PII_PATTERNS = [
    r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b',  # CPF
    r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # Cartão
    r'\b[\w.-]+@[\w.-]+\.\w+\b',  # Email
    r'\b\d{2}[\s.-]?\d{4,5}[\s.-]?\d{4}\b',  # Telefone
]

def contains_pii(text: str) -> bool:
    return any(re.search(p, text) for p in PII_PATTERNS)

# Se contém PII, FORÇA namespace personal
if contains_pii(memory.what) or contains_pii(memory.how):
    memory.where = f"user:{user_id}"
```

---

## 🧭 Próximos Passos

Escolha seu caminho baseado no que você quer fazer agora:

> **🚀 Quer configurar shared memory no seu agente?**
> 
> ```bash
> # .env
> CORTEX_MEMORY_MODE=hybrid  # individual | shared | hybrid
> ```
> 
> ```bash
> # Armazenar com nível específico
> curl -X POST http://localhost:8000/memory/remember \
>   -H "X-Cortex-Namespace: suporte" \
>   -H "X-Cortex-User: user_123" \
>   -d '{"who": ["João"], "what": "preferencia", "memory_level": "personal"}'
> ```
> → [API Reference](../architecture/api-reference.md)

> **🔬 Quer entender como padrões são promovidos para LEARNED?**
> 
> O DreamAgent detecta padrões comuns entre usuários e promove para LEARNED (após anonimização).
> → [Consolidação Hierárquica](./consolidation.md)

> **💡 Quer ver a economia com shared memory?**
> 
> No benchmark de Dev Team, shared memory economizou **15.2%** vs memória individual.
> → [Benchmarks: Shared Memory](../research/benchmarks.md#benchmark-de-shared-memory)

> **🏥 Quer garantir compliance (LGPD, HIPAA)?**
> 
> PII/PCI é **automaticamente detectado** e forçado para namespace PERSONAL.
> Ver seção [Proteção de PII/PCI](#proteção-de-piipci) acima.

---

## Compliance

| Regulação | Como Cortex Atende |
|-----------|-------------------|
| **LGPD** | PII isolado em PERSONAL, nunca compartilhado |
| **GDPR** | Right to be forgotten via namespace delete |
| **HIPAA** | PHI em PERSONAL com audit trail |
| **PCI-DSS** | Dados de cartão NUNCA saem de PERSONAL |

---

*Documento canônico de memória compartilhada — Última atualização: Janeiro 2026*

