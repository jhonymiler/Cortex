# Idea: Universal Event Parser — A Direction for Cortex v6+

> Captured from a focused brainstorm session. Not implemented yet.
> This is the **research direction**, not a roadmap.

---

## The thesis

5W1H is a **view** over a more fundamental representation: **events with
semantic roles**. A model that extracts events directly (not 5W1H spans)
generalizes better, is smaller, and feeds downstream systems (memory,
RAG, reasoning, planning).

The natural evolution of Cortex:

```
v5 (current):  Regex + embeddings + LLM fallback
v6:            Universal Event Extractor
               → Entity Memory
               → Incremental Coreference
               → Event Graph
               → 5W1H projection (when needed)
v7:            Add temporal reasoning, causal graph, contradiction,
               event merging, abstraction
v8:            Episodic memory: Episode = Events + Entities + Time
               + Cause + Goals + Outcomes
```

The endpoint (v8) is closer to what cognitive systems and agents actually
need. It's no longer "an extractor". It's a **Universal Event Parser**.

---

## The user's 7 points (refined)

### 1. Eliminate separate NER stage

Current pipeline (my proposal):
```
Text → NER → Event Extraction + Role Labeling → 5W1H
```

User's proposal (better):
```
Text → Event Extraction + Role Labeling → Structured Event Graph → 5W1H
```

**Why:** Modern joint models learn entity boundaries implicitly as part of
role labeling. Explicit NER is an unnecessary intermediate step.

**Benefits:**
- Lower latency (one stage vs two)
- Lower complexity (one model vs two)
- No error accumulation between stages

