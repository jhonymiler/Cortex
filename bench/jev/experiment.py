"""
Jev (TypeSafe System One) as Cortext's judge — an experiment.

    python bench/jev/experiment.py            # needs JEV_API_KEY (env or .env)

Task 1 — relation between a new memory and existing ones
  (same / contradicts / refines / unrelated), per language condition:
  pt-pt, en-en, es-es, and cross-language pt->en, es->pt. "batch" mode asks
  about 4 candidates in one request (one call per write, the intended design);
  "pair" mode asks one pair per request (pt-pt only), to see if batching hurts.
Task 2 — is an agent prompt a durable fact worth storing?

Baselines: Cortext's current heuristics on the same inputs.
Writes bench/jev/results/<timestamp>.json and prints a report.
"""

from __future__ import annotations

import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

from dataset import DURABLE, RELATION  # noqa: E402

URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
LABELS = ["same", "contradicts", "refines", "unrelated"]
CONDITIONS = [("pt", "pt"), ("en", "en"), ("es", "es"), ("pt", "en"), ("es", "pt")]
PRICE_PER_INPUT_TOKEN = 0.042 / 1_000_000  # USD, output is free (docs.typesafe.ai/models)

RELATION_CRITERIA = {
    "same": "States the same fact as new_memory, possibly paraphrased or in another language.",
    "contradicts": "Cannot be true at the same time as new_memory (a different value, the opposite, or a change that replaces it).",
    "refines": "Agrees with new_memory and adds detail, a condition or an outcome.",
    "unrelated": "About a different topic or attribute, even if it involves the same person or thing.",
}


def api_key() -> str:
    for name in ("JEV_API_KEY", "TYPESAFE_API_KEY"):
        if os.environ.get(name):
            return os.environ[name]
    env = HERE.parent.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip() in ("JEV_API_KEY", "TYPESAFE_API_KEY") and v.strip():
                return v.strip().strip('"').strip("'")
    raise SystemExit("JEV_API_KEY not set (env or .env)")


KEY = api_key()


