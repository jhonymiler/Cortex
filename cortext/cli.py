"""Cortext command-line interface.

Entry point: ``cortext-memory``. The star command is ``setup`` — a small,
dependency-free wizard that installs and configures the Cortext memory plugin
for Hermes (or explains library usage if Hermes is not present).

Usage:
    cortext-memory serve                    # run the daemon in the foreground
    cortext-memory daemon start|stop|status # run it in the background
    cortext-memory dashboard                # open the control panel
    cortext-memory install <agent>          # claude | cursor | copilot | vscode | mcp
    cortext-memory hook <agent> <event>     # (called by agent hooks)
    cortext-memory mcp                      # MCP server on stdio
    cortext-memory recall "query" | remember "fact" | stats | ns
    cortext-memory setup                    # Hermes wizard
    cortext-memory info
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

# ---- tiny ANSI toolkit (no dependencies) ------------------------------------

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str) -> str:
    return code if _USE_COLOR else ""


RESET = _c("\033[0m")
BOLD = _c("\033[1m")
DIM = _c("\033[2m")
CYAN = _c("\033[36m")
GREEN = _c("\033[32m")
YELLOW = _c("\033[33m")
RED = _c("\033[31m")
MAGENTA = _c("\033[35m")


def _box(title: str, lines: list[str]) -> None:
    width = max([len(title)] + [len(_strip(line)) for line in lines]) + 2
    top = f"{CYAN}╭{'─' * width}╮{RESET}"
    print(top)
    print(f"{CYAN}│{RESET} {BOLD}{title}{RESET}{' ' * (width - len(title) - 1)}{CYAN}│{RESET}")
    print(f"{CYAN}├{'─' * width}┤{RESET}")
    for line in lines:
        pad = width - len(_strip(line)) - 1
        print(f"{CYAN}│{RESET} {line}{' ' * pad}{CYAN}│{RESET}")
    print(f"{CYAN}╰{'─' * width}╯{RESET}")


def _strip(s: str) -> str:
    import re

    return re.sub(r"\033\[[0-9;]*m", "", s)


def _ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def _warn(msg: str) -> None:
    print(f"  {YELLOW}!{RESET} {msg}")


def _step(msg: str) -> None:
    print(f"  {CYAN}•{RESET} {msg}")


def _ask(prompt: str, default: str, interactive: bool) -> str:
    if not interactive:
        return default
    try:
        ans = input(f"  {MAGENTA}?{RESET} {prompt} {DIM}[{default}]{RESET} ").strip()
    except EOFError:
        return default
    return ans or default


def _ask_bool(prompt: str, default: bool, interactive: bool) -> bool:
    d = "Y/n" if default else "y/N"
    ans = _ask(f"{prompt} ({d})", "", interactive).lower()
    if not ans:
        return default
    return ans in ("y", "yes", "s", "sim")


# ---- helpers ----------------------------------------------------------------

def _version() -> str:
    try:
        from cortext import __version__

        return __version__
    except Exception:
        return "?"


def _hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME")
    return Path(env) if env else Path.home() / ".hermes"


def _plugin_src() -> Path:
    """Locate the bundled Hermes plugin directory inside the installed package."""
    return Path(__file__).resolve().parent / "hermes_plugin"


def _banner() -> None:
    print()
    print(f"{BOLD}{CYAN}  Cortext{RESET} {DIM}v{_version()}{RESET} — cognitive memory for AI agents")
    print(f"{DIM}  W5H-structured · contradiction-aware · internationalized{RESET}")
    print()


# ---- commands ---------------------------------------------------------------

def cmd_info(_args) -> int:
    _banner()
    src = _plugin_src()
    _box(
        "Status",
        [
            f"library      {GREEN}installed{RESET}  (cortext v{_version()})",
            f"hermes home  {_hermes_home()}",
            f"plugin files {'found' if src.exists() else RED + 'missing' + RESET}",
        ],
    )
    print()
    from cortext.server import client, config

    running = client.is_running()
    _box(
        "Daemon",
        [
            f"status       {GREEN + 'running' + RESET if running else YELLOW + 'stopped' + RESET}",
            f"url          {config.base_url()}",
            f"database     {config.db_path()}",
        ],
    )
    print()
    print(f"  {DIM}Library use (any framework):{RESET}")
    print("      from cortext import CortextV5")
    print("      cortex = CortextV5(namespace='myapp', path='~/.cortext/memory.db')")
    print()
    print(f"  Agents: {BOLD}cortext-memory install claude|cursor|copilot|vscode|mcp{RESET}")
    print(f"  Hermes: {BOLD}cortext-memory setup{RESET}")
    print()
    return 0


def _install_plugin(home: Path, copy: bool) -> Path:
    dest = home / "plugins" / "cortext"
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = _plugin_src()
    if dest.is_symlink() or dest.exists():
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        else:
            shutil.rmtree(dest)
    if copy:
        shutil.copytree(src, dest)
    else:
        try:
            dest.symlink_to(src, target_is_directory=True)
        except OSError:
            shutil.copytree(src, dest)
    return dest


def _write_native_config(home: Path, values: dict) -> Path:
    path = home / "cortext.json"
    existing: dict = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8")) or {}
        except Exception:
            existing = {}
    existing.update(values)
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except Exception:
        pass
    return path


def _set_provider_in_yaml(home: Path) -> bool:
    """Set ``provider: cortext`` *inside the top-level ``memory:`` block only*.

    Scoped to the memory block so it never touches an unrelated ``provider:``
    (e.g. ``model.provider``). If the block has no ``provider:`` key, one is
    inserted. Returns True on change. Best-effort and indentation-preserving.
    """
    cfg = home / "config.yaml"
    if not cfg.exists():
        return False
    try:
        import re

        lines = cfg.read_text(encoding="utf-8").splitlines(keepends=True)
        in_memory = False
        mem_indent = ""
        insert_at = None
        for i, line in enumerate(lines):
            if re.match(r"^memory:\s*$", line):
                in_memory = True
                insert_at = i + 1
                continue
            if in_memory:
                stripped = line.strip()
                # A non-indented, non-blank line ends the block.
                if stripped and not line[0].isspace():
                    break
                m = re.match(r"^(\s+)provider:\s*.*$", line)
                if m:
                    lines[i] = f"{m.group(1)}provider: cortext\n"
                    cfg.write_text("".join(lines), encoding="utf-8")
                    return True
                if stripped and mem_indent == "":
                    mem_indent = line[: len(line) - len(line.lstrip())]
        # No provider key in the memory block — insert one.
        if insert_at is not None:
            indent = mem_indent or "  "
            lines.insert(insert_at, f"{indent}provider: cortext\n")
            cfg.write_text("".join(lines), encoding="utf-8")
            return True
    except Exception:
        pass
    return False


def cmd_hermes_install(args) -> int:
    home = _hermes_home()
    if not _plugin_src().exists():
        print(f"{RED}error:{RESET} bundled plugin not found in the package", file=sys.stderr)
        return 1
    home.mkdir(parents=True, exist_ok=True)
    dest = _install_plugin(home, copy=getattr(args, "copy", False))
    _ok(f"plugin installed at {dest}")
    return 0


def cmd_setup(args) -> int:
    _banner()
    interactive = sys.stdin.isatty() and not getattr(args, "yes", False)
    home = _hermes_home()

    _step(f"library: cortext v{_version()}")

    if not home.exists():
        _warn(f"Hermes not detected at {home}")
        print()
        print(f"  {BOLD}You don't need Hermes.{RESET} Cortext is a framework-agnostic library:")
        print()
        print(f"      {DIM}from cortext import CortextV5{RESET}")
        print(f"      {DIM}cortex = CortextV5(namespace='myapp'){RESET}")
        print(f"      {DIM}cortex.remember(what='...', who=['alice']){RESET}")
        print(f"      {DIM}ctx, _ = cortex.recall('what did alice say?'){RESET}")
        print()
        print("  Or the neutral chat bridge (LangChain / LangGraph / any loop):")
        print(f"      {DIM}from cortext.integration import AgentMemoryBridge{RESET}")
        print()
        print(f"  Set {BOLD}HERMES_HOME{RESET} and re-run if Hermes lives elsewhere.")
        print()
        return 0

    _ok(f"Hermes detected at {home}")

    # 1. Install plugin files.
    dest = _install_plugin(home, copy=getattr(args, "copy", False))
    kind = "copied" if getattr(args, "copy", False) else "linked"
    _ok(f"plugin {kind} → {dest}")

    # 2. Configure.
    namespace = _ask("namespace (memory isolation)", "hermes", interactive)
    policy = _ask("validation_policy (warn/block)", "warn", interactive)
    if policy not in ("warn", "block"):
        policy = "warn"
    max_tokens = _ask("max_context_tokens", "300", interactive)
    dream = _ask_bool("enable background DreamAgent consolidation?", True, interactive)

    values = {
        "namespace": namespace,
        "validation_policy": policy,
        "max_context_tokens": int(max_tokens) if str(max_tokens).isdigit() else 300,
        "dream_agent": dream,
    }
    cfg_path = _write_native_config(home, values)
    _ok(f"config written → {cfg_path}")

    # 3. Activate provider.
    if _set_provider_in_yaml(home):
        _ok("set memory.provider: cortext in config.yaml")
    else:
        _warn("could not auto-edit config.yaml — set 'memory.provider: cortext' yourself")

    print()
    _box(
        "Cortext is set up ✓",
        [
            f"namespace      {GREEN}{namespace}{RESET}",
            f"validation     {policy}",
            f"context cap    {values['max_context_tokens']} tokens",
            f"dream agent    {'on' if dream else 'off'}",
            "",
            f"{DIM}Memory is recalled before each turn and stored after.{RESET}",
            f"{DIM}Start Hermes normally — no tool needed.{RESET}",
        ],
    )
    print()
    return 0


# ---- daemon, agents, memory ---------------------------------------------------

def cmd_serve(args) -> int:
    import logging

    from cortext.server.daemon import serve

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    return serve(host=args.host, port=args.port, db=args.db, dream_interval=args.dream_interval)


def cmd_daemon(args) -> int:
    from cortext.server import client, config

    action = args.action
    if action == "status":
        if client.is_running():
            h = client.get("/api/health")
            _ok(f"running · pid {h['pid']} · v{h['version']} · up {h['uptime_s']}s · {config.base_url()}")
            return 0
        _warn("stopped")
        return 1
    if action in ("stop", "restart"):
        if client.is_running():
            _ok("stopped") if client.stop_daemon() else _warn("could not stop the daemon")
        elif action == "stop":
            _warn("not running")
    if action in ("start", "restart"):
        if client.is_running():
            _ok(f"already running at {config.base_url()}")
            return 0
        if client.start_daemon():
            _ok(f"started at {config.base_url()} (log: {config.log_file()})")
            return 0
        print(f"{RED}error:{RESET} daemon did not come up; see {config.log_file()}", file=sys.stderr)
        return 1
    return 0


def cmd_dashboard(args) -> int:
    import webbrowser

    from cortext.server import client, config

    if not client.ensure_daemon():
        print(f"{RED}error:{RESET} daemon did not come up; see {config.log_file()}", file=sys.stderr)
        return 1
    url = config.base_url() + "/"
    _ok(f"dashboard at {url}")
    if not args.no_open:
        webbrowser.open(url)
    return 0


def cmd_hook(args) -> int:
    from cortext.agents.hooks import run

    return run(args.agent, args.event)


def cmd_mcp(_args) -> int:
    from cortext.agents.mcp import main as mcp_main

    return mcp_main()


def cmd_install(args) -> int:
    from cortext.agents import install

    plan = install.run(args.target, project=args.project, dry_run=args.dry_run, classic=args.classic)
    if args.target == "mcp":
        print(plan.notes[0])
        return 0
    head = "Would change" if args.dry_run else "Changed"
    _box(f"Cortext → {args.target}", [f"{head}:"] + [f"  {c}" for c in plan.changes or ["(nothing)"]])
    for n in plan.notes:
        _step(n)
    return 0


def _ns(args) -> str:
    from cortext.server import config

    return args.ns or config.namespace_for(os.getcwd())


def cmd_recall(args) -> int:
    from cortext.server import client

    client.ensure_daemon()
    r = client.post("/api/recall", {"ns": _ns(args), "query": args.query, "max_results": args.limit, "touch": False})
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0
    if not r["memories"]:
        _warn(f"nothing relevant in {_ns(args)} ({r['ms']} ms)")
        return 0
    for m in r["memories"]:
        who = ", ".join(m["who"])
        print(f"  {DIM}{m['id'][:8]}{RESET} {CYAN}{m['tier']:<9}{RESET} " + (f"{BOLD}{who}{RESET} | " if who else "") + m["what"])
    print(f"  {DIM}{len(r['memories'])} hits in {r['ms']} ms · {_ns(args)}{RESET}")
    return 0


def cmd_remember(args) -> int:
    from cortext.server import client

    client.ensure_daemon()
    body = {"ns": _ns(args), "text": args.text, "importance": args.importance}
    if args.who:
        body["who"] = [w.strip() for w in args.who.split(",") if w.strip()]
    r = client.post("/api/remember", body)
    if r["stored"]:
        _ok(f"stored {r['id'][:8]} in {_ns(args)} ({r['ms']} ms){' — ' + r['reason'] if r['status'] == 'WARN' else ''}")
        return 0
    _warn(f"not stored: {r['reason']}")
    return 1


def cmd_stats(args) -> int:
    from cortext.server import client

    client.ensure_daemon()
    if args.ns:
        print(json.dumps(client.get(f"/api/stats?ns={args.ns}"), ensure_ascii=False, indent=2))
        return 0
    o = client.get("/api/overview")
    lines = [f"{n['name']:<32} {n['memories']:>7} memories" for n in o["namespaces"]] or ["(empty)"]
    lines += ["", "levels  " + "  ".join(f"{k} {v}" for k, v in o["levels"].items())]
    lat = o["latency"]
    lines.append(f"latency recall p50 {lat['recall']['p50_ms']} ms · remember p50 {lat['remember']['p50_ms']} ms")
    _box(f"Cortext · {o['total_memories']} memories", lines)
    return 0


def cmd_ns(args) -> int:
    from cortext.server import config

    print(config.namespace_for(args.path or os.getcwd()))
    return 0


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="cortext-memory",
        description="Cortext — cognitive memory for AI agents.",
    )
    sub = parser.add_subparsers(dest="command")

    p_setup = sub.add_parser("setup", help="install + configure the Hermes plugin (wizard)")
    p_setup.add_argument("--yes", action="store_true", help="non-interactive (use defaults)")
    p_setup.add_argument("--copy", action="store_true", help="copy plugin files instead of symlinking")
    p_setup.set_defaults(func=cmd_setup)

    p_inst = sub.add_parser("hermes-install", help="drop the plugin into ~/.hermes/plugins (no config)")
    p_inst.add_argument("--copy", action="store_true", help="copy instead of symlink")
    p_inst.set_defaults(func=cmd_hermes_install)

    p_info = sub.add_parser("info", help="show status")
    p_info.set_defaults(func=cmd_info)

    p_serve = sub.add_parser("serve", help="run the memory daemon in the foreground")
    p_serve.add_argument("--host")
    p_serve.add_argument("--port", type=int)
    p_serve.add_argument("--db", help="SQLite file (default ~/.cortext/memory.db)")
    p_serve.add_argument("--dream-interval", type=int, default=1800, help="seconds between consolidation cycles (0 = off)")
    p_serve.set_defaults(func=cmd_serve)

    p_d = sub.add_parser("daemon", help="start/stop/status of the background daemon")
    p_d.add_argument("action", choices=["start", "stop", "restart", "status"])
    p_d.set_defaults(func=cmd_daemon)

    p_dash = sub.add_parser("dashboard", help="open the control panel in the browser")
    p_dash.add_argument("--no-open", action="store_true", help="print the URL only")
    p_dash.set_defaults(func=cmd_dashboard)

    p_hook = sub.add_parser("hook", help="agent hook adapter (reads the agent's JSON on stdin)")
    p_hook.add_argument("agent", choices=["claude", "claude-code", "vscode", "cursor", "copilot", "generic"])
    p_hook.add_argument("event")
    p_hook.set_defaults(func=cmd_hook)

    p_mcp = sub.add_parser("mcp", help="MCP server on stdio (Cursor, Copilot, Windsurf, Claude Desktop, ...)")
    p_mcp.set_defaults(func=cmd_mcp)

    p_ins = sub.add_parser("install", help="wire Cortext into an agent")
    p_ins.add_argument("target", choices=["claude", "cursor", "copilot", "vscode", "mcp"])
    p_ins.add_argument("--project", help="configure this repository (project-scoped files)")
    p_ins.add_argument("--classic", action="store_true", help="claude: settings.json command hooks instead of the mod")
    p_ins.add_argument("--dry-run", action="store_true", help="show what would change")
    p_ins.set_defaults(func=cmd_install)

    p_rc = sub.add_parser("recall", help="recall memories for a query")
    p_rc.add_argument("query")
    p_rc.add_argument("--ns", help="namespace (default: this project's)")
    p_rc.add_argument("--limit", type=int, default=8)
    p_rc.add_argument("--json", action="store_true")
    p_rc.set_defaults(func=cmd_recall)

    p_rm = sub.add_parser("remember", help="store a fact")
    p_rm.add_argument("text")
    p_rm.add_argument("--who", help="comma-separated participants")
    p_rm.add_argument("--importance", type=float, default=0.7)
    p_rm.add_argument("--ns")
    p_rm.set_defaults(func=cmd_remember)

    p_st = sub.add_parser("stats", help="memory levels, sizes and latency")
    p_st.add_argument("--ns")
    p_st.set_defaults(func=cmd_stats)

    p_ns = sub.add_parser("ns", help="print the namespace for a folder")
    p_ns.add_argument("path", nargs="?")
    p_ns.set_defaults(func=cmd_ns)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        return cmd_info(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
