"""Where the daemon lives and how clients find it.

Everything is overridable by environment, so hooks spawned by any agent
resolve the same daemon without arguments:

  CORTEXT_HOME       state directory            (default ~/.cortext)
  CORTEXT_DB         SQLite file                (default $CORTEXT_HOME/memory.db)
  CORTEXT_HOST       bind/connect address       (default 127.0.0.1)
  CORTEXT_PORT       port                       (default 7077)
  CORTEXT_NAMESPACE  force one namespace for every agent/project
  CORTEXT_TOKEN      optional shared secret; when set, API calls must send it
                     as the X-Cortext-Token header

This module imports only the standard library: hooks import it on every event.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("CORTEXT_HOME") or Path.home() / ".cortext").expanduser()


def db_path() -> Path:
    env = os.environ.get("CORTEXT_DB")
    return Path(env).expanduser() if env else home() / "memory.db"


def host() -> str:
    return os.environ.get("CORTEXT_HOST", "127.0.0.1")


def port() -> int:
    try:
        return int(os.environ.get("CORTEXT_PORT", "7077"))
    except ValueError:
        return 7077


def token() -> str:
    return os.environ.get("CORTEXT_TOKEN", "")


def base_url() -> str:
    return f"http://{host()}:{port()}"


def pid_file() -> Path:
    return home() / "daemon.pid"


def log_file() -> Path:
    return home() / "daemon.log"


def _git_root(start: Path) -> Path | None:
    for p in (start, *start.parents):
        if (p / ".git").exists():
            return p
    return None


def namespace_for(cwd: str | None = None) -> str:
    """The namespace an agent working in ``cwd`` reads and writes.

    One namespace per project (the git root's folder name, else the cwd's),
    so memories of one codebase never leak into another. CORTEXT_NAMESPACE
    pins a single namespace for everything.
    """
    forced = os.environ.get("CORTEXT_NAMESPACE")
    if forced:
        return forced
    if not cwd:
        return "default"
    path = Path(cwd).expanduser()
    root = _git_root(path) or path
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", root.name).strip("-").lower()
    return f"project:{name}" if name else "default"
