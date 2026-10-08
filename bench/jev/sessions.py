"""
Multi-turn agent sessions with planted durable facts, for comparing WHEN to
abstract memories (per turn, per turn with context, per window, per session).

Each turn has the user's prompt and the agent's answer (what it did/found).
GOLD lists the durable facts a good memory should end up holding after the
session, each tagged with the trap it tests:
  plain      — stated once, in one turn
  agent      — discovered by the agent (in the answer), not said by the user
  completed  — only complete when two turns are read together
  superseded — changed later in the session; only the final value is gold
STALE lists values that must NOT survive as current facts.

Written by Claude for this experiment; small and synthetic.
"""

SESSIONS = [
    {
        "id": "dev-pt", "lang": "pt",
        "turns": [
            ("roda os testes do módulo de pagamentos", "Rodei pytest tests/payments: 3 falhas, todas por falta da variável DATABASE_URL apontando para o Postgres de teste."),
            ("ah sim, aqui os testes de integração sempre precisam do Postgres local na porta 5433", "Configurei DATABASE_URL=postgresql://localhost:5433/test e os 3 testes passaram."),
            ("ok", "Certo."),
            ("vamos fazer deploy na quinta, como sempre", "Anotado: deploy de produção às quintas."),
            ("corrige o typo no README", "Corrigi 'pagametos' para 'pagamentos' no README."),
            ("na verdade mudou: a partir deste mês o deploy é às quartas, por causa do freeze de quinta do time de infra", "Entendido: deploys passam a ser às quartas por causa do freeze de quinta da infra."),
            ("quem é o dono do serviço de conciliação?", "Pelo CODEOWNERS, o dono de services/reconciliation é o time do Bruno."),
            ("valeu", "De nada!"),
        ],
        "gold": [
            ("plain", "Integration tests need a local Postgres on port 5433 (DATABASE_URL)"),
            ("superseded", "Production deploys happen on Wednesdays because infra has a Thursday freeze"),
            ("agent", "The reconciliation service (services/reconciliation) is owned by Bruno's team"),
        ],
        "stale": ["Production deploys happen on Thursdays"],
    },
    {
        "id": "dev-en", "lang": "en",
        "turns": [
            ("why is the checkout endpoint slow?", "Profiled it: 80% of the time is an N+1 query loading cart items. Added a select_related; p95 went from 1.8s to 220ms."),
            ("nice. we never use raw SQL in this repo, always the ORM", "Understood, I kept the fix in the ORM."),
            ("run the linter", "ruff: 0 issues."),
            ("the billing module", "Which change do you want in the billing module?"),
            ("must never import from ui/. add a check for that", "Added an import-linter contract forbidding billing -> ui and wired it into CI."),
            ("thanks", "You're welcome."),
            ("what's the coverage now?", "Total coverage is 81%."),
        ],
        "gold": [
            ("agent", "Checkout slowness was an N+1 query on cart items, fixed with select_related (p95 1.8s -> 220ms)"),
            ("plain", "The repo never uses raw SQL; always the ORM"),
            ("completed", "The billing module must never import from ui/ (enforced by an import-linter contract in CI)"),
        ],
        "stale": [],
    },
    {
        "id": "support-es", "lang": "es",
        "turns": [
            ("el cliente Luis de la cuenta 2291 llamó otra vez por la factura duplicada", "Revisé la cuenta 2291: hay dos facturas del 3 de octubre por el mismo pedido. Abrí el ticket FAC-118 para anular una."),
            ("él solo puede atender llamadas por la tarde, trabaja de noche", "Anotado en el perfil: contactar a Luis solo por la tarde."),
            ("ok gracias", "De nada."),
            ("prefiere que le escribamos por WhatsApp", "Perfecto, canal preferido: WhatsApp."),
            ("perdón, me equivoqué: él no usa WhatsApp, solo correo electrónico", "Corregido: el canal preferido de Luis es el correo electrónico, no WhatsApp."),
            ("¿cuánto tarda la anulación?", "La anulación de FAC-118 tarda hasta 5 días hábiles."),
        ],
        "gold": [
            ("agent", "Customer Luis (account 2291) has a duplicate invoice from Oct 3; ticket FAC-118 opened to void one"),
            ("plain", "Luis can only take calls in the afternoon because he works at night"),
            ("superseded", "Luis's preferred channel is email; he does not use WhatsApp"),
        ],
        "stale": ["Luis prefers to be contacted on WhatsApp"],
    },
    {
        "id": "edu-pt", "lang": "pt",
        "turns": [
            ("prepara uma lista de exercícios de frações para a turma do 6º B", "Montei 12 exercícios de frações, do básico ao intermediário."),
            ("o João dessa turma tem muita dificuldade com denominadores diferentes", "Vou incluir 3 exercícios extras de soma com denominadores diferentes, com dicas."),
            ("e a Beatriz precisa de prova adaptada por causa da dislexia: fonte maior e enunciados curtos", "Gerei uma versão adaptada para a Beatriz com fonte 16 e enunciados curtos."),
            ("perfeito", "Ótimo!"),
            ("a escola pede que toda lista seja entregue na sexta", "Adicionei 'entrega: sexta-feira' no cabeçalho."),
            ("imprime em PDF", "PDF gerado: lista-fracoes-6B.pdf."),
        ],
        "gold": [
            ("plain", "Student João (6th grade B) struggles with adding fractions with different denominators"),
            ("plain", "Student Beatriz needs adapted tests due to dyslexia: larger font and short statements"),
            ("plain", "The school requires every exercise list to be handed in on Friday"),
        ],
        "stale": [],
    },
    {
        "id": "dev-mixed", "lang": "pt/en",
        "turns": [
            ("configura o cache do catálogo", "Coloquei Redis com TTL de 1 hora para o catálogo."),
            ("1 hora é muito, os preços mudam toda hora. usa 10 minutos", "Ajustei o TTL do cache do catálogo para 10 minutos."),
            ("and invalidate the product entry right away when its price changes", "Added an invalidation hook on price updates that deletes the product's cache key immediately."),
            ("show me the diff", "Here is the diff of catalog/cache.py and catalog/signals.py."),
            ("lgtm", "Merged."),
        ],
        "gold": [
            ("completed", "The catalog cache uses Redis with a 10-minute TTL and is invalidated immediately when a product price changes"),
        ],
        "stale": ["The catalog cache TTL is 1 hour"],
    },
]


