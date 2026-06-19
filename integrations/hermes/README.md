# Cortext memory provider for Hermes

A **standalone, plug-and-play** [Hermes](https://github.com/NousResearch/hermes-agent)
memory provider backed by Cortext. Per Hermes policy it is *not* bundled into the
Hermes tree — it installs as a standalone plugin under `~/.hermes/plugins/`. The
plugin ships **inside the `cortext-memory` package**, so there is nothing to
clone.

> **Don't use Hermes?** You don't need it. Cortext is a framework-agnostic
> library — use `cortext.CortextV5` or `cortext.integration.AgentMemoryBridge`
> directly (LangChain, LangGraph, CrewAI, your own loop). See
> [../../docs/INTEGRATION.md](../../docs/INTEGRATION.md). The rest of this page is
> Hermes-specific.

## Install (one command)

```bash
pip install cortext-memory
cortext-memory setup
```

`cortext-memory setup` is a small wizard that:
- detects Hermes (`$HERMES_HOME`, default `~/.hermes`),
- installs the bundled plugin into `~/.hermes/plugins/cortext`,
- writes `$HERMES_HOME/cortext.json` and sets `memory.provider: cortext`.

Non-interactive: `cortext-memory setup --yes`. Files-only (no config):
`cortext-memory hermes-install`. Status: `cortext-memory info`.

## Activate manually (optional)

`setup` does this for you. To do it by hand, set in `$HERMES_HOME/config.yaml`:

```yaml
memory:
  provider: cortext            # select Cortext as the memory backend
  cortext:
    # --- core ---
    namespace: hermes          # memory isolation namespace (per user/agent)
    max_context_tokens: 300    # cap on context injected before each turn
    validation_policy: warn    # warn | block — contradiction handling at write time

    # --- W5H extraction ---
    use_llm_extractor: false   # true = LLM-assisted extraction (slower, better)
    llm_extractor_model: ''    # e.g. gemma3:4b (Ollama); only if use_llm_extractor: true
    llm_extractor_base_url: http://localhost:11434

    # --- inspection ---
    expose_inspect_tool: false # true = expose the cortext_inspect tool (on-demand audit)

    # --- background consolidation (DreamAgent) ---
    dream_agent: true                 # consolidate/prune in the background while idle
    dream_interval_seconds: 1800      # seconds between cycles (30 min)
    dream_use_llm: false              # true = LLM writes info-preserving merges
    dream_llm_model: ''               # e.g. llama3.1:8b (Ollama) or an OpenRouter model
    dream_llm_base_url: http://localhost:11434/v1
    dream_llm_api_key_env: ''         # env var holding the API key (blank for Ollama)
    dream_max_llm_merges: 3           # max LLM merge calls per cycle (cost budget)
```

Config precedence: `$HERMES_HOME/cortext.json` (written by `hermes memory setup`)
wins; the `memory.cortext` block above is read as a fallback.

## How it behaves

Transparent, context-only memory — no tool is forced on the model:

| Hook | What happens |
|------|--------------|
| `prefetch` | Recalls relevant W5H memories, injects a compact `Cortext Memory (recalled)` block before the turn. |
| `sync_turn` | Stores the completed exchange (contradiction-validated at write time). |
| persistence | Graph saved to `$HERMES_HOME/cortext_<namespace>.json`. |
| DreamAgent | Optional background thread: replays, consolidates duplicates, prunes forgotten. |
| `cortext_inspect` | Opt-in tool (off by default) to audit W5H, match scores, and stats. |

## Uninstall

```bash
rm ~/.hermes/plugins/cortext        # remove the plugin
# set memory.provider back to your previous backend in config.yaml
```

## Where the code lives

The provider ships inside the package at `cortext/hermes_plugin/`
(`__init__.py` = `CortextMemoryProvider`; `plugin.yaml` = manifest with
`version` + `pip_dependencies`). The `cortext-memory` CLI
([`cortext/cli.py`](../../cortext/cli.py)) installs it. Unit tests that run
without Hermes (the base class is stubbed) live in
[`tests/`](tests/).
