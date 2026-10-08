# Cortext for coding agents

Cortext gives Claude Code, Cursor, GitHub Copilot and any MCP client one shared,
per-project long-term memory. Everything runs locally.

```bash
pip install cortext-memory
cortext-memory install claude      # Claude Code (function-hook mod)
cortext-memory install cursor      # Cursor (hooks + MCP)
cortext-memory install copilot     # Copilot CLI (hooks + MCP); add --project <repo> for VS Code
cortext-memory dashboard           # open the control panel
```

## How it fits together

```
 Claude Code mod ─┐                         ┌─ /api/recall   (~0.2–1 ms)
 hook commands ───┼──► cortext daemon ──────┼─ /api/turn
 MCP server ──────┘    127.0.0.1:7077       ├─ /api/remember
                       (graphs kept warm)   └─ dashboard at /
                              │
                     ~/.cortext/memory.db   (SQLite WAL, one file, a namespace per project)
```

Agent hooks start a new process for every event. Loading and indexing a graph in
each would cost up to a second, so they call the **daemon** instead, which keeps
every namespace loaded. The first hook of the day starts it if needed
(`cortext-memory daemon start` does the same by hand).

**Namespaces.** Each project gets its own: `project:<git-root folder name>`.
Memories of one codebase never leak into another. Set `CORTEXT_NAMESPACE` to use
one namespace everywhere. `cortext-memory ns` prints the one for the current folder.

## What each agent gets

| | Recall injected per prompt | Digest at session start | Turn captured | Memory tools |
|---|---|---|---|---|
| **Claude Code** (mod) | yes (`prompt.submit` context) | — | yes (`turn.complete`) | `memory_recall`, `memory_remember`, `memory_forget` + `/memory` pane |
| **Claude Code** (`--classic` hooks) | yes (`UserPromptSubmit`) | yes (`SessionStart`) | yes (`Stop`, from the transcript) | via MCP if added |
| **Cursor** | via MCP + rule (hook emulation) | yes (`sessionStart`) | yes (`beforeSubmitPrompt` + `afterAgentResponse`) | MCP |
| **Copilot CLI** | via MCP + instructions | yes (`sessionStart`) | yes (`userPromptSubmitted` + `agentStop`) | MCP |
| **VS Code Copilot Chat** | via MCP + `copilot-instructions.md` | — | via `memory_capture_turn` | MCP |
| **Any MCP client** (Windsurf, Claude Desktop, Codex, Gemini CLI, Zed, Cline) | via MCP + instructions | — | via `memory_capture_turn` | MCP |

### Hook emulation for agents without per-prompt hooks

Cursor's and Copilot's hooks can add context only at session start. For those
agents, and for any agent with no hooks at all, the MCP server's `instructions`
(and the rule/instructions file the installer writes) tell the model to:

1. call `memory_recall` with the request at the start of every task;
2. call `memory_remember` when it learns something durable;
3. call `memory_capture_turn` with a short summary at the end.

These are the same three moments a hook system covers, carried out by the model
through tools.

## Claude Code: the mod

`install claude` copies the mod to `~/.cortext/claude-mod`, points its
`command` option at this install, and adds that folder to
`CLAUDE_CODE_PLUGIN_DIRS` in `~/.claude/settings.json`. New sessions load it.
Alternatively, install it from this repository's marketplace:

```
/plugin install cortext --marketplace jhonymiler/Cortex
```

What it does:

- **Every prompt:** recalls from the daemon and attaches the result as context the
  model reads but the user doesn't see (`<cortext-memory>` block). Slash commands
  are skipped.
- **Every finished turn:** stores the prompt (`what`) and the start of the answer
  (`how`). One-word acknowledgements are skipped. A previously injected block is
  stripped first, so memory never feeds on itself.
- **Tools:** `mcp__cortext__memory_recall`, `memory_remember`, `memory_forget`.
- **`/memory`:** a pane with the memory levels, the last recall and latency, plus
  buttons to refresh, consolidate and open the dashboard. The status line shows
  `◆ cortext N mem`.

