# Evidence: what Cortext is worth, measured

Every number below comes from a script in this repository. Each section names
its command and its result file. Where a dataset is small or written by us, the
section says so.

## 1. Agents answer better with Cortext — end-to-end

`python bench/value/memory_value.py 60 dev` and `... 60 heldout`. Each project's
history has one real session (planted facts, corrections) buried among 60
routine filler turns. A later session asks questions. The agent is Claude Haiku 4.5;
answers are graded by Claude Opus 5.5 (correct / wrong / stale / abstained). For
questions nobody ever answered, "I don't know" is correct.

The **held-out** set (4 new sessions, 13 questions) was written after the
pipeline was tuned on the dev set (5 sessions, 17 questions), and run only to
check that the tuning generalizes.

| What the agent gets before answering | Correct (dev + held-out) | Stale questions → right | Tokens / question | Turns kept active |
|---|---|---|---|---|
| nothing | 5/30 (**17%**) | 0/6 | 0 | — |
| the entire history | 30/30 (100%) | 6/6 | **~1,000** | 592 |
| top-3 raw turns, BM25 (plain chat RAG) | 29/30 (97%) | 6/6 | ~76 | 592 |
| Cortext, raw turns | 28/30 (93%) | 6/6 | ~101 | 592 |
| Cortext, background "facts" mode (rewrite turns into facts) | 25/30 (83%) | 4/6 | ~77 | — |
| **Cortext 0.5 default, background "gate" mode** | **29/30 (97%)** | **6/6** | ~113 | **77 (13%)** |

Per split: gate 16/17 dev, 13/13 held-out; raw 15/17 and 13/13; RAG 16/17 and 13/13.
Results: `bench/value/results/value_{dev,heldout}_60_*.json`.

**What this shows**

- Memory moves the agent from **17% to 97%** correct on questions about earlier
  sessions, and it doesn't make things up: the unanswerable questions were
  answered "I don't know" in every condition.
- Cortext matches the full history using **~11% of the tokens**, and the gate
  archives **87% of turns** as noise without losing accuracy.
- On this benchmark Cortext **ties** a plain BM25 retrieval over raw turns. Its
  measured advantages are elsewhere: contradiction detection at write time
  (section 3), a memory that stays small and clean (87% of turns archived),
  sub-millisecond latency (section 2), cross-language recall and agent
  integration. A harder retrieval benchmark is future work.
- **Rewriting turns into facts hurts**, and it is unstable across runs (76–94% on
  dev for the same pipeline). Summaries lose detail and the order of corrections.
  That is why "gate" (keep raw turns, archive noise, index the extracted facts
  on the turns) is the default, and "facts" is opt-in (`CORTEXT_ABSTRACTION=facts`).

**How we got here (failures included):**

| Run | Change | Dev | Held-out |
|---|---|---|---|
| 1 | facts mode | 15/17 | — |
| 2 | + about/terms requested from the model | 13/17 | facts 11/13, raw 13/13 |
| 3 | measured prompt + deterministic preservation guard | 14/17 | facts 10/13 |
| 4 | + gate mode | gate 14/17 | gate 12/13 |
| 5 | recall: a newer correction survives the cutoff; context oldest → newest | gate 17/17, raw 16/17 | gate 12/13 |
| 6 | gate keeps a lone correction related to a kept memory | gate 16/17, raw 15/17 | **gate 13/13**, raw 13/13 |

Each run's failures were inspected by hand, then generalized into a rule that
does not mention the test data (e.g. "a newer memory sharing a rare term with
the best match may be its correction"). The quality benchmark below
(section 5) cost 0.04 P@5 for the recency rule. The trade is documented there.

## 2. It is fast enough to sit in every prompt

`python bench/latency_benchmark.py`. Synthetic corpus: 300 people, a verb shared
by 10% of memories. Writes are validated **and** persisted to SQLite before they
return.

| Memories | Write + validate + persist | Recall by participant | Recall by text |
|---|---|---|---|
| 1,000 | 0.39 ms | 0.37 ms | 0.06 ms |
| 20,000 | 0.45 ms | 0.42 ms | 0.22 ms |
| 50,000 | 0.54 ms | 1.17 ms | 0.51 ms |

Before (0.3.1, same corpus, memory only, nothing persisted): at 20,000 memories a
write took 4.3 ms and a recall 193 ms, and saving rewrote the whole JSON file
(0.7 s). Through the local daemon, a hook's recall costs ~1 ms plus process start.

## 3. Writes catch contradictions that keyword rules miss

`python bench/jev/experiment.py` and `bench/jev/adversarial.py`: 400 + 29
labeled memory pairs in PT/EN/ES and across languages.

| Judge | Relation accuracy (round 1) | Adversarial | "Worth storing?" |
|---|---|---|---|
| Cortext 0.4 heuristics | 28% | 13.8% | 55.6% |
| Jev (TypeSafe) | 99.5% | 86.2% | 100% |
| Jev, with Haiku when Jev's confidence is < 0.9 | 99.5% | **96.6%** | — |
| Haiku alone | — | 93.1% | 100% (extraction) |

Every Jev judgment at confidence ≥ 0.9 was correct (72–89% of all judgments).
Details: [experiments/2026-10-jev-judge.md](experiments/2026-10-jev-judge.md).

## 4. The background pipeline keeps memory correct, not just big

`python bench/jev/timing.py`: 5 multi-turn sessions, 12 gold facts, 3 values that
change mid-session. Graded by Opus.

| | Gold captured | Stale value kept | Useful | Memories |
|---|---|---|---|---|
| Store every turn (0.4 behaviour) | 100% | 3/3 | 78% | 32 |
| **Window of 4 + consolidation (0.5)** | **100%** | **0/3** | **93%** | **15** |

Haiku extraction on 48 prompts: 24/24 durable prompts gave ≥ 1 fact, 24/24 noise
prompts gave none, and 27/27 extracted facts were faithful to the text.
Consolidation picked merge vs dispute correctly 40/40, with 0/20 merges inventing
content.

## 5. Fewer tokens, better precision than plain retrieval

`python bench/run_benchmark.py`, against an unstructured top-k baseline:

| | Tokens | P@5 |
|---|---|---|
| Baseline top-k | 460 avg | 0.603 |
| Cortext | 107 avg (**−76.8%**) | **0.817** |

(0.4 scored 0.859; the 0.5 recency rule adds one harmless extra result to
"Quem pediu reembolso?" ("Pedro pediu suporte"), a memory newer than the best
match and sharing its term. That is the same shape as a correction, and
deterministically indistinguishable from one in an 8-memory graph.)

## What these numbers do not show yet

- Datasets are small, and most were written for these experiments. They test
  specific failure modes (stale values, cross-language, noise), not broad
  coverage. Next: replay real exported sessions.
- Model latency was measured through `claude -p` (API p50 ~5–7 s including CLI
  overhead). It runs in the background, off the prompt path.
- No multi-person (collective) evaluation yet. The content-addressing
  reinforcement count is the building block for it.
- Value benchmark: 30 questions, one noise seed. Differences of one question
  (3 points) between Cortext variants and RAG are within run-to-run noise.
