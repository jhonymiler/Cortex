# Detector Compliance

> How Cortext satisfies the **5-element detector** from the framework in
> *"Código: Uma Teoria da Informação Funcional"* — the criterion that
> distinguishes *encoded information* from mere correlation.

## Compliance summary

| Element | Status | Implementation |
|---------|--------|----------------|
| **E1. Discrete alphabet** | ✅ | `Entity`, `Memory`, `Relation` types in `cortext.core.{memory,entity,relation}` |
| **E2. Syntax** | ✅ | W5H enforced in `Memory.__post_init__` (raises on empty `what`, out-of-range importance) |
| **E3. Separable mapping + external referent** | ✅ | `who` points to real-world entities; `where`/`when` are physical/contextual referents |
| **E4. Independent interpreter** | ✅ | `StructuralQueryParser` (deterministic regex) + embedding recall + `LLMExtractor` fallback — the LLM is *not* the interpreter |
| **E5. Functional semantics** | ✅ | `ForgetGate` (3-signal active forgetting), Ebbinghaus decay (R = e^(−t/S)), `DreamAgent` consolidation, `access_count` reinforcement |

## Normative prevention (correctness norm)

The framework requires a **correctness norm** — a privileged reading exists and
violations are detectable. Cortext implements this with `CanonicalValidator`,
which runs *before* a write so contradictions are prevented, not merely detected
after the fact:

| Detection level | Mechanism | Trigger |
|-----------------|-----------|---------|
| 1. Heuristic | Negation words (PT/EN/ES) + token Jaccard | "não gosta" vs "gosta" |
| 2. Token | Token similarity (free, fast) | >0.85 = redundancy, ~0.3 = potential contradiction |
| 3. Embedding | sentence-transformers (optional) | Semantic opposition invisible at token level |

## Empirical benchmark

Cortext vs an unstructured top-k baseline (return-all-memories), 2 scenarios,
reproducible via `python bench/run_benchmark.py`:

| Metric | Baseline | Cortext | Improvement |
|--------|----------|---------|-------------|
| Context tokens | 100% | 26% of baseline | **74% reduction** |
| Precision@5 | 0.603 avg | 0.819 avg | **+36% relative** |
| Contradiction detection (0 FP) | 0% | 67–100% per scenario | Norm enforcement |
| Recall latency | — (no parser) | ~0.1 ms / query | Deterministic, fast |

## Design choices

What Cortext deliberately includes, and what it deliberately leaves out, to keep
the system simple while staying detector-compliant:

**Included**
- W5H schema with syntax enforcement at construction time.
- Preventive `CanonicalValidator` (3 detection levels).
- Deterministic recall interpreter (regex + token + optional embedding) —
  pluggable extractors for PT/EN/ES with an LLM fallback for any language.
- Pure Ebbinghaus decay (R = e^(−t/S)) plus a forget gate.
- Optional `DreamAgent` background consolidation (heuristic by default, LLM-merge
  optional).
- Pure library: no HTTP, no MCP — embed it directly in an agent loop.

**Left out (on purpose)**
- SM-2 / adaptive spacing — Ebbinghaus is sufficient.
- Large feature-flag matrices — three knobs (validation policy, embedding tier,
  dream agent) cover the real cases.
- Graph-expansion retrieval (BFS / Louvain / PageRank) — decay + structural
  recall are enough.
- Heavyweight context packers and multi-level hierarchical recall — replaced by a
  compact `pack_for_context` and a binary active/archived model.

## Result: 5/5 ✅

All five detector elements are satisfied, normative prevention works (0 false
positives across the benchmark), and the claims are empirically validated.
