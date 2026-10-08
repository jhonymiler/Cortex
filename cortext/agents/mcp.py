"""
Cortext MCP server (stdio, JSON-RPC 2.0, no dependencies).

    cortext-memory mcp

Gives any MCP client — Cursor, VS Code / GitHub Copilot, Copilot CLI,
Windsurf, Claude Desktop, Codex, Gemini CLI, Zed — memory tools backed by the
local daemon. For agents whose hooks can't inject context per prompt, the
``instructions`` returned at initialize are the hook emulation: they tell the
model to recall at the start of each task and store durable facts as it
learns them.

Namespace: CORTEXT_NAMESPACE if set (the installer sets it for project-scoped
configs), else derived from the server's working directory.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable, Optional

from cortext.server import client, config

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")

INSTRUCTIONS = """Cortext is your long-term memory for this project, persisted across sessions.
- At the START of every task, call memory_recall with the user's request (or its key terms) and use what it returns. Treat recalled facts as possibly stale: verify against the code before relying on them.
- When you learn something durable — a decision and its reason, a convention, a fix for a recurring problem, where something lives, a user preference — call memory_remember with one concise fact (who/what/why/how).
- At the END of a task, call memory_capture_turn with the request and a one-paragraph summary of what you did.
Never store secrets, credentials or personal data."""

TOOLS: list[dict[str, Any]] = [
    {
        "name": "memory_recall",
        "description": "Recall memories relevant to a request from this project's long-term memory. Call at the start of each task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The request or its key terms."},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 20, "default": 6},
            },
            "required": ["query"],
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "memory_remember",
        "description": "Store one durable fact (decision, convention, fix, location, preference). Structured as W5H: what is required.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "what": {"type": "string", "description": "The fact, one sentence."},
                "who": {"type": "array", "items": {"type": "string"}, "description": "People/components involved."},
                "why": {"type": "string", "description": "Reason or cause."},
                "how": {"type": "string", "description": "Method, outcome or resolution."},
                "where": {"type": "string", "description": "Area/module/context."},
                "importance": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.7},
            },
            "required": ["what"],
        },
    },
    {
        "name": "memory_capture_turn",
        "description": "Log a finished task: the request and a short summary of what was done. Call at the end of each task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "request": {"type": "string"},
                "summary": {"type": "string"},
            },
            "required": ["request", "summary"],
        },
    },
    {
        "name": "memory_about",
        "description": "Everything remembered about one entity (person, component, service).",
        "inputSchema": {
            "type": "object",
            "properties": {"entity": {"type": "string"}, "limit": {"type": "integer", "default": 20}},
            "required": ["entity"],
        },
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "memory_forget",
        "description": "Delete a memory by id (use when a recalled fact is wrong or obsolete).",
        "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
        "annotations": {"destructiveHint": True},
    },
    {
        "name": "memory_stats",
        "description": "Memory levels (working, episodic, semantic, fading, archived), size and latency.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True},
    },
]


def _namespace() -> str:
    return os.environ.get("CORTEXT_NAMESPACE") or config.namespace_for(os.getcwd())


def _text(s: str, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": s}], "isError": is_error}


def _lines(records: list[dict[str, Any]]) -> str:
    out = []
    for r in records:
        who = ", ".join(r.get("who") or [])
        line = f"[{r['id'][:8]}] ({r.get('tier')}) " + (f"{who} | " if who else "") + r["what"]
        if r.get("how"):
            line += f" → {r['how'][:200]}"
        out.append(line)
    return "\n".join(out)


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    ns = _namespace()
    if name == "memory_recall":
        r = client.post("/api/recall", {"ns": ns, "query": args.get("query", ""), "max_results": int(args.get("max_results", 6))})
        if not r["memories"]:
            return _text("No relevant memories.")
        return _text(_lines(r["memories"]))
    if name == "memory_remember":
        body = {k: args[k] for k in ("what", "who", "why", "how", "where", "importance") if args.get(k) not in (None, "")}
        body["ns"] = ns
        r = client.post("/api/remember", body)
        if not r.get("stored"):
            return _text(f"Not stored: {r.get('reason')}", is_error=True)
        note = f" (warning: {r['reason']})" if r.get("status") == "WARN" else ""
        return _text(f"Stored {r['id'][:8]}{note}")
    if name == "memory_capture_turn":
        r = client.post("/api/turn", {"ns": ns, "user": args.get("request", ""), "assistant": args.get("summary", ""), "agent": "mcp"})
        return _text("Captured." if r.get("stored") else f"Skipped ({r.get('skipped') or r.get('reason')}).")
    if name == "memory_about":
        from urllib.parse import quote

        r = client.get(f"/api/memories?ns={quote(ns)}&who={quote(args.get('entity', ''))}&limit={int(args.get('limit', 20))}")
        return _text(_lines(r["memories"]) or "Nothing remembered about that.")
    if name == "memory_forget":
        mid = args.get("id", "")
        if len(mid) < 36:  # accept the 8-char prefix shown by recall
            from urllib.parse import quote

            page = client.get(f"/api/memories?ns={quote(ns)}&limit=500")
            full = [m["id"] for m in page["memories"] if m["id"].startswith(mid)]
            if len(full) != 1:
                return _text("Ambiguous or unknown id.", is_error=True)
            mid = full[0]
        r = client.delete(f"/api/memory/{mid}?ns={ns}")
        return _text("Deleted." if r.get("deleted") else "No such memory.", is_error=not r.get("deleted"))
    if name == "memory_stats":
        from urllib.parse import quote

        s = client.get(f"/api/stats?ns={quote(ns)}")
        return _text(json.dumps({"namespace": ns, "levels": s["levels"], "graph": s["graph"], "latency": s["latency"]}, indent=2))
    return _text(f"Unknown tool: {name}", is_error=True)


class Server:
    def __init__(self, write: Callable[[str], None]) -> None:
        self._write = write

    def send(self, msg: dict[str, Any]) -> None:
        self._write(json.dumps(msg, ensure_ascii=False) + "\n")

    def handle(self, msg: dict[str, Any]) -> Optional[dict[str, Any]]:
        method = msg.get("method")
        mid = msg.get("id")
        if mid is None:  # notification (initialized, cancelled, ...)
            return None
        try:
            result = self._result(method, msg.get("params") or {})
        except _RpcError as e:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": e.code, "message": str(e)}}
        except client.DaemonUnavailable as e:
            result = _text(f"Cortext daemon unavailable: {e}", is_error=True)
        except Exception as e:
            result = _text(f"{type(e).__name__}: {e}", is_error=True)
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def _result(self, method: Optional[str], params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            asked = params.get("protocolVersion")
            from cortext import __version__

            client.ensure_daemon()
            return {
                "protocolVersion": asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "cortext", "title": "Cortext memory", "version": __version__},
                "instructions": INSTRUCTIONS,
            }
        if method == "ping":
            return {}
        if method == "tools/list":
            return {"tools": TOOLS}
        if method == "tools/call":
            client.ensure_daemon()
            return call_tool(params.get("name", ""), params.get("arguments") or {})
        if method in ("resources/list", "prompts/list"):
            return {method.split("/")[0]: []}
        raise _RpcError(-32601, f"method not found: {method}")


class _RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def main() -> int:
    out = sys.stdout

    def write(s: str) -> None:
        out.write(s)
        out.flush()

    server = Server(write)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            server.send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            continue
        batch = msg if isinstance(msg, list) else [msg]
        for m in batch:
            if isinstance(m, dict):
                reply = server.handle(m)
                if reply is not None:
                    server.send(reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
