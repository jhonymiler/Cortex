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

Memories live in a **`MemoryGraph`**, which also tracks **`Entity`** nodes and
typed **`Relation`** edges. Each memory carries usage metadata (`access_count`,
`last_accessed`, `consolidated_into`) that drives decay, levels and consolidation.

### Indexes

Every lookup on the hot path is served from an index; nothing scans the graph:

| Index | Key → value | Serves |
|---|---|---|
| token | content token → memory ids | text recall, validation candidates, redundancy |
| who | folded participant name → memory ids | structural recall, `about()`, neighbours |
| where | place → memory ids | `find_memories(where=)` |
| no-who | memory ids with no participant | validation candidate pruning |
| entity name | folded name → entity ids | homonym check |
| node adjacency | node id → relation ids (ordered) | `find_relations()` |

Tokens come from one tokenizer (`cortext/core/text.py`): lowercase, accents
folded (`não` = `nao`), conservative plural stemming (`filas` = `fila`),
stopwords and short tokens dropped, memoized. The memory tables are dict
subclasses that update the indexes on every write, so even direct
`graph._memories[id] = m` assignments stay consistent. Entities and memories
form a bipartite graph through `who`: two memories are **neighbours** when they
share a participant.

### Levels

`memory_tier()` places each memory on a lifecycle the dashboard and the agents show:

| Level | Rule |
|---|---|
| working | stored less than an hour ago and not yet reinforced |
| episodic | short term: retrievable, not reinforced |
| semantic | long term: ≥3 accesses, importance ≥0.8, or a consolidation summary |
| fading | retrievability below 0.3 — a candidate for the forget gate |
| archived | merged into another memory by consolidation (kept for audit) |

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

Recall generates candidates from the indexes and scores only those:

1. **Structural** — when the extractor finds W5H in the question ("O que Ana
   pediu?"), the participant's memories are scored first. Only when they don't
   fill `max_results` above what a non-participant could score are memories
   matched by `what` alone considered. For a common verb, that skips thousands of
   candidates.
2. **Token match** — postings are accumulated per memory. A memory qualifies by
   covering ≥30% of the query's tokens, or ≥50% of the IDF mass of the query
   terms the graph knows through at least one informative term. The second rule
   is what lets a 20-word agent prompt find a 5-word memory. A query term that
   names a participant ranks above a mere mention, and results under half the best
   score are dropped.
3. **Embeddings** — only when 1–2 found nothing and `sentence-transformers` is
   installed. Vectors are cached per memory.

Memories merged away by consolidation are excluded *before* ranking.

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

`CortexV5(path="memory.db")` attaches a **`SQLiteStore`**. The graph records
which memories, entities and relations changed (`drain_all_changes`), and each
flush upserts or deletes exactly those rows in one transaction. WAL journaling
with `synchronous=NORMAL` makes a commit a log append with no fsync, and readers
in other processes are never blocked. One file holds every namespace. Rows store
the object's JSON, so adding a field never needs a migration.

New memories are flushed before `remember()` returns. Access counts from
`recall()` are written behind: with the next write, `flush()`, `close()`, or
every 2 s in the daemon. A read never waits on the disk.

`MemoryGraph.save(path)` / `load(path)` (and `CortexV5(path="x.json")`) keep
the original whole-graph JSON snapshot.

## Background abstraction: turns → durable facts

Raw agent turns are noisy. A background queue turns them into durable facts with
the **user's own small model**, so there's no API key and no per-call cost to the project:

```
turn ──▶ stored raw at once (recallable immediately) ──▶ session buffer
4 turns / session end / 5 min idle ──▶ job "extract"  (window → durable facts, user's language + English)
gate (default): no fact in the window      ──▶ its turns archived as noise
                                               (unless a turn shares a rare term with a kept memory:
                                                a lone "actually make it 10%" is a correction)
                facts found                ──▶ raw turns stay active; facts indexed on them (alt)
facts (opt-in): facts ──▶ job "consolidate" ──▶ raw turns replaced by consolidated facts
```

- **Queue:** `cortext/server/queue.py`, a state machine in the same SQLite file
  (`pending → leased → done`, retries up to 3, expired leases return to pending).
- **Workers:** the Claude Code mod leases jobs every 20 s and runs them with
  `$.model.complete({ model: "haiku" })`. With `CORTEXT_LLM=claude-cli` or `http`
  the daemon runs them itself. `cortext-memory queue drain` processes the queue
  once. A worker only turns a prompt into text: the daemon builds every prompt
  and applies every answer (`cortext/server/abstraction.py`).
- **Why gate is the default:** measured end-to-end in `docs/EVIDENCE.md`.
  Agents answered 29/30 with gate vs 25/30 when turns were rewritten into
  facts. Summaries lose detail and the order of corrections, while raw turns
  read in order let the agent see "X, then actually Y". The model's extraction
  is reliable as a noise classifier (24/24 durable, 24/24 noise), so gate uses
  it for that and archives 87% of turns. Windows of 4 turns
  (`docs/experiments/2026-10-jev-judge.md`) keep it at a quarter of per-turn calls.
- **Recall and corrections:** context is packed oldest → newest, and a memory
  newer than the best match that shares one of its rare terms survives the
  relative cutoff, so a correction reaches the agent after the value it corrects.
- **Languages:** each fact is kept in the user's language with an English
  rendering in `Memory.alt` (indexed), so a query in either language finds it.
- **Without a worker** nothing degrades: raw turns stay recallable exactly as in 0.4.

### Content addressing

`Memory.fingerprint` hashes the normalized who + what + where (case, accents,
punctuation and spacing ignored; `cortext/core/text.py:fingerprint`). Writing a
fact that is already stored reinforces it: `occurrence_count` grows, importance
keeps the maximum, a missing why/how is filled in, and the source is recorded in
`metadata.seen_by`. The lookup is an O(1) index. For a team, this gives the
count of independent people who asserted a fact.

## Service layer

```
cortext/server/daemon.py   ThreadingHTTPServer on 127.0.0.1:7077 — JSON API + dashboard + SSE
cortext/server/engine.py   MemoryEngine: one CortexV5 per namespace over one SQLiteStore,
                           turn capture, session digest, activity feed, background
                           flusher (2 s) and DreamAgent loop (30 min)
cortext/server/client.py   stdlib http.client; starts the daemon on demand
cortext/server/queue.py    JobQueue state machine (SQLite)
cortext/server/abstraction.py  window → extract → consolidate prompts and their application
cortext/llm.py             LLM backends for the daemon worker: claude-cli (user login), OpenAI-compatible http
cortext/agents/hooks.py    universal hook adapter (Claude Code, Cursor, Copilot, generic)
cortext/agents/mcp.py      MCP server on stdio
cortext/agents/claude_mod  Claude Code function-hook mod
```

`import cortext` is lazy (PEP 562), so a hook process imports the client in a
few milliseconds without loading the engine. See [AGENTS.md](AGENTS.md).
