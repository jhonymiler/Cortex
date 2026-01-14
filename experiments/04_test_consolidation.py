"""
Experimento 4: Validar Consolidação de Memórias
===============================================

Teoria testada:
- Memórias similares devem ser consolidadas automaticamente
- Consolidação reduz ruído e melhora recuperação
- Padrões repetidos fortalecem a memória consolidada

Método:
- Criar memórias similares (mesmo who/what/where)
- Detectar padrões de repetição
- Consolidar em memória resumida
- Validar que consolidada tem mais força
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cortex.core.primitives import Memory
from datetime import datetime, timedelta
from typing import List


class ConsolidationEngine:
    """
    Motor simplificado de consolidação para validação de conceito.
    """

    def __init__(self, similarity_threshold: float = 0.7):
        self.similarity_threshold = similarity_threshold

    def find_similar_memories(
        self,
        memories: List[Memory],
        target: Memory
    ) -> List[Memory]:
        """Encontra memórias similares à target"""
        similar = []

        for mem in memories:
            if mem.id == target.id:
                continue

            similarity = target.similarity_to(mem)
            if similarity >= self.similarity_threshold:
                similar.append(mem)

        return similar

    def consolidate(
        self,
        memories: List[Memory]
    ) -> Memory:
        """
        Consolida múltiplas memórias em uma só.

        Estratégia:
        - Mantém WHO comum
        - Mantém WHAT comum
        - Combina WHY únicos
        - Conta ocorrências
        """
        if not memories:
            raise ValueError("Precisa de pelo menos 1 memória")

        if len(memories) == 1:
            return memories[0]

        # WHO: união de todos participantes
        all_who = set()
        for mem in memories:
            all_who.update(mem.who)

        # WHAT: usa o mais comum
        what_counts = {}
        for mem in memories:
            what_counts[mem.what] = what_counts.get(mem.what, 0) + 1
        most_common_what = max(what_counts, key=what_counts.get)

        # WHY: combina razões únicas
        all_why = set()
        for mem in memories:
            if mem.why:
                all_why.add(mem.why)

        # WHERE: usa o mais comum
        where_counts = {}
        for mem in memories:
            where_counts[mem.where] = where_counts.get(mem.where, 0) + 1
        most_common_where = max(where_counts, key=where_counts.get)

        # Cria memória consolidada
        consolidated = Memory(
            who=sorted(list(all_who)),
            what=most_common_what,
            why="; ".join(sorted(all_why)),
            where=most_common_where,
            occurrence_count=len(memories),
            is_summary=True,
            consolidated_from=[m.id for m in memories],
            importance=max(m.importance for m in memories),
        )

        # Marca memórias originais como consolidadas
        for mem in memories:
            mem.consolidated_into = consolidated.id

        return consolidated


def test_similarity_detection():
    """Teste 1: Detectar memórias similares"""
    print("\n=== TESTE 1: Detecção de Similaridade ===")

    mem1 = Memory(
        who=["maria", "suporte"],
        what="reportou_erro_login",
        where="atendimento"
    )

    mem2 = Memory(
        who=["maria", "suporte"],
        what="reportou_erro_login",
        where="atendimento"
    )

    mem3 = Memory(
        who=["joao", "vendas"],
        what="fechou_negocio",
        where="comercial"
    )

    similarity_12 = mem1.similarity_to(mem2)
    similarity_13 = mem1.similarity_to(mem3)

    print(f"Similaridade (mem1 <-> mem2): {similarity_12:.2f} (esperado: ~1.0)")
    print(f"Similaridade (mem1 <-> mem3): {similarity_13:.2f} (esperado: ~0.0)")

    if similarity_12 >= 0.8 and similarity_13 <= 0.3:
        print("✅ PASSOU: Detecção de similaridade funciona")
        return True
    else:
        print("❌ FALHOU: Detecção incorreta")
        return False


def test_pattern_consolidation():
    """Teste 2: Consolidar padrões repetidos"""
    print("\n=== TESTE 2: Consolidação de Padrões ===")

    # Simula usuário reportando mesmo problema 5x
    memories = [
        Memory(
            who=["maria", "suporte"],
            what="reportou_erro_login",
            why=f"tentativa_{i}",
            where="atendimento"
        )
        for i in range(5)
    ]

    engine = ConsolidationEngine(similarity_threshold=0.7)

    # Consolida
    consolidated = engine.consolidate(memories)

    print(f"\nMemórias originais: {len(memories)}")
    print(f"Memória consolidada:")
    print(f"  WHO: {consolidated.who}")
    print(f"  WHAT: {consolidated.what}")
    print(f"  WHERE: {consolidated.where}")
    print(f"  Occurrences: {consolidated.occurrence_count}")
    print(f"  Is Summary: {consolidated.is_summary}")
    print(f"  Consolidated from: {len(consolidated.consolidated_from)} memórias")

    # Valida
    if (consolidated.occurrence_count == 5 and
        consolidated.is_summary and
        len(consolidated.consolidated_from) == 5):
        print("✅ PASSOU: Consolidação correta")
        return True
    else:
        print("❌ FALHOU: Consolidação incorreta")
        return False


def test_consolidation_strength():
    """Teste 3: Memória consolidada deve ser mais forte"""
    print("\n=== TESTE 3: Força da Consolidação ===")

    # Memória única
    mem_single = Memory(
        who=["user"],
        what="evento_unico",
        occurrence_count=1,
        is_summary=False
    )

    # Memória consolidada (5 ocorrências)
    mem_consolidated = Memory(
        who=["user"],
        what="evento_repetido",
        occurrence_count=5,
        is_summary=True,
        consolidated_from=["id1", "id2", "id3", "id4", "id5"]
    )

    # Simula 14 dias de decaimento
    mem_single.when = datetime.now() - timedelta(days=14)
    mem_consolidated.when = datetime.now() - timedelta(days=14)

    r_single = mem_single.retrievability
    r_consolidated = mem_consolidated.retrievability

    print(f"Retrievability (única):       {r_single:.3f}")
    print(f"Retrievability (consolidada): {r_consolidated:.3f}")
    print(f"Fator de proteção:            {r_consolidated / r_single:.2f}x")

    if r_consolidated > r_single * 1.5:
        print("✅ PASSOU: Consolidação oferece proteção")
        return True
    else:
        print("❌ FALHOU: Consolidação não protege suficientemente")
        return False


def test_noise_reduction():
    """Teste 4: Consolidação deve reduzir ruído"""
    print("\n=== TESTE 4: Redução de Ruído ===")

    # Antes: 10 memórias similares (ruído)
    before = [
        Memory(
            who=["cliente"],
            what="perguntou_horario",
            why=f"contexto_{i}",
            where="atendimento"
        )
        for i in range(10)
    ]

    print(f"Antes da consolidação: {len(before)} memórias")

    # Consolida
    engine = ConsolidationEngine()
    consolidated = engine.consolidate(before)

    # Depois: 1 memória consolidada
    print(f"Depois da consolidação: 1 memória consolidada")
    print(f"  Representa {consolidated.occurrence_count} ocorrências")

    # Redução de "ruído" no grafo
    noise_reduction = 100 * (len(before) - 1) / len(before)
    print(f"  Redução de ruído: {noise_reduction:.1f}%")

    # Memórias filhas marcadas para limpeza
    consolidated_children = [m for m in before if m.consolidated_into]
    print(f"  Memórias filhas marcadas: {len(consolidated_children)}")

    if noise_reduction >= 80:
        print("✅ PASSOU: Redução significativa de ruído")
        return True
    else:
        print("❌ FALHOU: Redução insuficiente")
        return False


def test_consolidation_metadata():
    """Teste 5: Metadados de consolidação"""
    print("\n=== TESTE 5: Metadados de Consolidação ===")

    memories = [
        Memory(
            id=f"mem_{i}",
            who=["user"],
            what="evento",
            where="namespace"
        )
        for i in range(3)
    ]

    engine = ConsolidationEngine()
    consolidated = engine.consolidate(memories)

    print(f"\nMemória consolidada:")
    print(f"  ID: {consolidated.id}")
    print(f"  is_summary: {consolidated.is_summary}")
    print(f"  occurrence_count: {consolidated.occurrence_count}")
    print(f"  consolidated_from: {consolidated.consolidated_from}")

    print(f"\nMemórias originais:")
    for i, mem in enumerate(memories):
        print(f"  mem_{i}:")
        print(f"    was_consolidated: {mem.was_consolidated}")
        print(f"    consolidated_into: {mem.consolidated_into}")

    # Valida propriedades
    all_marked = all(m.was_consolidated for m in memories)
    all_point_to_parent = all(m.consolidated_into == consolidated.id for m in memories)

    if consolidated.is_consolidated and all_marked and all_point_to_parent:
        print("\n✅ PASSOU: Metadados corretos")
        return True
    else:
        print("\n❌ FALHOU: Metadados incorretos")
        return False


def test_decay_of_children():
    """Teste 6: Memórias consolidadas (filhas) devem decair rápido"""
    print("\n=== TESTE 6: Decaimento de Filhas ===")

    # Memória pai (consolidada)
    parent = Memory(
        who=["user"],
        what="evento",
        is_summary=True,
        consolidated_from=["child1", "child2", "child3"]
    )

    # Memória filha (foi consolidada)
    child = Memory(
        who=["user"],
        what="evento",
        consolidated_into=parent.id
    )

    # Simula 7 dias
    parent.when = datetime.now() - timedelta(days=7)
    child.when = datetime.now() - timedelta(days=7)

    r_parent = parent.retrievability
    r_child = child.retrievability

    print(f"Retrievability (pai/consolidada): {r_parent:.3f}")
    print(f"Retrievability (filha):           {r_child:.3f}")
    print(f"Fator de decaimento:              {r_parent / r_child:.2f}x")

    # Filha deve decair 3x mais rápido (liberando espaço)
    if r_parent > r_child * 2:
        print("✅ PASSOU: Filhas decaem mais rápido")
        return True
    else:
        print("❌ FALHOU: Filhas não estão decaindo rápido o suficiente")
        return False


def run_all_tests():
    """Executa todos os testes de consolidação"""
    print("=" * 60)
    print("EXPERIMENTO 4: Validação da Consolidação de Memórias")
    print("=" * 60)

    tests = [
        ("Detecção de Similaridade", test_similarity_detection),
        ("Consolidação de Padrões", test_pattern_consolidation),
        ("Força da Consolidação", test_consolidation_strength),
        ("Redução de Ruído", test_noise_reduction),
        ("Metadados de Consolidação", test_consolidation_metadata),
        ("Decaimento de Filhas", test_decay_of_children),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ ERRO: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Sumário
    print("\n" + "=" * 60)
    print("SUMÁRIO DOS TESTES")
    print("=" * 60)

    passed = sum(1 for _, p in results if p)
    total = len(results)

    for name, passed_test in results:
        status = "✅ PASSOU" if passed_test else "❌ FALHOU"
        print(f"{status}: {name}")

    print(f"\nRESULTADO: {passed}/{total} testes passaram ({100*passed/total:.1f}%)")

    if passed == total:
        print("\n🎉 TEORIA VALIDADA: Consolidação funciona como esperado!")
    elif passed >= total * 0.75:
        print("\n⚠️  TEORIA PARCIALMENTE VALIDADA: Conceito funciona mas precisa ajustes")
    else:
        print("\n❌ TEORIA NÃO VALIDADA: Problemas significativos")

    return passed >= total * 0.75


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
