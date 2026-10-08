"""
SQLiteStore — incremental, crash-safe persistence for MemoryGraph.

Each flush writes only the memories, entities and relations that changed
since the previous flush (``MemoryGraph.drain_all_changes``), in one
transaction. WAL journaling with ``synchronous=NORMAL`` makes a commit an
append to the log with no fsync, so a write costs tens of microseconds, and
readers in other processes are never blocked by the writer.

Rows hold the object's JSON (the same shape as ``to_dict``), keyed by
(namespace, id): the schema never changes when a field is added to Memory.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    ns TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
    PRIMARY KEY (ns, id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS entities (
    ns TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
    PRIMARY KEY (ns, id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS relations (
    ns TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
    PRIMARY KEY (ns, id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY, value TEXT
);
"""

_DUMP = json.JSONEncoder(ensure_ascii=False, default=str, separators=(",", ":")).encode


class SQLiteStore:
    """Incremental SQLite persistence; one file holds every namespace."""

    def __init__(self, path: Any) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None, timeout=10)
        self._lock = threading.Lock()
        c = self._conn
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA temp_store=MEMORY")
        c.execute("PRAGMA mmap_size=268435456")
        c.executescript(_SCHEMA)
        c.execute("INSERT OR IGNORE INTO meta(key, value) VALUES ('schema', '1')")

    def load(self, namespace: str):
        """Build a MemoryGraph for ``namespace`` from the rows on disk."""
        from cortext.core.entity import Entity
        from cortext.core.graph import MemoryGraph
        from cortext.core.memory import Memory
        from cortext.core.relation import Relation

        graph = MemoryGraph(namespace=namespace)
        loads = json.loads
        with self._lock:
            mem_rows = self._conn.execute("SELECT data FROM memories WHERE ns=?", (namespace,)).fetchall()
            ent_rows = self._conn.execute("SELECT data FROM entities WHERE ns=?", (namespace,)).fetchall()
            rel_rows = self._conn.execute("SELECT data FROM relations WHERE ns=?", (namespace,)).fetchall()
        for (data,) in mem_rows:
            graph.add_memory(Memory.from_dict(loads(data)))
        for (data,) in ent_rows:
            graph.add_entity(Entity.from_dict(loads(data)))
        for (data,) in rel_rows:
            graph.add_relation(Relation.from_dict(loads(data)))
        graph.drain_all_changes()  # what was just loaded is not a change
        return graph

    def flush(self, graph) -> int:
        """Write what changed in ``graph`` since the last flush. Returns rows written."""
        ch = graph.drain_all_changes()
        ns = graph.namespace
        writes = 0
        with self._lock:
            c = self._conn
            c.execute("BEGIN")
            try:
                for table, up, rm in (
                    ("memories", ch["memories"], ch["deleted_memories"]),
                    ("entities", ch["entities"], ch["deleted_entities"]),
                    ("relations", ch["relations"], ch["deleted_relations"]),
                ):
                    if up:
                        c.executemany(
                            f"INSERT OR REPLACE INTO {table}(ns, id, data) VALUES (?, ?, ?)",
                            [(ns, o.id, _DUMP(o.to_dict())) for o in up],
                        )
                    if rm:
                        c.executemany(f"DELETE FROM {table} WHERE ns=? AND id=?", [(ns, i) for i in rm])
                    writes += len(up) + len(rm)
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise
        return writes

    def namespaces(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute("SELECT DISTINCT ns FROM memories ORDER BY ns").fetchall()
        return [r[0] for r in rows]

    def drop_namespace(self, namespace: str) -> None:
        with self._lock:
            for table in ("memories", "entities", "relations"):
                self._conn.execute(f"DELETE FROM {table} WHERE ns=?", (namespace,))

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.execute("PRAGMA optimize")
            finally:
                self._conn.close()

    def __repr__(self) -> str:
        return f"SQLiteStore({str(self.path)!r})"
