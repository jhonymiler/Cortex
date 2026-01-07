#!/usr/bin/env python3
"""
Teste de otimização do recall.

Este script testa as melhorias implementadas na Opção 5 Híbrida:
- Índice invertido para busca O(log n)
- Threshold de relevância mínima
- Métricas de recall
"""

import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime

# Adiciona o projeto ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cortex.core.memory_graph import MemoryGraph, RECALL_MIN_THRESHOLD
from cortex.core.episode import Episode


def create_test_episodes(graph: MemoryGraph, count: int = 100) -> None:
    """Cria episódios de teste variados."""
    domains = [
        ("customer_support", "Cliente {} solicitou suporte técnico", "Problema resolvido com {}"),
        ("financial", "Pagamento de R${} processado", "Transação aprovada para {}"),
        ("technical", "Bug no módulo {} identificado", "Correção aplicada por {}"),
        ("sales", "Proposta enviada para cliente {}", "Negociação em andamento"),
        ("hr", "Funcionário {} solicitou férias", "Aprovado pelo gestor"),
    ]
    
    for i in range(count):
        domain, action_template, outcome_template = domains[i % len(domains)]
        episode = Episode(
            action=action_template.format(i),
            context=f"Domínio: {domain}, interação #{i}",
            outcome=outcome_template.format(i),
            importance=0.5 + (i % 5) * 0.1,
        )
        graph.add_episode(episode)


def test_recall_performance(graph: MemoryGraph, queries: list[str]) -> dict:
    """Testa performance do recall com várias queries."""
    results = {
        "queries": [],
        "total_time_ms": 0,
        "avg_time_ms": 0,
        "total_episodes_found": 0,
        "avg_episodes_found": 0,
    }
    
    for query in queries:
        start = time.time()
        result = graph.recall(query, limit=5)
        elapsed_ms = (time.time() - start) * 1000
        
        results["queries"].append({
            "query": query,
            "time_ms": round(elapsed_ms, 2),
            "episodes_found": len(result.episodes),
            "entities_found": len(result.entities),
            "metrics": result.metrics,
        })
        results["total_time_ms"] += elapsed_ms
        results["total_episodes_found"] += len(result.episodes)
    
    n = len(queries)
    results["avg_time_ms"] = round(results["total_time_ms"] / n, 2)
    results["avg_episodes_found"] = round(results["total_episodes_found"] / n, 2)
    
    return results


def main():
    print("=" * 60)
    print("🧪 TESTE DE OTIMIZAÇÃO DO RECALL (Opção 5 Híbrida)")
    print("=" * 60)
    print()
    
    # Configuração
    test_dir = Path("/home/jhony/projetos/Estudos-IA/Cortex/data/test_recall_opt")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Limpa dados anteriores
    graph_file = test_dir / "memory_graph.json"
    if graph_file.exists():
        graph_file.unlink()
    
    # Cria grafo
    graph = MemoryGraph(storage_path=test_dir)
    
    print(f"📊 Configurações de recall:")
    print(f"   - Threshold mínimo: {RECALL_MIN_THRESHOLD}")
    print(f"   - Max candidatos: {os.getenv('CORTEX_RECALL_MAX_CANDIDATES', 50)}")
    print(f"   - Max resultados: {os.getenv('CORTEX_RECALL_MAX_RESULTS', 10)}")
    print()
    
    # Testa com diferentes tamanhos
    sizes = [50, 100, 200]
    queries = [
        "suporte técnico",
        "pagamento processado",
        "bug correção",
        "proposta cliente",
        "férias funcionário",
        "problema resolvido",
        "transação aprovada",
        "módulo identificado",
        "negociação",
        "gestor aprovado",
    ]
    
    for size in sizes:
        print(f"📝 Criando {size} episódios de teste...")
        
        # Limpa e recria
        graph.clear()
        create_test_episodes(graph, size)
        
        stats = graph.stats()
        print(f"   - Episódios: {stats['total_episodes']}")
        print(f"   - Índice invertido: {stats['inverted_index_stats']}")
        print()
        
        print(f"🔍 Testando {len(queries)} queries...")
        results = test_recall_performance(graph, queries)
        
        print(f"\n📈 Resultados com {size} episódios:")
        print(f"   - Tempo médio: {results['avg_time_ms']:.2f}ms")
        print(f"   - Episódios encontrados (média): {results['avg_episodes_found']}")
        print()
        
        # Mostra detalhes da primeira query
        first = results["queries"][0]
        print(f"   Detalhes da query '{first['query']}':")
        print(f"   - Tempo: {first['time_ms']:.2f}ms")
        print(f"   - Episódios: {first['episodes_found']}")
        print(f"   - Entidades: {first['entities_found']}")
        if first.get("metrics"):
            m = first["metrics"]
            print(f"   - Termos na query: {m.get('query_terms', '?')}")
            print(f"   - Total no grafo: {m.get('total_episodes', '?')}")
            print(f"   - Threshold usado: {m.get('threshold_used', '?')}")
        print()
    
    # Teste de precisão
    print("=" * 60)
    print("🎯 TESTE DE PRECISÃO")
    print("=" * 60)
    
    # Recria grafo limpo
    graph.clear()
    
    # Adiciona episódios específicos
    specific_episodes = [
        Episode(
            action="Cliente Carlos solicitou reembolso",
            context="Produto com defeito",
            outcome="Reembolso aprovado em 24h",
            importance=0.8,
        ),
        Episode(
            action="Bug crítico no sistema de pagamentos",
            context="Transações duplicadas",
            outcome="Correção emergencial aplicada",
            importance=0.9,
        ),
        Episode(
            action="Reunião com equipe de vendas",
            context="Planejamento Q1 2026",
            outcome="Metas definidas",
            importance=0.6,
        ),
    ]
    
    for ep in specific_episodes:
        graph.add_episode(ep)
    
    # Adiciona ruído
    for i in range(50):
        graph.add_episode(Episode(
            action=f"Atividade genérica {i}",
            context=f"Contexto aleatório {i}",
            outcome=f"Resultado padrão {i}",
            importance=0.3,
        ))
    
    print(f"\n📊 Grafo criado: {graph.stats()['total_episodes']} episódios")
    print(f"   - 3 episódios específicos + 50 ruído")
    print()
    
    # Testa queries específicas
    precision_tests = [
        ("Carlos reembolso", "Cliente Carlos"),
        ("bug pagamentos", "Bug crítico"),
        ("reunião vendas", "Reunião com equipe"),
    ]
    
    print("🔎 Testando precisão:")
    for query, expected_contains in precision_tests:
        result = graph.recall(query, limit=3)
        found = False
        for ep in result.episodes:
            if expected_contains.lower() in ep.action.lower():
                found = True
                break
        
        status = "✅" if found else "❌"
        print(f"   {status} Query: '{query}'")
        print(f"      Esperado: '{expected_contains}'")
        print(f"      Encontrado: {len(result.episodes)} episódios")
        if result.episodes:
            print(f"      Primeiro: '{result.episodes[0].action[:50]}...'")
        if result.metrics:
            print(f"      Recall time: {result.metrics.get('recall_time_ms', '?')}ms")
        print()
    
    # Limpa dados de teste
    print("🧹 Limpando dados de teste...")
    import shutil
    if test_dir.exists():
        shutil.rmtree(test_dir)
    
    print()
    print("=" * 60)
    print("✅ TESTE CONCLUÍDO")
    print("=" * 60)


if __name__ == "__main__":
    main()

