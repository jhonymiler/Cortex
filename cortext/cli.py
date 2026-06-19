"""Cortext command-line interface.

Entry point: ``cortext-memory``. The star command is ``setup`` — a small,
dependency-free wizard that installs and configures the Cortext memory plugin
for Hermes (or explains library usage if Hermes is not present).

Usage:
    cortext-memory setup            # interactive wizard
    cortext-memory setup --yes      # non-interactive (defaults)
    cortext-memory hermes-install   # just drop the plugin in, no config
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
    print(f"  {DIM}Library use (any framework):{RESET}")
    print("      from cortext import CortextV5")
    print("      cortex = CortextV5(namespace='myapp')")
    print()
    print(f"  Run {BOLD}cortext-memory setup{RESET} to wire it into Hermes.")
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
    """Best-effort: set memory.provider: cortext in config.yaml. Returns True if set."""
    cfg = home / "config.yaml"
    if not cfg.exists():
        return False
    try:
        text = cfg.read_text(encoding="utf-8")
        import re

        new, n = re.subn(r"(?m)^(\s*provider:\s*).+$", r"\1cortext", text, count=1)
        if n and new != text:
            cfg.write_text(new, encoding="utf-8")
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

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        return cmd_info(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
