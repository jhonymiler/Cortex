# Integration

Cortex is designed to be a **transparent memory layer** around an agent loop:
recall relevant memories before the LLM call, store the turn after it. The model
never needs to manage memory explicitly.

## The bridge pattern

`HermesCortexBridge` is the reference implementation:

```python
from cortext.integration import HermesCortexBridge

bridge = HermesCortexBridge(
    namespace="session-1",        # isolate memory per session/user
    max_context_tokens=300,       # cap on injected context
)

# 1. Before the LLM call — recall and inject:
context = bridge.pre_chat(user_input)
system_prompt = (context + "\n\n" + base_system_prompt) if context else base_system_prompt

# 2. Call your LLM with system_prompt ...

# 3. After the turn — persist it:
bridge.post_chat(user_message=user_input, assistant_message=reply)
```

`pre_chat` returns a compact recalled-context string (or empty). `post_chat`
extracts W5H from the turn and stores it, running contradiction validation.

## Persistence

The bridge holds an in-memory graph. Persist it across sessions:

```python
from cortext.core.graph import MemoryGraph

# load on startup
bridge.cortex.graph = MemoryGraph.load(store_path, namespace="session-1")

# save after writes
bridge.cortex.graph.save(store_path)
```

## Background consolidation

Run the `DreamAgent` periodically (e.g. on a timer thread) to consolidate
duplicates and prune forgotten memories while the agent is idle:

```python
from cortext.workers.dream_agent import DreamAgent

dream = DreamAgent(llm_fn=None)          # heuristic merges; pass an llm_fn for LLM merges
result = dream.run_cycle(bridge.cortex.graph)
# result.n_replayed, result.n_consolidated, result.n_cleaned
```

## Reference: the Hermes memory plugin

A production integration exists as a Hermes `MemoryProvider`. It wires the bridge
into the agent's `prefetch` (recall before turn) and `sync_turn` (store after
turn) hooks, adds JSON persistence under `$HERMES_HOME`, runs the DreamAgent on a
background thread, and optionally exposes a `cortex_inspect` tool for auditing the
W5H structure, match scores, and graph stats on demand.

The key property: it is a **plugin**. Memory is recalled and stored transparently;
no memory tool is forced on the model. This is the recommended shape for adding
Cortex to any agent framework that has pre/post-turn hooks.
