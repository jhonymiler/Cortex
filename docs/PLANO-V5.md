# Cortex v5 — Plano Arquitetural (greenfield)

> Projeto NOVO, do zero. Inteiramente em `/projetos/IA/cortex-v5/`.
> Não mexe no cortex legado (`/projetos/IA/memorias/cortex/`).
> O que está bom na Fase 1 (CanonicalValidator, StructuralQueryParser) é
> **adaptado/copiado**, não reescrito do zero.

---

## 1. TESE A DEMONSTRAR

> "Um sistema de memória agêntica que satisfaz o detector de 5 elementos
> do framework é 77%+ mais eficiente em tokens, ~37% mais preciso em
> retrieval, e detecta contradições que sistemas sem NORMA não detectam."

**Validação empírica:** Fase 1 já demonstrou -77.9% tokens. v5 deve replicar
e estender com internacionalização desde o dia 1.

---

## 2. PRINCÍPIOS DE DESIGN

### 2.1 O que MANTER (validado empiricamente)

| Componente                     | Origem         | Por que mantém                    |
|--------------------------------|----------------|----------------------------------|
| W5H como schema de Memory      | Detector elem. 1+2 | Estrutura canônica, extensível   |
| Ebbinghaus decay (R = e^(-t/S))| decay.py       | Base científica sólida            |
| Forget Gate (3 sinais)         | decay.py       | Princípio, não heurística        |
| CanonicalValidator (NORMA)     | Fase 1         | Validação preventiva funciona     |
| StructuralQueryParser (parser)| Fase 1         | 77.9% economia validada           |
| pack_for_context (compacto)    | Fase 1         | Estrela da eficiência             |
| RRF + MMR                      | ranking.py     | Estado-da-arte em IR              |
| IdentityKernel (Memory Firewall)| identity.py    | Proteção ≠ memória, separar       |
| NamespacedMemoryManager        | namespace.py   | Isolamento por namespace          |
| Relation tipada                | relation.py    | Associação explícita              |

### 2.2 O que SIMPLIFICAR (cortar inchaço)

- **9 feature flags** → 2-3 importantes (relevance, decay_mode, agent_mode)
- **SM-2 adaptativo** → fórmula simples (EF fixo + decay)
- **Context Packer (300 linhas)** → reescrever como `pack_for_context` (50 linhas)
- **BFS Expansion, Louvain, PageRank** → mover pra módulo opcional `cortex_v5.contrib.graph` (só importar se precisar)
- **Hierarchical Recall com 4 níveis** → 2 níveis (active/archived) com decay
- **Inverted Index** → opcional, só pra escala >10k memories

### 2.3 O que ADICIONAR (v5 novo)

| Componente                     | Por que adiciona                |
|--------------------------------|---------------------------------|
| `lang` field em Memory         | Internacionalização desde o dia 1 |
| `Extractor` interface pluggable| Idioma-independente             |
| `RegexExtractor` (PT + EN + ES)| Patterns por idioma            |
| `LLMExtractor` (opcional)      | Fallback para queries complexas  |
| `HybridExtractor`              | Regex primeiro, LLM fallback     |
| Lang detector automático        | Detecta PT/EN/ES do input       |
| Validator de contradição V2    | 3 níveis: heurística + embedding + LLM |
| `AgentWrapper` (Modo 2)        | Interceptação automática LLM    |
| `Lang` field em QueryIntent    | Schema canônico preserva lang   |

### 2.4 O que CORTAR (decisão consciente)

- **Neo4j adapter** (manter JSON storage por enquanto — reavaliar em v6 se escala)
- **9 melhorias científicas** como features isoladas (consolidar nas 2-3 que importam)
- **MCP como modo primário** (manter como opcional, Modo 2 é o default)

---

## 3. ARQUITETURA

### 3.1 Estrutura de diretórios

