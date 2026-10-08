"""Background abstraction: window → extract → consolidate, with a scripted model."""

import json

import pytest

from cortext.server.engine import MemoryEngine


class Scripted:
    """A fake LLM: answers by job kind, records the prompts it saw."""

    name = "scripted"

    def __init__(self, extract, consolidate):
        self.extract, self.consolidate, self.prompts = extract, consolidate, []

    def complete(self, prompt, system=""):
        self.prompts.append(prompt)
        if prompt.startswith("Part of an agent session"):
            return "```json\n" + json.dumps(self.extract(prompt)) + "\n```"
        return json.dumps(self.consolidate(prompt))


@pytest.fixture()
def engine(tmp_path):
    e = MemoryEngine(tmp_path / "m.db", dream_interval_seconds=0, enable_embeddings=False, llm=None)
    e.abstractor.mode = "facts"
    yield e
    e.close()


@pytest.fixture()
def gate(tmp_path):
    e = MemoryEngine(tmp_path / "g.db", dream_interval_seconds=0, enable_embeddings=False, llm=None)
    assert e.abstractor.mode == "gate"  # the default
    yield e
    e.close()


def test_gate_keeps_raw_turns_archives_noise_and_indexes_facts(gate):
    llm = Scripted(extract=lambda p: {"facts": [{"fact": "Júlia cobre as entregas da Fernanda",
                                                 "en": "Julia covers Fernanda's deliverables"}]},
                   consolidate=lambda p: pytest.fail("gate mode never consolidates"))
    out = turns(gate, "hr", "s1", [
        ("o Rafael cobre a Fernanda na licença", "Anotado."),
        ("roda o linter de novo", "0 issues."),
        ("corrigindo: quem cobre a Fernanda é a Júlia", "Corrigido."),
        ("mostra o git status", "limpo"),
    ])
    gate.abstractor.drain(llm)
    c = gate.cortex("hr")
    states = [c.get(o["id"]).consolidated_into for o in out]
    assert states == [None, "abstracted:noise", None, "abstracted:noise"]
    # both raw turns stay: the agent sees the correction in order
    ctx = gate.recall("hr", "who covers Fernanda?")["context"]
    assert "Júlia" in ctx and "Rafael" in ctx


def turns(e, ns, session, pairs):
    return [e.capture_turn(ns, u, a, agent="test", session=session) for u, a in pairs]


def test_window_of_four_becomes_facts_and_turns_are_archived(engine):
    llm = Scripted(
        extract=lambda p: {"facts": ["Production deploys happen on Wednesdays because of the Thursday infra freeze"]},
        consolidate=lambda p: {"memories": [{"id": None, "what": "Production deploys happen on Wednesdays (Thursday infra freeze)"}], "retire": []},
    )
    out = turns(engine, "p", "s1", [
        ("vamos fazer deploy na quinta, como sempre", "Anotado."),
        ("corrige o typo no README por favor", "Corrigido."),
        ("mudou: deploy agora é na quarta por causa do freeze", "Entendido."),
        ("roda os testes de integração de novo", "Passaram."),
    ])
    assert "abstract_job" in out[-1] and all("abstract_job" not in o for o in out[:-1])
    assert engine.abstractor.drain(llm) == 2  # extract, then consolidate
    c = engine.cortex("p")
    active = [m for m in c.graph.iter_memories() if not m.consolidated_into]
    assert [m.what for m in active] == ["Production deploys happen on Wednesdays (Thursday infra freeze)"]
    assert active[0].metadata["kind"] == "fact" and len(active[0].metadata["from_turns"]) == 4
    assert all(c.get(o["id"]).consolidated_into == active[0].id for o in out)
    ctx = engine.recall("p", "em que dia fazemos deploy?")["context"]
    assert "Wednesdays" in ctx and "quinta" not in ctx


def test_consolidation_updates_and_retires_existing_memories(engine):
    c = engine.cortex("p")
    old, _ = c.remember(what="The catalog cache TTL is 1 hour in Redis", importance=0.7)
    gone, _ = c.remember(what="The catalog cache is never invalidated on price changes", importance=0.7)
    seen = {}

    def consolidate(prompt):
        seen["prompt"] = prompt
        return {"memories": [{"id": old.id[:8], "what": "The catalog cache TTL is 10 minutes in Redis"}],
                "retire": [gone.id[:8]]}

    llm = Scripted(extract=lambda p: {"facts": ["Catalog cache TTL is now 10 minutes"]}, consolidate=consolidate)
    turns(engine, "p", "s2", [("usa 10 minutos de TTL no cache do catálogo", "Feito.")])
    engine.end_session("p", "s2")
    engine.abstractor.drain(llm)
    assert old.id[:8] in seen["prompt"] and gone.id[:8] in seen["prompt"]  # related memories were offered
    assert old.what == "The catalog cache TTL is 10 minutes in Redis"
    assert old.metadata["history"] == ["The catalog cache TTL is 1 hour in Redis"]
    assert gone.consolidated_into == "superseded"


def test_noise_window_is_archived_without_a_consolidate_call(engine):
    llm = Scripted(extract=lambda p: {"facts": []}, consolidate=lambda p: pytest.fail("no consolidate for noise"))
    out = turns(engine, "p", "s3", [("roda o linter agora", "0 issues."), ("mostra o git status", "limpo"),
                                     ("formata o arquivo main", "ok"), ("faz o build de novo", "41s")])
    engine.abstractor.drain(llm)
    c = engine.cortex("p")
    assert all(c.get(o["id"]).consolidated_into == "abstracted:noise" for o in out)
    assert engine.recall("p", "linter")["memories"] == []


