# Cortex v5

> **Memory system for AI agents — 5-element detector compliant, internationalized, efficient.**

Cortex v5 is a complete rewrite of [Cortex v3](../memorias/cortex/) implementing
the **5-element detector** of the framework in
*"Código: Uma Teoria da Informação Funcional"*.

The framework's core claim: a memory system is **encoded information** (not mere
correlation) when it satisfies five structural elements — discrete alphabet,
syntax, separable arbitrary mapping with external referent, independent
interpreter, and functional semantics.

Cortex v5 implements this detector as an **operational tool**: every component
contributes to one or more elements, and you can audit the system against the
framework directly.

## Key properties

- **5/5 detector compliance** — every element implemented and tested
- **Internationalized** — W5H schema is universal, but extraction is pluggable
  (PT, EN, ES via regex; LLM fallback for arbitrary languages)
- **Normative** — CanonicalValidator with 3 detection levels prevents
  contradictions at write time, not just detects them after
- **Efficient** — empirical 77%+ token reduction vs unstructured retrieval
- **Simple** — no 9-feature-flag hell, no SM-2, no BFS expansion. Just decay
  and forget gate, with optional dream agent consolidation.

## Quick start

```python
from cortex_v5 import CortexV5

cortex = CortexV5(namespace="myapp")

# Store a memory (W5H structure)
cortex.remember(
    who=["Maria"],
    what="reportou erro de pagamento",
    why="cartão expirado",
    where="suporte",
    how="orientada a atualizar dados",
    lang="pt",
)

# Recall with deterministic structural parsing
context = cortex.recall("O que Maria pediu?")
print(context)
# Output: Maria | reportou erro de pagamento → orientada a atualizar dados

# Or use the agent wrapper (Modo 2) for full auto-interception
from cortex_v5.integration import AgentWrapper

agent = AgentWrapper(llm=my_llm, cortex=cortex)
response = agent.chat("Maria ligou reclamando do mesmo problema")
# Cortex auto-injects context; LLM doesn't need to know about memory
```

## Multi-language

```python
# Portuguese (default)
cortex.recall("O que Maria pediu?")

# English (auto-detected or explicit)
cortex.recall("What did Maria ask?", lang="en")
# → Maria | reportou erro de pagamento (or english equivalent if stored)

# Spanish
cortex.recall("¿Qué pidió María?", lang="es")
```

The W5H schema is universal. The **extraction** of W5H values from text is
the only language-specific part, and it's pluggable:

```python
from cortex_v5.recall import HybridExtractor, RegexExtractor, LLMExtractor

# Fast path: regex (PT, EN, ES)
extractor = HybridExtractor(
    primary=RegexExtractor(lang="auto"),   # detects per-query
    fallback=LLMExtractor(model="gemma3:4b"),  # when regex fails
)
```

## Architecture

See `docs/PLANO-V5.md` for the full architectural plan and rationale.

Briefly:

```
[Query] → [LangDetector] → [HybridExtractor] → [QueryIntent (W5H)]
                                                    ↓
[Memory write] → [CanonicalValidator V2] → [3-level contradiction check]
                                                    ↓
                                            [Memory Graph]
                                                    ↓
[Recall] → [StructuralQueryParser] → [pack_for_context] → [compact prompt]
```

## Detection levels

The CanonicalValidator runs 3 levels of contradiction detection:

1. **Heuristic** (always): negation words + polarity inversion
2. **Embedding** (optional, requires `sentence-transformers`):
   semantic similarity for implicit contradictions
3. **LLM-as-judge** (optional, requires LLM call): for ambiguous cases
   where 1+2 disagree

## Benchmarks

See `bench/results/` for empirical comparison vs Cortex v3.

Headline result (4 scenarios, 5 metrics):
- **77.9% token reduction** on context injection
- **+37% Precision@5** in retrieval
- **0 false positives** in contradiction detection

## Development

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run benchmarks
PYTHONPATH=. python bench/run_benchmark_v5.py
```

## License

MIT — see `LICENSE`.

## Related projects

- [Cortex v3](../memorias/cortex/) — predecessor (legacy, preserved)
- [Fase 1 extensions](../memorias/cortex/tree/refactor/v4-extensions) —
  CanonicalValidator and StructuralQueryParser that v5 builds on
- [The framework book](../../Livros/Código: Uma Teoria da Informação Funcional/) —
  the theoretical foundation
