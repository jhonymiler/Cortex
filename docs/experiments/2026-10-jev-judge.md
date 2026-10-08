# Experiment: Jev (TypeSafe System One) as Cortext's judge — 2026-10-08

**Question.** Can a typed-decision model replace Cortext's heuristics for the
judgments that need language understanding: contradiction/duplicate detection
between memories (across languages) and "is this worth remembering"?

**Model.** `jev-1.13.0` via `POST https://api.typesafe.ai/v1/systemone`, using
`choice` (relation), `noul` (durable) and `score` (importance) questions.
**Baseline.** Cortext 0.4.0 heuristics on the same inputs: `CanonicalValidator`
(token Jaccard + negation words) and the engine's trivial-prompt filter.

**Reproduce.** `JEV_API_KEY=... python bench/jev/experiment.py` (round 1) and
`python bench/jev/adversarial.py` (round 2). Raw results: `bench/jev/results/`.

**Data caveat.** Both datasets were written by Claude for this experiment (not an
external benchmark): they are small and may share the author's phrasing. Labels
in round 2 were chosen to be undisputable, but two of the four misses below are
arguably label errors. Treat the numbers as directional.

## Round 1 — 20 scenarios × 4 relations × 5 language conditions (400 judgments) + 36 prompts

Relation (same / contradicts / refines / unrelated), one request per write with
4 candidates ("batch"), or one pair per request ("pair"):

| Condition | n | Jev accuracy | Jev macro-F1 | Heuristic accuracy | Heuristic macro-F1 |
|---|---|---|---|---|---|
| pt-pt (batch) | 80 | 100.0% | 1.00 | 30.0% | 0.18 |
| en-en | 80 | 98.8% | 0.99 | 28.7% | 0.16 |
| es-es | 80 | 98.8% | 0.99 | 31.2% | 0.20 |
| pt → en | 80 | 100.0% | 1.00 | 25.0% | 0.10 |
| es → pt | 80 | 100.0% | 1.00 | 25.0% | 0.10 |
| pt-pt (pair) | 80 | 98.8% | 0.99 | 30.0% | 0.18 |

Per class (batch, Jev | heuristic): same 98% | 0%, contradicts 100% | 12%,
refines 100% | 0%, unrelated 100% | 100%. Both misses were `same → refines`
on "works remotely from Recife" vs "is remote and lives in Recife", at
confidence 0.52 and 0.36.

Calibration (batch): confidence ≥ 0.9 → 88.8% of judgments, 100% accurate;
0.7–0.9 → 7.2%, 100%; < 0.7 → 4.0%, 87.5%.

Durable fact (threshold p ≥ 0.5): Jev 100% (36/36) vs heuristic 55.6%.
Importance score (0–4): durable avg 2.94, noise avg 0.25.

Ceiling effect: round 1 was too easy to discriminate; hence round 2.

## Round 2 — adversarial (29 pairs + 12 prompts)

| Trap | n | Jev | Heuristic |
|---|---|---|---|
| temporal supersession | 3 | 2 | 0 |
| world knowledge | 4 | 3 | 0 |
| homonyms | 2 | 2 | 2 |
| same attribute, different scope | 2 | 2 | 1 |
| units / numeric equivalence | 4 | 4 | 0 |
| double negation | 3 | 3 | 0 |
| slang / typos (PT-BR) | 3 | 3 | 0 |
| opinion vs fact | 1 | 0 | 1 |
| refines vs contradicts | 2 | 2 | 0 |
| noisy agent-turn memory | 2 | 1 | 0 |
| cross-language idioms | 3 | 3 | 0 |
| **Total** | **29** | **86.2%** | **13.8%** |

Misses:
- "Carla é a gerente do time de dados" vs "Carla saiu da empresa em agosto" → `unrelated` (gold `contradicts`), conf 0.36.
- "build usa Node 20" vs "versão LTS do Node lançada em abril de 2023" → `refines` (gold `same`), conf 0.37.
- "estoque é escrito em Python" vs "Bruno acha que deveríamos reescrever em Go" → `contradicts` (gold `unrelated`), conf 0.23.
- short memory vs agent turn with more detail → `refines` (gold `same`), conf 0.81. Arguably `refines` is right.

Calibration: ≥ 0.9 → 21/29 judgments, 100% accurate; 0.7–0.9 → 3, 67%; < 0.7 → 5, 40%.

