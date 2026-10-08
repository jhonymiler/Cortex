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
    yield e
    e.close()


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
