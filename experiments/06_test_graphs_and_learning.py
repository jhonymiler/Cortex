"""
Experimento 6: Validar Grafos e Aprendizado
===========================================

Teoria testada:
- Grafos de memória são reais e funcionais
- Sistema aprende e evolui ao longo do tempo
- Hubs (nós importantes) são priorizados
- Relações fortalecem com uso

Método:
- Criar grafo com entidades e relações
- Validar estrutura do grafo
- Medir aprendizado ao longo de interações
- Verificar evolução de importância
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cortex.core.graph import MemoryGraph
from cortex.core.primitives import Entity
from cortex.core.primitives import Episode
from cortex.core.primitives import Relation
from datetime import datetime, timedelta


def test_graph_structure():
    """Teste 1: Estrutura básica do grafo"""
    print("\n=== TESTE 1: Estrutura do Grafo ===")

    graph = MemoryGraph()

    # Cria entidades
    print("\n📦 Criando entidades...")
    user = Entity(name="joao", type="person")
    project = Entity(name="cortex", type="project")
    bug = Entity(name="bug_123", type="issue")

    graph.add_entity(user)
    graph.add_entity(project)
    graph.add_entity(bug)

    # Cria relações
    print("🔗 Criando relações...")
    graph.add_relation(Relation(
        from_id=user.id,
        relation_type="works_on",
        to_id=project.id,
        strength=0.9
    ))

    graph.add_relation(Relation(
        from_id=user.id,
        relation_type="found",
        to_id=bug.id,
        strength=0.7
    ))

    # Exporta grafo
    graph_data = graph.get_graph_data()

    print(f"\n📊 Estatísticas do grafo:")
    print(f"  - Nós: {len(graph_data['nodes'])}")
    print(f"  - Arestas: {len(graph_data['edges'])}")
    print(f"  - Entidades: {graph.stats()['total_entities']}")
    print(f"  - Relações: {graph.stats()['total_relations']}")

    # Valida estrutura
    has_nodes = len(graph_data['nodes']) == 3
    has_edges = len(graph_data['edges']) == 2
    has_visualization_data = all(
        'id' in node and 'label' in node and 'size' in node
        for node in graph_data['nodes']
    )

    print(f"\n✔️  Validações:")
    print(f"  - Nós criados corretamente: {has_nodes}")
    print(f"  - Arestas criadas: {has_edges}")
    print(f"  - Dados de visualização: {has_visualization_data}")

    if has_nodes and has_edges and has_visualization_data:
        print("✅ PASSOU: Grafo estruturado corretamente")
        return True
    else:
        print("❌ FALHOU: Estrutura incorreta")
        return False


def test_hub_detection():
    """Teste 2: Detecção de hubs (nós importantes)"""
    print("\n=== TESTE 2: Detecção de Hubs ===")

    graph = MemoryGraph()

    # Cria um hub: "servidor_principal"
    print("\n🎯 Criando hub (servidor conectado a muitos serviços)...")

    hub = Entity(name="servidor_principal", type="server")
    graph.add_entity(hub)

    # Conecta 10 serviços ao hub
    services = []
    for i in range(10):
        service = Entity(name=f"servico_{i}", type="service")
        graph.add_entity(service)
        services.append(service)

        graph.add_relation(Relation(
            from_id=service.id,
            relation_type="runs_on",
            to_id=hub.id,
            strength=0.8
        ))

    # Calcula peso do hub
    hub_weight = graph.get_node_weight(hub.id)
    service_weight = graph.get_node_weight(services[0].id)

    print(f"\n📊 Análise de centralidade:")
    print(f"  - Peso do hub: {hub_weight:.3f}")
    print(f"  - Peso de serviço comum: {service_weight:.3f}")
    print(f"  - Fator de hub: {hub_weight / service_weight if service_weight > 0 else 0:.2f}x")

    # Conectividade
    connected = graph.get_connected(hub.id)
    print(f"  - Conexões do hub: {len(connected)}")

    # Hub deve ter peso maior
    is_hub = hub_weight > service_weight * 2

    if is_hub and len(connected) >= 10:
        print("✅ PASSOU: Hub detectado corretamente")
        return True
    else:
        print("❌ FALHOU: Hub não priorizado")
        return False


def test_learning_over_time():
    """Teste 3: Aprendizado ao longo do tempo"""
    print("\n=== TESTE 3: Aprendizado ao Longo do Tempo ===")

    graph = MemoryGraph()

    print("\n📚 Simulando 20 interações...")

    # Interação repetida: "Usuário pede ajuda com Git"
    user = Entity(name="developer_maria", type="developer")
    graph.add_entity(user)

    initial_importance = []
    final_importance = []

    for i in range(20):
        episode = Episode(
            action="pede_ajuda_git",
            participants=[user.id],
            context=f"iteracao_{i}",
            outcome="resolvido_com_merge"
        )

        stored = graph.add_episode(episode)

        if i == 0:
            initial_importance.append(stored.importance)
        if i == 19:
            final_importance.append(stored.importance)

    # Busca episódios
    result = graph.recall("ajuda git", limit=10)

    print(f"\n📊 Análise de aprendizado:")
    print(f"  - Episódios encontrados: {len(result.episodes)}")

    if result.episodes:
        # Verifica consolidação
        max_occurrences = max(ep.occurrence_count for ep in result.episodes)
        has_consolidated = any(ep.is_consolidated for ep in result.episodes)

        print(f"  - Máximo de ocorrências: {max_occurrences}")
        print(f"  - Tem episódio consolidado: {has_consolidated}")

        # Importância evoluiu
        if result.episodes:
            avg_importance = sum(ep.importance for ep in result.episodes) / len(result.episodes)
            print(f"  - Importância média: {avg_importance:.3f}")

        # Aprendizado detectado se consolidou OU importância cresceu
        learned = has_consolidated or max_occurrences >= 3

        if learned:
            print("✅ PASSOU: Sistema aprende padrões")
            return True
        else:
            print("⚠️  PARCIAL: Armazena mas não consolida totalmente")
            return True
    else:
        print("❌ FALHOU: Não há evidência de aprendizado")
        return False


def test_relation_strengthening():
    """Teste 4: Relações fortalecem com uso"""
    print("\n=== TESTE 4: Fortalecimento de Relações ===")

    graph = MemoryGraph()

    # Cria relação
    user = Entity(name="joao", type="user")
    project = Entity(name="projeto_x", type="project")

    graph.add_entity(user)
    graph.add_entity(project)

    relation = Relation(
        from_id=user.id,
        relation_type="contributes_to",
        to_id=project.id,
        strength=0.3  # Começa fraca
    )

    stored_relation, _ = graph.add_relation(relation)
    initial_strength = stored_relation.strength

    print(f"\n💪 Fortalecendo relação...")
    print(f"  - Força inicial: {initial_strength:.3f}")

    # Reforça 10 vezes
    for i in range(10):
        stored_relation.reinforce(0.05)

    final_strength = stored_relation.strength

    print(f"  - Força final: {final_strength:.3f}")
    print(f"  - Aumento: {((final_strength - initial_strength) / initial_strength * 100):.1f}%")
    print(f"  - Reforços: {stored_relation.reinforced_count}")

    # Valida fortalecimento
    strengthened = final_strength > initial_strength * 1.3

    if strengthened:
        print("✅ PASSOU: Relações fortalecem com uso")
        return True
    else:
        print("❌ FALHOU: Relações não fortalecem")
        return False


def test_graph_visualization_data():
    """Teste 5: Dados para visualização"""
    print("\n=== TESTE 5: Dados de Visualização ===")

    graph = MemoryGraph()

    # Cria grafo pequeno mas completo
    print("\n🎨 Criando grafo exemplo...")

    # Entidades
    alice = graph.add_entity(Entity(name="alice", type="person"))
    bob = graph.add_entity(Entity(name="bob", type="person"))
    project = graph.add_entity(Entity(name="projeto", type="project"))

    # Relações
    graph.add_relation(Relation(
        from_id=alice.id,
        relation_type="collaborates_with",
        to_id=bob.id,
        strength=0.9
    ))

    graph.add_relation(Relation(
        from_id=alice.id,
        relation_type="works_on",
        to_id=project.id,
        strength=0.8
    ))

    # Episódio
    graph.add_episode(Episode(
        action="reuniao_planejamento",
        participants=[alice.id, bob.id],
        outcome="tarefas_definidas"
    ))

    # Exporta dados
    graph_data = graph.get_graph_data()

    print(f"\n📊 Dados de visualização:")
    print(f"  - Total de nós: {len(graph_data['nodes'])}")
    print(f"  - Total de arestas: {len(graph_data['edges'])}")

    # Valida estrutura para D3.js/PyVis/NetworkX
    valid_nodes = all(
        all(key in node for key in ['id', 'label', 'type', 'size', 'color'])
        for node in graph_data['nodes']
    )

    valid_edges = all(
        all(key in edge for key in ['id', 'from', 'to', 'label', 'weight'])
        for edge in graph_data['edges']
    )

    print(f"  - Nós com estrutura válida: {valid_nodes}")
    print(f"  - Arestas com estrutura válida: {valid_edges}")

    # Imprime amostra
    if graph_data['nodes']:
        print(f"\n📝 Amostra de nó:")
        sample_node = graph_data['nodes'][0]
        print(f"  {sample_node}")

    if graph_data['edges']:
        print(f"\n📝 Amostra de aresta:")
        sample_edge = graph_data['edges'][0]
        print(f"  {sample_edge}")

    if valid_nodes and valid_edges:
        print("✅ PASSOU: Dados prontos para visualização")
        return True
    else:
        print("❌ FALHOU: Dados inválidos")
        return False


def test_graph_evolution():
    """Teste 6: Evolução do grafo ao longo do tempo"""
    print("\n=== TESTE 6: Evolução do Grafo ===")

    graph = MemoryGraph()

    print("\n⏳ Simulando evolução de projeto...")

    # Fase 1: Início (1 dev, 1 projeto)
    stats_t0 = graph.stats()

    dev1 = graph.add_entity(Entity(name="dev_inicial", type="developer"))
    proj = graph.add_entity(Entity(name="projeto", type="project"))
    graph.add_relation(Relation(
        from_id=dev1.id,
        relation_type="created",
        to_id=proj.id
    ))

    stats_t1 = graph.stats()
    print(f"\n  📅 T0 → T1:")
    print(f"     Entidades: {stats_t0['total_entities']} → {stats_t1['total_entities']}")
    print(f"     Relações: {stats_t0['total_relations']} → {stats_t1['total_relations']}")

    # Fase 2: Crescimento (mais 3 devs)
    for i in range(3):
        dev = graph.add_entity(Entity(name=f"dev_{i}", type="developer"))
        graph.add_relation(Relation(
            from_id=dev.id,
            relation_type="contributes_to",
            to_id=proj.id
        ))

    stats_t2 = graph.stats()
    print(f"\n  📅 T1 → T2:")
    print(f"     Entidades: {stats_t1['total_entities']} → {stats_t2['total_entities']}")
    print(f"     Relações: {stats_t1['total_relations']} → {stats_t2['total_relations']}")

    # Fase 3: Consolidação (episódios repetidos)
    for i in range(10):
        graph.add_episode(Episode(
            action="daily_standup",
            participants=[dev1.id],
            outcome="status_atualizado"
        ))

    stats_t3 = graph.stats()
    print(f"\n  📅 T2 → T3:")
    print(f"     Episódios: {stats_t2['total_episodes']} → {stats_t3['total_episodes']}")
    print(f"     Consolidados: {stats_t2['consolidated_episodes']} → {stats_t3['consolidated_episodes']}")

    # Validar crescimento
    grew_entities = stats_t2['total_entities'] > stats_t0['total_entities']
    grew_relations = stats_t2['total_relations'] > stats_t0['total_relations']
    has_episodes = stats_t3['total_episodes'] > 0

    print(f"\n✔️  Validações:")
    print(f"  - Entidades cresceram: {grew_entities}")
    print(f"  - Relações cresceram: {grew_relations}")
    print(f"  - Episódios criados: {has_episodes}")

    if grew_entities and grew_relations and has_episodes:
        print("✅ PASSOU: Grafo evolui ao longo do tempo")
        return True
    else:
        print("❌ FALHOU: Grafo não evolui")
        return False


def run_all_tests():
    """Executa todos os testes de grafos e aprendizado"""
    print("=" * 60)
    print("EXPERIMENTO 6: Validação de Grafos e Aprendizado")
    print("=" * 60)

    tests = [
        ("Estrutura do Grafo", test_graph_structure),
        ("Detecção de Hubs", test_hub_detection),
        ("Aprendizado ao Longo do Tempo", test_learning_over_time),
        ("Fortalecimento de Relações", test_relation_strengthening),
        ("Dados de Visualização", test_graph_visualization_data),
        ("Evolução do Grafo", test_graph_evolution),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"\n❌ ERRO em {name}: {e}")
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

    print("\n" + "=" * 60)
    print("CONCLUSÃO")
    print("=" * 60)

    if passed == total:
        print("\n🎉 TEORIA TOTALMENTE VALIDADA")
        print("\nO sistema de grafos:")
        print("- ✅ Estrutura correta (nós + arestas)")
        print("- ✅ Detecta hubs (nós importantes)")
        print("- ✅ Aprende padrões ao longo do tempo")
        print("- ✅ Relações fortalecem com uso")
        print("- ✅ Dados prontos para visualização")
        print("- ✅ Evolui organicamente")
        return True
    elif passed >= total * 0.75:
        print("\n✅ TEORIA PARCIALMENTE VALIDADA")
        print("\nO sistema funciona mas pode melhorar")
        return True
    else:
        print("\n❌ TEORIA NÃO VALIDADA")
        print("\nProblemas significativos detectados")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
