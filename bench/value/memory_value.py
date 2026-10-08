"""
Does memory make an agent answer better in a LATER session? End-to-end value benchmark.

    python bench/value/memory_value.py            # agent = Haiku, judge = Opus (via claude -p)

History per project: one real session with planted facts (bench/jev/sessions.py),
buried among NOISE filler turns (routine commands an agent sees all day). Then a
new session asks QUESTIONS whose answers are in that history, plus questions
whose answer was superseded, plus questions nobody ever answered (the agent
should say it doesn't know).

Conditions (what the agent gets before the question):
  none        — nothing
  full        — the entire history (upper bound on information, max tokens)
  rag-turns   — top-3 raw turns by term overlap (the usual "embed the chat" memory)
  cortex      — Cortext 0.4 as shipped: turns captured, recalled per question
  cortex+facts — background queue, "facts" mode: windows of 4 turns → extract →
                consolidate (with related stored memories); raw turns replaced by facts
  cortex+gate  — background queue, "gate" mode (the 0.5 default): windows with no
                durable fact are archived as noise; useful windows keep their raw
                turns, with the extracted facts indexed on them
                (model: Haiku via `claude -p`, cached; same extraction for both modes)

Scored by Opus per question: correct / wrong / stale (used a superseded value) /
abstained; for unanswerable questions, abstaining is correct.
"""

from __future__ import annotations

import json
import math
import random
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "bench" / "jev"))
sys.path.insert(0, str(ROOT))

from sessions import HELDOUT_SESSIONS, SESSIONS  # noqa: E402
from system2 import USAGE, llm_json  # noqa: E402

from cortext.core.text import tokenize  # noqa: E402
from cortext.llm import DEFAULT_SYSTEM  # noqa: E402
from cortext.server.engine import MemoryEngine  # noqa: E402

# Questions asked in a later session. kind: fact | stale (answer was superseded) | unknown
QUESTIONS = {
    "dev-pt": [
        ("fact", "Os testes de integração de pagamentos estão falhando com erro de conexão ao banco. O que preciso configurar?",
         "A local Postgres on port 5433 via DATABASE_URL (postgresql://localhost:5433/test)"),
        ("stale", "Em que dia da semana fazemos deploy de produção?", "Wednesday (moved from Thursday because of the infra freeze)"),
        ("fact", "Com quem devo falar antes de mudar o serviço de conciliação?", "Bruno's team, the owner of services/reconciliation"),
        ("unknown", "Qual é o limite de memória dos pods de pagamentos no Kubernetes?", "Unknown — never discussed"),
    ],
    "dev-en": [
        ("fact", "The checkout endpoint is slow again. What caused it last time and how was it fixed?",
         "N+1 query loading cart items; fixed with select_related (p95 1.8s -> 220ms)"),
        ("fact", "Can I write this report query in raw SQL?", "No — the repo never uses raw SQL, always the ORM"),
        ("fact", "Is it OK for billing to import a helper from ui/?", "No — billing must never import from ui/ (import-linter contract in CI)"),
        ("unknown", "Which Python version does production run?", "Unknown — never discussed"),
    ],
    "support-es": [
        ("fact", "¿Qué problema tiene la cuenta 2291 y hay algún ticket abierto?", "Duplicate invoice from Oct 3; ticket FAC-118 to void one"),
        ("stale", "¿Por qué canal debo contactar a Luis?", "Email — he does not use WhatsApp"),
        ("fact", "¿A qué hora del día conviene llamar a Luis?", "Afternoon — he works at night"),
        ("unknown", "¿Cuál es el plan contratado por Luis?", "Unknown — never discussed"),
    ],
    "edu-pt": [
        ("fact", "Que adaptação a prova da Beatriz precisa?", "Larger font and short statements (dyslexia)"),
        ("fact", "Em que o João do 6º B tem mais dificuldade?", "Adding fractions with different denominators"),
        ("fact", "Qual o dia de entrega das listas de exercícios?", "Friday"),
    ],
    "dev-mixed": [
        ("stale", "What TTL does the catalog cache use?", "10 minutes (Redis), invalidated immediately on price change"),
        ("fact", "If a product's price changes, how long until customers see it?", "Immediately — the product's cache entry is invalidated on price change"),
    ],
}

QUESTIONS_HELDOUT = {
    "hr-pt": [
        ("fact", "Quando a Fernanda volta da licença?", "Around August/September — maternity leave from March for 6 months"),
        ("stale", "Quem está cobrindo o trabalho da Fernanda?", "Júlia (not Rafael)"),
        ("fact", "Em quais meses acontecem as avaliações de desempenho?", "June and December"),
        ("unknown", "Qual é o salário da Fernanda?", "Unknown — never discussed"),
    ],
    "course-en": [
        ("fact", "Which concept did students struggle with in the module 2 quiz?", "Variance vs standard deviation (question 5)"),
        ("fact", "When is Tom's module 3 project due?", "Friday the 18th (extension for a family emergency)"),
        ("fact", "Can a student hand in next term's project as a PDF?", "No — projects must be notebooks, never PDFs"),
    ],
    "shop-es": [
        ("fact", "¿Por qué devuelven tanto la línea Andes?", "Size M runs small (38% of last month's returns)"),
        ("fact", "¿Cómo se envían los pedidos de Carmen?", "Without the invoice inside the box — she buys gifts"),
        ("stale", "¿Desde qué importe el envío es gratis?", "50 euros"),
        ("unknown", "¿Cuál es el proveedor de la línea Andes?", "Unknown — never discussed"),
    ],
    "go-en": [
        ("fact", "Why was ledger leaking goroutines?", "Response bodies not closed on non-200 replies in ledger/sync.go; fixed with defer resp.Body.Close()"),
        ("stale", "What canary do we use when deploying ledger?", "10% for 30 minutes"),
    ],
}