```
cortex-v5/
├── pyproject.toml
├── README.md
├── LICENSE (MIT)
├── cortex_v5/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── memory.py            # Memory com lang
│   │   ├── graph.py             # MemoryGraph enxuto
│   │   ├── entity.py            # Entity (copy/refactor)
│   │   ├── relation.py          # Relation tipada
│   │   ├── namespace.py         # Isolamento
│   │   ├── validation/
│   │   │   ├── __init__.py
│   │   │   ├── canonical.py     # V2 (heurística + embedding + LLM)
│   │   │   └── contradiction.py # Heurísticas expandidas
│   │   ├── recall/
│   │   │   ├── __init__.py
│   │   │   ├── extractor.py     # Pluggable interface
│   │   │   ├── extractors/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── regex_pt.py
│   │   │   │   ├── regex_en.py
│   │   │   │   ├── regex_es.py
│   │   │   │   ├── llm.py
│   │   │   │   └── hybrid.py
│   │   │   ├── lang_detect.py   # Detecção de idioma
│   │   │   ├── parser.py        # StructuralQueryParser (refatorado)
│   │   │   ├── pack.py          # pack_for_context compacto
│   │   │   └── ranking.py       # RRF + MMR (refatorado)
│   │   ├── decay/
│   │   │   ├── __init__.py
│   │   │   ├── ebbinghaus.py    # Curva R = e^(-t/S)
│   │   │   └── forget_gate.py   # 3 sinais
│   │   └── integration/
│   │       ├── __init__.py
│   │       └── agent_wrapper.py # Modo 2 (interceptação)
│   ├── api.py                   # API REST enxuta
│   └── version.py
├── tests/
│   ├── core/
│   │   ├── test_memory.py
│   │   ├── test_graph.py
│   │   ├── test_canonical_validator.py
│   │   ├── test_extractor.py
│   │   ├── test_recall.py
│   │   ├── test_decay.py
│   │   └── test_agent_wrapper.py
│   └── integration/
│       └── test_e2e.py
├── bench/
│   ├── scenarios/
│   │   ├── customer_support_pt.json
│   │   ├── customer_support_en.json
│   │   ├── personal_assistant_pt.json
│   │   ├── developer_agent_pt.json
│   │   └── long_horizon_pt.json
│   ├── run_benchmark_v5.py
│   └── results/
├── docs/
│   ├── design-decisions.md
│   ├── detector-compliance.md
│   └── v4-to-v5-migration.md
└── examples/
    ├── minimal_usage.py
    └── langchain_integration.py
```

### 3.2 Fluxo de dados

```
[Query em qualquer idioma]
        ↓
[LangDetector]  → "pt" | "en" | "es" | "auto"
        ↓
[HybridExtractor] (regex + LLM fallback)
        ↓
[QueryIntent]  (W5H canônico, lang field)
        ↓
[StructuralQueryParser.recall(query, graph)]
   ├── structural match (W5H exact/partial)
   ├── semantic fallback (token jaccard ou embedding)
   └── pack_for_context (max_tokens)
        ↓
[Compact context string] → injetado no LLM

[Memory write]
        ↓
[CanonicalValidator.validate_write] (3 níveis)
   ├── Level 1: heurística (negação + polarity)
   ├── Level 2: embedding similarity (se embedding disponível)
   └── Level 3: LLM-as-judge (se configurado)
        ↓
[Result: OK / WARN / BLOCKED]
        ↓
[Write to graph] (se não bloqueado)
```

### 3.3 Detector compliance (alvo 5/5)

| Elemento                  | Implementação v5                           | Veredito esperado |
|---------------------------|--------------------------------------------|-------------------|
| 1. Alfabeto discreto      | Memory dataclass com tipos + namespace     | ✓                 |
| 2. Sintaxe                | W5H enforced via `__post_init__` + types   | ✓ (target)        |
| 3. Mapeamento separável   | Entity/Memory aponta pra referente externo | ✓                 |
| 4. Intérprete dedicado    | Extractor pluggable (regex+LLM), não LLM genérico | ✓        |
| 5. Semântica funcional     | Forget Gate + decay + função clara        | ✓                 |

**NORMA (preventiva):** CanonicalValidator v2 com 3 níveis.
**Detector compliance target:** 5/5 com banda full (não inconclusivo).

---

## 4. PLANO DE EXECUÇÃO

