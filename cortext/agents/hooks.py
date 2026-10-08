"""
Universal hook adapter: one command, every agent's hook format.

    cortext-memory hook <agent> <event>        (stdin: the agent's JSON payload)

Agents and the events wired for them:

  claude   SessionStart      -> inject the project's long-term memory digest
  (also    UserPromptSubmit  -> recall for the prompt, inject as additionalContext
  VS Code  Stop              -> store the finished turn (read from transcript_path)
  agent hooks, same format)

  cursor   sessionStart      -> inject digest            ({"additional_context"})
           beforeSubmitPrompt-> remember the prompt for this conversation
           afterAgentResponse-> store prompt + response as a turn

  copilot  sessionStart      -> inject digest            ({"additionalContext"})
           userPromptSubmitted -> remember the prompt for this session
           agentStop         -> store the turn (response from transcriptPath)

  generic  recall            -> stdin {"prompt","cwd"}: print the context block
           turn              -> stdin {"user","assistant","cwd"}: store it

Cursor and Copilot cannot inject context per prompt from a hook; there the
per-prompt recall comes from the MCP server (``cortext-memory mcp``) plus an
instructions file the installer writes. Hooks still capture every turn.

Never blocks the agent: any failure exits 0 with no output. Imports only the
standard library and the daemon client.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

from cortext.server import client, config


# --- pending prompts (pairing a prompt with the response that follows) --------

def _pending_path(agent: str, session: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in (session or "nosession"))[:120]
    return config.home() / "pending" / f"{agent}-{safe}.json"


def _save_pending(agent: str, session: str, prompt: str, cwd: str) -> None:
    p = _pending_path(agent, session)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"prompt": prompt, "cwd": cwd, "ts": time.time()}), encoding="utf-8")


def _pop_pending(agent: str, session: str) -> dict[str, Any]:
    p = _pending_path(agent, session)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        p.unlink()
        return data
    except (OSError, ValueError):
        return {}


def _sweep_pending(max_age_s: float = 86400) -> None:
    d = config.home() / "pending"
    if not d.is_dir():
        return
    cutoff = time.time() - max_age_s
    for f in d.iterdir():
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
        except OSError:
            pass


# --- transcripts ----------------------------------------------------------------

def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in (None, "text") and isinstance(block.get("text"), str):
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    if isinstance(content, dict):
        return _text_of(content.get("content") or content.get("text"))
    return ""


def last_exchange(transcript_path: str, tail_bytes: int = 512_000) -> tuple[str, str]:
    """(last real user prompt, last assistant text) from a JSONL transcript.

    Tolerant of the Claude Code shape ({"type","message":{"role","content"}})
    and of flat {"role","content"} / {"type":"user.message","data":...} rows.
    Tool results (user rows with no text) are not prompts.
    """
    path = Path(transcript_path).expanduser()
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - tail_bytes))
        raw = f.read().decode("utf-8", errors="replace")
    lines = raw.splitlines()
    if size > tail_bytes and lines:
        lines = lines[1:]  # first line may be cut
    user, assistant = "", ""
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        msg = row.get("message") if isinstance(row.get("message"), dict) else row
        role = msg.get("role") or row.get("type") or ""
        role = str(role).split(".")[0].lower()
        if row.get("isMeta"):
            continue
        text = _text_of(msg.get("content", msg.get("data"))).strip()
        if not text:
            continue
        if role == "assistant" and not assistant and not user:
            assistant = text
        elif role == "user" and not user:
            if text.startswith("<") and ("command-name>" in text or "local-command" in text):
                continue
            user = text
            if assistant:
                break
    return user, assistant


# --- outputs per agent ----------------------------------------------------------

def _emit(obj: Optional[dict]) -> None:
    if obj:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False))
        sys.stdout.flush()


def _recall(ns: str, prompt: str) -> str:
    if not prompt or len(prompt.strip()) < 3:
        return ""
    r = client.post("/api/recall", {"ns": ns, "query": prompt[:2000], "max_results": 6, "max_tokens": 350}, timeout=3)
    return r.get("context") or ""


def _digest(ns: str) -> str:
    r = client.get(f"/api/digest?ns={_q(ns)}", timeout=3)
    return r.get("context") or ""


def _q(s: str) -> str:
    from urllib.parse import quote

    return quote(s, safe="")


def _end(ns: str, session: str) -> None:
    client.post("/api/session/end", {"ns": ns, "session": session}, timeout=5)


def _turn(ns: str, user: str, assistant: str, agent: str, session: str) -> None:
    if user.strip():
        client.post("/api/turn", {"ns": ns, "user": user, "assistant": assistant, "agent": agent, "session": session}, timeout=5)


# --- handlers -------------------------------------------------------------------

def handle_claude(event: str, data: dict) -> Optional[dict]:
    ev = (event or data.get("hook_event_name") or "").replace("_", "").lower()
    cwd = data.get("cwd") or os.getcwd()
    ns = config.namespace_for(cwd)
    session = data.get("session_id", "")
    if ev == "sessionstart":
        ctx = _digest(ns)
        return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}} if ctx else None
    if ev == "userpromptsubmit":
        prompt = data.get("prompt", "")
        _save_pending("claude", session, prompt, cwd)
        ctx = _recall(ns, prompt)
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}} if ctx else None
    if ev == "sessionend":
        _end(ns, session)
        return None
    if ev == "stop":
        if data.get("stop_hook_active"):
            return None
        pending = _pop_pending("claude", session)
        user, assistant = "", data.get("last_assistant_message", "") or ""
        if data.get("transcript_path"):
            try:
                user, t_assistant = last_exchange(data["transcript_path"])
                assistant = assistant or t_assistant
            except OSError:
                pass
        _turn(ns, pending.get("prompt") or user, assistant, "claude-code", session)
        return None
    return None


def handle_cursor(event: str, data: dict) -> Optional[dict]:
    ev = (event or data.get("hook_event_name") or "").lower()
    roots = data.get("workspace_roots") or []
    cwd = roots[0] if roots else (data.get("cwd") or os.getcwd())
    ns = config.namespace_for(cwd)
    session = data.get("conversation_id") or data.get("session_id") or ""
    if ev == "sessionstart":
        ctx = _digest(ns)
        return {"additional_context": ctx} if ctx else {}
    if ev == "beforesubmitprompt":
        _save_pending("cursor", session, data.get("prompt", ""), cwd)
        return {"continue": True}
    if ev == "afteragentresponse":
        pending = _pop_pending("cursor", session)
        _turn(ns, pending.get("prompt", ""), data.get("text", ""), "cursor", session)
        return {}
    if ev == "sessionend":
        _end(ns, session)
        return {}
    return {}


def handle_copilot(event: str, data: dict) -> Optional[dict]:
    ev = (event or data.get("hookEventName") or "").lower()
    cwd = data.get("cwd") or os.getcwd()
    ns = config.namespace_for(cwd)
    session = data.get("sessionId") or data.get("session_id") or ""
    if ev == "sessionstart":
        ctx = _digest(ns)
        return {"additionalContext": ctx} if ctx else None
    if ev in ("userpromptsubmitted", "userpromptsubmit"):
        _save_pending("copilot", session, data.get("prompt", ""), cwd)
        return None
    if ev == "sessionend":
        _end(ns, session)
        return None
    if ev in ("agentstop", "stop"):
        pending = _pop_pending("copilot", session)
        user, assistant = pending.get("prompt", ""), ""
        tp = data.get("transcriptPath") or data.get("transcript_path")
        if tp:
            try:
                t_user, assistant = last_exchange(tp)
                user = user or t_user
            except OSError:
                pass
        _turn(ns, user, assistant, "copilot", session)
        return None
    return None


def handle_generic(event: str, data: dict) -> Optional[str]:
    cwd = data.get("cwd") or os.getcwd()
    ns = data.get("namespace") or config.namespace_for(cwd)
    if event == "recall":
        return _recall(ns, data.get("prompt") or data.get("query") or "")
    if event == "digest":
        return _digest(ns)
    if event == "turn":
        _turn(ns, data.get("user", ""), data.get("assistant", ""), data.get("agent", "generic"), data.get("session", ""))
    return None


HANDLERS = {"claude": handle_claude, "claude-code": handle_claude, "vscode": handle_claude,
            "cursor": handle_cursor, "copilot": handle_copilot}


def run(agent: str, event: str, stdin_text: Optional[str] = None) -> int:
    """Entry point. Always returns 0: a memory hook must never break the agent."""
    try:
        raw = stdin_text if stdin_text is not None else sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        if not isinstance(data, dict):
            data = {}
        if not client.ensure_daemon():
            return 0
        if agent == "generic":
            out = handle_generic(event, data)
            if out:
                sys.stdout.write(out)
            return 0
        handler = HANDLERS.get(agent)
        if handler is not None:
            _emit(handler(event, data))
        if event.lower() in ("sessionstart", "session_start"):
            _sweep_pending()
    except Exception as e:  # pragma: no cover - fail-safe path
        if os.environ.get("CORTEXT_DEBUG"):
            print(f"cortext hook error: {type(e).__name__}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    args = sys.argv[1:] + ["", ""]
    raise SystemExit(run(args[0], args[1]))
