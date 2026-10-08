"""
JobQueue — the background work queue, as an explicit state machine in SQLite.

    pending ──lease──▶ leased ──complete──▶ done
       ▲                 │
       └──fail/expire────┤  (attempts < max_attempts)
                         └──fail──▶ failed      (attempts exhausted)

Workers lease a job for a bounded time; a lease that expires (the worker's
session closed, the process died) returns the job to `pending` on the next
lease call, so no job is lost and none is processed twice concurrently.

Jobs live in the same SQLite file as the memories, so the queue survives
restarts. The daemon decides *what* a job means (it builds the prompt and
applies the answer); a worker only turns a prompt into text — the user's own
Haiku inside the Claude Code mod, a `claude -p` process, or any LLM endpoint.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from typing import Any, Optional

STATES = ("pending", "leased", "done", "failed")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ns TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    lease_until REAL,
    worker TEXT,
    error TEXT,
    result TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state, id);
"""


class JobQueue:
    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock, max_attempts: int = 3) -> None:
        self._c = conn
        self._lock = lock
        self.max_attempts = max_attempts
        with self._lock:
            self._c.executescript(_SCHEMA)

    def enqueue(self, ns: str, kind: str, payload: dict[str, Any]) -> int:
        now = time.time()
        with self._lock:
            cur = self._c.execute(
                "INSERT INTO jobs(ns, kind, payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (ns, kind, json.dumps(payload, ensure_ascii=False), now, now),
            )
            return int(cur.lastrowid)

    def lease(self, worker: str, kinds: Optional[list[str]] = None, seconds: float = 120.0) -> Optional[dict[str, Any]]:
        """Take the oldest pending job (expired leases count as pending)."""
        now = time.time()
        with self._lock:
            c = self._c
            c.execute("BEGIN IMMEDIATE")
            try:
                c.execute(
                    "UPDATE jobs SET state='pending', worker=NULL, updated_at=? "
                    "WHERE state='leased' AND lease_until < ?", (now, now))
                q = "SELECT id, ns, kind, payload, attempts FROM jobs WHERE state='pending'"
                args: list[Any] = []
                if kinds:
                    q += f" AND kind IN ({','.join('?' * len(kinds))})"
                    args += kinds
                row = c.execute(q + " ORDER BY id LIMIT 1", args).fetchone()
                if row is None:
                    c.execute("COMMIT")
                    return None
                c.execute(
                    "UPDATE jobs SET state='leased', worker=?, lease_until=?, attempts=attempts+1, updated_at=? "
                    "WHERE id=?", (worker, now + seconds, now, row[0]))
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise
        return {"id": row[0], "ns": row[1], "kind": row[2], "payload": json.loads(row[3]), "attempt": row[4] + 1}

    def complete(self, job_id: int, result: Optional[dict[str, Any]] = None) -> bool:
        with self._lock:
            cur = self._c.execute(
                "UPDATE jobs SET state='done', result=?, lease_until=NULL, updated_at=? WHERE id=? AND state='leased'",
                (json.dumps(result or {}, ensure_ascii=False), time.time(), job_id))
            return cur.rowcount == 1

    def fail(self, job_id: int, error: str) -> str:
        """Record a failure; the job retries until max_attempts, then is `failed`."""
        with self._lock:
            row = self._c.execute("SELECT attempts FROM jobs WHERE id=? AND state='leased'", (job_id,)).fetchone()
            if row is None:
                return "unknown"
            state = "failed" if row[0] >= self.max_attempts else "pending"
            self._c.execute(
                "UPDATE jobs SET state=?, error=?, worker=NULL, lease_until=NULL, updated_at=? WHERE id=?",
                (state, error[:500], time.time(), job_id))
            return state

    def get(self, job_id: int) -> Optional[dict[str, Any]]:
        with self._lock:
            row = self._c.execute(
                "SELECT id, ns, kind, state, attempts, error, result FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        return {"id": row[0], "ns": row[1], "kind": row[2], "state": row[3], "attempts": row[4],
                "error": row[5], "result": json.loads(row[6]) if row[6] else None}

    def stats(self, ns: Optional[str] = None) -> dict[str, int]:
        q = "SELECT state, COUNT(*) FROM jobs" + (" WHERE ns=?" if ns else "") + " GROUP BY state"
        with self._lock:
            rows = self._c.execute(q, (ns,) if ns else ()).fetchall()
        out = dict.fromkeys(STATES, 0)
        out.update({s: n for s, n in rows})
        return out

    def prune(self, older_than_s: float = 7 * 86400) -> int:
        """Drop finished jobs older than the horizon (the memories they made stay)."""
        with self._lock:
            cur = self._c.execute(
                "DELETE FROM jobs WHERE state IN ('done','failed') AND updated_at < ?", (time.time() - older_than_s,))
            return cur.rowcount
