"""
Persistence backends for a MemoryGraph.

  SQLiteStore — incremental (only what changed is written), WAL mode, many
                namespaces in one file. The default for anything long-lived.
  JsonStore   — one JSON snapshot per namespace, rewritten on flush. Kept for
                compatibility with files written by MemoryGraph.save().

``open_store(path)`` picks one from the file suffix.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from cortext.store.sqlite import SQLiteStore
from cortext.store.json_store import JsonStore


class Store(Protocol):
    def load(self, namespace: str) -> Any: ...
    def flush(self, graph: Any) -> int: ...
    def namespaces(self) -> list[str]: ...
    def close(self) -> None: ...


def open_store(path: Any) -> "Store":
    """Open a store for ``path``: ``.json`` -> JsonStore, anything else -> SQLite."""
    p = Path(path).expanduser()
    if p.suffix.lower() == ".json":
        return JsonStore(p)
    return SQLiteStore(p)


__all__ = ["Store", "SQLiteStore", "JsonStore", "open_store"]
