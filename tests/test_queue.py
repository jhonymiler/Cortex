"""JobQueue state machine: pending → leased → done | retry | failed, lease expiry."""

import sqlite3
import threading
import time

from cortext.server.queue import JobQueue


def make(max_attempts=3):
    return JobQueue(sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False), threading.Lock(), max_attempts)


def test_lease_complete_cycle():
    q = make()
    jid = q.enqueue("p", "abstract", {"turn": 1})
    job = q.lease("w1")
    assert job["id"] == jid and job["payload"] == {"turn": 1} and job["attempt"] == 1
    assert q.lease("w2") is None  # leased jobs are not handed out twice
    assert q.complete(jid, {"facts": 2})
    assert q.get(jid)["state"] == "done" and q.get(jid)["result"] == {"facts": 2}
    assert q.stats() == {"pending": 0, "leased": 0, "done": 1, "failed": 0}


def test_fifo_and_kind_filter():
    q = make()
    a = q.enqueue("p", "abstract", {})
    b = q.enqueue("p", "judge", {})
    assert q.lease("w", kinds=["judge"])["id"] == b
    assert q.lease("w")["id"] == a


def test_retry_then_failed():
    q = make(max_attempts=2)
    jid = q.enqueue("p", "abstract", {})
    q.lease("w")
    assert q.fail(jid, "model busy") == "pending"
    assert q.lease("w")["attempt"] == 2
    assert q.fail(jid, "model busy again") == "failed"
    assert q.lease("w") is None
    assert q.get(jid)["error"] == "model busy again"


def test_expired_lease_returns_to_pending():
    q = make()
    jid = q.enqueue("p", "abstract", {})
    q.lease("w-dead", seconds=0.01)
    time.sleep(0.03)
    job = q.lease("w-alive")
    assert job["id"] == jid and job["attempt"] == 2
    assert not q.complete(999, {})  # unknown job


def test_complete_requires_lease():
    q = make()
    jid = q.enqueue("p", "abstract", {})
    assert not q.complete(jid, {})  # still pending
