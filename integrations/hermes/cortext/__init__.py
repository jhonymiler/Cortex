"""Cortext memory provider for Hermes (standalone plugin).

Wraps the Cortext cognitive memory system (W5H-structured, contradiction-aware,
internationalized) as a Hermes ``MemoryProvider``. This ships as a *standalone*
plugin — drop it in ``~/.hermes/plugins/cortext/`` (or install via pip entry
point); it is not bundled into the Hermes tree.

Context-only provider: it auto-recalls relevant memories before each turn
(``prefetch``) and auto-stores each completed turn (``sync_turn``). The default
path exposes no tool; an opt-in ``cortext_inspect`` tool can be enabled for
on-demand auditing.

The in-memory graph is persisted to ``$HERMES_HOME/cortext_<namespace>.json`` so
memory survives across sessions.

Configuration lives in ``$HERMES_HOME/cortext.json`` (written by
``hermes memory setup``); the ``memory.cortext`` block of ``config.yaml`` is read
as a fallback. Selected with::

    memory:
      provider: cortext
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "cortext.json"

CORTEXT_INSPECT_SCHEMA = {
    "name": "cortext_inspect",
    "description": (
        "Audit the Cortext memory directly. Memory is normally recalled and "
        "injected automatically each turn — use this tool only when you need to "
        "SEE the structured detail behind a memory (the W5H decomposition, "
        "importance, access count, match score) or to deliberately probe.\n\n"
        "ACTIONS:\n"
        "• recall — structured recall for a query: returns matching memories with "
        "full metadata and per-memory match score.\n"
        "• about — everything known about an entity (person/project), ranked by "
        "importance.\n"
        "• stats — graph size and namespace counters."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["recall", "about", "stats"],
                "description": "What to inspect.",
            },
            "query": {"type": "string", "description": "Natural-language query (for 'recall')."},
            "entity": {"type": "string", "description": "Entity name (for 'about')."},
            "limit": {"type": "integer", "description": "Max memories to return."},
        },
        "required": ["action"],
    },
}


def _hermes_home() -> Path:
    """Profile-aware Hermes home (respects profile overrides)."""
    try:
        from hermes_constants import get_hermes_home

        return get_hermes_home()
    except Exception:
        return Path.home() / ".hermes"


def _load_plugin_config() -> dict:
    """Load config from the native ``cortext.json`` file, with config.yaml fallback.

    Precedence: ``$HERMES_HOME/cortext.json`` (written by ``save_config``) wins;
    if absent, fall back to the ``memory.cortext`` block of ``config.yaml`` (and
    the legacy ``memory.cortex`` / ``plugins.cortex`` locations).
    """
    home = _hermes_home()

    # 1. Native config file (authoritative; written by hermes memory setup).
    native = home / CONFIG_FILENAME
    if native.exists():
        try:
            import json

            return json.loads(native.read_text(encoding="utf-8")) or {}
        except Exception as e:
            logger.warning("cortext: failed to read %s (%s)", native, e)

    # 2. config.yaml fallback.
    try:
        from hermes_cli.config import cfg_get
        import yaml

        config_path = home / "config.yaml"
        if not config_path.exists():
            return {}
        with open(config_path, encoding="utf-8-sig") as f:
            all_config = yaml.safe_load(f) or {}
        for path in (("memory", "cortext"), ("memory", "cortex"), ("plugins", "cortex")):
            cfg = cfg_get(all_config, *path, default=None)
            if cfg is not None:
                return cfg or {}
    except Exception:
        pass
    return {}


class CortextMemoryProvider(MemoryProvider):
    """Cortext cognitive memory as a Hermes provider."""

    def __init__(self, config: Optional[dict] = None):
        self._config = config or _load_plugin_config()
        self._bridge = None
        self._store_path: Optional[Path] = None
        self._dirty = False
        self._last_injected_tokens = 0  # tokens injected by the most recent prefetch
        self._enc = None
        # Guards every graph read/write/save. Reentrant so a locked caller
        # (e.g. sync_turn) can call _save() which also locks.
        self._lock = threading.RLock()
        self._dream = None                   # DreamAgent instance
        self._dream_thread = None            # background daemon thread
        self._dream_stop = threading.Event() # signals the loop to exit

    def _count_tokens(self, text: str) -> int:
        if not text:
            return 0
        try:
            if self._enc is None:
                import tiktoken

                self._enc = tiktoken.get_encoding("cl100k_base")
            return len(self._enc.encode(text))
        except Exception:
            return len(text) // 4

    @property
    def last_injected_tokens(self) -> int:
        """Tokens injected by the most recent prefetch (for status display)."""
        return self._last_injected_tokens

    @property
    def name(self) -> str:
        return "cortext"

    def is_available(self) -> bool:
        try:
            import cortext  # noqa: F401

            return True
        except Exception:
            logger.warning("cortext provider unavailable: cortext not importable")
            return False

    def get_config_schema(self) -> List[Dict[str, Any]]:
        return [
            {"key": "namespace", "description": "Memory isolation namespace", "default": "hermes"},
            {"key": "max_context_tokens", "description": "Max tokens of context injected per turn", "default": 300},
            {"key": "validation_policy", "description": "Contradiction handling at write time", "choices": ["warn", "block"], "default": "warn"},
            {"key": "use_llm_extractor", "description": "Use LLM for W5H extraction (slower, better)", "default": False},
            {"key": "llm_extractor_model", "description": "Ollama model for LLM W5H extraction (e.g. 'gemma3:4b'). Empty = heuristic only.", "default": ""},
            {"key": "llm_extractor_base_url", "description": "Ollama base URL for the extractor model", "default": "http://localhost:11434"},
            {"key": "expose_inspect_tool", "description": "Expose the cortext_inspect tool for on-demand auditing. Default off.", "default": False},
            {"key": "dream_agent", "description": "Run the DreamAgent in the background (replay, consolidate, prune). On by default.", "default": True},
            {"key": "dream_interval_seconds", "description": "Seconds between background DreamAgent cycles", "default": 1800},
            {"key": "dream_use_llm", "description": "Use an LLM to write info-preserving merged memories during consolidation.", "default": False},
            {"key": "dream_llm_model", "description": "Model for LLM consolidation (OpenAI-compatible). Ollama: 'llama3.1:8b'.", "default": ""},
            {"key": "dream_llm_base_url", "description": "OpenAI-compatible base URL (Ollama: .../v1; OpenRouter: https://openrouter.ai/api/v1)", "default": "http://localhost:11434/v1"},
            {"key": "dream_llm_api_key_env", "description": "Env var name holding the API key (blank for keyless Ollama)", "default": ""},
            {"key": "dream_max_llm_merges", "description": "Max LLM merge calls per cycle (cost/latency budget)", "default": 3},
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        """Persist provider settings to ``$HERMES_HOME/cortext.json`` (atomic)."""
        import json

        config_path = Path(hermes_home) / CONFIG_FILENAME
        existing: dict = {}
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text(encoding="utf-8")) or {}
            except Exception:
                existing = {}
        existing.update(values)
        try:
            from utils import atomic_json_write

            atomic_json_write(config_path, existing, mode=0o600)
        except Exception:
            config_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        # Keep the live config in sync so a re-setup in the same process sees it.
        self._config = existing

    def _build_llm_fn(self):
        """Build an Ollama-backed callable(prompt)->str for W5H extraction.

        Returns None when no model is configured. Uses stdlib urllib (no deps).
        """
        model = str(self._config.get("llm_extractor_model", "")).strip()
        if not model:
            return None
        base_url = str(self._config.get("llm_extractor_base_url", "http://localhost:11434")).rstrip("/")

        def _llm_fn(prompt: str) -> str:
            import json
            import urllib.request

            payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
            req = urllib.request.Request(
                f"{base_url}/api/generate", data=payload, headers={"Content-Type": "application/json"}
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "") or ""
            except Exception as e:
                logger.debug("cortext llm_fn (%s) failed: %s", model, e)
                return ""

        return _llm_fn

    def initialize(self, session_id: str, **kwargs) -> None:
        from cortext.integration import AgentMemoryBridge
        from cortext.core.graph import MemoryGraph
        from cortext.core.validation import ValidationPolicy

        # MemoryManager injects a profile-aware hermes_home; fall back to the
        # profile-aware helper (never a bare Path.home()) if it is ever absent.
        hermes_home = Path(kwargs.get("hermes_home") or _hermes_home())
        namespace = self._config.get("namespace", "hermes")
        self._store_path = hermes_home / f"cortext_{namespace}.json"

        policy = (
            ValidationPolicy.BLOCK
            if str(self._config.get("validation_policy", "warn")).lower() == "block"
            else ValidationPolicy.WARN
        )

        self._bridge = AgentMemoryBridge(
            namespace=namespace,
            validation_policy=policy,
            use_llm_extractor=bool(self._config.get("use_llm_extractor", False)),
            max_context_tokens=int(self._config.get("max_context_tokens", 300)),
        )

        if self._config.get("use_llm_extractor", False):
            llm_fn = self._build_llm_fn()
            if llm_fn is not None:
                from cortext.core.recall.text_extractor import default_extractor

                self._bridge.text_extractor = default_extractor(llm_fn=llm_fn)
                logger.info("cortext: LLM extractor active (model=%s)", self._config.get("llm_extractor_model"))
            else:
                logger.warning("cortext: use_llm_extractor=true but no llm_extractor_model set; using heuristic")

        # Load persisted graph if present.
        try:
            with self._lock:
                self._bridge.cortex.graph = MemoryGraph.load(self._store_path, namespace=namespace)
            logger.info("cortext: loaded %d memories from %s", len(self._bridge.cortex.graph), self._store_path)
        except Exception as e:
            logger.warning("cortext: failed to load store (%s); starting empty", e)

        self._maybe_start_dream_agent()

    def _build_dream_llm_fn(self):
        """Build an OpenAI-compatible callable(prompt)->str for LLM consolidation."""
        if not self._config.get("dream_use_llm", False):
            return None
        model = str(self._config.get("dream_llm_model", "")).strip()
        if not model:
            logger.warning("cortext: dream_use_llm=true but no dream_llm_model set")
            return None
        base_url = str(self._config.get("dream_llm_base_url", "http://localhost:11434/v1")).rstrip("/")
        import os

        key_env = str(self._config.get("dream_llm_api_key_env", "")).strip()
        api_key = os.environ.get(key_env, "") if key_env else ""

        def _llm_fn(prompt: str) -> str:
            import json
            import urllib.request

            body = json.dumps(
                {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                }
            ).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            req = urllib.request.Request(f"{base_url}/chat/completions", data=body, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"] or ""
            except Exception as e:
                logger.debug("cortext dream llm_fn (%s) failed: %s", model, e)
                return ""

        return _llm_fn

    def _maybe_start_dream_agent(self) -> None:
        if not self._config.get("dream_agent", True):
            return
        from cortext.workers.dream_agent import DreamAgent

        dream_llm = self._build_dream_llm_fn()
        self._dream = DreamAgent(llm_fn=dream_llm, max_llm_merges=int(self._config.get("dream_max_llm_merges", 3)))
        if dream_llm is not None:
            logger.info("cortext: DreamAgent LLM consolidation ON (model=%s)", self._config.get("dream_llm_model"))
        self._dream_stop.clear()
        interval = max(60, int(self._config.get("dream_interval_seconds", 1800)))

        def _loop() -> None:
            # Wait first so we don't consolidate immediately at startup.
            while not self._dream_stop.wait(interval):
                try:
                    with self._lock:
                        result = self._dream.run_cycle(self._bridge.cortex.graph)
                        self._dirty = True
                        self._save()
                    logger.info(
                        "cortext dream cycle: replayed=%d consolidated=%d cleaned=%d (%.0fms)",
                        result.n_replayed, result.n_consolidated, result.n_cleaned, result.duration_ms,
                    )
                except Exception as e:
                    logger.debug("cortext dream cycle failed: %s", e)

        self._dream_thread = threading.Thread(target=_loop, name="cortext-dream-agent", daemon=True)
        self._dream_thread.start()
        logger.info("cortext: DreamAgent started (every %ds)", interval)

    def system_prompt_block(self) -> str:
        return (
            "## Cortext Memory\n"
            "Your long-term memory is managed automatically by Cortext:\n"
            "- Relevant past memories are recalled and injected as context each "
            "turn (look for a 'Cortext Memory (recalled)' block).\n"
            "- Every turn of this conversation is persisted automatically after "
            "you reply — you do not need to take any action to save it.\n"
            "Just answer normally; storage and recall happen for you."
        )

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self._bridge or not query:
            self._last_injected_tokens = 0
            return ""
        try:
            with self._lock:
                context = self._bridge.pre_chat(query)
            if not context:
                self._last_injected_tokens = 0
                return ""
            block = "## Cortext Memory (recalled)\n" + context
            self._last_injected_tokens = self._count_tokens(block)
            return block
        except Exception as e:
            logger.debug("cortext prefetch failed: %s", e)
            self._last_injected_tokens = 0
            return ""

    def sync_turn(
        self,
        user_content: str,
        assistant_content: str,
        *,
        session_id: str = "",
        messages: Any = None,
    ) -> None:
        if not self._bridge or not user_content:
            return
        try:
            with self._lock:
                self._bridge.post_chat(
                    user_message=user_content,
                    assistant_message=assistant_content or "",
                )
                self._dirty = True
                self._save()
        except Exception as e:
            logger.debug("cortext sync_turn failed: %s", e)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        # Opt-in: only expose the inspect tool when explicitly enabled.
        if not self._config.get("expose_inspect_tool", False):
            return []
        return [CORTEXT_INSPECT_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        import json

        if tool_name != "cortext_inspect" or not self._bridge:
            return json.dumps({"error": f"unknown tool: {tool_name}"})
        action = (args.get("action") or "recall").lower()
        try:
            with self._lock:
                if action == "recall":
                    query = args.get("query", "")
                    if not query:
                        return json.dumps({"error": "query is required for action 'recall'"})
                    result = self._bridge.inspect(query, max_results=int(args.get("limit", 5)))
                elif action == "about":
                    entity = args.get("entity", "")
                    if not entity:
                        return json.dumps({"error": "entity is required for action 'about'"})
                    result = self._bridge.about(entity, max_results=int(args.get("limit", 20)))
                elif action == "stats":
                    result = self._bridge.stats()
                else:
                    return json.dumps({"error": f"unknown action: {action}"})
            return json.dumps(result, ensure_ascii=False, default=str)
        except Exception as e:
            logger.debug("cortext_inspect failed: %s", e)
            return json.dumps({"error": str(e)})

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        with self._lock:
            self._save()

    def shutdown(self) -> None:
        # Stop the DreamAgent loop before the final save.
        self._dream_stop.set()
        if self._dream_thread is not None:
            self._dream_thread.join(timeout=2)
            self._dream_thread = None
        with self._lock:
            self._save()
        self._bridge = None

    def _save(self) -> None:
        """Persist the graph. Acquires _lock (reentrant) so every call site is
        synchronized against the DreamAgent thread and sync_turn."""
        with self._lock:
            if not self._bridge or not self._store_path or not self._dirty:
                return
            try:
                self._bridge.cortex.graph.save(self._store_path)
                self._dirty = False
            except Exception as e:
                logger.debug("cortext save failed: %s", e)


def register(ctx) -> None:
    """Register the Cortext memory provider with the plugin system."""
    provider = CortextMemoryProvider(config=_load_plugin_config())
    ctx.register_memory_provider(provider)