NOISE_USER = [
    "roda os testes", "run the linter", "mostra o git status", "formata o arquivo", "what does this function do?",
    "explica esse erro", "renomeia a variável x para total", "show me the diff", "ok", "valeu", "continua",
    "abre o arquivo de config", "faz o build", "adiciona um log aqui", "remove esse print", "fix the typo",
    "qual a diferença entre map e filter?", "resume esse arquivo", "gera um docstring", "lgtm",
]
NOISE_AGENT = [
    "Feito.", "Rodei: todos os testes passaram.", "0 problemas encontrados.", "Aqui está o diff.",
    "Essa função converte o payload para o formato interno.", "Renomeei em 3 lugares.", "Build concluído em 41s.",
    "Adicionei o log na linha 88.", "Removido.", "Corrigido.", "map transforma cada item; filter seleciona itens.",
]


class CachedHaiku:
    """The product's LLM backend interface, served by the cached `claude -p` helper."""

    name = "haiku-cached"

    def complete(self, prompt: str, system: str = DEFAULT_SYSTEM) -> str:
        out, _ = llm_json(prompt, model="haiku", max_tokens=1200)
        return json.dumps(out, ensure_ascii=False)


def history(sess, noise_turns: int, rng: random.Random) -> list[tuple[str, str]]:
    """The session's real turns spread among noise turns, in order."""
    noise = [(rng.choice(NOISE_USER), rng.choice(NOISE_AGENT)) for _ in range(noise_turns)]
    out = noise[:]
    slots = sorted(rng.sample(range(len(out) + 1), len(sess["turns"])))
    for k, (slot, turn) in enumerate(zip(slots, sess["turns"])):
        out.insert(slot + k, turn)
    return out


def fmt(turns) -> str:
    return "\n".join(f"USER: {u}\nAGENT: {a}" for u, a in turns)


def rag_turns(turns, question: str, k: int = 3) -> str:
    """BM25-lite over raw turns — the usual unstructured chat memory."""
    q = tokenize(question)
    docs = [tokenize(u + " " + a) for u, a in turns]
    n = len(docs)
    df = {t: sum(t in d for d in docs) for t in q}
    scored = []
    for i, d in enumerate(docs):
        s = sum(math.log(1 + n / df[t]) for t in q if t in d and df[t])
        if s > 0:
            scored.append((s, i))
    top = sorted(scored, reverse=True)[:k]
    return fmt([turns[i] for _, i in sorted(top, key=lambda x: x[1])])


def agent_answer(context: str, question: str) -> str:
    ctx = f"What you remember from earlier sessions with this user/project:\n{context}\n\n" if context.strip() else ""
    out, _ = llm_json(
        f"{ctx}Question: {question}\n\nAnswer briefly in the question's language. If what you remember does not "
        'contain the answer, say you don\'t know rather than guessing. {"answer": "..."}', model="haiku")
    return str(out.get("answer", ""))


def judge(question: str, kind: str, gold: str, answers: dict[str, str]) -> dict:
    listing = "\n".join(f"- {name}: {a}" for name, a in answers.items())
    out, _ = llm_json(
        f"QUESTION: {question}\nGOLD: {gold}\nTYPE: {kind}\n\nANSWERS:\n{listing}\n\n"
        "Grade each answer: 'correct' (matches GOLD's key facts; for TYPE unknown, correct means it says it doesn't "
        "know), 'abstained' (says it doesn't know when GOLD has an answer), 'stale' (states a value that GOLD says was "
        "superseded), or 'wrong' (anything else, including invented answers to unknown questions).\n"
        '{"grades": {"<name>": "correct|abstained|stale|wrong"}}', model="opus")
    return out.get("grades", {})


DEV_SESSIONS, DEV_QUESTIONS = SESSIONS, QUESTIONS


