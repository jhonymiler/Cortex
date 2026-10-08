# Cortext

*Read this in [Português](README.pt-br.md).*

> **Long-term memory for AI agents: an indexed W5H memory graph that stores and
> recalls in under a millisecond, plugs into Claude Code, Cursor and Copilot,
> and shows its memory levels in a live dashboard.**

![Cortext dashboard: memory clouds by level, KPIs, live recall](docs/assets/dashboard.png)

Cortext gives an agent a memory that is *structured* rather than a flat vector
store. Every memory is a **W5H** record (who, what, why, when, where, how), checked
against what is already known so contradictions don't slip in, and recalled by a
deterministic, index-backed parser that returns a **compact** context block
instead of raw chunks. Pure Python, **zero required dependencies**, local-first.

```bash
pip install cortext-memory
cortext-memory install claude     # or: cursor | copilot | vscode | mcp
cortext-memory dashboard
```

## What's inside

| | |
|---|---|
| **Indexed memory graph** | Inverted indexes by token, participant and place; candidates come from the indexes, never a scan. Entities link memories into a graph. |
| **Background abstraction** | Raw turns become durable facts in the background, with **your own Haiku** (the Claude Code mod runs the queue via `$.model.complete`; other agents via `claude -p`). Superseded values are retired, duplicates merged, noise archived: no API key, no extra bill. |
| **Content-addressed facts** | The same fact written again by any agent or person reinforces the stored memory instead of duplicating it, and the sources are counted. |
| **Incremental SQLite** | WAL-mode store that writes only what changed, one file for every namespace. Access counts are written behind, so reads never wait on the disk. |
| **Memory levels** | working → episodic → semantic → fading → archived, from age, reinforcement, importance and Ebbinghaus retrievability. |
| **Contradiction-aware writes** | `CanonicalValidator` flags or blocks `X` vs `not X` at write time (heuristic → embedding → LLM levels). |
| **Self-pruning** | Ebbinghaus decay, a forget gate, and a DreamAgent that merges duplicates and prunes what's no longer used. It never prunes important memories or summaries. |
| **Agent integrations** | Claude Code **mod** (function hooks), universal **hook adapter** (Claude Code, Cursor, Copilot), **MCP server** for any client, one-command installers. |
| **Control panel** | Live dashboard served by the local daemon: memory clouds per level, latency, recall playground, memory browser, activity feed. |

## Performance

Measured with `python bench/latency_benchmark.py` (synthetic corpus: 300
participants, a verb shared by 10% of memories; Linux, CPython 3.10, NVMe). Writes
are validated **and** persisted to SQLite before returning.

| Memories | Write + validate + persist | Recall by participant | Recall by text | Cold reload |
|---|---|---|---|---|
| 1,000 | 0.37 ms | 0.38 ms | 0.06 ms | 58 ms |
| 5,000 | 0.39 ms | 0.18 ms | 0.12 ms | 0.24 s |
| 20,000 | 0.44 ms | 0.53 ms | 0.26 ms | 0.93 s |
| 50,000 | 0.53 ms | 1.13 ms | 0.55 ms | 2.3 s |

The same corpus on 0.3.1 (in-memory only, nothing persisted): at 20,000
memories, a write took **4.3 ms**, a recall **193 ms**, and saving rewrote the whole
JSON file (**0.7 s**). That is ~10× faster writes and ~360× faster recall, now with
durable storage. Through the daemon, an agent hook's recall round-trip costs
about 1 ms plus process start.

Quality, from `python bench/run_benchmark.py` against an unstructured top-k baseline:

| Scenario | Tokens (baseline → Cortext) | Savings | P@5 (baseline → Cortext) | Contradiction detection |
|---|---|---|---|---|
| customer_support | 540 → 126 | **76.7%** | 0.367 → 0.833 | 100% |
| personal_assistant | 380 → 88 | **76.8%** | 0.840 → 0.800 | 67% |
| **Average** | — | **76.8%** | **0.603 → 0.817** | 83.5% |

## Evidence

Every claim here is measured by a script in this repository; see
**[docs/EVIDENCE.md](docs/EVIDENCE.md)**. Highlights:

