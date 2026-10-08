"""
Installers: wire Cortext into each agent, extending (never replacing) configs.

    cortext-memory install claude   [--classic] [--dry-run]
    cortext-memory install cursor   [--project DIR] [--dry-run]
    cortext-memory install copilot  [--project DIR] [--dry-run]
    cortext-memory install vscode   --project DIR   [--dry-run]
    cortext-memory install mcp      (print a config snippet for any MCP client)

Every command written into a config uses absolute paths (this interpreter),
so hooks work whatever PATH the agent runs with. A JSON config is read,
extended and written back; the first time a file is changed a copy is kept
as ``<file>.cortext-backup``. Running an installer twice changes nothing.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from cortext.agents.mcp import INSTRUCTIONS

PY = sys.executable
MOD_SRC = Path(__file__).resolve().parent / "claude_mod"
MARK_BEGIN = "<!-- cortext-memory:begin -->"
MARK_END = "<!-- cortext-memory:end -->"


def _q(s: str) -> str:
    return s if os.name == "nt" else shlex.quote(s)


def hook_cmd(agent: str, event: str) -> str:
    return f"{_q(PY)} -m cortext.agents.hooks {agent} {event}"


def cli_path() -> str:
    """The cortext-memory script beside this interpreter, else the module form."""
    script = Path(PY).with_name("cortext-memory.exe" if os.name == "nt" else "cortext-memory")
    return str(script) if script.exists() else PY


def mcp_server_spec() -> dict[str, Any]:
    return {"command": PY, "args": ["-m", "cortext.agents.mcp"]}


@dataclass
class Plan:
    """What an installer will do; applied all at once (or only printed)."""

    dry_run: bool = False
    changes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def _backup(self, path: Path) -> None:
        bak = path.with_name(path.name + ".cortext-backup")
        if path.exists() and not bak.exists():
            shutil.copy2(path, bak)

    def edit_json(self, path: Path, mutate: Callable[[dict], bool]) -> None:
        """Load JSON (or {}), let ``mutate`` extend it; write only if it changed."""
        path = path.expanduser()
        data: dict = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8") or "{}")
            except ValueError:
                self.notes.append(f"skipped {path}: not valid JSON (fix it, then re-run)")
                return
            if not isinstance(data, dict):
                self.notes.append(f"skipped {path}: top level is not an object")
                return
        if not mutate(data):
            self.notes.append(f"unchanged {path} (already configured)")
            return
        self.changes.append(f"updated {path}")
        if self.dry_run:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        self._backup(path)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, path)

    def upsert_block(self, path: Path, body: str, header: str = "") -> None:
        """Add (or refresh) a marked block in a text file, leaving the rest as is."""
        path = path.expanduser()
        text = path.read_text(encoding="utf-8") if path.exists() else header
        block = f"{MARK_BEGIN}\n{body.rstrip()}\n{MARK_END}\n"
        if MARK_BEGIN in text and MARK_END in text:
            start = text.index(MARK_BEGIN)
            end = text.index(MARK_END) + len(MARK_END)
            new = text[:start] + block.rstrip("\n") + text[end:]
        else:
            new = (text.rstrip("\n") + "\n\n" if text.strip() else text) + block
        if new == text:
            self.notes.append(f"unchanged {path} (already configured)")
            return
        self.changes.append(f"updated {path}")
        if not self.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._backup(path)
            path.write_text(new, encoding="utf-8")

    def write_file(self, path: Path, content: str) -> None:
        path = path.expanduser()
        if path.exists() and path.read_text(encoding="utf-8") == content:
            self.notes.append(f"unchanged {path}")
            return
        self.changes.append(f"wrote {path}")
        if not self.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


def _add_hook_entry(hooks: dict, event: str, entry: dict, same: Callable[[dict], bool]) -> bool:
    arr = hooks.setdefault(event, [])
    if any(isinstance(e, dict) and same(e) for e in arr):
        return False
    arr.append(entry)
    return True


# --- Claude Code ------------------------------------------------------------------

def install_claude(plan: Plan, classic: bool = False) -> None:
    settings = Path("~/.claude/settings.json")
    if classic:
        def mutate(d: dict) -> bool:
            hooks = d.setdefault("hooks", {})
            changed = False
            for event in ("SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"):
                cmd = hook_cmd("claude", event)
                entry = {"hooks": [{"type": "command", "command": cmd, "timeout": 15}]}
                changed |= _add_hook_entry(
                    hooks, event, entry,
                    lambda e: any("cortext.agents.hooks" in h.get("command", "") for h in e.get("hooks", [])),
                )
            return changed

        plan.edit_json(settings, mutate)
        plan.notes.append("classic hooks: SessionStart (digest), UserPromptSubmit (recall), Stop (store turn)")
        return

    # The mod: copy it to a folder we own, point its `command` option at this
    # install, and load it in every session through CLAUDE_CODE_PLUGIN_DIRS.
    dest = Path("~/.cortext/claude-mod").expanduser()
    plan.changes.append(f"copied mod -> {dest}")
    if not plan.dry_run:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(MOD_SRC, dest, ignore=shutil.ignore_patterns("tests", "node_modules", "types-cache"))
        manifest = dest / ".claude-plugin" / "plugin.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["userConfig"]["command"]["default"] = cli_path()
        port = os.environ.get("CORTEXT_PORT")
        if port and port.isdigit():
            data["userConfig"]["port"]["default"] = int(port)
        manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def mutate_env(d: dict) -> bool:
        env = d.setdefault("env", {})
        current = [p for p in str(env.get("CLAUDE_CODE_PLUGIN_DIRS", "")).split(os.pathsep) if p]
        if str(dest) in current:
            return False
        env["CLAUDE_CODE_PLUGIN_DIRS"] = os.pathsep.join(current + [str(dest)])
        return True

    plan.edit_json(settings, mutate_env)
    plan.notes.append("the mod loads in new Claude Code sessions; run /memory to open its pane")
    plan.notes.append("don't also install --classic: both would inject the same memory")


# --- Cursor -----------------------------------------------------------------------

def install_cursor(plan: Plan, project: Path | None = None) -> None:
    def mutate_hooks(d: dict) -> bool:
        d.setdefault("version", 1)
        hooks = d.setdefault("hooks", {})
        changed = False
        for event in ("sessionStart", "beforeSubmitPrompt", "afterAgentResponse", "sessionEnd"):
            changed |= _add_hook_entry(
                hooks, event, {"command": hook_cmd("cursor", event)},
                lambda e: "cortext.agents.hooks" in e.get("command", ""),
            )
        return changed

    def mutate_mcp(d: dict) -> bool:
        servers = d.setdefault("mcpServers", {})
        spec = mcp_server_spec()
        if project is not None:
            from cortext.server.config import namespace_for

            spec = {**spec, "env": {"CORTEXT_NAMESPACE": namespace_for(str(project))}}
        if servers.get("cortext") == spec:
            return False
        servers["cortext"] = spec
        return True

    base = project / ".cursor" if project else Path("~/.cursor")
    plan.edit_json(base / "hooks.json", mutate_hooks)
    plan.edit_json(base / "mcp.json", mutate_mcp)
    rule = (
        "---\ndescription: Cortext long-term memory\nalwaysApply: true\n---\n\n" + INSTRUCTIONS + "\n"
    )
    if project:
        plan.write_file(project / ".cursor" / "rules" / "cortext-memory.mdc", rule)
    else:
        plan.notes.append("for every project, also add the text of `cortext-memory install mcp` as a Cursor User Rule")
    plan.notes.append("Cursor injects memory at sessionStart; per-prompt recall comes from the MCP tools + rule")


# --- GitHub Copilot ---------------------------------------------------------------

def install_copilot(plan: Plan, project: Path | None = None) -> None:
    def mutate_hooks(d: dict) -> bool:
        d.setdefault("version", 1)
        hooks = d.setdefault("hooks", {})
        changed = False
        for event in ("sessionStart", "userPromptSubmitted", "agentStop", "sessionEnd"):
            cmd = hook_cmd("copilot", event)
            changed |= _add_hook_entry(
                hooks, event, {"type": "command", "bash": cmd, "powershell": cmd, "timeoutSec": 15},
                lambda e: "cortext.agents.hooks" in (e.get("bash", "") + e.get("command", "")),
            )
        return changed

    hooks_file = (project / ".github" / "hooks" / "cortext.json") if project else Path("~/.copilot/hooks/cortext.json")
    plan.edit_json(hooks_file, mutate_hooks)

    def mutate_cli_mcp(d: dict) -> bool:
        servers = d.setdefault("mcpServers", {})
        spec = {"type": "local", **mcp_server_spec(), "tools": ["*"]}
        if servers.get("cortext") == spec:
            return False
        servers["cortext"] = spec
        return True

    plan.edit_json(Path("~/.copilot/mcp-config.json"), mutate_cli_mcp)
    if project:
        install_vscode(plan, project)
    else:
        plan.notes.append("for VS Code Copilot Chat, run: cortext-memory install vscode --project <repo>")


def install_vscode(plan: Plan, project: Path) -> None:
    from cortext.server.config import namespace_for

    def mutate(d: dict) -> bool:
        servers = d.setdefault("servers", {})
        spec = {"type": "stdio", **mcp_server_spec(), "env": {"CORTEXT_NAMESPACE": namespace_for(str(project))}}
        if servers.get("cortext") == spec:
            return False
        servers["cortext"] = spec
        return True

    plan.edit_json(project / ".vscode" / "mcp.json", mutate)
    plan.upsert_block(project / ".github" / "copilot-instructions.md", "## Long-term memory (Cortext)\n\n" + INSTRUCTIONS)


# --- generic MCP ------------------------------------------------------------------

def mcp_snippet() -> str:
    spec = {"mcpServers": {"cortext": mcp_server_spec()}}
    return (
        "Add this server to your MCP client (Windsurf, Claude Desktop, Codex, Gemini CLI, Zed, Cline, ...):\n\n"
        + json.dumps(spec, indent=2)
        + "\n\nAnd this to the agent's rules / system instructions (hook emulation):\n\n"
        + INSTRUCTIONS
        + "\n"
    )


TARGETS = ("claude", "cursor", "copilot", "vscode", "mcp")


def run(target: str, project: str | None = None, dry_run: bool = False, classic: bool = False) -> Plan:
    plan = Plan(dry_run=dry_run)
    proj = Path(project).expanduser().resolve() if project else None
    if target == "claude":
        install_claude(plan, classic=classic)
    elif target == "cursor":
        install_cursor(plan, proj)
    elif target == "copilot":
        install_copilot(plan, proj)
    elif target == "vscode":
        if proj is None:
            raise SystemExit("install vscode needs --project <repo folder>")
        install_vscode(plan, proj)
    elif target == "mcp":
        plan.notes.append(mcp_snippet())
    else:
        raise SystemExit(f"unknown target {target!r}; choose one of: {', '.join(TARGETS)}")
    return plan