**Mapping (the user's insight):**
```
agent     ≈ who
patient   ≈ object
location  ≈ where
time      ≈ when
cause     ≈ why
instrument ≈ how
manner    ≈ how
purpose   ≈ why
```

### 2. Don't train for 5W1H directly

The fundamental representation is `Event(trigger, agent, patient,
recipient, instrument, location, time, cause, purpose, manner)`.

Example:
```
Input: "João comprou um carro ontem porque Maria pediu."

Events extracted:
  Event(trigger="comprar", agent="João", patient="carro",
        time="ontem", cause="Maria pediu")
  Event(trigger="pedir", agent="Maria")

Projection to 5W1H (when needed):
  who = event.agent
  what = event.trigger
  when = event.time
  why = event.cause
```

Training directly on `Event` representation generalizes better across
languages than training on language-specific 5W1H spans.

### 3. Coreference is NOT optional for memory

For memory to maintain continuity, coreference is necessary:
```
Input: "Maria ligou. Ela disse que chegaria amanhã."

Without coreference:
  event1.agent = "Maria"
  event2.agent = "Ela"   ← loses continuity

With coreference:
  event1.agent = Maria (id_17)
  event2.agent = Maria (id_17)  ← same entity
```

Pipeline:
```
Event Extraction → Entity Memory → Incremental Coreference → Event Graph
```

Doesn't need a heavy coreference model. A simple **entity memory** with
heuristics:
- "Ela" (feminine pronoun) → most recent feminine entity
- "Ele" (masculine pronoun) → most recent masculine entity
- "Eles/Elas" → most recent plural entities of that gender
- "Isso/Isso aqui" → most recent event trigger

This is "almost free" computationally but enormous for memory coherence.

### 4. Abandon ACE2005 as primary dataset

ACE is excellent but small and English-only. The user's proposed mix:

| Dataset | Type | Language | Strength |
|---------|------|----------|----------|
| PropBank | Semantic roles | EN (PT available) | Strong predicate-argument |
| Universal Dependencies | Syntactic deps | 100+ langs | Strong syntactic structure |
| WikiEvents | Event extraction | EN | Diverse event types |
| FrameNet | Semantic frames | EN | Rich frame semantics |
| Synthetic data | Generated | Any | Scalable, controllable |

**Hypothesis:** ~70% of performance comes from synthetic data.
This means we can bootstrap a high-quality跨城跨extractor without
massive human-annotated corpora.

### 5. Model size can be smaller

Estimate: **20-50M parameters**, fine-tuned, ONNX+INT8.

Candidates:
- ModernBERT-small (20M)
- Custom Transformer (50M, purpose-built)
- SmolLM2-135M (quantized, generalist)

A 20-50M model specialized in:
- Event extraction
- Semantic role labeling
- Span extraction
- Coreference (simple)

...would likely outperform a 270M generalist encoder on this specific
task. Smaller + specialized > bigger + generalist.

### 6. Span extraction > BIO tagging

BIO tagging:
```
João      B-WHO
comprou   B-WHAT
carro     I-WHAT
ontem     B-WHEN
```

Span extraction:
```
{"trigger": [1,1], "agent": [0,0], "patient": [2,3], "time": [4,4]}
```

Or directly as text:
```
{"agent": "João", "trigger": "comprou", "patient": "um carro", "time": "ontem"}
```

Span extraction generalizes better, handles discontinuous spans, and
output is more interpretable.

### 7. <5ms per sentence is achievable

Stack:
- ONNX Runtime
- INT8 quantization
- AVX2 SIMD
- 20-50M parameter model

Target latency: **2-5ms per sentence** on CPU.

This makes the extractor usable **inline in chat** without perceptible
delay.

---

## The evolutionary path (capture, don't commit to dates)

### v6 — Universal Event Parser

```
Text
  ↓
Universal Event Extractor (single model, 20-50M params, ONNX+INT8)
  ↓
Structured Event Graph:
  Event(trigger, agent, patient, recipient, instrument,
       location, time, cause, purpose, manner)
  ↓
Incremental Coreference (entity memory + heuristics)
  ↓
5W1H projection (when downstream needs it)
```

Replaces v5's `RegexExtractor` + `EmbeddingRecall` + `LLMExtractor`
with a single, fast, specialized model.

### v7 — Reasoning layer

Adds on top of v6:
- **Temporal reasoning**: when did Event A happen relative to Event B?
- **Causal graph**: Event A caused Event B?
- **Contradiction detection**: Event A's claims contradict existing?
- **Event merging**: similar events consolidated
- **Abstraction layer**: extract patterns across many events

### v8 — Episodic memory

```
Episode = {
  events: [Event, ...]
  entities: {entity_id → Entity}
  time: TimeRange
  cause: Optional<Event]
  goals: [Goal]
  outcomes: [Outcome]
}
```

This is what cognitive systems and agents actually need. Not "5W1H" but
"what happened, who was involved, when, why, what was the goal, what
was the result".

---

## Why this could be a paper

The thesis is non-trivial:

> **Universal Event Parsing — A single small model (20-50M) that extracts
> structured events from text, performs incremental coreference, and
> serves as the semantic backbone for agent memory, RAG, and reasoning.**

Compared to:
- LLM-as-parser: 100x slower, costs money, hallucination
- Regex/heuristic: brittle, language-specific, no coreference
- Existing event extraction papers: focus on single task (event det or
  role labeling), not unified memory-ready representation

The unique contribution:
1. **Single model, multiple tasks** (extraction + coreference + roles)
2. **Designed for memory** (output schema optimized for downstream)
3. **Small enough for production** (<100MB, CPU-inferrable, <10ms)
4. **Cross-language** by training on Universal Dependencies + synthetic

Reproducible artifacts:
- Trained model on HuggingFace
- Training pipeline (HuggingFace Transformers + Datasets)
- Synthetic data generator
- Cortex v6 integration code
- Benchmarks vs LLM-as-parser

---

## Open questions

1. **Where does event merging happen?** In the model output (canonical form) or post-processing?
2. **How does the model handle multi-event sentences?** Joint decoding vs sequential?
3. **What's the right loss function?** Span extraction + role classification + coreference as joint multi-task?
4. **How to generate high-quality synthetic data?** LLM-as-generator (expensive but one-time) or rule-based (cheap but lower quality)?
5. **Where does the model live in the detector compliance?** It's elem. 4 (interpreter) but a learned one — does that still satisfy "dedicated interpreter"?

---

## Status

- [x] Idea captured
- [ ] Validated with experiment
- [ ] Architecture spec
- [ ] Implementation
- [ ] Paper draft

This file is the **first artifact** of a possible research project.
Not yet committed to. Ready when you are.
