"""
Experimento 1: Validar se o decaimento cognitivo funciona
==========================================================

Teoria testada:
- Memórias devem decair exponencialmente com o tempo (curva de Ebbinghaus)
- Memórias acessadas frequentemente devem decair mais lentamente
- Hubs (memórias conectadas) devem ser protegidos
- Memórias consolidadas devem durar mais

Método:
- Criar memórias com diferentes padrões de acesso
- Simular passagem de tempo
- Verificar se o retrievability segue curva esperada
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from datetime import datetime, timedelta
from cortex.core.memory import Memory
import math


def test_basic_decay():
    """Teste 1: Memória deve decair exponencialmente"""
    print("\n=== TESTE 1: Decaimento Básico ===")

    mem = Memory(
        who=["usuario"],
        what="teste_inicial",
        stability=7.0  # 7 dias base
    )

    # Simula passagem de tempo alterando when
    results = []
    for days in [0, 1, 3, 7, 14, 30]:
        # Simula tempo desde criação
        mem.when = datetime.now() - timedelta(days=days)
        mem.last_accessed = None  # Força usar when

        retrievability = mem.retrievability
        expected = math.exp(-days / 7.0)

        results.append({
            'dias': days,
            'retrievability': retrievability,
            'esperado': expected,
            'diferenca': abs(retrievability - expected)
        })

        print(f"Dia {days:2d}: R={retrievability:.3f} (esperado: {expected:.3f})")

    # Valida que segue curva de Ebbinghaus
    max_error = max(r['diferenca'] for r in results)
    print(f"\n✓ Erro máximo: {max_error:.4f}")

    if max_error < 0.01:
        print("✅ PASSOU: Curva de decaimento correta")
        return True
    else:
        print("❌ FALHOU: Desvio da curva esperada")
        return False


def test_access_protection():
    """Teste 2: Memórias acessadas devem decair mais lentamente"""
    print("\n=== TESTE 2: Proteção por Acesso ===")

    # Memória nunca acessada
    mem_never = Memory(who=["user"], what="nunca_acessada", stability=7.0)
    mem_never.when = datetime.now() - timedelta(days=7)
    mem_never.last_accessed = None

    # Memória acessada 10x
    mem_accessed = Memory(who=["user"], what="muito_acessada", stability=7.0)
    mem_accessed.when = datetime.now() - timedelta(days=7)
    mem_accessed.access_count = 10
    mem_accessed.last_accessed = datetime.now() - timedelta(days=7)

    r_never = mem_never.retrievability
    r_accessed = mem_accessed.retrievability

    print(f"Nunca acessada (7 dias): R={r_never:.3f}")
    print(f"Acessada 10x (7 dias):   R={r_accessed:.3f}")
    print(f"Diferença: {r_accessed - r_never:.3f}")

    if r_accessed > r_never * 1.5:
        print("✅ PASSOU: Acesso protege contra decaimento")
        return True
    else:
        print("❌ FALHOU: Acesso não oferece proteção suficiente")
        return False


def test_consolidation_protection():
    """Teste 3: Memórias consolidadas devem durar mais"""
    print("\n=== TESTE 3: Proteção por Consolidação ===")

    # Memória normal
    mem_normal = Memory(who=["user"], what="evento_unico")
    mem_normal.when = datetime.now() - timedelta(days=14)

    # Memória consolidada (resumo de múltiplas)
    mem_consolidated = Memory(
        who=["user"],
        what="evento_repetido",
        occurrence_count=5,
        is_summary=True,
        consolidated_from=["id1", "id2", "id3", "id4", "id5"]
    )
    mem_consolidated.when = datetime.now() - timedelta(days=14)

    r_normal = mem_normal.retrievability
    r_consolidated = mem_consolidated.retrievability

    print(f"Normal (14 dias):       R={r_normal:.3f}")
    print(f"Consolidada (14 dias):  R={r_consolidated:.3f}")
    print(f"Fator de proteção: {r_consolidated / r_normal:.2f}x")

    if r_consolidated > r_normal * 1.8:
        print("✅ PASSOU: Consolidação oferece proteção forte")
        return True
    else:
        print("❌ FALHOU: Consolidação não protege suficientemente")
        return False


def test_forgotten_threshold():
    """Teste 4: Memórias devem ser marcadas como esquecidas"""
    print("\n=== TESTE 4: Limiar de Esquecimento ===")

    mem = Memory(who=["user"], what="memoria_antiga")

    # Simula 60 dias sem acesso
    mem.when = datetime.now() - timedelta(days=60)
    mem.last_accessed = None

    r = mem.retrievability
    print(f"Retrievability após 60 dias: {r:.4f}")

    FORGOTTEN_THRESHOLD = 0.1

    if r < FORGOTTEN_THRESHOLD:
        print(f"✅ PASSOU: Memória abaixo do limiar ({FORGOTTEN_THRESHOLD})")
        return True
    else:
        print(f"❌ FALHOU: Memória ainda acima do limiar")
        return False


def test_spaced_repetition():
    """Teste 5: Revisões espaçadas devem fortalecer memória"""
    print("\n=== TESTE 5: Spaced Repetition ===")

    mem = Memory(who=["user"], what="aprendizado", stability=7.0)

    # Simula padrão de revisão: dia 0, 1, 3, 7
    access_pattern = [0, 1, 3, 7]

    print("\nPadrão de revisão espaçada:")
    for day in access_pattern:
        mem.touch()
        print(f"  Dia {day}: access_count={mem.access_count}, stability={mem.stability:.2f}")

    # Testa retrievability após 14 dias
    mem.last_accessed = datetime.now() - timedelta(days=14 - 7)  # 7 dias desde último acesso
    r = mem.retrievability

    print(f"\nRetrievability 14 dias após criação: {r:.3f}")

    # Compara com memória não revisada
    mem_no_review = Memory(who=["user"], what="sem_revisao", stability=7.0)
    mem_no_review.when = datetime.now() - timedelta(days=14)
    r_no_review = mem_no_review.retrievability

    print(f"Sem revisão (mesmo período):         {r_no_review:.3f}")
    print(f"Benefício da revisão espaçada:       {r / r_no_review:.2f}x")

    if r > r_no_review * 2:
        print("✅ PASSOU: Spaced repetition funciona")
        return True
    else:
        print("❌ FALHOU: Efeito de spaced repetition fraco")
        return False


def run_all_tests():
    """Executa todos os testes de decaimento"""
    print("=" * 60)
    print("EXPERIMENTO 1: Validação do Decaimento Cognitivo")
    print("=" * 60)

    tests = [
        ("Decaimento Exponencial", test_basic_decay),
        ("Proteção por Acesso", test_access_protection),
        ("Proteção por Consolidação", test_consolidation_protection),
        ("Limiar de Esquecimento", test_forgotten_threshold),
        ("Spaced Repetition", test_spaced_repetition),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ ERRO: {e}")
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
        print("\n🎉 TEORIA VALIDADA: O decaimento cognitivo funciona como esperado!")
    elif passed >= total * 0.8:
        print("\n⚠️  TEORIA PARCIALMENTE VALIDADA: Maioria dos testes passou")
    else:
        print("\n❌ TEORIA NÃO VALIDADA: Problemas significativos detectados")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)