def main() -> None:
    rng = random.Random(7)
    noise_turns = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    split = sys.argv[2] if len(sys.argv) > 2 else "dev"
    SESSIONS, QUESTIONS = (HELDOUT_SESSIONS, QUESTIONS_HELDOUT) if split == "heldout" else (DEV_SESSIONS, DEV_QUESTIONS)
    tmp = Path(tempfile.mkdtemp(prefix="cortext-value-"))
    eng_raw = MemoryEngine(tmp / "raw.db", dream_interval_seconds=0, enable_embeddings=False, llm=None)
    eng_llm = MemoryEngine(tmp / "llm.db", dream_interval_seconds=0, enable_embeddings=False, llm=None)
    eng_llm.abstractor.mode = "facts"
    eng_gate = MemoryEngine(tmp / "gate.db", dream_interval_seconds=0, enable_embeddings=False, llm=None)

    histories = {s["id"]: history(s, noise_turns, rng) for s in SESSIONS}

    # cortex (as shipped): every turn captured
    for s in SESSIONS:
        for u, a in histories[s["id"]]:
            eng_raw.capture_turn(s["id"], u, a, agent="bench")

    # cortex+llm: the same turns through the product's queue, noise included.
    t_q = time.perf_counter()
    backend = CachedHaiku()
    for eng in (eng_llm, eng_gate):
        for s in SESSIONS:
            for u, a in histories[s["id"]]:
                eng.capture_turn(s["id"], u, a, agent="bench", session=s["id"])
            eng.end_session(s["id"], s["id"])
        with ThreadPoolExecutor(max_workers=3) as pool:  # three workers drain the shared queue
            list(pool.map(lambda w, e=eng: e.abstractor.drain(backend, worker=f"w{w}"), range(3)))
    queue_s = time.perf_counter() - t_q
    abstracted = {s["id"]: [m.what for m in eng_llm.cortex(s["id"]).graph.iter_memories() if not m.consolidated_into]
                  for s in SESSIONS}

    jobs = []
    for s in SESSIONS:
        for kind, q, gold in QUESTIONS[s["id"]]:
            h = histories[s["id"]]
            contexts = {
                "none": "",
                "full": fmt(h),
                "rag-turns": rag_turns(h, q),
                "cortex": eng_raw.recall(s["id"], q, max_results=6, max_tokens=350, touch=False)["context"],
                "cortex+facts": eng_llm.recall(s["id"], q, max_results=6, max_tokens=350, touch=False)["context"],
                "cortex+gate": eng_gate.recall(s["id"], q, max_results=6, max_tokens=350, touch=False)["context"],
            }
            jobs.append((s["id"], kind, q, gold, contexts))

    def run(job):
        sid, kind, q, gold, contexts = job
        answers = {name: agent_answer(ctx, q) for name, ctx in contexts.items()}
        grades = judge(q, kind, gold, answers)
        return {"session": sid, "kind": kind, "question": q, "gold": gold,
                "tokens": {n: len(c) // 4 for n, c in contexts.items()}, "answers": answers, "grades": grades}

    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(run, jobs))

    names = ["none", "full", "rag-turns", "cortex", "cortex+facts", "cortex+gate"]
    q = eng_llm.queue.stats()
    print(f"{len(rows)} questions · {noise_turns} noise turns per project · queue {q} in {queue_s:.0f}s · "
          f"active memories after abstraction {sum(map(len, abstracted.values()))} (vs "
          f"{sum(len(histories[s['id']]) for s in SESSIONS)} turns) · LLM calls {USAGE['calls']} uncached · "
          f"notional ${USAGE['cost_usd']:.2f}\n")
    print(f"{'condition':<14}{'correct':>9}{'facts':>8}{'stale→ok':>10}{'unknown→ok':>12}{'stale ans':>11}{'tokens/q':>10}")
    summary = {}
    for n in names:
        g = [r["grades"].get(n, "wrong") for r in rows]
        acc = sum(x == "correct" for x in g) / len(g)
        f_, s_, u_ = ([r["grades"].get(n, "wrong") == "correct" for r in rows if r["kind"] == kind]
                      for kind in ("fact", "stale", "unknown"))
        stale_ans = sum(x == "stale" for x in g)
        tok = sum(r["tokens"][n] for r in rows) / len(rows)
        summary[n] = {"accuracy": acc, "fact": sum(f_) / len(f_), "stale_ok": sum(s_) / len(s_),
                      "unknown_ok": sum(u_) / len(u_), "stale_answers": stale_ans, "tokens_per_question": tok}
        print(f"{n:<14}{acc:>9.0%}{sum(f_)}/{len(f_):<5}{sum(s_)}/{len(s_):<7}{sum(u_)}/{len(u_):<9}{stale_ans:>8}{tok:>10.0f}")

    out = ROOT / "bench" / "value" / "results" / f"value_{split}_{noise_turns}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"split": split, "noise_turns": noise_turns, "summary": summary, "rows": rows, "queue": q,
                               "facts": abstracted, "llm_usage": USAGE}, ensure_ascii=False, indent=1))
    print(f"\nsaved {out.relative_to(ROOT)}")
    gate_active = sum(1 for s in SESSIONS for m in eng_gate.cortex(s["id"]).graph.iter_memories() if not m.consolidated_into)
    print(f"gate mode: {gate_active} active memories left of {sum(len(histories[s['id']]) for s in SESSIONS)} turns")
    for e in (eng_raw, eng_llm, eng_gate):
        e.close()


if __name__ == "__main__":
    main()
