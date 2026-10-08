# Cortext (cortext-memory)

## What this is

Long-term memory for AI agents. A W5H `Memory` graph with inverted indexes
(token / who / where) answers recall and validated writes in under a millisecond
at 20k memories, persisted incrementally in SQLite. A local daemon keeps graphs
warm for agents that spawn a process per hook (Claude Code, Cursor, Copilot),
an MCP server covers any MCP client, and the daemon serves a live dashboard.
Pure Python ≥ 3.10, zero required dependencies.

## Commands

- Install (dev): `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"`
- Test (all): `.venv/bin/python -m pytest -q` — includes `integrations/hermes/tests`
- Test (single): `.venv/bin/python -m pytest -q tests/test_service.py::test_mcp_protocol`
- Lint: `.venv/bin/ruff check .` (rule set pinned in `pyproject.toml`)
- Benchmark: `.venv/bin/python bench/run_benchmark.py` (writes `bench/results/*.json`)
- Latency at scale: `.venv/bin/python bench/latency_benchmark.py`
- Value end-to-end (needs `claude` login): `.venv/bin/python bench/value/memory_value.py 60`
- Model experiments (need `claude`, `JEV_API_KEY` in `.env`): `bench/jev/*.py`; LLM answers
  are cached in `bench/jev/results/llm_cache.jsonl`, so re-runs resume
- Daemon: `.venv/bin/cortext-memory serve` (foreground) / `daemon start|stop|status`
- Dashboard: `.venv/bin/cortext-memory dashboard` → http://127.0.0.1:7077
- Claude Code mod: `claude plugin validate cortext/agents/claude_mod` and
  `claude plugin test cortext/agents/claude_mod`

## Layout

- `cortext/core/` — engine: `graph.py` (indexed tables), `memory.py`, `text.py`
  (the one tokenizer: fold accents, plural stem, stopwords), `recall/`,
  `validation/`, `decay/` (Ebbinghaus + `memory_tier`)
- `cortext/store/` — `SQLiteStore` (incremental, WAL, all namespaces in one file),
  `JsonStore` (legacy snapshot)
- `cortext/cortex.py` — `CortexV5` facade (aliases `CortextV5`, `Cortex`), thread-safe
- `cortext/server/` — `daemon.py` (HTTP API + `static/dashboard.html`),
  `engine.py` (multi-namespace service), `queue.py` (job state machine),
  `abstraction.py` (turns → facts: window → extract → consolidate),
  `client.py` + `config.py` (stdlib only)
- `cortext/llm.py` — LLM backends for the daemon worker (`claude -p` on the user's
  login, OpenAI-compatible http)
- `cortext/agents/` — `hooks.py` (universal hook adapter), `mcp.py` (stdio MCP),
  `install.py` (per-agent installers), `claude_mod/` (Claude Code function-hook mod)
- `cortext/hermes_plugin/` — Hermes memory provider shipped in the wheel
- `.claude-plugin/marketplace.json` — makes this repo installable with
  `/plugin install cortext --marketplace jhonymiler/Cortex`

## Conventions

- Hot paths read indexes, never scan `graph.iter_memories()`. New lookups go
  into `MemoryGraph` as an index method.
- Anything a hook imports (`cortext.server.client/config`, `cortext.agents.hooks`,
  `cortext.agents.mcp`) uses the standard library only; `cortext/__init__.py`
  exports lazily. `tests/test_engine_v04.py::test_import_is_lazy` guards it.
- Hooks never break an agent: every failure exits 0 with no output.
- Installers extend configs (read → merge → write, `*.cortext-backup` once);
  they never replace a user's file.
- Decay counts from `created_at`/`last_accessed`, not `when` (the event time).
- Design changes to memory quality are decided by measurement: record the data in
  `docs/experiments/` (and `docs/EVIDENCE.md`) together with the change.
- `.env` holds local secrets and is gitignored; never print its values.
- Recall touches (access counts) are write-behind; new memories are written
  synchronously when a store is attached.

## Gotchas

- `graph._memories` / `graph._entities` are dict subclasses that maintain the
  indexes; tests write to them directly, so keep that working.
- A JSON store only writes on `flush()`/`close()`; SQLite writes on every mutation.
- The daemon rejects non-JSON writes and non-local Host/Origin headers — clients
  must send `Content-Type: application/json` even on DELETE.
- Cursor and Copilot hooks can inject context only at session start; per-prompt
  recall there comes from the MCP tools plus the instructions file.

## Harness

- Zone rules: `.claude/rules/` (the Claude Code mod has its own)