- Agents with Cortext answer **97%** of questions about earlier sessions vs **17%** without memory, matching the full history with **~11% of the tokens**, while archiving 87% of turns as noise ([value benchmark](docs/EVIDENCE.md#1-agents-answer-better-with-cortext--end-to-end), with a held-out set).
- Background abstraction keeps memory **correct**: 100% of planted facts
  captured and 0 of 3 superseded values kept, vs 3 of 3 kept when every turn is
  stored ([experiment](docs/experiments/2026-10-jev-judge.md)).
- Contradiction and relation judgments go from 28% (keyword rules) to 96.6%
  (calibrated judge plus your Haiku for its uncertain cases), in PT/EN/ES and
  across languages.

## Coding agents

```bash
cortext-memory install claude              # Claude Code: function-hook mod
cortext-memory install cursor              # Cursor: hooks + MCP (+ --project <repo> for a rule)
cortext-memory install copilot             # Copilot CLI: hooks + MCP
cortext-memory install vscode --project .  # VS Code Copilot Chat: MCP + instructions
cortext-memory install mcp                 # print config for any other MCP client
```

- **Claude Code**: the mod attaches recalled memory to every prompt, stores every
  finished turn, gives the model `memory_recall` / `memory_remember` /
  `memory_forget` tools, and adds a `/memory` pane with the levels. Also
  installable as `/plugin install cortext --marketplace jhonymiler/Cortex`.
- **Cursor / Copilot**: their hooks inject the project's long-term memory at session
  start and capture every turn. Per-prompt recall runs through the MCP tools, guided
  by an instructions file ("hook emulation").
- **Agents without hooks** (Windsurf, Claude Desktop, Codex, Gemini CLI, Zed, …):
  the MCP server's instructions make the model recall at the start of a task,
  remember durable facts, and log a summary at the end.

Every agent talks to one local daemon (`127.0.0.1:7077`, started on demand) that
keeps a warm graph per project. See **[docs/AGENTS.md](docs/AGENTS.md)**.

## Library

```python
from cortext import CortextV5

cortex = CortextV5(namespace="myapp", path="~/.cortext/memory.db")  # path is optional

cortex.remember(who=["Maria"], what="reportou erro de pagamento",
                why="cartão expirado", how="orientada a atualizar dados")

context, result = cortex.recall("O que Maria reportou?")
print(context)
# Maria | reportou erro de pagamento → orientada a atualizar dados

cortex.levels()        # {'working': 1, 'episodic': 0, 'semantic': 0, 'fading': 0, 'archived': 0}
cortex.stats()         # sizes, writes, levels, p50/p95 latency
```

`CortexV5` is thread-safe. For the "recall before the call, store after it"
loop there is a framework-neutral `AgentMemoryBridge`:

```python
from cortext.integration import AgentMemoryBridge

bridge = AgentMemoryBridge(namespace="session-1", path="~/.cortext/memory.db")
context = bridge.recall_context(user_input)                          # before the LLM call
bridge.store_turn(user_message=user_input, assistant_message=reply)  # after the turn
```

LangChain, LangGraph and other frameworks: [docs/INTEGRATION.md](docs/INTEGRATION.md).
Hermes: `cortext-memory setup` installs the bundled provider, see
[integrations/hermes/README.md](integrations/hermes/README.md).

## How it works

```
WRITE   W5H ─▶ CanonicalValidator (candidates from the indexes) ─▶ MemoryGraph ─▶ SQLite (changed rows only)
RECALL  query ─▶ extractor (PT/EN/ES regex, optional LLM) ─▶ indexed candidates ─▶ rank ─▶ compact block
DECAY   Ebbinghaus retrievability + forget gate; DreamAgent merges duplicates, prunes, replays
LEVELS  working → episodic → semantic → fading → archived
```

Design details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Install

```bash
pip install cortext-memory
pip install "cortext-memory[embeddings]"   # optional: sentence-transformers for embedding recall/validation
```

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q                  # 271 tests
.venv/bin/ruff check .
.venv/bin/python bench/latency_benchmark.py    # latency at scale
.venv/bin/python bench/run_benchmark.py        # token savings / precision
claude plugin test cortext/agents/claude_mod   # the Claude Code mod
```

## License

MIT — see [LICENSE](LICENSE).
