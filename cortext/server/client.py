"""
Thin client for the Cortext daemon — standard library only, imports in ~1 ms.

Agent hooks and the MCP server call the daemon through this. If no daemon
answers, ``ensure_daemon`` starts one in the background (same interpreter)
and waits for it, so the first hook of the day pays the start-up once and
every later one is a ~1 ms local call.
"""

from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import time
from typing import Any, Optional

from cortext.server import config


class DaemonUnavailable(RuntimeError):
    pass


def _request(method: str, path: str, body: Optional[dict] = None, timeout: float = 3.0) -> Any:
    conn = http.client.HTTPConnection(config.host(), config.port(), timeout=timeout)
    headers = {"Host": f"127.0.0.1:{config.port()}"}
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    if method != "GET":
        headers["Content-Type"] = "application/json"  # the daemon refuses non-JSON writes
    if config.token():
        headers["X-Cortext-Token"] = config.token()
    try:
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        payload = resp.read()
    except OSError as e:
        raise DaemonUnavailable(str(e)) from e
    finally:
        conn.close()
    out = json.loads(payload.decode("utf-8") or "null")
    if resp.status >= 400:
        raise RuntimeError(out.get("error") if isinstance(out, dict) else f"HTTP {resp.status}")
    return out


def get(path: str, timeout: float = 3.0) -> Any:
    return _request("GET", path, timeout=timeout)


def post(path: str, body: dict, timeout: float = 5.0) -> Any:
    return _request("POST", path, body, timeout=timeout)


def delete(path: str, timeout: float = 3.0) -> Any:
    return _request("DELETE", path, timeout=timeout)


def is_running(timeout: float = 0.3) -> bool:
    try:
        return bool(get("/api/health", timeout=timeout).get("ok"))
    except Exception:
        return False


def start_daemon(wait: float = 6.0) -> bool:
    """Start the daemon detached from this process. True once it answers."""
    home = config.home()
    home.mkdir(parents=True, exist_ok=True)
    log = open(config.log_file(), "ab")
    kwargs: dict[str, Any] = {"stdout": log, "stderr": log, "stdin": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([sys.executable, "-m", "cortext.server.daemon"], **kwargs)
    log.close()
    deadline = time.time() + wait
    while time.time() < deadline:
        if is_running(timeout=0.2):
            return True
        time.sleep(0.05)
    return False


def ensure_daemon(autostart: bool = True) -> bool:
    if is_running():
        return True
    if not autostart or os.environ.get("CORTEXT_NO_AUTOSTART"):
        return False
    return start_daemon()


def stop_daemon() -> bool:
    try:
        post("/api/shutdown", {}, timeout=2)
    except Exception:
        return False
    for _ in range(40):
        if not is_running(timeout=0.1):
            return True
        time.sleep(0.05)
    return False
