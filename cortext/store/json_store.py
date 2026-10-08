"""JsonStore — the original one-file-per-namespace JSON snapshot."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class JsonStore:
    """Snapshot persistence: ``flush`` rewrites the whole file when anything changed.

    ``path`` is the file for a single namespace (the format MemoryGraph.save
    writes). Prefer SQLiteStore for anything that writes often.
    """

    def __init__(self, path: Any) -> None:
        self.path = Path(path).expanduser()

    def load(self, namespace: str):
        from cortext.core.graph import MemoryGraph

        graph = MemoryGraph.load(self.path, namespace=namespace)
        graph.namespace = namespace
        return graph

    def flush(self, graph) -> int:
        if not (graph._dirty or graph._deleted or graph._other_changes):
            return 0
        graph.save(self.path)
        graph.drain_all_changes()
        return len(graph)

    def namespaces(self) -> list[str]:
        return []

    def close(self) -> None:
        pass