# Held-out set: written after the abstraction prompt and recall were tuned on
# SESSIONS, before running anything on these. Used to check that the tuning
# generalizes instead of fitting the first set.
HELDOUT_SESSIONS = [
    {
        "id": "hr-pt", "lang": "pt",
        "turns": [
            ("preciso montar o plano de férias do time de dados", "Montei uma planilha com os períodos solicitados por cada pessoa."),
            ("a Fernanda vai sair de licença-maternidade em março, por 6 meses", "Registrado: Fernanda em licença de março a agosto."),
            ("quem cobre as entregas dela nesse período é o Rafael", "Anotado: Rafael assume as entregas da Fernanda durante a licença."),
            ("ok", "Certo."),
            ("e lembra: aqui as avaliações de desempenho são sempre em junho e dezembro", "Anotado: ciclos de avaliação em junho e dezembro."),
            ("corrigindo: o Rafael vai estar alocado no projeto novo, quem cobre a Fernanda é a Júlia", "Corrigido: Júlia cobre as entregas da Fernanda, não o Rafael."),
        ],
        "gold": [("plain", "Fernanda will be on maternity leave from March for 6 months"),
                 ("superseded", "Júlia covers Fernanda's work during the leave (not Rafael)"),
                 ("plain", "Performance reviews happen in June and December")],
        "stale": ["Rafael covers Fernanda's work during the leave"],
    },
    {
        "id": "course-en", "lang": "en",
        "turns": [
            ("grade the quiz answers from module 2", "Graded: class average 7.4; question 5 had the most errors (confusing variance with standard deviation)."),
            ("Tom asked for an extension on the module 3 project", "Noted the request."),
            ("approved, he has until Friday the 18th because of a family emergency", "Recorded: Tom's module 3 deadline extended to Friday the 18th."),
            ("thanks", "You're welcome."),
            ("for next term, students must submit projects as notebooks, never as PDFs", "Noted the submission format rule for next term."),
        ],
        "gold": [("agent", "In the module 2 quiz most students confused variance with standard deviation (question 5)"),
                 ("completed", "Tom's module 3 project deadline was extended to Friday the 18th (family emergency)"),
                 ("plain", "From next term, projects must be submitted as notebooks, never PDFs")],
        "stale": [],
    },
    {
        "id": "shop-es", "lang": "es",
        "turns": [
            ("analiza las devoluciones del último mes", "El 38% de las devoluciones son de la talla M de la línea Andes: los clientes dicen que viene pequeña."),
            ("ok, vamos a avisar en la ficha del producto", "Agregué una nota 'talla pequeña, se recomienda pedir una más' en la línea Andes."),
            ("la clienta Carmen siempre compra para regalo, mándale los pedidos sin factura en la caja", "Anotado en el perfil de Carmen: pedidos sin factura dentro de la caja."),
            ("gracias", "De nada."),
            ("el envío gratis ahora empieza en 50 euros, no en 40", "Actualicé el umbral de envío gratis a 50 euros."),
        ],
        "gold": [("agent", "38% of last month's returns were size M of the Andes line, which runs small"),
                 ("plain", "Customer Carmen buys gifts: ship her orders without the invoice in the box"),
                 ("superseded", "Free shipping starts at 50 euros")],
        "stale": ["Free shipping starts at 40 euros"],
    },
    {
        "id": "go-en", "lang": "en",
        "turns": [
            ("the ledger service keeps leaking goroutines, find out why", "Found it: the HTTP client in ledger/sync.go never closes response bodies on non-200 replies. Added defer resp.Body.Close() and a leak test."),
            ("we deploy ledger with a canary at 5% for 30 minutes before full rollout", "Understood, I'll keep the canary step in the pipeline."),
            ("run go vet", "go vet: no issues."),
            ("actually make the canary 10%", "Changed the canary to 10% for 30 minutes."),
        ],
        "gold": [("agent", "The ledger service leaked goroutines because ledger/sync.go did not close response bodies on non-200 replies; fixed with defer resp.Body.Close()"),
                 ("superseded", "Ledger deploys use a 10% canary for 30 minutes before full rollout")],
        "stale": ["Ledger deploys use a 5% canary"],
    },
]