Durable facts hidden inside commands ("corrige esse teste, e lembra que aqui a
gente sempre usa Decimal pra dinheiro") and look-alike one-offs: Jev 12/12,
heuristic 6/12. Separation: lowest durable p = 0.86, highest noise p = 0.41.

## Cost and latency

216 requests (round 1): 160,807 input tokens ≈ **US$ 0.0068** (output is free),
i.e. ~745 tokens and ~US$ 0.00003 per write-time judgment. Latency over the
internet from Brazil: **p50 289 ms, p95 989 ms**, 0 errors, 6 concurrent requests.

## Conclusions

1. On these data Jev is far better than the heuristics at every judgment that
   needs language understanding, and works across PT/EN/ES and between them.
   The docs warn about non-English quality; on these short memories no penalty
   showed up.
2. **Confidence is usable for routing.** In both rounds, every judgment at
   confidence ≥ 0.9 was correct (88.8% and 72% of judgments). Below that,
   accuracy drops sharply. Policy: apply automatically at ≥ 0.9; otherwise
   escalate (a generative model, or the dashboard's review queue).
3. **Latency rules out the per-prompt hot path** (~0.3–1 s vs Cortext's ~0.5 ms).
   Use it asynchronously: store immediately, judge in the background, mark
   the memory as pending until the judgment lands.
4. Weak spots to cover with escalation: temporal supersession framed as an
   event ("left the company"), opinion vs fact, and implicit equivalences that
   need dates or versions.
5. Batching 4 candidates per request did not hurt accuracy (pt-pt: batch 100%
   vs pair 98.8%): one call per write is viable.

---

# Rounds 3–4 — the user's own model ("System 2") and WHEN to abstract — 2026-10-08

**Setup.** Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) through `claude -p` on the
user's own Claude Code login: the same client the mod reaches with
`$.model.complete`. Each call is isolated (`--tools ""`, `--strict-mcp-config`,
`--no-session-persistence`, an empty cwd; ~3.4k input tokens). The neutral grader
in round 4 is Claude Opus 5.5, which does not judge its own work. Every model
answer is cached on disk by (model, prompt) at temperature 0, so runs resume after a failure.
Scripts: `bench/jev/system2.py`, `bench/jev/timing.py`, `bench/jev/sessions.py`.
An earlier attempt through a `trycloudflare` proxy was abandoned (HTTP 530/502,
then the hostname disappeared). That proxy also injected ~34k tokens per call,
so its latency was never representative.

## Round 3 — Haiku with and without Jev (162 Haiku calls, API p50 5.6 s)

**A. Cascade:** Jev decides when its confidence is ≥ 0.9; Haiku re-judges the rest.

| | Jev alone | Cascade | Haiku alone |
|---|---|---|---|
| Round 1 (400 judgments) | 99.5% | 99.5% | — |
| Round 2 adversarial (29) | 86.2% | **96.6%** | 93.1% |
| The 53 judgments Jev was unsure of | 47/53 | — | **50/53** |

**B. Consolidation:** Haiku merges multilingual clusters (PT + EN + ES) or declares
a dispute; Jev verifies the merge. Correct action (merge vs dispute): **40/40**.
Jev's check: sources preserved 50/60, merges flagged as inventing **0/20**. All
10 "lost" flags sit at p 0.29–0.49, and spot checks show the information
reworded, not dropped ("approximately 400 lines"). Jev is a weaker verifier of
merges than a classifier of relations.

**C. Extraction** (48 prompts, 24 durable / 24 noise, including facts hidden in
commands): durable → ≥ 1 fact **24/24**; noise → 0 facts **24/24**; extracted
facts faithful to the prompt (Jev) **27/27**.

## Round 4 — WHEN to abstract (5 sessions, 12 gold facts, 3 stale values; graded by Opus)

| Strategy | Gold captured | Stale kept | Useful | Duplicates | Memories |
|---|---|---|---|---|---|
| per turn, raw | 100% | **3/3** | 78% | 0 | 32 |
| per turn + heuristic dedup | 100% | 3/3 | 78% | 0 | 32 |
| **per turn + Haiku consolidation** | **100%** | **0/3** | **95%** | 0 | 20 |
| per turn + Jev consolidation | **46%** | 0/3 | 100% | 0 | 16 |
| per turn, with session context | 92% | 0/3 | 95% | 1 | 21 |
| **window of 4 + Haiku consolidation** | **100%** | **0/3** | 93% | 0 | **15** |
| whole session at the end | 92% | 0/3 | 90% | 0 | 21 |

89 Haiku calls and 44 Jev calls in this round.

## Decisions taken from these numbers

1. **Abstraction runs in windows of 4 turns, then the LLM consolidates.** This ties
   for best quality with per-turn + consolidation and makes 4× fewer calls on the
   user's quota. Implemented in `cortext/server/abstraction.py`.
2. **Extraction without consolidation keeps stale values alive** (3/3), so
   consolidation is mandatory.
3. **Jev must not consolidate.** It decides but cannot write, so merging becomes
   choosing one sentence and information is lost (46%). Locally, the user's Haiku
   is enough; Jev's place is a fast, calibrated judge (cascade, verification,
   a remote server with no user model available).
4. **Facts are stored in the user's language with an English pivot** (`Memory.alt`,
   indexed). A unit test showed a PT question missing an EN-only fact through
   term recall.
5. **Coreference** (the Event Parser idea) needs no separate model: the
   extraction prompt requires self-contained facts that name who/what.

## Round 5 — end-to-end value (moved to docs/EVIDENCE.md)

The decisive test, an agent answering later-session questions with each kind of
memory on a dev set and a held-out set, is in
[docs/EVIDENCE.md §1](../EVIDENCE.md#1-agents-answer-better-with-cortext--end-to-end).
It reversed one decision above: rewriting turns into consolidated facts (round 4's
winner on fact capture) lost to keeping raw turns and archiving noise ("gate").
Rewriting drops detail and the order of corrections, which an agent reading raw
turns in order uses. Fact capture in isolation was the wrong proxy.
