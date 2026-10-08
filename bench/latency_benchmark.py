"""
Latency at scale: validated writes, persisted writes, recall, reload.

    python bench/latency_benchmark.py            # N = 1k, 5k, 20k, 50k
    python bench/latency_benchmark.py 1000 5000  # custom sizes

Synthetic corpus: 300 participants, 10 verbs, 2,000 objects, 5 places — so a
participant owns ~N/300 memories and a common verb appears in ~N/10 of them,
the shape that makes naive recall and validation scan.
"""

from __future__ import annotations

import os
import random
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cortext import CortexV5  # noqa: E402

NAMES = [f"Pessoa{i}" for i in range(300)]
VERBS = ["pediu", "comprou", "reclamou de", "gosta de", "trabalha com", "esqueceu", "enviou", "cancelou", "aprovou", "revisou"]
OBJS = [f"item{i}" for i in range(2000)]
PLACES = ["suporte", "vendas", "infra", "dev", "casa"]


def fact(rng: random.Random) -> dict:
    return {
        "who": [rng.choice(NAMES)],
        "what": f"{rng.choice(VERBS)} {rng.choice(OBJS)} {rng.choice(OBJS)}",
        "where": rng.choice(PLACES),
    }


def run(n: int) -> dict:
    rng = random.Random(n)
    db = os.path.join(tempfile.mkdtemp(), "bench.db")
    c = CortexV5(namespace="bench", path=db, enable_embedding_recall=False)

    t = time.perf_counter()
    for _ in range(n):
        c.remember(**fact(rng))  # validated + persisted (SQLite, synchronous)
    write_ms = (time.perf_counter() - t) / n * 1000

    structural = [f"O que {rng.choice(NAMES)} pediu?" for _ in range(200)]
    free = [f"{rng.choice(OBJS)} {rng.choice(OBJS)}" for _ in range(200)]
    t = time.perf_counter()
    for q in structural:
        c.recall(q)
    rs_ms = (time.perf_counter() - t) / len(structural) * 1000
    t = time.perf_counter()
    for q in free:
        c.recall(q)
    rf_ms = (time.perf_counter() - t) / len(free) * 1000
    c.close()

    t = time.perf_counter()
    c2 = CortexV5(namespace="bench", path=db, enable_embedding_recall=False)
    reload_ms = (time.perf_counter() - t) * 1000
    assert len(c2.graph) == n
    c2.close()
    return {"n": n, "write_ms": write_ms, "recall_structural_ms": rs_ms, "recall_free_ms": rf_ms, "reload_ms": reload_ms}


def main() -> None:
    sizes = [int(a) for a in sys.argv[1:]] or [1_000, 5_000, 20_000, 50_000]
    print(f"{'N':>7}  {'write+persist':>13}  {'recall (who)':>12}  {'recall (text)':>13}  {'reload':>9}")
    for n in sizes:
        r = run(n)
        print(f"{r['n']:>7}  {r['write_ms']:>10.3f} ms  {r['recall_structural_ms']:>9.3f} ms  "
              f"{r['recall_free_ms']:>10.3f} ms  {r['reload_ms']:>6.0f} ms")


if __name__ == "__main__":
    main()