### 4.1 Fases

```
F0: Setup (~30min)
    - pyproject.toml, README, .gitignore
    - Estrutura de diretórios
    - git init

F1: Core (Memory, Entity, Relation, Graph) (~2-3h)
    - Memory com lang field
    - Graph enxuto
    - Tests básicos (15+ testes)

F2: Internacionalização (Extractor pluggable) (~2-3h)
    - Extractor interface
    - RegexExtractor PT, EN, ES
    - LangDetector
    - HybridExtractor
    - Tests (20+ testes multi-idioma)

F3: Validator V2 (NORMA 3 níveis) (~2h)
    - CanonicalValidator V2 (heurística mantida)
    - Contradiction heuristics expandidas
    - Embedding similarity level 2 (opcional)
    - LLM-as-judge level 3 (opcional, pluggable)
    - Tests (15+ testes, incluindo EN)

F4: Recall (Parser + Pack + Ranking) (~2h)
    - Reusar/refatorar da Fase 1
    - pack_for_context otimizado
    - RRF + MMR simplificado
    - Tests (10+ testes)

F5: Decay + Forget Gate (~1h)
    - Ebbinghaus simples
    - Forget Gate
    - Tests (8+ testes)

F6: AgentWrapper (Modo 2) (~2-3h)
    - Interceptação automática
    - Integração com LLM (OpenAI, Anthropic, Ollama)
    - Tests (8+ testes integração)

F7: Benchmarks (~1-2h)
    - Adaptar cenários da Fase 1 (PT)
    - Adicionar 1 cenário EN
    - Rodar v3 vs v5
    - Gerar tabela empírica
    - Comparação com Fase 1

F8: Documentação (~1h)
    - README
    - docs/design-decisions.md
    - docs/detector-compliance.md
    - examples/

Total: ~14-18h de trabalho (1-2 semanas)
```

### 4.2 Critério de "pronto"

- [ ] Todos os 5 elementos do detector passam (5/5)
- [ ] Benchmarks mostram >= 70% token reduction (mantém ganho da Fase 1)
- [ ] 90%+ testes passando
- [ ] Documentação completa
- [ ] Pelo menos 1 idioma extra além de PT funciona end-to-end

### 4.3 Critério de "abortar" / voltar pra Fase 1

- [ ] Se v5 não atingir 5/5 no detector após F3
- [ ] Se benchmarks mostrarem regressão vs Fase 1
- [ ] Se internacionalização quebrar o detector

---

## 5. DECISÕES PENDENTES (precisam de confirmação)

1. **Nome da pasta:** `/projetos/IA/cortex-v5/` ✓ (já criado)
2. **Package name:** `cortex_v5` (Python) — `import cortex_v5`
3. **Storage backend:** JSON only (Neo4j opcional em v6)
4. **LLM providers no Modo 2:** OpenAI, Anthropic, Ollama, vLLM (não todos inicialmente)
5. **Embedding provider:** sentence-transformers (local, grátis) opcional
6. **Versão inicial:** 5.0.0
7. **License:** MIT (mesma do cortex atual)

---

## 6. RELAÇÃO COM PROJETOS EXISTENTES

| Projeto                                  | Relação                              |
|------------------------------------------|--------------------------------------|
| `/projetos/IA/memorias/cortex/` (v3)     | LEGADO. Não tocado. Referência.      |
| `refactor/v4-extensions` branch (Fase 1) | FONTE. Copiar/adaptar CanonicalValidator, StructuralQueryParser. |
| `/projetos/Livros/Código: Uma Teoria.../`| TEORIA. Detector de 5 elementos.     |
| `Pappers-Atack/OP-2-agent-memory/`       | COMPARAÇÃO. Aplicar detector em v5.  |

---

## 7. PRÓXIMO PASSO IMEDIATO

Se você aprovar o plano:
- F0: setup (30min)
- F1: Core (2-3h)
- F2: Internacionalização (2-3h)

**Estimativa total v5: 14-18h de trabalho focado = 1-2 semanas.**

Após F1+F2, eu paro pra você revisar antes de seguir pra F3.
