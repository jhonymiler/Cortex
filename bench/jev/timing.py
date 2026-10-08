"""
Round 4: WHEN to abstract memories, and whether Jev is needed to consolidate them.

    python bench/jev/timing.py      # needs LLM_BASE_URL, LLM_API_KEY, JEV_API_KEY

Extraction (the user's Haiku, as the background queue would run it):
  S1 per-turn       — each turn alone
  S2 turn+context   — each turn, seeing the session's memories so far; returns add/update/remove
  S3 window-4       — every 4 turns
  S4 session        — once, at the end

Consolidation of S1/S3 output (S2 consolidates itself, S4 is a single pass):
  raw        — nothing
  heuristic  — Cortext's CanonicalValidator rules
  haiku      — one Haiku call merges the session's facts (no Jev)
  jev        — Jev judges each new fact against the store (same/refines/contradicts/unrelated)

Evaluated by a third model (Opus) that sees the transcript, the gold facts and
the stale values: gold recall (by trap), stale leaks, useful-memory precision,
duplicates. Neither pipeline judges itself.
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

from experiment import RELATION_CRITERIA, baseline_relation, call  # noqa: E402
from sessions import SESSIONS  # noqa: E402
from system2 import USAGE, llm_json  # noqa: E402

COUNT = {"haiku": 0, "jev": 0}

RULES = (
    "Durable facts: decisions, conventions, constraints, ownership, preferences, causes of problems and their fixes, "
    "facts about customers/students/employees, things the agent discovered that will matter later. "
    "Not durable: one-off commands, acknowledgements, generic questions, transient output. "
    "Write each fact as one self-contained sentence in English, naming who/what it is about."
)


def haiku(prompt: str) -> dict:
    COUNT["haiku"] += 1
    out, _ = llm_json(prompt, max_tokens=1200)
    return out


def fmt_turns(turns) -> str:
    return "\n".join(f"USER: {u}\nAGENT: {a}" for u, a in turns)


# --- extraction strategies --------------------------------------------------------------

def s1_per_turn(sess) -> list[str]:
    facts = []
    for u, a in sess["turns"]:
        out = haiku(f"One turn of an agent session:\n{fmt_turns([(u, a)])}\n\n{RULES}\n"
                    'Return 0 to 3: {"facts": ["..."]}')
        facts += [f for f in out.get("facts", []) if isinstance(f, str)]
    return facts


def s2_turn_with_context(sess) -> list[str]:
    store: dict[str, str] = {}
    n = 0
    for u, a in sess["turns"]:
        listing = "\n".join(f"{k}: {v}" for k, v in store.items()) or "(none yet)"
        out = haiku(
            f"Memories stored so far in this session:\n{listing}\n\nNew turn:\n{fmt_turns([(u, a)])}\n\n{RULES}\n"
            "Update the memory: add new durable facts; if the turn changes or completes a stored memory, update it "
            "(keep every detail, newest value wins); remove a memory only if the turn says it is no longer true.\n"
            '{"add": ["..."], "update": [{"id": "m1", "what": "..."}], "remove": ["m2"]}'
        )
        for f in out.get("add", []) or []:
            if isinstance(f, str) and f.strip():
                n += 1
                store[f"m{n}"] = f
        for upd in out.get("update", []) or []:
            if isinstance(upd, dict) and upd.get("id") in store and upd.get("what"):
                store[upd["id"]] = upd["what"]
        for rid in out.get("remove", []) or []:
            store.pop(rid, None)
    return list(store.values())


def s3_window(sess, size: int = 4) -> list[str]:
    facts = []
    turns = sess["turns"]
    for i in range(0, len(turns), size):
        out = haiku(f"Part of an agent session:\n{fmt_turns(turns[i:i + size])}\n\n{RULES}\n"
                    "If a later turn changes something said earlier, keep only the final value.\n"
                    'Return 0 to 5: {"facts": ["..."]}')
        facts += [f for f in out.get("facts", []) if isinstance(f, str)]
    return facts


def s4_session(sess) -> list[str]:
    out = haiku(f"A whole agent session:\n{fmt_turns(sess['turns'])}\n\n{RULES}\n"
                "If a later turn changes something said earlier, keep only the final value.\n"
                'Return 0 to 6: {"facts": ["..."]}')
    return [f for f in out.get("facts", []) if isinstance(f, str)]


# --- consolidation -------------------------------------------------------------------------

def c_heuristic(facts: list[str]) -> list[str]:
    store: list[str] = []
    for f in facts:
        rels = [baseline_relation([], f, s) for s in store]
        if "same" in rels:
            continue
        if "contradicts" in rels:
            store[rels.index("contradicts")] = f
            continue
        store.append(f)
    return store


def c_haiku(facts: list[str]) -> list[str]:
    if len(facts) < 2:
        return facts
    listing = "\n".join(f"{i + 1}. {f}" for i, f in enumerate(facts))
    out = haiku(f"Facts extracted from one session, in order (later = newer):\n{listing}\n\n"
                "Produce the final memory: merge duplicates and facts that complete each other into one, "
                "keep every detail, and when two conflict keep only the newer value. Invent nothing.\n"
                '{"memories": ["..."]}')
    return [m for m in out.get("memories", []) if isinstance(m, str)]


def c_jev(facts: list[str]) -> list[str]:
    store: list[str] = []
    for f in facts:
        if not store:
            store.append(f)
            continue
        existing = {f"m{i + 1}": s for i, s in enumerate(store)}
        COUNT["jev"] += 1
        resp, _ = call({"new_memory": f, "existing_memories": existing}, {
            f"rel_{k}": {"type": "choice", "instructions": f"How does existing_memories.{k} relate to new_memory?",
                         "criteria": RELATION_CRITERIA} for k in existing})
        rels = [(int(k[5:]) - 1, a["choice"]) for k, a in resp["answers"].items()]
        same = [i for i, r in rels if r == "same"]
        contra = [i for i, r in rels if r == "contradicts"]
        refines = [i for i, r in rels if r == "refines"]
        if contra:                      # newer value wins
            store[contra[0]] = f
        elif same or refines:           # keep the more detailed wording
            i = (same or refines)[0]
            if len(f) > len(store[i]):
                store[i] = f
        else:
            store.append(f)
    return store


# --- evaluation (Opus) ------------------------------------------------------------------------

def evaluate(sess, memories: list[str]) -> dict:
    gold = [g for _, g in sess["gold"]]
    listing = "\n".join(f"{i}. {m}" for i, m in enumerate(memories)) or "(empty)"
    out, _ = llm_json(
        f"TRANSCRIPT:\n{fmt_turns(sess['turns'])}\n\nGOLD facts a good memory must contain:\n"
        + "\n".join(f"{i}. {g}" for i, g in enumerate(gold))
        + "\n\nSTALE values that must NOT be kept as current:\n"
        + ("\n".join(f"{i}. {s}" for i, s in enumerate(sess["stale"])) or "(none)")
        + f"\n\nMEMORIES produced by the system:\n{listing}\n\n"
        "Grade strictly. gold_captured[i]: is gold i fully stated (all its key details) by one or more memories? "
        "stale_kept[i]: does any memory still state stale value i as current? For each memory: useful = a durable, "
        "faithful fact from the transcript (not noise, not invented); duplicate_of = index of an EARLIER memory "
        "saying the same thing, else null.\n"
        '{"gold_captured": [true], "stale_kept": [false], "memories": [{"useful": true, "duplicate_of": null}]}',
        model="opus", max_tokens=1500,
    )
    return out


def main() -> None:
    t0 = time.perf_counter()

    def run_session(sess):
        ext = {"S1": s1_per_turn(sess), "S2": s2_turn_with_context(sess), "S3": s3_window(sess), "S4": s4_session(sess)}
        variants = {
            "S1 per-turn · raw": ext["S1"],
            "S1 per-turn · heuristic": c_heuristic(ext["S1"]),
            "S1 per-turn · haiku": c_haiku(ext["S1"]),
            "S1 per-turn · jev": c_jev(ext["S1"]),
            "S2 turn+context": ext["S2"],
            "S3 window-4 · raw": ext["S3"],
            "S3 window-4 · haiku": c_haiku(ext["S3"]),
            "S3 window-4 · jev": c_jev(ext["S3"]),
            "S4 session": ext["S4"],
        }
        graded = {name: (mems, evaluate(sess, mems)) for name, mems in variants.items()}
        return sess, graded

    def safe(sess):
        try:
            return run_session(sess)
        except Exception as e:
            print(f"  session {sess['id']} failed ({type(e).__name__}: {e}); re-run to resume from cache")
            return None

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = [r for r in pool.map(safe, SESSIONS) if r is not None]
    if not results:
        raise SystemExit("no session completed (is the LLM endpoint up?)")

    names = list(results[0][1])
    traps = sorted({t for s in SESSIONS for t, _ in s["gold"]})
    api = sorted(USAGE["api_ms"] or [0])
    print(f"{len(SESSIONS)} sessions · haiku calls {COUNT['haiku']} · jev calls {COUNT['jev']} · "
          f"LLM API p50 {api[len(api) // 2] / 1000:.1f}s · notional LLM cost ${USAGE['cost_usd']:.2f} · "
          f"{time.perf_counter() - t0:.0f}s\n")
    head = f"{'variant':<26}{'gold':>7}" + "".join(f"{t[:10]:>11}" for t in traps) + f"{'stale':>7}{'useful':>8}{'dups':>6}{'mems':>6}"
    print(head)
    summary = {}
    for name in names:
        got = tot = stale = stale_tot = useful = mems = dups = 0
        by_trap = {t: [0, 0] for t in traps}
        for sess, graded in results:
            memories, ev = graded[name]
            gc = ev.get("gold_captured", [])
            for j, (trap, _) in enumerate(sess["gold"]):
                ok = bool(gc[j]) if j < len(gc) else False
                got += ok
                tot += 1
                by_trap[trap][0] += ok
                by_trap[trap][1] += 1
            sk = ev.get("stale_kept", [])
            stale += sum(bool(x) for x in sk[: len(sess["stale"])])
            stale_tot += len(sess["stale"])
            ms = ev.get("memories", [])
            mems += len(memories)
            useful += sum(bool(m.get("useful")) for m in ms[: len(memories)] if isinstance(m, dict))
            dups += sum(m.get("duplicate_of") is not None for m in ms[: len(memories)] if isinstance(m, dict))
        summary[name] = {"gold": got / tot, "stale_kept": stale, "useful": useful / max(1, mems), "dups": dups,
                         "memories": mems, "by_trap": {t: v[0] / v[1] for t, v in by_trap.items()}}
        print(f"{name:<26}{got / tot:>7.0%}" + "".join(f"{by_trap[t][0]}/{by_trap[t][1]:<8}".rjust(11) for t in traps)
              + f"{stale}/{stale_tot}".rjust(7) + f"{useful / max(1, mems):>8.0%}{dups:>6}{mems:>6}")

    print("\nexample (dev-pt):")
    for name in ("S1 per-turn · raw", "S2 turn+context", "S4 session"):
        print(f"  {name}:")
        for m in results[0][1][name][0]:
            print(f"    - {m}")

    out = HERE / "results" / f"timing_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps({
        "counts": COUNT, "llm_usage": USAGE, "summary": summary,
        "sessions": [{"id": s["id"], "variants": {n: {"memories": g[0], "eval": g[1]} for n, g in gr.items()}}
                     for s, gr in results],
    }, ensure_ascii=False, indent=1))
    print(f"\nsaved {out.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
