# Cortext memory provider for Hermes

A **standalone** [Hermes](https://github.com/NousResearch/hermes-agent) memory
provider backed by Cortext. It is not bundled into the Hermes tree — per Hermes
policy, new memory backends ship as standalone plugins installed under
`~/.hermes/plugins/`.

## Install

```bash
pip install cortext-memory
```

Then drop this plugin where Hermes discovers user plugins:

```bash
# symlink (recommended — tracks updates)
ln -s "$(pwd)/cortext" ~/.hermes/plugins/cortext
# or copy
cp -r cortext ~/.hermes/plugins/cortext
```

Select it and run setup:

```bash
hermes memory setup        # writes $HERMES_HOME/cortext.json
# or set in config.yaml:  memory.provider: cortext
```

## What it does

Context-only, transparent memory:

- **`prefetch`** — recalls relevant W5H memories and injects a compact
  `Cortext Memory (recalled)` block before each turn.
- **`sync_turn`** — stores each completed exchange (contradiction-validated).
- **persistence** — graph saved to `$HERMES_HOME/cortext_<namespace>.json`.
- **DreamAgent** — optional background consolidation while idle.
- **`cortext_inspect`** — opt-in tool (off by default) to audit W5H, scores, stats.

## Config

Written by `hermes memory setup` to `$HERMES_HOME/cortext.json`; the
`memory.cortext` block of `config.yaml` is read as a fallback. Keys: `namespace`,
`max_context_tokens`, `validation_policy`, `use_llm_extractor`, `dream_agent`,
`dream_interval_seconds`, and the LLM-extractor / dream-LLM options (see
`get_config_schema`).

## Note on independence

The Cortext library itself is framework-agnostic — this plugin only *consumes*
it via `cortext.CortextV5` / `cortext.integration.AgentMemoryBridge`. The same
library powers LangChain/LangGraph/CrewAI integrations with no Hermes coupling.
