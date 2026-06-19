# Cortex

*Read this in [Português](README.pt-br.md).*

> **A cognitive memory system for AI agents — structured, internationalized, contradiction-aware, and token-efficient.**

Cortex gives an LLM agent a long-term memory that is *structured* rather than a
flat vector store. Every memory is decomposed into a **W5H** record (who, what,
why, when, where, how), validated against what is already known so the agent
does not silently store contradictions, and recalled through a deterministic
structural parser that returns a **compact** context string instead of a wall
of raw chunks.

It is a pure Python library with **zero required dependencies**, local-first,
and designed to plug into an agent loop as a transparent memory layer (recall
before the turn, store after it).

```python
from cortext import CortexV5

cortex = CortexV5(namespace="myapp")

# Store a structured memory (W5H)
cortex.remember(
    who=["Maria"],
    what="reportou erro de pagamento",
    why="cartão expirado",
    where="suporte",
    how="orientada a atualizar dados",
    lang="pt",
)

# Recall — returns (compact_context, RecallResult)
context, result = cortex.recall("O que Maria pediu?")
print(context)
# Maria | reportou erro de pagamento
```

## Why structured memory

Most agent memory is "embed the turn, retrieve top-k chunks." That works until
it doesn't: chunks are bulky, retrieval mixes unrelated facts, and nothing stops
the store from holding `X` and `not X` at the same time.

Cortex takes a different stance — memory is **encoded information**, not mere
correlation. It is built around five structural properties (discrete schema,
syntax, an arbitrary-but-stable mapping to external referents, an independent
interpreter, and functional semantics driven by usage). In practice that buys
you four concrete things:

| Property | What it means in practice |
|---|---|
| **Structured (W5H)** | Recall returns `Maria \| reportou erro → orientada a atualizar dados`, not a 90-token chunk. |
| **Normative** | A `CanonicalValidator` detects contradictions *at write time* (3 levels: heuristic → embedding → LLM-as-judge) and can warn or block. |
| **Internationalized** | The W5H schema is language-neutral; only extraction is language-specific, and it is pluggable (PT/EN/ES regex + optional LLM fallback). |
| **Self-pruning** | Ebbinghaus decay + a forget gate + an optional background `DreamAgent` that replays, consolidates duplicates, and prunes what is no longer used. |

## Benchmarks

Reproducible on this repo (`python bench/run_benchmark.py`), comparing Cortex
against an unstructured top-k baseline across 2 scenarios:

| Scenario | Tokens (baseline → Cortex) | Savings | P@5 (baseline → Cortex) | Contradiction detection |
|---|---|---|---|---|
| customer_support | 540 → 123 | **77.2%** | 0.367 → 0.778 | 100% |
| personal_assistant | 380 → 111 | **70.8%** | 0.840 → 0.860 | 67% |
| **Average** | — | **74.0%** | **0.603 → 0.819** | 83.5% |

- **~74% fewer context tokens** for the same retrieved information.
- **Precision@5 up from 0.60 to 0.82** — recall returns the *right* memories.
- **Zero false positives** in contradiction detection across both scenarios.
- **~0.1 ms** average recall latency (pure Python, in-memory graph).

Token savings directly cut prompt cost and free context budget for the actual
task; higher precision means the agent sees fewer irrelevant memories.

## Install

```bash
pip install cortext
```

Optional extras:

```bash
pip install "cortext[embeddings]"   # sentence-transformers for embedding-level validation
pip install "cortext[dev]"          # pytest, ruff
```

Cortex runs with **no extra dependencies** by default. The embedding and
LLM-as-judge contradiction levels are opt-in.

## How it works

```
WRITE   text/W5H ──▶ CanonicalValidator (3-level) ──▶ Memory Graph
                         (warn or block contradictions)

RECALL  query ──▶ LangDetector ──▶ HybridExtractor ──▶ QueryIntent (W5H)
                                                            │
              Memory Graph ──▶ StructuralQueryParser ──▶ pack_for_context
                                                            │
                                                   compact context string

DECAY   Ebbinghaus retrievability + ForgetGate, with an optional background
        DreamAgent that replays, consolidates duplicates, and prunes.
```

### Internationalization

The W5H schema is universal; **extraction** is the only language-specific part,
and it is pluggable:

```python
from cortext import RegexExtractor, HybridExtractor, LLMExtractor

extractor = HybridExtractor(
    primary=RegexExtractor(default_lang="auto"),   # PT, EN, ES — detected per query
    fallback=LLMExtractor(model_fn=my_llm_call),   # any language, when regex misses
)
```

Recall is matched within the language of the stored content — store and query in
the same language for best results, or wire an LLM extractor for arbitrary
languages.

## Using it inside an agent

The intended pattern is a transparent memory layer: recall before the LLM call,
store after it. `HermesCortexBridge` is a reference implementation of exactly
this:

```python
from cortext.integration import HermesCortexBridge

bridge = HermesCortexBridge(namespace="session-1")

# Before the LLM call — inject recalled context:
context = bridge.pre_chat(user_input)
system_prompt = context + "\n\n" + base_system_prompt

# After the turn — persist it:
bridge.post_chat(user_message=user_input, assistant_message=reply)
```

See [docs/INTEGRATION.md](docs/INTEGRATION.md) for plugging Cortex into an agent
(including the Hermes memory plugin) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
for the component-by-component design.

## Development

```bash
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

pytest                                  # 190+ tests
python bench/run_benchmark.py        # reproduce the benchmarks
```

## License

MIT — see [LICENSE](LICENSE).