def call(state, questions, retries: int = 5) -> tuple[dict, float]:
    body = json.dumps({"model": MODEL, "state": state, "questions": questions}).encode()
    for attempt in range(retries):
        req = urllib.request.Request(URL, data=body, headers={
            "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            return data, (time.perf_counter() - t0) * 1000
        except urllib.error.HTTPError as e:
            if e.code in (429, 529, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read()[:300]!r}") from e
    raise RuntimeError("unreachable")


def relation_question(key: str) -> dict:
    return {
        "type": "choice",
        "instructions": f"How does existing_memories.{key} relate to new_memory?",
        "criteria": RELATION_CRITERIA,
    }


# --- Cortext baseline (CanonicalValidator's heuristics, applied pairwise) ---------

def baseline_relation(who: list[str], new: str, old: str) -> str:
    """CanonicalValidator's rules: Jaccard >= 0.85 -> same; >= 0.3 with one-sided
    negation -> contradicts; otherwise unrelated (it has no notion of refines)."""
    from cortext.core.validation.canonical import _has_negation, _tokenize

    a, b = _tokenize(new), _tokenize(old)
    sim = len(a & b) / len(a | b) if a and b else 0.0
    if sim >= 0.85:
        return "same"
    neg = _has_negation(new) != _has_negation(old)
    if sim >= 0.3 and neg:
        return "contradicts"
    return "unrelated"


def baseline_durable(text: str) -> bool:
    from cortext.server.engine import _TRIVIAL

    t = text.strip()
    return not (len(t) < 12 or t.startswith("/") or _TRIVIAL.match(t))


# --- task builders --------------------------------------------------------------------

def relation_jobs(rng: random.Random) -> list[dict]:
    jobs = []
    for si, sc in enumerate(RELATION):
        for la, lb in CONDITIONS:
            labels = LABELS[:]
            rng.shuffle(labels)
            existing = {f"m{i + 1}": {"who": sc["who"], "what": sc[lab][lb]} for i, lab in enumerate(labels)}
            jobs.append({
                "mode": "batch", "cond": f"{la}-{lb}", "scenario": si,
                "state": {"new_memory": {"who": sc["who"], "what": sc["anchor"][la]}, "existing_memories": existing},
                "questions": {f"rel_{k}": relation_question(k) for k in existing},
                "gold": {f"rel_{k}": lab for k, lab in zip(existing, labels)},
                "texts": {f"rel_{k}": (sc["anchor"][la], v["what"]) for k, v in existing.items()},
                "who": sc["who"],
            })
        for lab in LABELS:  # pair mode, pt-pt
            jobs.append({
                "mode": "pair", "cond": "pt-pt", "scenario": si,
                "state": {"new_memory": {"who": sc["who"], "what": sc["anchor"]["pt"]},
                          "existing_memories": {"m1": {"who": sc["who"], "what": sc[lab]["pt"]}}},
                "questions": {"rel_m1": relation_question("m1")},
                "gold": {"rel_m1": lab},
                "texts": {"rel_m1": (sc["anchor"]["pt"], sc[lab]["pt"])},
                "who": sc["who"],
            })
    return jobs


def durable_jobs() -> list[dict]:
    jobs = []
    for i, (text, lang, gold) in enumerate(DURABLE):
        jobs.append({
            "mode": "durable", "cond": lang, "item": i, "gold": gold, "text": text,
            "state": {"agent_prompt": text},
            "questions": {
                "durable": {
                    "type": "noul",
                    "instructions": "Does agent_prompt state a durable fact, decision, convention, preference or "
                                    "constraint worth remembering in long-term memory for future sessions?",
                    "criteria": {
                        "true": "A lasting fact about the project, team, customer, student or user that will matter later.",
                        "false": "A one-off command, a generic question, an acknowledgement or small talk.",
                    },
                },
                "importance": {
                    "type": "score",
                    "instructions": "How important is agent_prompt to remember for future work?",
                    "criteria": ["not worth storing", "minor", "useful", "important", "critical"],
                },
            },
        })
    return jobs


# --- run & report -----------------------------------------------------------------------

def run_job(job: dict) -> dict:
    try:
        resp, ms = call(job["state"], job["questions"])
        return {**job, "resp": resp, "ms": ms}
    except Exception as e:  # keep going; report failures
        return {**job, "error": str(e)}


def macro_f1(pairs: list[tuple[str, str]]) -> float:
    f1s = []
    for lab in LABELS:
        tp = sum(1 for g, p in pairs if g == lab and p == lab)
        fp = sum(1 for g, p in pairs if g != lab and p == lab)
        fn = sum(1 for g, p in pairs if g == lab and p != lab)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(f1s) / len(f1s)


def main() -> None:
    rng = random.Random(42)
    jobs = relation_jobs(rng) + durable_jobs()
    print(f"{len(jobs)} requests to {MODEL} ...", flush=True)
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(run_job, jobs))
    wall = time.perf_counter() - t0

    errors = [r for r in results if "error" in r]
    ok = [r for r in results if "resp" in r]
    model = ok[0]["resp"].get("model") if ok else "?"
    tokens = sum(r["resp"].get("usage", {}).get("input_tokens", 0) for r in ok)
    lat = sorted(r["ms"] for r in ok)

    rel_rows = []  # (mode, cond, gold, pred, conf, baseline)
    for r in ok:
        if r["mode"] in ("batch", "pair"):
            for q, gold in r["gold"].items():
                a = r["resp"]["answers"][q]
                new, old = r["texts"][q]
                rel_rows.append({
                    "mode": r["mode"], "cond": r["cond"], "gold": gold, "pred": a.get("choice"),
                    "conf": a.get("confidence"), "probs": a.get("probabilities"),
                    "baseline": baseline_relation(r["who"], new, old), "new": new, "old": old,
                })
    dur_rows = []
    for r in ok:
        if r["mode"] == "durable":
            a = r["resp"]["answers"]
            dur_rows.append({
                "lang": r["cond"], "text": r["text"], "gold": r["gold"],
                "p_durable": a["durable"].get("noul"), "importance": a["importance"].get("score"),
                "imp_conf": a["importance"].get("confidence"), "baseline": baseline_durable(r["text"]),
            })

    print(f"\nmodel {model} · {len(ok)} ok, {len(errors)} errors · wall {wall:.1f}s · "
          f"latency p50 {lat[len(lat)//2]:.0f} ms p95 {lat[int(len(lat)*.95)]:.0f} ms · "
          f"{tokens} input tokens ≈ ${tokens * PRICE_PER_INPUT_TOKEN:.4f}")
    for e in errors[:3]:
        print("  error:", e["error"][:200])

    print("\nTASK 1 — relation (accuracy / macro-F1)        Jev            Cortext heuristic")
    groups = defaultdict(list)
    for row in rel_rows:
        groups[(row["mode"], row["cond"])].append(row)
    for (mode, cond), rows in sorted(groups.items(), key=lambda x: (x[0][0] != "batch", x[0][1])):
        acc = sum(r["gold"] == r["pred"] for r in rows) / len(rows)
        bacc = sum(r["gold"] == r["baseline"] for r in rows) / len(rows)
        print(f"  {mode:<6}{cond:<7} n={len(rows):<4} {acc:6.1%} / {macro_f1([(r['gold'], r['pred']) for r in rows]):.2f}"
              f"      {bacc:6.1%} / {macro_f1([(r['gold'], r['baseline']) for r in rows]):.2f}")

    batch = [r for r in rel_rows if r["mode"] == "batch"]
    print("\n  per class, batch mode (recall: Jev | heuristic)")
    for lab in LABELS:
        rows = [r for r in batch if r["gold"] == lab]
        print(f"    {lab:<12} {sum(r['pred'] == lab for r in rows) / len(rows):6.1%} | "
              f"{sum(r['baseline'] == lab for r in rows) / len(rows):6.1%}")
    cm = Counter((r["gold"], r["pred"]) for r in batch)
    print("\n  confusion (rows = gold, cols = Jev):  " + "  ".join(f"{lab[:5]:>6}" for lab in LABELS))
    for g in LABELS:
        print(f"    {g:<12}" + "".join(f"{cm[(g, p)]:>8}" for p in LABELS))

    print("\n  calibration (batch): confidence bucket → share of judgments, accuracy")
    for lo, hi in ((0.9, 1.01), (0.7, 0.9), (0.0, 0.7)):
        rows = [r for r in batch if r["conf"] is not None and lo <= r["conf"] < hi]
        if rows:
            print(f"    [{lo:.1f}, {min(hi, 1):.1f})  {len(rows) / len(batch):6.1%} of judgments  "
                  f"accuracy {sum(r['gold'] == r['pred'] for r in rows) / len(rows):6.1%}")

    print("\nTASK 2 — durable fact? (threshold 0.5)")
    for lang in ("pt", "en", "es", "all"):
        rows = [r for r in dur_rows if lang == "all" or r["lang"] == lang]
        acc = sum((r["p_durable"] >= 0.5) == r["gold"] for r in rows) / len(rows)
        bacc = sum(r["baseline"] == r["gold"] for r in rows) / len(rows)
        print(f"  {lang:<4} n={len(rows):<3} Jev {acc:6.1%}   heuristic {bacc:6.1%}")
    imp_d = [r["importance"] for r in dur_rows if r["gold"] and r["importance"] is not None]
    imp_n = [r["importance"] for r in dur_rows if not r["gold"] and r["importance"] is not None]
    if imp_d and imp_n:
        print(f"  importance score: durable avg {sum(imp_d) / len(imp_d):.2f} vs noise avg {sum(imp_n) / len(imp_n):.2f}")

    wrong = [r for r in batch if r["gold"] != r["pred"]]
    print(f"\n  sample of Jev errors ({len(wrong)} total, batch):")
    for r in wrong[:12]:
        print(f"    [{r['cond']}] gold={r['gold']:<11} jev={r['pred']:<11} conf={r['conf']:.2f}  "
              f"{r['new'][:45]!r} vs {r['old'][:45]!r}")
    for r in dur_rows:
        if (r["p_durable"] >= 0.5) != r["gold"]:
            print(f"    durable miss: gold={r['gold']} p={r['p_durable']:.2f} {r['text']!r}")

    out = HERE / "results" / f"jev_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "model": model, "requests": len(jobs), "errors": [e["error"] for e in errors],
        "wall_s": wall, "latency_ms": lat, "input_tokens": tokens,
        "relation": rel_rows, "durable": dur_rows,
    }, ensure_ascii=False, indent=1))
    print(f"\nsaved {out.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
