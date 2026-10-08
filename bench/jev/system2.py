"""
Round 3: a generative "System 2" (Claude Haiku) on top of Jev's "System 1".

    python bench/jev/system2.py     # needs JEV_API_KEY, LLM_BASE_URL, LLM_API_KEY (env or .env)

A. Cascade — Haiku re-judges only the relations Jev answered with confidence
   < 0.9 (from the round 1 and 2 result files); compare cascade vs Jev alone.
B. Consolidation — Haiku merges multilingual clusters into one memory, or
   declares a dispute when they contradict; Jev verifies the merge preserved
   each source's information (System 1 checking System 2).
C. Extraction — Haiku extracts 0–3 durable facts from agent prompts; Jev checks
   each fact is stated or implied by the prompt.

LLM_BASE_URL is any OpenAI-compatible /chat/completions endpoint.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

from adversarial import DURABLE_HARD  # noqa: E402
from dataset import DURABLE, RELATION  # noqa: E402
from experiment import RELATION_CRITERIA, call  # noqa: E402


def _env(name: str) -> str:
    if os.environ.get(name):
        return os.environ[name]
    for line in (HERE.parent.parent / ".env").read_text().splitlines():
        k, _, v = line.partition("=")
        if k.strip() == name:
            return v.strip().strip('"').strip("'")
    raise SystemExit(f"{name} not set")


LLM_MODEL = os.environ.get("LLM_MODEL", "haiku")
# claude-cli (default): each call is an isolated `claude -p` on the user's own
# Claude Code login — what the mod's $.model.complete would use. http: any
# OpenAI-compatible endpoint (LLM_BASE_URL + LLM_API_KEY).
LLM_BACKEND = os.environ.get("LLM_BACKEND", "claude-cli")
LLM_URL = _env("LLM_BASE_URL").rstrip("/") + "/chat/completions" if LLM_BACKEND == "http" else "claude -p"
LLM_KEY = _env("LLM_API_KEY") if LLM_BACKEND == "http" else ""
SYSTEM = ("You are a memory-curation component inside a software system. "
          "Answer with one JSON object only, no prose, no code fences.")
USAGE = {"calls": 0, "api_ms": [], "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
_EMPTY_CWD = __import__("tempfile").mkdtemp(prefix="cortext-llm-")  # no project CLAUDE.md here


_CACHE_FILE = HERE / "results" / "llm_cache.jsonl"
_CACHE: dict[str, dict] = {}
_CACHE_LOCK = __import__("threading").Lock()
if _CACHE_FILE.exists():
    for _line in _CACHE_FILE.read_text().splitlines():
        try:
            _row = json.loads(_line)
            _CACHE[_row["k"]] = _row["v"]
        except (ValueError, KeyError):
            pass


def llm_json(prompt: str, retries: int = 6, model: str | None = None, max_tokens: int = 800) -> tuple[dict, float]:
    """One JSON answer from the LLM. Answers are cached on disk by (model, prompt):
    at temperature 0 a re-run after a dropped tunnel resumes instead of starting over."""
    import hashlib

    key = hashlib.sha256(f"{model or LLM_MODEL}\n{max_tokens}\n{prompt}".encode()).hexdigest()
    if key in _CACHE:
        return _CACHE[key], 0.0
    out, ms = _llm_json_uncached(prompt, retries, model, max_tokens)
    with _CACHE_LOCK:
        _CACHE[key] = out
        with open(_CACHE_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({"k": key, "v": out}, ensure_ascii=False) + "\n")
    return out, ms


def _parse_json_object(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    return json.loads(m.group(0)) if m else {}


def _claude_cli(prompt: str, retries: int, model: str | None) -> tuple[dict, float]:
    import subprocess

    cmd = ["claude", "-p", "--model", model or LLM_MODEL, "--tools", "", "--no-session-persistence",
           "--strict-mcp-config", "--system-prompt", SYSTEM, "--output-format", "json"]
    for attempt in range(retries):
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=_EMPTY_CWD, timeout=300)
        try:
            raw = proc.stdout
            env = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            if env.get("is_error"):
                raise RuntimeError(env.get("result") or "is_error")
            u = env.get("usage", {})
            USAGE["calls"] += 1
            USAGE["api_ms"].append(env.get("duration_api_ms") or env.get("duration_ms") or 0)
            USAGE["cost_usd"] += env.get("total_cost_usd") or 0.0
            USAGE["input_tokens"] += (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) \
                + (u.get("cache_creation_input_tokens") or 0)
            USAGE["output_tokens"] += u.get("output_tokens") or 0
            return _parse_json_object(env.get("result", "")), float(env.get("duration_api_ms") or 0)
        except (ValueError, RuntimeError) as e:
            if attempt == retries - 1:
                raise RuntimeError(f"claude -p failed: {e}; stderr: {proc.stderr[:300]}") from e
            time.sleep(min(60, 3 * 2 ** attempt))
    raise RuntimeError("unreachable")


def _llm_json_uncached(prompt: str, retries: int, model: str | None, max_tokens: int) -> tuple[dict, float]:
    if LLM_BACKEND != "http":
        return _claude_cli(prompt, retries, model)
    body = json.dumps({
        "model": model or LLM_MODEL, "temperature": 0, "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": "You are a memory-curation component inside a software system. "
                                          "Answer with one JSON object only, no prose, no code fences."},
            {"role": "user", "content": prompt},
        ],
    }).encode()
    for attempt in range(retries):
        req = urllib.request.Request(LLM_URL, data=body, headers={
            "Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.loads(r.read())
            text = data["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", text, re.DOTALL)
            return json.loads(m.group(0)) if m else {}, (time.perf_counter() - t0) * 1000
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == retries - 1:
                raise
            time.sleep(min(60, 3 * 2 ** attempt))  # tunnels return 530 when briefly overloaded
    raise RuntimeError("unreachable")


# --- A. cascade -----------------------------------------------------------------------

def relation_prompt(new: str, old: str) -> str:
    crit = "\n".join(f"- {k}: {v}" for k, v in RELATION_CRITERIA.items())
    return (
        "Classify how EXISTING relates to NEW, two memories an agent stored (they may be in different languages).\n"
        f"NEW: {new}\nEXISTING: {old}\n\nLabels:\n{crit}\n\n"
        'Answer: {"relation": "<label>", "reason": "<one short sentence>"}'
    )


def latest(pattern: str) -> dict:
    files = sorted((HERE / "results").glob(pattern))
    if not files:
        raise SystemExit(f"run the earlier rounds first ({pattern})")
    return json.loads(files[-1].read_text())


# --- B. consolidation -------------------------------------------------------------------

def merge_prompt(memories: list[dict]) -> str:
    listing = "\n".join(f"{i + 1}. [{m['lang']}] {m['what']}" for i, m in enumerate(memories))
    return (
        "These memories were stored by different people, possibly in different languages, about the same subject.\n"
        f"{listing}\n\n"
        "If they are compatible (same fact, or one adds detail), merge them into ONE memory in English that keeps "
        "every piece of information from every item and invents nothing:\n"
        '{"action": "merge", "what": "<merged fact>", "who": ["<participants>"]}\n'
        "If any two cannot both be true now, do not merge:\n"
        '{"action": "dispute", "conflict": "<what disagrees>"}'
    )


# --- C. extraction ----------------------------------------------------------------------

def extract_prompt(text: str) -> str:
    return (
        "An agent received this prompt from a user:\n"
        f"PROMPT: {text}\n\n"
        "Extract the durable facts worth keeping in long-term memory for future sessions: decisions, conventions, "
        "constraints, ownership, preferences, facts about customers/students/employees. Ignore one-off commands, "
        "temporary states, generic questions and small talk. Keep each fact in the prompt's language, one sentence. "
        'Return 0 to 3: {"facts": ["..."]}'
    )


def main() -> None:
    t_start = time.perf_counter()
    r1 = latest("jev_2*.json")
    r2 = latest("jev_adversarial_*.json")

    # A: everything Jev was unsure about, plus the whole adversarial set for Haiku-alone accuracy
    r1_batch = [r for r in r1["relation"] if r["mode"] == "batch"]
    unsure_r1 = [r for r in r1_batch if (r["conf"] or 0) < 0.9]
    a_items = [("r1", r) for r in unsure_r1] + [("r2", r) for r in r2["relation"]]

    clusters = []
    for i, sc in enumerate(RELATION):
        clusters.append(("merge", i, [
            {"lang": "pt", "what": sc["anchor"]["pt"]},
            {"lang": "en", "what": sc["same"]["en"]},
            {"lang": "es", "what": sc["refines"]["es"]},
        ]))
        clusters.append(("dispute", i, [
            {"lang": "pt", "what": sc["anchor"]["pt"]},
            {"lang": "es", "what": sc["contradicts"]["es"]},
        ]))

    prompts = [(t, lang, gold) for t, lang, gold in DURABLE] + [(t, "?", gold) for t, gold in DURABLE_HARD]

    def run_a(item):
        tag, r = item
        out, ms = llm_json(relation_prompt(r["new"], r["old"]))
        return tag, r, out.get("relation"), ms

    def run_b(cl):
        kind, i, mems = cl
        out, ms = llm_json(merge_prompt(mems))
        return kind, i, mems, out, ms

    def run_c(p):
        text, lang, gold = p
        out, ms = llm_json(extract_prompt(text))
        return text, lang, gold, [f for f in out.get("facts", []) if isinstance(f, str) and f.strip()], ms

    def settled(futures):
        """Results of the futures that succeeded; a dead tunnel must not sink the run."""
        out = []
        for f in futures:
            try:
                out.append(f.result())
            except Exception as e:
                print(f"  dropped one item: {type(e).__name__}: {e}")
        return out

    with ThreadPoolExecutor(max_workers=3) as pool:
        fa = [pool.submit(run_a, x) for x in a_items]
        fb = [pool.submit(run_b, x) for x in clusters]
        fc = [pool.submit(run_c, x) for x in prompts]
        a_res, b_res, c_res = settled(fa), settled(fb), settled(fc)
    print(f"completed: cascade {len(a_res)}/{len(a_items)}, consolidation {len(b_res)}/{len(clusters)}, "
          f"extraction {len(c_res)}/{len(prompts)}")
    llm_ms = sorted(ms for *_, ms in a_res + b_res + c_res)

    # --- A report
    print(f"Haiku via {LLM_URL} · {USAGE['calls']} uncached calls · API p50 {sorted(USAGE['api_ms'] or [0])[len(USAGE['api_ms'])//2]/1000:.1f}s "
          f"· notional cost ${USAGE['cost_usd']:.2f} (subscription quota)\n")
    print("A. CASCADE (Jev if conf >= 0.9, else Haiku)")
    haiku_on = {(tag, r["new"], r["old"]): pred for tag, r, pred, _ in a_res}
    for tag, rows, name in (("r1", r1_batch, "round 1 (400)"), ("r2", r2["relation"], "round 2 adversarial (29)")):
        jev = sum(r["pred"] == r["gold"] for r in rows)
        casc = 0
        for r in rows:
            pred = r["pred"] if (r["conf"] or 0) >= 0.9 else haiku_on.get((tag, r["new"], r["old"]), r["pred"])
            casc += pred == r["gold"]
        print(f"  {name:<26} Jev alone {jev / len(rows):6.1%}   cascade {casc / len(rows):6.1%}")
    unsure = [(tag, r, p) for tag, r, p, _ in a_res if (r["conf"] or 0) < 0.9]
    print(f"  on the {len(unsure)} judgments Jev was unsure of: Jev {sum(r['pred'] == r['gold'] for _, r, _ in unsure)}"
          f"/{len(unsure)}, Haiku {sum(p == r['gold'] for _, r, p in unsure)}/{len(unsure)}")
    r2_rows = [(r, p) for tag, r, p, _ in a_res if tag == "r2"]
    print(f"  Haiku alone on adversarial: {sum(p == r['gold'] for r, p in r2_rows)}/{len(r2_rows)}")
    for r, p in r2_rows:
        if p != r["gold"]:
            print(f"    ✗ haiku [{r['trap']}] gold={r['gold']} haiku={p}: {r['new'][:50]!r} vs {r['old'][:50]!r}")

    # --- B: Jev verifies each merge preserves each source item
    print("\nB. CONSOLIDATION (Haiku writes, Jev verifies)")
    action_ok = sum((out.get("action") == kind) for kind, _, _, out, _ in b_res)
    print(f"  correct action (merge vs dispute): {action_ok}/{len(b_res)}")
    verify_jobs = []
    for kind, i, mems, out, _ in b_res:
        if kind == "merge" and out.get("action") == "merge" and out.get("what"):
            qs = {f"keeps_{j}": {
                "type": "noul",
                "instructions": {"question": "Is all the information in source preserved in merged_memory, "
                                             "possibly translated or reworded?", "source": m["what"]},
            } for j, m in enumerate(mems)}
            qs["invents"] = {"type": "noul", "instructions": {
                "question": "Does merged_memory state anything that none of the sources say?",
                "sources": [m["what"] for m in mems]}}
            verify_jobs.append((i, out["what"], qs))
    with ThreadPoolExecutor(max_workers=6) as pool:
        verified = list(pool.map(lambda j: (j[0], j[1], call({"merged_memory": j[1]}, j[2])[0]), verify_jobs))
    kept = total = invented = 0
    for i, merged, resp in verified:
        for q, a in resp["answers"].items():
            if q.startswith("keeps_"):
                total += 1
                kept += a["noul"] >= 0.5
                if a["noul"] < 0.5:
                    print(f"    lost info [{i}] {merged[:90]!r} ({q}, p={a['noul']:.2f})")
            elif a["noul"] >= 0.5:
                invented += 1
                print(f"    invented? [{i}] {merged[:90]!r} (p={a['noul']:.2f})")
    print(f"  merges verified by Jev: sources preserved {kept}/{total}, merges flagged as inventing {invented}/{len(verified)}")
    for kind, _i, _mems, out, _ in b_res[:4]:
        print(f"    e.g. {kind:<7} → {json.dumps(out, ensure_ascii=False)[:150]}")

    # --- C: extraction, Jev checks faithfulness
    print("\nC. EXTRACTION (Haiku extracts, Jev checks each fact is in the prompt)")
    tp = sum(1 for _, _, gold, facts, _ in c_res if gold and facts)
    tn = sum(1 for _, _, gold, facts, _ in c_res if not gold and not facts)
    pos = sum(1 for *_, gold, _, _ in c_res if gold)
    print(f"  durable prompts with >=1 fact: {tp}/{pos}   noise prompts with 0 facts: {tn}/{len(c_res) - pos}")
    fjobs = [(text, f) for text, _, _, facts, _ in c_res for f in facts]
    with ThreadPoolExecutor(max_workers=6) as pool:
        fver = list(pool.map(lambda tf: (tf, call({"agent_prompt": tf[0]}, {"faithful": {
            "type": "noul", "instructions": {"question": "Is fact stated or directly implied by agent_prompt?",
                                             "fact": tf[1]}}})[0]), fjobs))
    faithful = sum(r["answers"]["faithful"]["noul"] >= 0.5 for _, r in fver)
    print(f"  extracted facts judged faithful by Jev: {faithful}/{len(fver)}")
    for text, _, gold, facts, _ in c_res:
        if bool(facts) != gold:
            print(f"    ✗ gold={gold} facts={facts} ← {text!r}")
    for (text, f), r in fver:
        if r["answers"]["faithful"]["noul"] < 0.5:
            print(f"    unfaithful? {f!r} ← {text!r}")
    for text, _, _gold, facts, _ in c_res[:3] + c_res[36:39]:
        print(f"    e.g. {text[:55]!r} → {facts}")

    out = HERE / "results" / f"system2_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps({
        "llm_model": LLM_MODEL, "llm_backend": LLM_BACKEND, "llm_latency_ms": llm_ms, "llm_usage": USAGE,
        "cascade": [{"tag": t, **r, "haiku": p} for t, r, p, _ in a_res],
        "consolidation": [{"kind": k, "scenario": i, "sources": m, "out": o} for k, i, m, o, _ in b_res],
        "extraction": [{"text": t, "lang": lg, "gold": g, "facts": f} for t, lg, g, f, _ in c_res],
        "wall_s": time.perf_counter() - t_start,
    }, ensure_ascii=False, indent=1))
    print(f"\nsaved {out.relative_to(HERE.parent.parent)} · wall {time.perf_counter() - t_start:.0f}s")


if __name__ == "__main__":
    main()
