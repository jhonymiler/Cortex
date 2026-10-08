"""
Tests for the 0.4 engine: indexed graph, incremental SQLite store, memory
levels, and the regressions fixed along the way.
"""

import subprocess
import sys
from datetime import datetime, timedelta

import pytest

from cortext import CortexV5, Memory, MemoryGraph
from cortext.core.decay import memory_tier, retrievability
from cortext.core.recall import RegexExtractor, StructuralQueryParser, pack_for_context
from cortext.core.validation import CanonicalValidator
from cortext.store import SQLiteStore
from cortext.workers import DreamAgent


# --- regressions --------------------------------------------------------------

def test_pack_separates_memories_with_newlines():
    """Regression: lines were joined with "" — two memories ran together."""
    mems = [Memory(who=["A"], what="first fact"), Memory(who=["B"], what="second fact")]
    packed = pack_for_context(mems, None, max_tokens=200)
    assert packed.splitlines() == ["A | first fact", "B | second fact"]


def test_pack_includes_outcome():
    packed = pack_for_context([Memory(who=["Ana"], what="pediu deploy", how="feito via Helm")])
    assert packed == "Ana | pediu deploy → feito via Helm"


@pytest.mark.parametrize("query,who", [
    ("O que Ana pediu?", "ana"),
    ("O que a Ana pediu?", "ana"),
    ("Onde Otávio mora?", "otávio"),
    ("quem é a Alice?", "alice"),
])
def test_names_starting_with_article_letters(query, who):
    """Regression: the optional article ate the first letter ("Ana" -> "na")."""
    assert RegexExtractor().extract(query).who == [who]


def test_memory_roundtrip_keeps_consolidation_state():
    """Regression: to_dict dropped lang and every consolidation field."""
    m = Memory(who=["X"], what="merged one", lang="pt", is_summary=True,
               consolidated_from=["a", "b"], consolidated_into="c", occurrence_count=3)
    back = Memory.from_dict(m.to_dict())
    assert (back.lang, back.is_summary, back.consolidated_from, back.consolidated_into, back.occurrence_count) == \
        ("pt", True, ["a", "b"], "c", 3)


def test_recall_and_pack_accepts_intent():
    """Regression: recall_and_pack passed a dict where QueryIntent was expected."""
    g = MemoryGraph()
    g.add_memory(Memory(who=["Maria"], what="pediu reembolso"))
    out = StructuralQueryParser(enable_embedding_recall=False).recall_and_pack("O que Maria pediu?", g)
    assert "Maria" in out


def test_archived_memories_do_not_take_top_k_slots():
    """Regression: merged-away memories were filtered after top-k."""
    c = CortexV5(enable_embedding_recall=False)
    canonical, _ = c.remember(who=["Ana"], what="Ana pediu relatório mensal", validate=False)
    for i in range(5):
        dup, _ = c.remember(who=["Ana"], what=f"Ana pediu relatório mensal {i}", validate=False, importance=0.9)
        dup.consolidated_into = canonical.id
    _, result = c.recall("O que Ana pediu?", max_results=1)
    assert [m.id for m in result.memories] == [canonical.id]


def test_validator_history_is_bounded():
    v = CanonicalValidator(history_size=10)
    g = MemoryGraph()
    for i in range(50):
        v.validate_write(Memory(what=f"fato {i}"), g)
    assert len(v.get_history()) == 10


def test_decay_counts_from_storage_not_event_time():
    m = Memory(what="nasceu em Recife", when=datetime(1990, 5, 1))
    assert retrievability(m) > 0.95


# --- indexes ------------------------------------------------------------------

def test_direct_table_writes_keep_indexes_in_sync():
    g = MemoryGraph()
    g._memories["k1"] = Memory(who=["Maria Silva"], what="pediu reembolso")
    assert g.ids_for_who("Maria") == {"k1"}
    assert g.ids_for_token("reembolso") == {"k1"}
    g._memories.pop("k1")
    assert g.ids_for_who("Maria") == set()
    assert g.ids_for_token("reembolso") == set()


def test_reindex_after_edit():
    g = MemoryGraph()
    m = g.add_memory(Memory(what="usa redis"))
    m.what = "usa memcached"
    g.reindex(m)
    assert g.ids_for_token("memcached") == {m.id}
    assert g.ids_for_token("redis") == set()


def test_accent_folding_matches():
    g = MemoryGraph()
    m = g.add_memory(Memory(what="não usar migração manual"))
    assert m.id in g.ids_for_tokens(["nao", "migracao"])