def test_mod_style_worker_through_lease_and_complete(engine):
    turns(engine, "p", "s4", [("o banco principal é Postgres 15 com réplica", "Anotado.")])
    engine.end_session("p", "s4")
    job = engine.lease_job("mod")
    assert job["kind"] == "extract" and "Postgres 15" in job["prompt"] and job["model"] == "haiku"
    assert engine.complete_job(job["id"], '{"facts": [{"fact": "O banco principal é Postgres 15 com réplica", "en": "The main database is Postgres 15 with a replica"}]}')["ok"]
    job2 = engine.lease_job("mod")
    assert job2["kind"] == "consolidate"
    engine.complete_job(job2["id"], '{"memories": [{"id": null, "what": "O banco principal é Postgres 15 com réplica de leitura", "en": "The main database is Postgres 15 with a read replica"}], "retire": []}')
    assert engine.lease_job("mod") is None
    assert engine.queue.stats("p")["done"] == 2
    # stored in the user's language, findable in either
    assert "Postgres 15" in engine.recall("p", "qual banco principal usamos?")["context"]
    assert "Postgres 15" in engine.recall("p", "what is the main database?")["context"]


def test_failed_model_call_retries_then_fails(engine):
    class Broken:
        name = "broken"

        def complete(self, prompt, system=""):
            raise TimeoutError("model unavailable")

    turns(engine, "p", "s5", [("decidimos usar feature flags no LaunchDarkly", "ok")])
    engine.end_session("p", "s5")
    for _ in range(3):
        engine.abstractor.work_once(Broken())
    assert engine.queue.stats("p")["failed"] == 1
    # the raw turn is still recallable: a dead model never loses memory
    assert "LaunchDarkly" in engine.recall("p", "onde ficam as feature flags?")["context"]


def test_source_turn_words_make_the_fact_findable_and_names_become_who(engine):
    fact = {"fact": "Luis solo puede atender llamadas por la tarde", "en": "Luis can only take calls in the afternoon"}
    llm = Scripted(extract=lambda p: {"facts": [fact]},
                   consolidate=lambda p: {"memories": [{"id": None, "what": fact["fact"], "en": fact["en"]}], "retire": []})
    turns(engine, "c", "s6", [("Luis trabaja de noche, solo atiende llamadas por la tarde", "Anotado en el perfil.")])
    engine.end_session("c", "s6")
    engine.abstractor.drain(llm)
    m = [x for x in engine.cortex("c").graph.iter_memories() if not x.consolidated_into][0]
    assert m.who == ["Luis"]
    assert "trabaja" in m.alt and "noche" in m.alt  # the user's own words, from the source turn
    assert "tarde" in engine.recall("c", "¿Luis trabaja de noche?")["context"]


def test_guard_replaces_a_lossy_consolidation_with_the_source_fact():
    from cortext.server.abstraction import Abstractor, key_terms

    assert {"5433", "luis", "services/reconciliation"} <= key_terms(
        "Para falar com Luis, o banco roda na porta 5433 e o dono é services/reconciliation")
    facts = [{"fact": "Os testes de integração precisam do Postgres local na porta 5433", "en": ""},
             {"fact": "Luis prefere contato por e-mail, não WhatsApp", "en": "Luis prefers email, not WhatsApp"}]
    lossy = [{"id": None, "what": "Os testes de integração precisam de um banco local"},
             {"id": None, "what": "O canal preferido é o e-mail, não WhatsApp"}]
    out = Abstractor.guard(facts, lossy)
    assert [m["what"] for m in out] == [facts[0]["fact"], facts[1]["fact"]]
    good = [{"id": None, "what": "Testes de integração exigem Postgres local na porta 5433"},
            {"id": None, "what": "Luis prefere e-mail; não usa WhatsApp"}]
    assert Abstractor.guard(facts, good) == good


def test_gate_keeps_a_lone_correction_related_to_a_kept_memory(gate):
    windows = iter([
        {"facts": [{"fact": "Ledger deploys use a 5% canary for 30 minutes", "en": ""}]},
        {"facts": []},  # the correction alone among chatter looks like noise
    ])
    llm = Scripted(extract=lambda p: next(windows), consolidate=lambda p: pytest.fail("gate never consolidates"))
    turns(gate, "go", "s1", [("we deploy ledger with a canary at 5% for 30 minutes", "ok"),
                                     ("run go vet", "no issues"), ("show the diff", "here"), ("lgtm", "merged")])
    gate.abstractor.drain(llm)
    second = turns(gate, "go", "s1", [("add a log line here", "added"), ("run the linter", "0 issues"),
                                      ("lgtm", "merged"), ("actually make the canary 10%", "Changed to 10%.")])
    gate.abstractor.drain(llm)
    c = gate.cortex("go")
    assert c.get(second[3]["id"]).consolidated_into is None          # the correction stays
    assert c.get(second[1]["id"]).consolidated_into == "abstracted:noise"
    ctx = gate.recall("go", "what canary do we use for ledger?")["context"]
    assert ctx.index("5%") < ctx.index("10%")
