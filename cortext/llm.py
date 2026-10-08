"""
LLM backends for background memory work (stdlib only).

A backend turns (system, prompt) into text. The daemon's queue worker uses
one when CORTEXT_LLM is set; inside Claude Code the mod does the same job with
the user's own model via $.model.complete, so no backend is needed there.

  claude-cli  `claude -p` on the user's own Claude Code login (subscription).
              Isolated: no tools, no MCP servers, no session saved, empty cwd.
  http        any OpenAI-compatible /chat/completions endpoint
              (CORTEXT_LLM_URL, CORTEXT_LLM_KEY), e.g. Anthropic-compatible
              gateways, OpenRouter, Ollama (/v1).

Model: CORTEXT_LLM_MODEL (default "haiku").
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from typing import Optional, Protocol

DEFAULT_SYSTEM = ("You are a memory-curation component inside a software system. "
                  "Answer with one JSON object only, no prose, no code fences.")


class LLMBackend(Protocol):
    name: str

    def complete(self, prompt: str, system: str = DEFAULT_SYSTEM) -> str: ...


class ClaudeCLI:
    name = "claude-cli"

    def __init__(self, model: str = "haiku", binary: str = "claude", timeout: float = 300) -> None:
        self.model = model
        self.binary = binary
        self.timeout = timeout
        self._cwd = tempfile.mkdtemp(prefix="cortext-llm-")  # no project CLAUDE.md is loaded from here

    def complete(self, prompt: str, system: str = DEFAULT_SYSTEM) -> str:
        cmd = [self.binary, "-p", "--model", self.model, "--tools", "", "--no-session-persistence",
               "--strict-mcp-config", "--system-prompt", system, "--output-format", "json"]
        env = {**os.environ, "CORTEXT_NO_AUTOSTART": "1", "CORTEXT_INSIDE_WORKER": "1"}
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=self._cwd,
                              timeout=self.timeout, env=env)
        raw = proc.stdout
        try:
            envelope = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        except ValueError as e:
            raise RuntimeError(f"claude -p returned no JSON: {proc.stderr[:300] or raw[:300]}") from e
        if envelope.get("is_error"):
            raise RuntimeError(f"claude -p error: {envelope.get('result')}")
        return str(envelope.get("result") or "")


class OpenAICompatible:
    name = "http"

    def __init__(self, url: str, key: str = "", model: str = "haiku", timeout: float = 120) -> None:
        self.url = url.rstrip("/") + ("" if url.rstrip("/").endswith("/chat/completions") else "/chat/completions")
        self.key = key
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str, system: str = DEFAULT_SYSTEM) -> str:
        body = json.dumps({"model": self.model, "temperature": 0, "max_tokens": 1200, "messages": [
            {"role": "system", "content": system}, {"role": "user", "content": prompt}]}).encode()
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        req = urllib.request.Request(self.url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read())
        return str(data["choices"][0]["message"]["content"] or "")


def from_env() -> Optional[LLMBackend]:
    """The backend CORTEXT_LLM names, or None (background abstraction off)."""
    kind = os.environ.get("CORTEXT_LLM", "").strip().lower()
    model = os.environ.get("CORTEXT_LLM_MODEL", "haiku")
    if kind in ("claude", "claude-cli"):
        if shutil.which("claude") is None:
            raise RuntimeError("CORTEXT_LLM=claude-cli but `claude` is not on PATH")
        return ClaudeCLI(model=model)
    if kind in ("http", "openai"):
        url = os.environ.get("CORTEXT_LLM_URL", "")
        if not url:
            raise RuntimeError("CORTEXT_LLM=http needs CORTEXT_LLM_URL")
        return OpenAICompatible(url, os.environ.get("CORTEXT_LLM_KEY", ""), model)
    return None


def parse_json_object(text: str) -> dict:
    """The first JSON object in a model's reply (tolerates code fences and prose)."""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return {}
    try:
        out = json.loads(m.group(0))
    except ValueError:
        return {}
    return out if isinstance(out, dict) else {}