Options (plugin config): `port` (7077), `command` (`cortext-memory`), `inject` (true).

If you prefer settings.json command hooks (older builds, or VS Code agent hooks
reading the same file): `cortext-memory install claude --classic`. Don't install
both, or memory gets injected twice.

## Cursor

`install cursor` extends `~/.cursor/hooks.json` (`sessionStart`,
`beforeSubmitPrompt`, `afterAgentResponse`) and `~/.cursor/mcp.json`. With
`--project <repo>` it writes those files under `<repo>/.cursor/` instead, pins
the namespace in the MCP server's env, and adds
`.cursor/rules/cortext-memory.mdc` (`alwaysApply: true`) with the hook-emulation
instructions. Without `--project`, paste the text from `cortext-memory install mcp`
into Cursor's User Rules once.

## GitHub Copilot

`install copilot` writes `~/.copilot/hooks/cortext.json` (`sessionStart`,
`userPromptSubmitted`, `agentStop`) and adds the server to
`~/.copilot/mcp-config.json`. With `--project <repo>` the hooks go to
`<repo>/.github/hooks/cortext.json`, and VS Code gets `<repo>/.vscode/mcp.json`
plus a marked block in `.github/copilot-instructions.md` (the rest of that file is
left as it was). The cloud agent runs remotely, has no local daemon, and isn't
covered.

## Any other MCP client

```bash
cortext-memory install mcp     # prints the server JSON and the instructions text
```

The server is `python -m cortext.agents.mcp`, speaking MCP over stdio with
protocol versions 2025-06-18, 2025-03-26 and 2024-11-05.

## Safety

- The installers **extend** configuration files: existing keys and hooks stay;
  the first change to a file keeps `<file>.cortext-backup`; re-running changes
  nothing. `--dry-run` shows what would change.
- The daemon listens on 127.0.0.1 only. It refuses a non-local `Host` or `Origin`
  (DNS rebinding) and any write that isn't JSON (cross-site forms). Set
  `CORTEXT_TOKEN` to require an `X-Cortext-Token` header on every API call.
- Hooks never break an agent: any failure (no daemon, timeout) exits 0 with no output.
- Recalled memory is framed as possibly stale, and the MCP instructions tell the
  model to verify it against the code.

## Environment

| Variable | Default | |
|---|---|---|
| `CORTEXT_HOME` | `~/.cortext` | state directory (db, pid, log, pending prompts) |
| `CORTEXT_DB` | `$CORTEXT_HOME/memory.db` | SQLite file |
| `CORTEXT_PORT` / `CORTEXT_HOST` | `7077` / `127.0.0.1` | daemon address |
| `CORTEXT_NAMESPACE` | per project | one namespace for everything |
| `CORTEXT_TOKEN` | — | shared secret for the API |
| `CORTEXT_NO_AUTOSTART` | — | hooks don't start the daemon |
| `CORTEXT_DEBUG` | — | hooks print errors to stderr |

## HTTP API

| Method | Path | |
|---|---|---|
| GET | `/api/health`, `/api/overview`, `/api/namespaces` | status |
| GET | `/api/stats?ns=`, `/api/levels?ns=` | per namespace |
| GET | `/api/memories?ns=&tier=&q=&who=&sort=&limit=&offset=` | browse |
| GET / DELETE | `/api/memory/<id>?ns=` | detail (with graph neighbours) / forget |
| GET | `/api/graph?ns=&limit=`, `/api/digest?ns=` | visualization / session digest |
| GET | `/api/activity?since=`, `/api/events` (SSE) | activity feed |
| GET | `/api/ns?cwd=` | namespace for a folder |
| POST | `/api/remember` `{ns, what \| text, who, why, how, where, importance}` | store |
| POST | `/api/recall` `{ns, query, max_results, max_tokens, touch}` | recall (returns `context`) |
| POST | `/api/turn` `{ns, user, assistant, agent, session}` | capture an exchange |
| POST | `/api/dream` `{ns}` | run a consolidation cycle |
