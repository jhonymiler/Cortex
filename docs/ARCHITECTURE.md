# Architecture

Cortex is a structured memory system. This document walks through each
component and how a memory flows through the system on write and on recall.

## Data model

A **`Memory`** is a W5H record, not a blob of text:

| Field | Meaning |
|---|---|
| `who` | list of participants (entities) |
| `what` | the action / fact (required) |
| `why` | cause or motivation |
| `when` | time reference |
| `where` | location or context (defaults to `"default"`) |
| `how` | manner / resolution |
| `importance` | 0.0–1.0 salience |
| `lang` | language tag of the content |

Memories live in a **`MemoryGraph`**, an in-memory store (with JSON persistence)
that also tracks **`Entity`** nodes and typed **`Relation`** edges between them.
Each memory carries usage metadata (`access_count`, `last_accessed`,
`consolidated_into`) that drives decay and consolidation.

## Write path

```
remember(W5H) ──▶ Memory(__post_init__ validates syntax)
              ──▶ CanonicalValidator.validate_write(memory, graph)
              ──▶ WARN | BLOCK | OK
              ──▶ graph.add_memory(memory)   # unless BLOCKED
```

### CanonicalValidator (the "norm")

Before a memory is stored, it is checked against what is already known. This is
what keeps the store from silently holding `X` and `not X`. Three levels run in
increasing cost order:

1. **Heuristic** (always on, free): negation words (PT/EN/ES) + token Jaccard
   similarity. Catches `"gosta de café"` vs `"não gosta de café"`.
2. **Embedding** (optional, needs `sentence-transformers`): semantic similarity
   for contradictions that are invisible at the token level.
3. **LLM-as-judge** (optional, needs an LLM call): for ambiguous cases where the
   first two levels disagree.

The policy is configurable: `ValidationPolicy.WARN` (store but flag) or
`ValidationPolicy.BLOCK` (refuse the write).

## Recall path

```
recall(query) ──▶ detect_lang
              ──▶ HybridExtractor → QueryIntent (W5H of the question)
              ──▶ StructuralQueryParser.recall(intent, graph)
              ──▶ drop memories merged away by consolidation
              ──▶ touch() returned memories (usage signal)
              ──▶ pack_for_context(memories, intent, max_tokens)
              ──▶ (compact_context_string, RecallResult)
```

The **interpreter is deterministic**: the structural parser, not an LLM, decides
which memories match. `pack_for_context` then emits a compact string
(`who | what → how`) bounded by `max_tokens`, instead of dumping raw chunks.

### Extraction is pluggable

`QueryIntent` (the W5H of the question) is produced by an extractor:

- `RegexExtractor` — fast PT/EN/ES patterns, language detected per query.
- `LLMExtractor` — calls a user-provided `model_fn` for arbitrary languages.
- `HybridExtractor` — regex first, LLM fallback when regex confidence is low.

The W5H schema is language-neutral; only extraction is language-specific.

## Decay and consolidation

Memory is not write-only. Functional semantics come from usage:

- **Ebbinghaus decay** — retrievability `R = e^(-t/S)` where stability `S`
  grows with reinforcement (`access_count`).
- **ForgetGate** — actively drops memories that are low-importance, decayed, and
  unused.
- **DreamAgent** — an optional background worker that replays recent memories,
  consolidates near-duplicates (heuristically, or via an LLM that writes an
  info-preserving merged memory), and prunes what the forget gate releases.
  Consolidated memories are marked `consolidated_into` so they no longer surface
  on recall but remain auditable.

## Persistence

`MemoryGraph.save(path)` / `MemoryGraph.load(path, namespace=...)` serialize the
whole graph to JSON. Namespaces isolate independent memory stores (e.g.
per-session or per-user) in separate files.
