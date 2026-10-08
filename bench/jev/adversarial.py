"""
Round 2: adversarial cases, built after round 1 hit a ceiling (99.6%).

Each relation case is one pair with a gold label and the trap it tests. Cases
whose label a careful human could reasonably dispute were left out.

    python bench/jev/adversarial.py
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))

from experiment import baseline_durable, baseline_relation, call, relation_question  # noqa: E402

# (trap, new_memory, existing_memory, gold)
CASES = [
    # temporal supersession: the newer statement replaces the older one
    ("temporal", "o banco principal é MySQL", "migramos o banco principal de MySQL para Postgres em março", "contradicts"),
    ("temporal", "Carla é a gerente do time de dados", "a Carla saiu da empresa em agosto", "contradicts"),
    ("temporal", "the API is on version 2", "we sunset API v2 last month; everyone is on v3", "contradicts"),
    # contradiction that needs world knowledge (no shared words, no negation)
    ("world", "o servidor de produção fica em Lisboa", "o servidor de produção fica na América do Sul", "contradicts"),
    ("world", "a reunião de planejamento é às segundas", "a reunião de planejamento acontece no primeiro dia útil da semana", "same"),
    ("world", "el cliente vive en Madrid", "el cliente vive en la capital de España", "same"),
    ("world", "o build usa Node 20", "o build usa a versão LTS do Node lançada em abril de 2023", "same"),
    # homonyms / different entities with the same name
    ("homonym", "Maria do financeiro aprova os reembolsos", "Maria do suporte atende o chat da madrugada", "unrelated"),
    ("homonym", "o serviço payments roda em Go", "o time de payments faz on-call em escala semanal", "unrelated"),
    # same attribute, different scope
    ("scope", "o ambiente de staging escala para zero à noite", "o ambiente de produção nunca escala para zero", "unrelated"),
    ("scope", "os alunos do 7º ano fazem prova às sextas", "os alunos do 9º ano fazem prova às quartas", "unrelated"),
    # numeric / unit equivalence
    ("units", "a API limita 100 requisições por minuto", "a API limita 6000 requisições por hora", "same"),
    ("units", "o timeout do gateway é de 30 segundos", "o gateway desiste depois de meio minuto", "same"),
    ("units", "o cache expira em 10 minutos", "o cache expira em 600 segundos", "same"),
    ("units", "o cache expira em 10 minutos", "o cache expira em 10 segundos", "contradicts"),
    # double negation / negated paraphrase
    ("negation", "não é proibido usar ORM neste projeto", "pode usar ORM neste projeto", "same"),
    ("negation", "nunca fazemos deploy na sexta", "deploy na sexta é proibido", "same"),
    ("negation", "nunca fazemos deploy na sexta", "sexta é o dia preferido para deploy", "contradicts"),
    # slang, typos, abbreviations (PT-BR)
    ("slang", "o deploy é pelo GitHub Actions com Helm", "deploy eh pelo actions c/ helm", "same"),
    ("slang", "o cliente Pedro prefere contato por WhatsApp", "Pedro não curte que mandem zap pra ele, só email", "contradicts"),
    ("slang", "a Ana prefere PRs pequenos", "Ana curte PR enxuto", "same"),
    # opinion vs fact
    ("opinion", "o serviço de estoque é escrito em Python", "o Bruno acha que deveríamos reescrever o estoque em Go", "unrelated"),
    # refines vs contradicts (detail that keeps the claim true)
    ("refine", "o reembolso sai em até 7 dias", "o reembolso sai em até 7 dias, e em 24h para clientes premium", "refines"),
    ("refine", "João tem dificuldade em matemática", "João tem dificuldade em matemática, especialmente geometria", "refines"),
    # noisy agent-turn memories (what = prompt, how = answer)
    ("turn", "pagamentos sobe via helm chart no k8s",
     "Como configuro o deploy do serviço de pagamentos no Kubernetes? → Usamos o Helm chart em infra/charts/payments com values-prod.yaml",
     "same"),
    ("turn", "o fluxo de reembolso usa a fila SQS refunds",
     "Refatora o worker de reembolso → movi o consumo da fila SQS 'refunds' para o RefundWorker e adicionei retry exponencial",
     "refines"),
    # cross-language with idiom
    ("crossling", "the team prefers small, frequent releases", "o time prefere lançar pouco e com frequência", "same"),
    ("crossling", "la clienta quiere factura en papel", "a cliente pediu nota fiscal só por e-mail, nada impresso", "contradicts"),
    ("crossling", "the student is fluent in Spanish", "o aluno fala espanhol fluentemente", "same"),
]

DURABLE_HARD = [
    # durable facts hidden inside commands or questions
    ("corrige esse teste, e lembra que aqui a gente sempre usa Decimal pra dinheiro", True),
    ("por que você usou tabs? neste repo é sempre 2 espaços", True),
    ("sempre me responda em português, mesmo quando eu escrever em inglês", True),
    ("fix the import, and note that the billing module must never import from ui/", True),
    ("arregla el bug; por cierto, el cliente ACME tiene SLA de 2 horas", True),
    ("antes de mexer no estoque fala com o Bruno, ele é o dono desse serviço", True),
    # look substantive but are one-off or temporary
    ("renomeia total para total_bruto no arquivo invoice.py", False),
    ("hoje estou com pressa, responde curto", False),
    ("explica o que é uma closure em JavaScript com um exemplo", False),
    ("roda o build de novo e me mostra só os erros", False),
    ("add a log line in the retry loop so I can debug this", False),
    ("¿puedes resumir este archivo en tres frases?", False),
]


def main() -> None:
    jobs = []
    for i, (_trap, new, old, _gold) in enumerate(CASES):
        jobs.append(("rel", i, {
            "state": {"new_memory": {"what": new}, "existing_memories": {"m1": {"what": old}}},
            "questions": {"rel_m1": relation_question("m1")},
        }))
    for i, (text, _gold) in enumerate(DURABLE_HARD):
        jobs.append(("dur", i, {
            "state": {"agent_prompt": text},
            "questions": {"durable": {
                "type": "noul",
                "instructions": "Does agent_prompt contain a durable fact, decision, convention, preference or "
                                "constraint worth remembering in long-term memory for future sessions?",
                "criteria": {
                    "true": "Contains a lasting fact about the project, team, customer, student or user, even if it is mentioned inside a request.",
                    "false": "Only a one-off command, a temporary state, a generic question, or small talk.",
                },
            }},
        }))

    def run(job):
        kind, i, req = job
        resp, ms = call(req["state"], req["questions"])
        return kind, i, resp, ms

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(run, jobs))

    by_trap = defaultdict(lambda: [0, 0, 0])  # n, jev ok, heuristic ok
    rows = []
    for kind, i, resp, _ms in results:
        if kind != "rel":
            continue
        trap, new, old, gold = CASES[i]
        a = resp["answers"]["rel_m1"]
        base = baseline_relation([], new, old)
        by_trap[trap][0] += 1
        by_trap[trap][1] += a["choice"] == gold
        by_trap[trap][2] += base == gold
        rows.append({"trap": trap, "new": new, "old": old, "gold": gold, "pred": a["choice"],
                     "conf": a.get("confidence"), "probs": a.get("probabilities"), "baseline": base})

    n = len(rows)
    print(f"RELATION (adversarial, n={n}): Jev {sum(r['pred'] == r['gold'] for r in rows) / n:.1%}"
          f"   heuristic {sum(r['baseline'] == r['gold'] for r in rows) / n:.1%}")
    for trap, (k, ok, bok) in by_trap.items():
        print(f"  {trap:<10} n={k}  Jev {ok}/{k}   heuristic {bok}/{k}")
    print("  calibration:")
    for lo, hi in ((0.9, 1.01), (0.7, 0.9), (0.0, 0.7)):
        sel = [r for r in rows if r["conf"] is not None and lo <= r["conf"] < hi]
        if sel:
            print(f"    [{lo:.1f},{min(hi, 1):.1f}) {len(sel):>2} judgments, accuracy {sum(r['pred'] == r['gold'] for r in sel) / len(sel):.0%}")
    for r in rows:
        if r["pred"] != r["gold"]:
            print(f"  ✗ [{r['trap']}] gold={r['gold']} jev={r['pred']} conf={r['conf']:.2f}: {r['new']!r} vs {r['old']!r}")

    drows = []
    for kind, i, resp, _ms in results:
        if kind == "dur":
            text, gold = DURABLE_HARD[i]
            p = resp["answers"]["durable"]["noul"]
            drows.append({"text": text, "gold": gold, "p": p, "baseline": baseline_durable(text)})
    m = len(drows)
    print(f"\nDURABLE (hard, n={m}): Jev {sum((r['p'] >= 0.5) == r['gold'] for r in drows) / m:.1%}"
          f"   heuristic {sum(r['baseline'] == r['gold'] for r in drows) / m:.1%}")
    for r in drows:
        mark = "✓" if (r["p"] >= 0.5) == r["gold"] else "✗"
        print(f"  {mark} p={r['p']:.2f} gold={r['gold']!s:<5} {r['text']!r}")

    out = HERE / "results" / f"jev_adversarial_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps({"relation": rows, "durable": drows}, ensure_ascii=False, indent=1))
    print(f"\nsaved {out.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
