"""
Service layer: the daemon over real HTTP, the agent hook adapter, the MCP
server and the installers. Each test runs against a daemon on an ephemeral
port with its own CORTEXT_HOME, never the user's.
"""

import http.client
import io
import json
import socket
import threading

import pytest

from cortext.server import client
from cortext.server.daemon import make_server
from cortext.server.engine import MemoryEngine


@pytest.fixture()
def daemon(tmp_path, monkeypatch):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    monkeypatch.setenv("CORTEXT_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CORTEXT_PORT", str(port))
    monkeypatch.setenv("CORTEXT_NO_AUTOSTART", "1")
    monkeypatch.delenv("CORTEXT_NAMESPACE", raising=False)
    monkeypatch.delenv("CORTEXT_TOKEN", raising=False)
    engine = MemoryEngine(tmp_path / "m.db", dream_interval_seconds=0)
    server = make_server(engine, "127.0.0.1", port)
    t = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    t.start()
    yield {"port": port, "engine": engine}
    server.stopping = True
    server.shutdown()
    server.server_close()
    engine.close()


def raw(port, method, path, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    conn.request(method, path, body=body, headers=headers or {})
    r = conn.getresponse()
    data = r.read()
    conn.close()
    return r.status, data


# --- daemon ---------------------------------------------------------------------------

def test_remember_recall_roundtrip(daemon):
    r = client.post("/api/remember", {"ns": "p", "what": "deploy roda via Helm", "who": ["CI"]})
    assert r["stored"] and r["status"] == "OK"
    out = client.post("/api/recall", {"ns": "p", "query": "como é o deploy?"})
    assert out["memories"][0]["what"] == "deploy roda via Helm"
    assert out["context"].startswith("<cortext-memory>") and "Helm" in out["context"]


def test_turn_capture_skips_trivial(daemon):
    assert client.post("/api/turn", {"ns": "p", "user": "ok", "assistant": "x"})["stored"] is False
    assert client.post("/api/turn", {"ns": "p", "user": "/clear", "assistant": "x"})["stored"] is False
    stored = client.post("/api/turn", {"ns": "p", "user": "Como configuro o cache Redis em staging?", "assistant": "Use REDIS_URL."})
    assert stored["stored"]


def test_injected_block_is_not_stored_back(daemon):
    user = "<cortext-memory>\n- old fact\n</cortext-memory> Explique o fluxo de reembolso do checkout"
    client.post("/api/turn", {"ns": "p", "user": user, "assistant": "..."})
    page = client.get("/api/memories?ns=p")
    assert page["memories"][0]["what"] == "Explique o fluxo de reembolso do checkout"


def test_overview_levels_graph_and_dashboard(daemon):
    client.post("/api/remember", {"ns": "p", "what": "Ana revisa PRs", "who": ["Ana"]})
    o = client.get("/api/overview")
    assert o["total_memories"] == 1 and o["levels"]["working"] == 1
    g = client.get("/api/graph?ns=p")
    assert {n["kind"] for n in g["nodes"]} == {"memory", "entity"}
    status, page = raw(daemon["port"], "GET", "/", headers={"Host": "127.0.0.1"})
    assert status == 200 and b"Nuvens de mem" in page


def test_forget_endpoint(daemon):
    mid = client.post("/api/remember", {"ns": "p", "what": "fato descartável"})["id"]
    assert client.delete(f"/api/memory/{mid}?ns=p")["deleted"] is True
    assert client.get("/api/memories?ns=p")["total"] == 0


def test_guards_reject_foreign_host_origin_and_form_posts(daemon):
    port = daemon["port"]
    assert raw(port, "GET", "/api/health", headers={"Host": "evil.example"})[0] == 403
    assert raw(port, "GET", "/api/health", headers={"Host": "127.0.0.1", "Origin": "https://evil.example"})[0] == 403
    status, _ = raw(port, "POST", "/api/remember", body=b"what=x",
                    headers={"Host": "127.0.0.1", "Content-Type": "application/x-www-form-urlencoded"})
    assert status == 403


def test_token_is_enforced_when_set(daemon, monkeypatch):
    monkeypatch.setenv("CORTEXT_TOKEN", "s3cret")
    assert raw(daemon["port"], "GET", "/api/health", headers={"Host": "127.0.0.1"})[0] == 403
    assert client.get("/api/health")["ok"]  # the client sends the header


def test_bad_input_is_400_not_500(daemon):
    status, body = raw(daemon["port"], "POST", "/api/recall", body=b"{}",
                       headers={"Host": "127.0.0.1", "Content-Type": "application/json"})
    assert status == 400 and b"query" in body


# --- hooks ----------------------------------------------------------------------------

def run_hook(monkeypatch, agent, event, payload):
    from cortext.agents import hooks

    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    assert hooks.run(agent, event, json.dumps(payload)) == 0
    text = out.getvalue()
    return json.loads(text) if text.strip() else None


def test_claude_hooks_inject_and_capture(daemon, monkeypatch, tmp_path):
    proj = tmp_path / "loja"
    proj.mkdir()
    ns = "project:loja"
    client.post("/api/remember", {"ns": ns, "what": "pagamentos usam idempotency-key", "importance": 0.9})

    out = run_hook(monkeypatch, "claude", "UserPromptSubmit",
                   {"session_id": "s1", "cwd": str(proj), "prompt": "como evitar cobrança duplicada nos pagamentos?"})
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit" and "idempotency" in ctx

    transcript = tmp_path / "t.jsonl"
    rows = [
        {"type": "user", "message": {"role": "user", "content": "como evitar cobrança duplicada nos pagamentos?"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Use a idempotency-key."}]}},
    ]
    transcript.write_text("\n".join(json.dumps(r) for r in rows))
    assert run_hook(monkeypatch, "claude", "Stop", {"session_id": "s1", "cwd": str(proj), "transcript_path": str(transcript)}) is None
    page = client.get(f"/api/memories?ns={ns}")
    turn = [m for m in page["memories"] if m["how"]]
    assert turn and turn[0]["how"] == "Use a idempotency-key."


def test_claude_session_start_digest(daemon, monkeypatch, tmp_path):
    client.post("/api/remember", {"ns": "project:repo", "what": "testes rodam com pytest -q", "importance": 0.9})
    (tmp_path / "repo").mkdir()
    out = run_hook(monkeypatch, "claude", "SessionStart", {"cwd": str(tmp_path / "repo")})
    assert "pytest -q" in out["hookSpecificOutput"]["additionalContext"]


def test_cursor_hooks_pair_prompt_and_response(daemon, monkeypatch, tmp_path):
    (tmp_path / "app").mkdir()
    base = {"conversation_id": "c9", "workspace_roots": [str(tmp_path / "app")]}
    assert run_hook(monkeypatch, "cursor", "beforeSubmitPrompt", {**base, "prompt": "Refatore o serviço de frete para usar cache"}) == {"continue": True}
    run_hook(monkeypatch, "cursor", "afterAgentResponse", {**base, "text": "Adicionei cache LRU no FreightService."})
    m = client.get("/api/memories?ns=project:app")["memories"][0]
    assert m["what"].startswith("Refatore o serviço de frete") and "LRU" in m["how"]
    start = run_hook(monkeypatch, "cursor", "sessionStart", base)
    assert "frete" in start["additional_context"]


def test_copilot_hooks(daemon, monkeypatch, tmp_path):
    (tmp_path / "api").mkdir()
    base = {"sessionId": "k1", "cwd": str(tmp_path / "api")}
    run_hook(monkeypatch, "copilot", "userPromptSubmitted", {**base, "prompt": "Adicione paginação no endpoint de pedidos"})
    run_hook(monkeypatch, "copilot", "agentStop", base)
    assert client.get("/api/memories?ns=project:api")["total"] == 1
    out = run_hook(monkeypatch, "copilot", "sessionStart", base)
    assert "paginação" in out["additionalContext"]


def test_hook_never_fails_without_daemon(monkeypatch, tmp_path):
    monkeypatch.setenv("CORTEXT_HOME", str(tmp_path))
    monkeypatch.setenv("CORTEXT_PORT", "9")  # nothing listens
    monkeypatch.setenv("CORTEXT_NO_AUTOSTART", "1")
    assert run_hook(monkeypatch, "claude", "UserPromptSubmit", {"prompt": "x" * 20}) is None


def test_last_exchange_skips_tool_results_and_commands(tmp_path):
    from cortext.agents.hooks import last_exchange

    rows = [
        {"type": "user", "message": {"role": "user", "content": "<command-name>/clear</command-name>"}},
        {"type": "user", "message": {"role": "user", "content": "Rode os testes e corrija o que falhar"}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "1", "name": "Bash", "input": {}}]}},
        {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1", "content": "ok"}]}},
        {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Todos passam agora."}]}},
    ]
    p = tmp_path / "t.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows))
    assert last_exchange(str(p)) == ("Rode os testes e corrija o que falhar", "Todos passam agora.")


# --- MCP --------------------------------------------------------------------------------

def test_mcp_protocol(daemon, monkeypatch):
    from cortext.agents.mcp import Server

    monkeypatch.setenv("CORTEXT_NAMESPACE", "project:mcp")
    s = Server(lambda _: None)
    init = s.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
    assert init["result"]["protocolVersion"] == "2025-06-18" and "memory_recall" in init["result"]["instructions"]
    assert s.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    names = [t["name"] for t in s.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]]
    assert {"memory_recall", "memory_remember", "memory_capture_turn", "memory_forget"} <= set(names)

    def call(name, args):
        return s.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
    stored = call("memory_remember", {"what": "filas usam SQS", "why": "retries nativos"})
    assert stored["isError"] is False and stored["content"][0]["text"].startswith("Stored ")
    got = call("memory_recall", {"query": "que fila usamos?"})
    assert "filas usam SQS" in got["content"][0]["text"]
    short_id = got["content"][0]["text"][1:9]
    assert call("memory_forget", {"id": short_id})["content"][0]["text"] == "Deleted."
    assert s.handle({"jsonrpc": "2.0", "id": 9, "method": "nope"})["error"]["code"] == -32601


# --- installers ---------------------------------------------------------------------------

def test_installers_extend_and_are_idempotent(tmp_path, monkeypatch):
    from cortext.agents import install

    monkeypatch.setenv("HOME", str(tmp_path))
    cursor_hooks = tmp_path / ".cursor" / "hooks.json"
    cursor_hooks.parent.mkdir(parents=True)
    cursor_hooks.write_text(json.dumps({"version": 1, "hooks": {"stop": [{"command": "./mine.sh"}]}}))

    plan = install.run("cursor")
    data = json.loads(cursor_hooks.read_text())
    assert data["hooks"]["stop"] == [{"command": "./mine.sh"}]  # untouched
    assert "cortext.agents.hooks cursor beforeSubmitPrompt" in data["hooks"]["beforeSubmitPrompt"][0]["command"]
    assert (tmp_path / ".cursor" / "hooks.json.cortext-backup").exists()
    assert plan.changes
    assert install.run("cursor").changes == []  # second run: nothing to do

    install.run("claude")
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    mod_dir = tmp_path / ".cortext" / "claude-mod"
    assert str(mod_dir) in settings["env"]["CLAUDE_CODE_PLUGIN_DIRS"]
    assert (mod_dir / "hooks" / "register.tsx").exists() and not (mod_dir / "tests").exists()

    proj = tmp_path / "repo"
    proj.mkdir()
    (proj / ".github").mkdir()
    (proj / ".github" / "copilot-instructions.md").write_text("# Team rules\n\nBe nice.\n")
    install.run("vscode", project=str(proj))
    install.run("vscode", project=str(proj))
    instructions = (proj / ".github" / "copilot-instructions.md").read_text()
    assert instructions.startswith("# Team rules") and instructions.count("cortext-memory:begin") == 1
    vs = json.loads((proj / ".vscode" / "mcp.json").read_text())
    assert vs["servers"]["cortext"]["env"]["CORTEXT_NAMESPACE"] == "project:repo"


def test_installer_dry_run_writes_nothing(tmp_path, monkeypatch):
    from cortext.agents import install

    monkeypatch.setenv("HOME", str(tmp_path))
    plan = install.run("copilot", dry_run=True)
    assert plan.changes and not (tmp_path / ".copilot").exists()
