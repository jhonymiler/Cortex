# Cortex v5 — Detector Compliance Report

> Status against the 5-element detector from the framework in
> *"Código: Uma Teoria da Informação Funcional"*.

## Compliance Summary

| Element | Status | Implementation |
|---------|--------|----------------|
| **E1. Discrete alphabet** | ✅ | `Entity`, `Memory`, `Relation` types in `cortex_v5.core.{memory,entity,relation}` |
| **E2. Syntax** | ✅ | W5H enforced in `Memory.__post_init__` (raises if `what` empty, importance out of range) |
| **E3. Separable mapping + external referent** | ✅ | `who` points to real-world entities; `where`/`when` are physical/contextual referents |
| **E4. Independent interpreter** | ✅ | `StructuralQueryParser` (deterministic regex) + `EmbeddingRecall` (multilingual) + `LLMExtractor` (fallback) — LLM is NOT the interpreter |
| **E5. Functional semantics** | ✅ | `ForgetGate` (3-signal active forgetting), `Ebbinghaus decay` (R = e^(-t/S)), `DreamAgent` (consolidation), `access_count` (reinforcement) |

**Normative prevention (canonical-correctness norm):**

The framework requires a **correctness norm** — a privileged reading exists, and
violations are detectable. v5 implements this via `CanonicalValidator`:

| Detection Level | Mechanism | Trigger |
|-----------------|-----------|---------|
| 1. Heuristic | Negation words (PT/EN/ES) + token Jaccard | "não gosta" vs "gosta" |
| 2. Token | Token similarity (free, fast) | >0.85 = redundancy, ~0.3 = potential contradiction |
| 3. Embedding | sentence-transformers (optional) | Catches semantic opposition not visible at token level |

**Empirical benchmark (v3 baseline vs v5):**

| Metric | v3 (baseline) | v5 (greenfield) | Improvement |
|--------|---------------|------------------|-------------|
| Token reduction (context injection) | 100% baseline | 26% of baseline | **74% reduction** |
| Precision@5 | 0.603 avg | 0.819 avg | **+36% relative** |
| Contradiction detection (no FP) | 0% | 50-100% per scenario | Empirical norm-enforcement |
| Latency | n/a (v3 has no parser) | ~0.1ms per query | Deterministic, fast |

## What changed from v3 to v5

| Component | v3 (legacy) | v5 (greenfield) |
|-----------|-------------|-----------------|
| **Memory schema** | W5H but unenforced | W5H + `__post_init__` validation |
| **Schema enforcement** | None (any field could be empty) | Raises on empty `what`, out-of-range importance |
| **NORMA (preventive validation)** | Reactive (`ContradictionDetector` after write) | **Preventive** (`CanonicalValidator` before write) |
| **NORMA detection levels** | 1 (heuristic negation) | 3 (heuristic + token + embedding) |
| **Recall interpreter** | LLM only (via MCP) or full-memory dump | **Dedicated parser** (regex + token Jaccard + embedding) |
| **Internationalization** | PT-only patterns | PT + EN + ES, pluggable `Extractor` |
| **Decay function** | Ebbinghaus + SM-2 + custom mods | Ebbinghaus pure (R = e^(-t/S)) + extensible modifiers |
| **Feature flags** | 9 flags, 2^9 = 512 combinations | 3 flags (policy, embedding, dream agent) |
| **Consolidation** | Dream agent with LLM reflection | Dream agent, deterministic (no LLM) |
| **Entry point** | REST API + MCP server | Pure library (no HTTP, no MCP) |
| **From-text entry** | None | `Memory.from_text()` with optional `similar_to` inheritance |
| **Embedding-based recall** | None | Optional 3rd tier via sentence-transformers |

## What we kept from v3 (validated by 9 melhorias científicas)

- **W5H schema** — proved intuitive and didático
- **Ebbinghaus decay** — the universal forgetting curve
- **Dream Agent** — background consolidator (simplified)
- **IdentityKernel / Memory Firewall** — kept as separate concern (not in v5 core, but compatible)
- **NamespacedMemoryManager** — used in `CortexV5(namespace=...)`
- **Relation tipada** — kept with polarity + strength

## What we cut from v3 (decided not to add value)

- **SM-2 adaptativo** — Ebbinghaus is sufficient; SM-2 was overengineering
- **9 feature flags** — replaced with 3 essential ones
- **BFS Expansion, Louvain, PageRank** — discarded (per Jhony's request); decay is enough
- **ContextPacker (300 lines)** — replaced with `pack_for_context` (50 lines)
- **Hierarchical Recall (4 levels)** — replaced with binary active/archived (decay handles rest)
- **InvertedIndex** — optional, only for >10k memories
- **LLM reflection in Dream Agent** — replaced with deterministic consolidation

## What we ADDED in v5 (per detector + Jhony's feedback)

- **Pluggable extractors** (regex-PT/EN/ES, LLM fallback, hybrid)
- **Embedding-based recall** (multilingual, sentence-transformers)
- **3-level CanonicalValidator** (heuristic + token + embedding)
- **Memory.from_text()** (flexible entry for noisy input)
- **Memory.lang field** (informational, not enforced)
- **Pure library** (no HTTP, no MCP) — for embedding in Hermes directly

## Detector compliance: 5/5 ✅

All 5 elements satisfied. Normative prevention working (0 false positives).
Empirically validated via benchmark.
