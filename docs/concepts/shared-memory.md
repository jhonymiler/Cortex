# 🔒 Memória Compartilhada com Isolamento

> **Documento Canônico** — Esta é a fonte única de verdade sobre memória compartilhada.  
> Outros documentos devem referenciar este arquivo em vez de duplicar explicações.

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

Quando um padrão se repete em múltiplos usuários:

```python
# DreamAgent detecta padrão comum
pattern = consolidate([
    "user:123 → problema com modem X",
    "user:456 → problema com modem X",
    "user:789 → problema com modem X",
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

## Relacionamento com Outros Conceitos

- **Modelo W5H**: Ver [Modelo de Memória](./memory-model.md)
- **Decaimento**: Ver [Decaimento Cognitivo](./cognitive-decay.md)
- **Consolidação**: Ver [Consolidação Hierárquica](./consolidation.md)

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

