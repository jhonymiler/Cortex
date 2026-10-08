---
paths:
  - "cortext/agents/claude_mod/**"
---

# Claude Code mod (function hooks)

- The API reference is the engine-written `claude-code.d.ts` (the `plugin-authoring`
  skill names its path); load that skill before editing the mod.
- A helper that receives `$` must be a top-level `function` declaration in the
  module (not a closure inside `register`), or `claude plugin validate` refuses it.
- Module-level variables reset on every reload; values a drawing reads live in
  `$.state` atoms declared in `types/index.d.ts`.
- Tests (`tests/*.test.ts`) must answer everything beneath the plugin themselves:
  `session.start`, `prompt.submit`, `turn.complete`, `command.register`,
  `tool.register`, `ui.status`; `$`-call hooks (`http.fetch`, `process.run`) return
  `{ value }` or `{ deny }`. See `engineBeneath()` in the existing test.
- Before finishing: `claude plugin validate cortext/agents/claude_mod` and
  `claude plugin test cortext/agents/claude_mod` must both pass.
- `install claude` copies this folder to `~/.cortext/claude-mod` (without `tests/`)
  and rewrites the `command` option default to the local `cortext-memory` path.
