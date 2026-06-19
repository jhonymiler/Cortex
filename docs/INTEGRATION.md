# Integration

Cortext is **framework-agnostic**: the library has no dependency on any agent
framework. There are two ways to use it.

1. **`CortextV5` directly** — the universal API (`remember` / `recall` /
   `inspect`). Works in any framework or plain code.
2. **`AgentMemoryBridge`** — optional convenience for the "recall before the
   call, store after it" chat pattern.

```bash
pip install cortext-memory     # provides the `cortext` import package
```

## The bridge pattern (any framework)

```python
from cortext.integration import AgentMemoryBridge

bridge = AgentMemoryBridge(
    namespace="session-1",        # isolate memory per session/user
    max_context_tokens=300,       # cap on injected context
)

# 1. Before the LLM call — recall and inject:
context = bridge.recall_context(user_input)
system_prompt = (context + "\n\n" + base_system_prompt) if context else base_system_prompt

# 2. Call your LLM with system_prompt ...

# 3. After the turn — persist it:
bridge.store_turn(user_message=user_input, assistant_message=reply)
```

> `HermesCortexBridge` is a deprecated alias of `AgentMemoryBridge`, kept for
> backward compatibility.

## LangChain

```python
from cortext import CortextV5

cortex = CortextV5(namespace="user-42")

def with_memory(user_input: str, base_system: str) -> str:
    context, _ = cortex.recall(user_input)
    return f"{context}\n\n{base_system}" if context else base_system

# ... after the chain produces `reply`:
cortex.remember(what=user_input, how=reply, who=["user-42"])
```

You can also wrap `cortex.recall` / `cortex.remember` as LangChain tools if you
want the model to query memory explicitly.

## LangGraph

```python
from cortext import CortextV5

cortex = CortextV5(namespace="user-42")

def recall_node(state):
    context, _ = cortex.recall(state["input"])
    if context:
        state["system"] = f"{context}\n\n{state['system']}"
    return state

def persist_node(state):
    cortex.remember(what=state["input"], how=state["reply"], who=[state["user"]])
    return state

# graph.add_node("recall", recall_node) -> model -> graph.add_node("persist", persist_node)
```

## Persistence

The bridge holds an in-memory graph. Persist it across runs:

```python
from cortext.core.graph import MemoryGraph

bridge.cortex.graph = MemoryGraph.load(store_path, namespace="session-1")  # startup
bridge.cortex.graph.save(store_path)                                       # after writes
```

## Background consolidation

Run the `DreamAgent` periodically (e.g. on a timer thread) to consolidate
duplicates and prune forgotten memories while idle:

```python
from cortext.workers.dream_agent import DreamAgent

dream = DreamAgent(llm_fn=None)          # heuristic merges; pass an llm_fn for LLM merges
result = dream.run_cycle(bridge.cortex.graph)
# result.n_replayed, result.n_consolidated, result.n_cleaned
```

## Hermes (plug-and-play plugin)

A ready-made Hermes memory provider ships **inside the package**. Per Hermes
policy it installs as a *standalone* plugin (not bundled into the Hermes tree),
in one command:

```bash
pip install cortext-memory
cortext-memory setup           # wizard: detect Hermes, install plugin, configure
```

The `cortext-memory` CLI bundles the plugin in the wheel and drops it into
`~/.hermes/plugins/cortext`, then writes `$HERMES_HOME/cortext.json`. The
provider recalls before each turn, stores after, persists to
`$HERMES_HOME/cortext_<namespace>.json`, runs the DreamAgent in the background,
and optionally exposes a `cortext_inspect` tool. See
[integrations/hermes/README.md](../integrations/hermes/README.md) for the full
manual and the annotated config.