def test_remove_memory_drops_its_relations():
    from cortext import Relation

    g = MemoryGraph()
    m = g.add_memory(Memory(what="x fact"))
    g.add_relation(Relation(from_id=m.id, relation_type="related_to", to_id="other"))
    g.remove_memory(m.id)
    assert g.find_relations(to_id="other") == []


def test_recall_scales_sublinearly():
    """10k unrelated memories must not slow a targeted recall to a scan."""
    import time

    c = CortexV5(enable_embedding_recall=False)
    for i in range(10_000):
        c.remember(who=[f"P{i % 500}"], what=f"evento{i} item{i % 997}", validate=False)
    t0 = time.perf_counter()
    for _ in range(50):
        c.recall("O que P7 fez?", touch=False)
    assert (time.perf_counter() - t0) / 50 < 0.02  # generous: ~0.5 ms in practice


# --- SQLite store ---------------------------------------------------------------

def test_sqlite_store_persists_incrementally(tmp_path):
    db = tmp_path / "m.db"
    c = CortexV5(namespace="ns1", path=db, enable_embedding_recall=False)
    a, _ = c.remember(who=["Ana"], what="prefere PRs curtos")
    b, _ = c.remember(who=["Bruno"], what="cuida do estoque")
    assert c.flush() == 0  # autosave already wrote them
    c.forget(b.id)
    c.close()

    c2 = CortexV5(namespace="ns1", path=db, enable_embedding_recall=False)
    assert c2.get(a.id) is not None and c2.get(b.id) is None
    c2.recall("O que Ana prefere?")
    assert c2.flush() == 1  # only the touched memory is rewritten
    c2.close()


def test_sqlite_namespaces_are_isolated(tmp_path):
    store = SQLiteStore(tmp_path / "m.db")
    one = CortexV5(namespace="a", store=store, enable_embedding_recall=False)
    two = CortexV5(namespace="b", store=store, enable_embedding_recall=False)
    one.remember(what="só em a")
    assert len(two.graph) == 0
    assert set(store.namespaces()) == {"a"}


def test_consolidation_survives_reload(tmp_path):
    db = tmp_path / "m.db"
    c = CortexV5(path=db, enable_dream_agent=True, enable_embedding_recall=False)
    for _ in range(3):
        c.remember(who=["Ana"], what="Ana pediu commits em inglês", validate=False)
    c.run_dream_cycle()
    archived = sum(1 for m in c.graph.iter_memories() if m.consolidated_into)
    assert archived == 2
    c.close()
    c2 = CortexV5(path=db, enable_embedding_recall=False)
    assert sum(1 for m in c2.graph.iter_memories() if m.consolidated_into) == 2


# --- memory levels ----------------------------------------------------------------

def test_memory_tiers():
    now = datetime.now()
    old = now - timedelta(days=3)
    assert memory_tier(Memory(what="novo"), now) == "working"
    assert memory_tier(Memory(what="evento", created_at=old, last_accessed=now), now) == "episodic"
    assert memory_tier(Memory(what="reforçada", created_at=old, access_count=5, last_accessed=now), now) == "semantic"
    assert memory_tier(Memory(what="velha", created_at=now - timedelta(days=40)), now) == "fading"
    assert memory_tier(Memory(what="unida", consolidated_into="x"), now) == "archived"


def test_levels_and_snapshot():
    c = CortexV5(enable_embedding_recall=False)
    c.remember(who=["Ana", "Bruno"], what="pareamento no checkout")
    levels = c.levels()
    assert levels["working"] == 1 and sum(levels.values()) == 1
    snap = c.graph_snapshot()
    kinds = sorted(n["kind"] for n in snap["nodes"])
    assert kinds == ["entity", "entity", "memory"]
    assert len(snap["links"]) == 2


# --- DreamAgent cleanup -----------------------------------------------------------

def test_cleanup_protects_important_and_takes_children_along():
    g = MemoryGraph()
    long_ago = datetime.now() - timedelta(days=400)
    keep = g.add_memory(Memory(what="decisão crítica", importance=0.9, created_at=long_ago))
    gone = g.add_memory(Memory(what="ruído antigo", importance=0.2, created_at=long_ago))
    child = g.add_memory(Memory(what="ruído antigo dup", importance=0.2, consolidated_into=gone.id))
    DreamAgent().run_cycle(g)
    assert g.get_memory(keep.id) is not None
    assert g.get_memory(gone.id) is None
    assert g.get_memory(child.id) is None  # no dangling consolidated_into


# --- packaging ---------------------------------------------------------------------

def test_import_is_lazy():
    """Hooks start a process per event: `import cortext` must not load the engine."""
    code = "import sys, cortext, cortext.server.client; print('cortext.cortex' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
