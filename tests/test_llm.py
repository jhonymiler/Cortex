"""LLM backend selection and tolerant JSON parsing."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from cortext.llm import ClaudeCLI, OpenAICompatible, from_env, parse_json_object


@pytest.mark.parametrize("text,expected", [
    ('{"facts": ["a"]}', {"facts": ["a"]}),
    ('```json\n{"facts": []}\n```', {"facts": []}),
    ('Here you go: {"ok": true} hope it helps', {"ok": True}),
    ("no json at all", {}),
    ('{"broken": ', {}),
    ("[1, 2]", {}),
])
def test_parse_json_object(text, expected):
    assert parse_json_object(text) == expected


def test_from_env(monkeypatch):
    monkeypatch.delenv("CORTEXT_LLM", raising=False)
    assert from_env() is None
    monkeypatch.setenv("CORTEXT_LLM", "http")
    monkeypatch.delenv("CORTEXT_LLM_URL", raising=False)
    with pytest.raises(RuntimeError):
        from_env()
    monkeypatch.setenv("CORTEXT_LLM_URL", "http://127.0.0.1:9/v1")
    b = from_env()
    assert isinstance(b, OpenAICompatible) and b.url.endswith("/v1/chat/completions")
    monkeypatch.setenv("CORTEXT_LLM", "claude-cli")
    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(RuntimeError):
        from_env()


def test_claude_cli_command_is_isolated(monkeypatch):
    seen = {}

    class Done:
        stdout = json.dumps({"is_error": False, "result": '{"facts": []}'})
        stderr = ""

    def fake_run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return Done()

    monkeypatch.setattr("cortext.llm.subprocess.run", fake_run)
    assert ClaudeCLI(model="haiku").complete("extract this") == '{"facts": []}'
    cmd = seen["cmd"]
    for flag in ("--tools", "--strict-mcp-config", "--no-session-persistence", "--system-prompt"):
        assert flag in cmd
    assert cmd[cmd.index("--model") + 1] == "haiku"
    assert seen["kw"]["input"] == "extract this"
    assert seen["kw"]["env"]["CORTEXT_NO_AUTOSTART"] == "1"  # the child must not start daemons or hooks loops


def test_openai_compatible_roundtrip():
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body["model"] == "haiku" and body["messages"][1]["content"] == "hi"
            assert self.headers["Authorization"] == "Bearer k"
            out = json.dumps({"choices": [{"message": {"content": '{"ok": true}'}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    b = OpenAICompatible(f"http://127.0.0.1:{srv.server_port}/v1", key="k", model="haiku")
    assert parse_json_object(b.complete("hi")) == {"ok": True}
    srv.server_close()
