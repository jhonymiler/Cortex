"""
Benchmark v3 vs v5: token reduction, precision, contradiction detection.

Approach:
  - v3 baseline: naive retrieval (return ALL memories as context)
  - v5: CortexV5.remember() + recall() with W5H + parser + pack
  - Same scenarios, same queries
  - Compare: tokens, precision@5, contradiction detection rate
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cortext import CortexV5
from cortext.core.validation import (
    CanonicalValidator,
    ValidationPolicy,
)


SCENARIOS_DIR = Path(__file__).parent / "scenarios"
RESULTS_DIR = Path(__file__).parent / "results"


def rough_token_count(text: str) -> int:
    """Approximate: 1 token ≈ 4 characters."""
    return len(text) // 4


def _populate_cortex(cortex: CortexV5, scenario: dict, lang: str = "pt") -> None:
    """Populate cortex with memories from scenario."""
    for m in scenario["memories"]:
        kwargs = {k: v for k, v in m.items() if k in ("who", "what", "why", "where", "how", "importance")}
        if "importance" not in kwargs:
            kwargs["importance"] = 0.5
        kwargs["lang"] = lang
        cortex.remember(**kwargs, validate=False)


def _v3_baseline_recall(scenario: dict) -> tuple[list[str], int, float]:
    """v3 baseline: return all memories (no parsing, no packing)."""
    start = time.perf_counter()
    parts = []
    for m in scenario["memories"]:
        who = ",".join(m.get("who", [])) or "?"
        line = f"[{who}] {m.get('what', '')}"
        if m.get("where") and m["where"] != "default":
            line += f" @ {m['where']}"
        parts.append(line)
    context = "\n".join(parts)
    tokens = rough_token_count(context)
    latency = (time.perf_counter() - start) * 1000
    return [f"mem-{i}" for i in range(len(scenario["memories"]))], tokens, latency


def _v5_recall(cortex: CortexV5, query: str, lang: str) -> tuple[list[str], int, float]:
    """v5: CortexV5.recall() with parser + pack."""
    start = time.perf_counter()
    context, result = cortex.recall(query, lang=lang)
    tokens = rough_token_count(context)
    latency = (time.perf_counter() - start) * 1000
    return [m.id for m in result.memories], tokens, latency


def _precision_at_k(returned_ids: list[str], relevant_who: list[str], graph, k: int = 5) -> float:
    """Precision@k: fraction of top-k results whose who overlaps with relevant."""
    if not returned_ids:
        return 0.0
    top_k = returned_ids[:k]
    relevant = 0
    for mem_id in top_k:
        mem = graph.get_memory(mem_id)
        if mem and any(r.lower() in [w.lower() for w in (mem.who or [])] for r in relevant_who):
            relevant += 1
    return relevant / min(k, len(top_k)) if top_k else 0.0


def _test_contradictions(scenario: dict, validator: CanonicalValidator) -> dict:
    """Test validator catches real contradictions."""
    result = {"true_positives": 0, "false_negatives": 0, "false_positives": 0, "true_negatives": 0}
    from cortext import Memory, MemoryGraph

    # Build the graph with ALL existing memories (unique keys)
    g = MemoryGraph()
    for i, m in enumerate(scenario["memories"]):
        existing = Memory(
            who=m.get("who", []),
            what=m.get("what", ""),
            where=m.get("where", "default"),
        )
        g._memories[f"existing-{i}"] = existing

    for cand in scenario.get("candidate_writes_contradicting", []):
        candidate = Memory(
            who=cand.get("who", []),
            what=cand.get("what", ""),
            where=cand.get("where", "default"),
        )
        v = validator.validate_write(candidate, g)
        should_block = cand.get("should_block", False)
        if should_block and v.status.value in ("BLOCKED", "WARN"):
            result["true_positives"] += 1
        elif should_block:
            result["false_negatives"] += 1
        elif not should_block and v.status.value == "OK":
            result["true_negatives"] += 1
        else:
            result["false_positives"] += 1
    return result


def run_scenario(scenario_path: Path) -> dict:
    with open(scenario_path) as f:
        scenario = json.load(f)

    print(f"\n{'='*60}")
    print(f"Scenario: {scenario['scenario']} (lang: {scenario['language']})")
    print(f"Memories: {len(scenario['memories'])}, Queries: {len(scenario['queries'])}")
    print(f"{'='*60}")

    # v3 baseline
    v3_ids, v3_total_tokens, _ = _v3_baseline_recall(scenario)

    # v5 setup
    cortex = CortexV5(namespace=f"bench-{scenario['scenario']}")
    _populate_cortex(cortex, scenario, lang=scenario.get("language", "pt")[:2])

    # v3-style validator (canonical contradiction check)
    validator = CanonicalValidator(policy=ValidationPolicy.WARN)

    # === Retrieval comparison ===
    v3_total = 0
    v5_total = 0
    v3_precisions = []
    v5_precisions = []
    v5_latencies = []
    retrieval_results = []

    for q_data in scenario["queries"]:
        query = q_data["query"]
        relevant_who = q_data.get("relevant_who", [])

        # v3 has no precision (returns everything); assume 1.0 since all there
        v3_p = 1.0  # all memories returned → recall = 1, but precision diluted
        # Actually measure: how many of returned are relevant
        v3_relevant = sum(1 for who_list in [m.get("who", []) for m in scenario["memories"]]
                          if any(r.lower() in [w.lower() for w in who_list] for r in relevant_who))
        v3_p_at_k = v3_relevant / min(5, len(scenario["memories"]))

        # v5
        v5_ids, v5_tok, v5_lat = _v5_recall(cortex, query, scenario.get("language", "pt")[:2])
        v5_p = _precision_at_k(v5_ids, relevant_who, cortex.graph, k=5)

        # Track totals (v3 returns full context per query = same total each time)
        v3_total += v3_total_tokens
        v5_total += v5_tok
        v3_precisions.append(v3_p_at_k)
        v5_precisions.append(v5_p)
        v5_latencies.append(v5_lat)

        retrieval_results.append({
            "query": query,
            "v3_tokens": v3_total_tokens,
            "v5_tokens": v5_tok,
            "v3_p5": round(v3_p_at_k, 3),
            "v5_p5": round(v5_p, 3),
            "v5_latency_ms": round(v5_lat, 3),
        })

    # === Contradiction detection ===
    cd_result = _test_contradictions(scenario, validator)
    cd_pct = cd_result["true_positives"] / max(1, cd_result["true_positives"] + cd_result["false_negatives"])

    # === Summary ===
    token_savings = (v3_total - v5_total) / v3_total * 100 if v3_total > 0 else 0
    avg_v3_p = sum(v3_precisions) / len(v3_precisions) if v3_precisions else 0
    avg_v5_p = sum(v5_precisions) / len(v5_precisions) if v5_precisions else 0
    avg_v5_lat = sum(v5_latencies) / len(v5_latencies) if v5_latencies else 0

    summary = {
        "scenario": scenario["scenario"],
        "n_memories": len(scenario["memories"]),
        "n_queries": len(scenario["queries"]),
        "v3_total_tokens": v3_total,
        "v5_total_tokens": v5_total,
        "token_savings_pct": round(token_savings, 1),
        "v3_avg_precision_at_5": round(avg_v3_p, 3),
        "v5_avg_precision_at_5": round(avg_v5_p, 3),
        "v5_avg_latency_ms": round(avg_v5_lat, 3),
        "contradiction_detection_pct": round(cd_pct * 100, 1),
        "true_positives": cd_result["true_positives"],
        "false_positives": cd_result["false_positives"],
        "false_negatives": cd_result["false_negatives"],
        "retrieval_results": retrieval_results,
    }

    print(f"\n[Results]")
    print(f"  Tokens:    v3={v3_total} → v5={v5_total} ({token_savings:.1f}% reduction)")
    print(f"  P@5:       v3={avg_v3_p:.3f} → v5={avg_v5_p:.3f}")
    print(f"  Latency:   v5={avg_v5_lat:.2f}ms (avg per query)")
    print(f"  Conflicts: detected {cd_pct*100:.0f}% (TP={cd_result['true_positives']}, FP={cd_result['false_positives']}, FN={cd_result['false_negatives']})")
    return summary


def main():
    RESULTS_DIR.mkdir(exist_ok=True, parents=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    summaries = []
    for f in sorted(SCENARIOS_DIR.glob("*.json")):
        summaries.append(run_scenario(f))

    # Save
    combined = {
        "timestamp": timestamp,
        "scenarios": summaries,
        "aggregate": _aggregate(summaries),
    }
    out_path = RESULTS_DIR / f"v5_benchmark_{timestamp}.json"
    with open(out_path, "w") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {out_path}")

    print_aggregate_table(summaries)


def _aggregate(summaries: list[dict]) -> dict:
    if not summaries:
        return {}
    n = len(summaries)
    return {
        "n_scenarios": n,
        "avg_token_savings_pct": round(sum(s["token_savings_pct"] for s in summaries) / n, 1),
        "avg_v3_precision": round(sum(s["v3_avg_precision_at_5"] for s in summaries) / n, 3),
        "avg_v5_precision": round(sum(s["v5_avg_precision_at_5"] for s in summaries) / n, 3),
        "avg_contradiction_detection_pct": round(sum(s["contradiction_detection_pct"] for s in summaries) / n, 1),
    }


def print_aggregate_table(summaries: list[dict]) -> None:
    print("\n" + "=" * 80)
    print("AGGREGATE TABLE — Cortex v3 (baseline) vs Cortex v5 (greenfield)")
    print("=" * 80)
    print(f"\n{'Scenario':<22} {'Tok v3':>8} {'Tok v5':>8} {'Save%':>7} {'P@5 v3':>7} {'P@5 v5':>7} {'CD':>6}")
    print("-" * 80)
    for s in summaries:
        print(
            f"{s['scenario']:<22} "
            f"{s['v3_total_tokens']:>8} "
            f"{s['v5_total_tokens']:>8} "
            f"{s['token_savings_pct']:>6.1f}% "
            f"{s['v3_avg_precision_at_5']:>7.3f} "
            f"{s['v5_avg_precision_at_5']:>7.3f} "
            f"{s['contradiction_detection_pct']:>5.0f}%"
        )
    if summaries:
        agg = _aggregate(summaries)
        print("-" * 80)
        print(
            f"{'AVERAGE':<22} "
            f"{'':>8} "
            f"{'':>8} "
            f"{agg['avg_token_savings_pct']:>6.1f}% "
            f"{agg['avg_v3_precision']:>7.3f} "
            f"{agg['avg_v5_precision']:>7.3f} "
            f"{'':>6}"
        )


if __name__ == "__main__":
    main()
