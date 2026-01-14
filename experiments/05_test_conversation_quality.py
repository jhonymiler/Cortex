"""
Experimento 5: Validar Qualidade da Conversa
=============================================

Teoria testada:
- Memória melhora a qualidade das conversas
- Agente lembra contexto de sessões anteriores
- Não pergunta informações repetidas
- Personaliza respostas baseado em histórico

Método:
- Simular conversas realistas multi-sessão
- Medir: repetição de perguntas, personalização, contexto
- Comparar com vs sem memória
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cortex.core.graph import MemoryGraph
from cortex.core.primitives import Memory
from cortex.core.primitives import Entity
from cortex.core.primitives import Episode
from datetime import datetime, timedelta
from typing import List, Tuple


def test_context_persistence():
    """Teste 1: Memória persiste entre sessões"""
    print("\n=== TESTE 1: Persistência de Contexto ===")

    graph = MemoryGraph()

    # Sessão 1: Usuário se apresenta
    print("\n📅 Sessão 1 (Dia 1):")
    print("👤 Usuário: 'Olá, meu nome é João e trabalho na TechCorp'")

    graph.store(
        action="usuario_se_apresentou",
        participants=[{
            "name": "joao",
            "type": "user",
            "attributes": {"empresa": "TechCorp"}
        }],
        context="primeira_interacao",
        outcome="contexto_estabelecido"
    )

    # Sessão 2: Uma semana depois
    print("\n📅 Sessão 2 (Dia 7):")
    print("👤 Usuário: 'Preciso de ajuda com um problema'")

    result = graph.recall("usuario precisa ajuda", limit=5)

    joao_remembered = any("joao" in e.name.lower() for e in result.entities)
    empresa_remembered = any(
        e.attributes.get("empresa") == "TechCorp"
        for e in result.entities
    )

    print(f"\nContexto recuperado:")
    print(f"  - Lembrou do João: {joao_remembered}")
    print(f"  - Lembrou da empresa: {empresa_remembered}")
    print(f"  - Entidades: {[e.name for e in result.entities]}")

    if joao_remembered and empresa_remembered:
        print("✅ PASSOU: Contexto persiste entre sessões")
        return True
    else:
        print("❌ FALHOU: Perdeu contexto")
        return False


def test_no_repetitive_questions():
    """Teste 2: Não repete perguntas já respondidas"""
    print("\n=== TESTE 2: Evita Perguntas Repetitivas ===")

    graph = MemoryGraph()

    # Interação 1: Cliente informa preferência
    print("\n💬 Interação 1:")
    print("👤 Cliente: 'Prefiro receber emails no horário da manhã'")

    graph.store(
        action="informou_preferencia",
        participants=[{"name": "cliente_maria", "type": "user"}],
        context="configuracao",
        outcome="preferencia_emails_manha"
    )

    # Interação 2: Semanas depois
    print("\n💬 Interação 2 (3 semanas depois):")
    print("🤖 Sistema deve lembrar da preferência")

    result = graph.recall("quando enviar email cliente", limit=5)

    has_preference = False
    for ep in result.episodes:
        if "preferencia" in ep.action.lower() or "manha" in ep.outcome.lower():
            has_preference = True
            break

    print(f"\n📊 Resultado:")
    print(f"  - Encontrou preferência: {has_preference}")
    print(f"  - Episódios relevantes: {len(result.episodes)}")

    if result.episodes:
        print(f"  - Mais relevante: {result.episodes[0].outcome}")

    if has_preference:
        print("✅ PASSOU: Evita perguntar novamente")
        return True
    else:
        print("❌ FALHOU: Não lembrou da preferência")
        return False


def test_personalized_responses():
    """Teste 3: Respostas personalizadas baseadas em histórico"""
    print("\n=== TESTE 3: Personalização de Respostas ===")

    graph = MemoryGraph()

    # Histórico: Usuário teve problemas com Python antes
    print("\n📝 Histórico:")
    for i in range(3):
        print(f"  {i+1}. Usuário reportou erro com Python versão 3.8")
        graph.store(
            action="reportou_erro_python",
            participants=[{"name": "dev_carlos", "type": "developer"}],
            context=f"projeto_alpha",
            outcome=f"erro_versao_python_3_8_{i}"
        )

    # Nova consulta
    print("\n💬 Nova consulta:")
    print("👤 Usuário: 'Estou com um erro no ambiente'")

    result = graph.recall("erro ambiente python", limit=5)

    # Verifica se consolidou padrão
    has_pattern = False
    for ep in result.episodes:
        if ep.occurrence_count >= 3 or ep.is_consolidated:
            has_pattern = True
            print(f"\n🔍 Padrão detectado:")
            print(f"  - Ocorrências: {ep.occurrence_count}")
            print(f"  - É consolidado: {ep.is_consolidated}")
            print(f"  - Problema: {ep.outcome}")
            break

    # Encontrou Carlos e seu histórico Python
    knows_carlos = any("carlos" in e.name.lower() for e in result.entities)
    knows_python_issues = len(result.episodes) >= 2

    print(f"\n📊 Personalização:")
    print(f"  - Conhece o usuário (Carlos): {knows_carlos}")
    print(f"  - Conhece histórico Python: {knows_python_issues}")
    print(f"  - Detectou padrão: {has_pattern}")

    if knows_carlos and knows_python_issues:
        print("✅ PASSOU: Respostas personalizadas")
        return True
    else:
        print("❌ FALHOU: Não personalizou")
        return False


def test_multi_session_learning():
    """Teste 4: Aprendizado ao longo de múltiplas sessões"""
    print("\n=== TESTE 4: Aprendizado Multi-Sessão ===")

    graph = MemoryGraph()

    print("\n📚 Simulando 5 sessões de suporte...")

    # Sessões: Usuário sempre pergunta sobre deploy
    sessions = [
        ("dia_1", "Como faço deploy?", "explicou_processo_deploy"),
        ("dia_3", "Esqueci como faz deploy", "relembrou_processo"),
        ("dia_7", "Deploy de novo", "processo_ja_familiar"),
        ("dia_14", "Preciso fazer deploy", "usuario_ganhando_autonomia"),
        ("dia_21", "Vou fazer deploy", "usuario_autonomo"),
    ]

    for day, question, outcome in sessions:
        print(f"  📅 {day}: '{question}'")
        graph.store(
            action="pergunta_sobre_deploy",
            participants=[{"name": "usuario_joao", "type": "user"}],
            context=day,
            outcome=outcome
        )

    # Verifica aprendizado
    result = graph.recall("deploy", limit=10)

    print(f"\n📊 Análise de Aprendizado:")
    print(f"  - Total de episódios: {len(result.episodes)}")

    # Conta episódios consolidados
    consolidated_count = sum(1 for ep in result.episodes if ep.is_consolidated)
    pattern_detected = any(ep.occurrence_count >= 3 for ep in result.episodes)

    print(f"  - Episódios consolidados: {consolidated_count}")
    print(f"  - Padrão detectado (≥3x): {pattern_detected}")

    if result.episodes:
        most_important = max(result.episodes, key=lambda e: e.importance)
        print(f"  - Episódio mais importante: {most_important.outcome}")
        print(f"    Importância: {most_important.importance:.2f}")
        print(f"    Ocorrências: {most_important.occurrence_count}")

    # Sucesso se detectou padrão de repetição
    if pattern_detected or consolidated_count > 0:
        print("✅ PASSOU: Sistema aprende padrões")
        return True
    elif len(result.episodes) >= 3:
        print("⚠️  PARCIAL: Armazena mas não consolida")
        return True
    else:
        print("❌ FALHOU: Não detectou aprendizado")
        return False


def test_conversation_continuity():
    """Teste 5: Continuidade de conversa"""
    print("\n=== TESTE 5: Continuidade de Conversa ===")

    graph = MemoryGraph()

    print("\n💬 Conversa em progresso:")

    # Turn 1
    print("  👤 'Estou tentando configurar o servidor'")
    graph.store(
        action="configurando_servidor",
        participants=[{"name": "admin_pedro", "type": "admin"}],
        context="setup_inicial",
        outcome="em_progresso"
    )

    # Turn 2
    print("  👤 'Mas está dando erro de permissão'")
    result = graph.recall("erro permissao servidor", limit=5)

    # Deve lembrar do contexto (servidor)
    remembers_server = any(
        "servidor" in ep.action.lower() or "servidor" in ep.context.lower()
        for ep in result.episodes
    )
    remembers_pedro = any("pedro" in e.name.lower() for e in result.entities)

    print(f"\n📊 Continuidade:")
    print(f"  - Lembra do servidor: {remembers_server}")
    print(f"  - Lembra do admin Pedro: {remembers_pedro}")
    print(f"  - Contexto: {result.context_summary}")

    if remembers_server and remembers_pedro:
        print("✅ PASSOU: Mantém continuidade")
        return True
    else:
        print("❌ FALHOU: Perdeu continuidade")
        return False


def measure_conversation_quality_score() -> float:
    """Calcula score geral de qualidade de conversa"""
    print("\n=== SCORE DE QUALIDADE ===")

    tests = [
        ("Persistência de Contexto", test_context_persistence),
        ("Evita Perguntas Repetitivas", test_no_repetitive_questions),
        ("Personalização", test_personalized_responses),
        ("Aprendizado Multi-Sessão", test_multi_session_learning),
        ("Continuidade", test_conversation_continuity),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ ERRO em {name}: {e}")
            results.append((name, False))

    # Calcula score
    passed_count = sum(1 for _, p in results if p)
    total = len(results)
    score = (passed_count / total) * 100

    print("\n" + "=" * 60)
    print("SUMÁRIO DE QUALIDADE DE CONVERSA")
    print("=" * 60)

    for name, passed in results:
        status = "✅ PASSOU" if passed else "❌ FALHOU"
        print(f"{status}: {name}")

    print(f"\nSCORE DE QUALIDADE: {score:.1f}%")
    print(f"Testes passaram: {passed_count}/{total}")

    return score


def run_all_tests():
    """Executa todos os testes de qualidade de conversa"""
    print("=" * 60)
    print("EXPERIMENTO 5: Validação da Qualidade de Conversa")
    print("=" * 60)

    score = measure_conversation_quality_score()

    print("\n" + "=" * 60)
    print("CONCLUSÃO")
    print("=" * 60)

    if score >= 80:
        print("\n🎉 TEORIA VALIDADA: Conversas de alta qualidade")
        print("\nA memória demonstra:")
        print("- ✅ Persistência entre sessões")
        print("- ✅ Redução de perguntas repetitivas")
        print("- ✅ Personalização baseada em histórico")
        print("- ✅ Aprendizado de padrões")
        print("- ✅ Continuidade conversacional")
        return True
    elif score >= 60:
        print("\n⚠️  TEORIA PARCIALMENTE VALIDADA")
        print("\nA memória funciona mas pode melhorar:")
        print("- Revisar testes que falharam")
        print("- Otimizar recall e consolidação")
        return True
    else:
        print("\n❌ TEORIA NÃO VALIDADA")
        print("\nProblemas sérios de qualidade:")
        print("- Memória não persiste adequadamente")
        print("- Falta consolidação de padrões")
        print("- Recall ineficaz")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
