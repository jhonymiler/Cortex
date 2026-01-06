#!/usr/bin/env python3
"""
Análise do Grafo de Memória do Cortex
Gera métricas de qualidade e visualização dos dados coletados
"""
import json
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime
from typing import Dict, List, Any
import statistics


def load_graph(graph_path: Path) -> Dict[str, Any]:
    """Carrega grafo de memória."""
    with open(graph_path) as f:
        return json.load(f)


def load_results(results_path: Path) -> Dict[str, Any]:
    """Carrega resultados do benchmark."""
    with open(results_path) as f:
        return json.load(f)


def analyze_entities(entities: Dict[str, Any]) -> Dict[str, Any]:
    """Analisa entidades no grafo."""
    types = Counter()
    access_counts = []
    names = []
    
    for entity in entities.values():
        types[entity.get("type", "unknown")] += 1
        access_counts.append(entity.get("access_count", 0))
        names.append(entity.get("name", ""))
    
    return {
        "total": len(entities),
        "types": dict(types),
        "access_distribution": {
            "min": min(access_counts) if access_counts else 0,
            "max": max(access_counts) if access_counts else 0,
            "avg": statistics.mean(access_counts) if access_counts else 0,
            "median": statistics.median(access_counts) if access_counts else 0,
        },
        "top_accessed": sorted(
            [(e["name"], e.get("access_count", 0)) for e in entities.values()],
            key=lambda x: x[1],
            reverse=True
        )[:10]
    }


def analyze_episodes(episodes: Dict[str, Any]) -> Dict[str, Any]:
    """Analisa episódios no grafo."""
    actions = Counter()
    consolidated = 0
    occurrence_counts = []
    participants_count = []
    
    for episode in episodes.values():
        action = episode.get("action", "unknown")
        actions[action] += 1
        
        if episode.get("is_consolidated", False):
            consolidated += 1
        
        occurrence_counts.append(episode.get("occurrence_count", 1))
        participants_count.append(len(episode.get("participants", [])))
    
    return {
        "total": len(episodes),
        "consolidated": consolidated,
        "consolidation_rate": (consolidated / len(episodes) * 100) if episodes else 0,
        "top_actions": actions.most_common(10),
        "occurrence_distribution": {
            "min": min(occurrence_counts) if occurrence_counts else 0,
            "max": max(occurrence_counts) if occurrence_counts else 0,
            "avg": statistics.mean(occurrence_counts) if occurrence_counts else 0,
            "median": statistics.median(occurrence_counts) if occurrence_counts else 0,
        },
        "participants_per_episode": {
            "min": min(participants_count) if participants_count else 0,
            "max": max(participants_count) if participants_count else 0,
            "avg": statistics.mean(participants_count) if participants_count else 0,
        }
    }


def analyze_relations(relations: Dict[str, Any], entities: Dict[str, Any]) -> Dict[str, Any]:
    """Analisa relações no grafo."""
    types = Counter()
    strengths = []
    
    # Mapeia entity -> incoming relations (centralidade)
    incoming = defaultdict(int)
    outgoing = defaultdict(int)
    
    for relation in relations.values():
        types[relation.get("relation_type", "unknown")] += 1
        strengths.append(relation.get("strength", 0))
        
        to_id = relation.get("to_id", "")
        from_id = relation.get("from_id", "")
        
        if to_id:
            incoming[to_id] += 1
        if from_id:
            outgoing[from_id] += 1
    
    # Identifica hubs (entidades com muitas conexões entrantes)
    hubs = sorted(
        [(entities.get(eid, {}).get("name", eid), count) 
         for eid, count in incoming.items()],
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    return {
        "total": len(relations),
        "types": dict(types),
        "strength_distribution": {
            "min": min(strengths) if strengths else 0,
            "max": max(strengths) if strengths else 0,
            "avg": statistics.mean(strengths) if strengths else 0,
            "median": statistics.median(strengths) if strengths else 0,
        },
        "centrality": {
            "total_entities_with_incoming": len(incoming),
            "total_entities_with_outgoing": len(outgoing),
            "avg_incoming": statistics.mean(incoming.values()) if incoming else 0,
            "avg_outgoing": statistics.mean(outgoing.values()) if outgoing else 0,
        },
        "hubs": hubs
    }


def analyze_graph_quality(graph: Dict[str, Any]) -> Dict[str, Any]:
    """Analisa qualidade geral do grafo."""
    entities = graph.get("entities", {})
    episodes = graph.get("episodes", {})
    relations = graph.get("relations", {})
    
    # Densidade do grafo
    num_entities = len(entities)
    num_episodes = len(episodes)
    num_relations = len(relations)
    
    max_relations = num_entities * num_episodes  # Simplificado
    density = (num_relations / max_relations * 100) if max_relations > 0 else 0
    
    # Proporções
    entity_episode_ratio = num_entities / num_episodes if num_episodes > 0 else 0
    relation_node_ratio = num_relations / (num_entities + num_episodes) if (num_entities + num_episodes) > 0 else 0
    
    return {
        "density_pct": density,
        "entity_episode_ratio": entity_episode_ratio,
        "relation_per_node": relation_node_ratio,
        "graph_size": {
            "entities": num_entities,
            "episodes": num_episodes,
            "relations": num_relations,
            "total_nodes": num_entities + num_episodes
        }
    }


def print_section(title: str, content: Any, indent: int = 0):
    """Imprime seção formatada."""
    prefix = "  " * indent
    print(f"\n{prefix}{'=' * 60}")
    print(f"{prefix}{title}")
    print(f"{prefix}{'=' * 60}")
    
    if isinstance(content, dict):
        for key, value in content.items():
            if isinstance(value, (dict, list)) and len(str(value)) > 80:
                print(f"{prefix}{key}:")
                print_section("", value, indent + 1)
            elif isinstance(value, float):
                print(f"{prefix}{key}: {value:.2f}")
            else:
                print(f"{prefix}{key}: {value}")
    elif isinstance(content, list):
        for item in content:
            print(f"{prefix}- {item}")
    else:
        print(f"{prefix}{content}")


def main():
    # Paths
    graph_path = Path("data/benchmark/memory_graph.json")
    results_path = Path("benchmark/results/benchmark_20260105_225459.json")
    summary_path = Path("benchmark/results/benchmark_20260105_225459.summary.json")
    
    print("\n" + "=" * 80)
    print(" 🧠 ANÁLISE DO GRAFO DE MEMÓRIA CORTEX")
    print("=" * 80)
    
    # Carrega dados
    print("\n📂 Carregando dados...")
    graph = load_graph(graph_path)
    results = load_results(results_path)
    with open(summary_path) as f:
        summary = json.load(f)
    
    # Resumo do benchmark
    print_section("📊 RESUMO DO BENCHMARK", {
        "Modelo": summary["overview"]["model"],
        "Duração": f"{summary['overview']['duration_seconds']:.2f}s",
        "Conversas": summary["overview"]["total_conversations"],
        "Sessões": summary["overview"]["total_sessions"],
        "Mensagens": summary["overview"]["total_messages"],
    })
    
    # Métricas de token
    print_section("💰 ECONOMIA DE TOKENS", {
        "Baseline Total": summary["token_metrics"]["baseline"]["total_tokens"],
        "Cortex Total": summary["token_metrics"]["cortex"]["total_tokens"],
        "Diferença": summary["token_metrics"]["comparison"]["token_difference"],
        "Economia %": f"{summary['token_metrics']['comparison']['token_difference_pct']:.2f}%",
        "Tokens/Msg (Baseline)": f"{summary['token_metrics']['baseline']['avg_tokens_per_message']:.1f}",
        "Tokens/Msg (Cortex)": f"{summary['token_metrics']['cortex']['avg_tokens_per_message']:.1f}",
    })
    
    # Métricas de tempo
    print_section("⏱️  DESEMPENHO TEMPORAL", {
        "Baseline Total": f"{summary['time_metrics']['baseline']['total_time_ms']:.0f}ms",
        "Cortex Total": f"{summary['time_metrics']['cortex']['total_time_ms']:.0f}ms",
        "Diferença": f"{summary['time_metrics']['comparison']['time_difference_ms']:.0f}ms",
        "Tempo/Msg (Baseline)": f"{summary['time_metrics']['baseline']['avg_time_ms']:.0f}ms",
        "Tempo/Msg (Cortex)": f"{summary['time_metrics']['cortex']['avg_time_ms']:.0f}ms",
        "Recall Médio": f"{summary['time_metrics']['cortex']['avg_recall_time_ms']:.2f}ms",
        "Store Médio": f"{summary['time_metrics']['cortex']['avg_store_time_ms']:.0f}ms",
    })
    
    # Métricas de memória
    print_section("🧠 TAXA DE ACERTO DE MEMÓRIA", {
        "Hit Rate": f"{summary['memory_metrics']['memory_hit_rate']:.1f}%",
        "Mensagens com memória": summary["memory_metrics"]["messages_with_memory"],
        "Mensagens sem memória": summary["memory_metrics"]["messages_without_memory"],
        "Entidades recuperadas": summary["memory_metrics"]["total_entities_recalled"],
        "Episódios recuperados": summary["memory_metrics"]["total_episodes_recalled"],
    })
    
    # Análise do grafo
    print("\n" + "=" * 80)
    print(" 🔍 ANÁLISE DETALHADA DO GRAFO")
    print("=" * 80)
    
    entities = graph.get("entities", {})
    episodes = graph.get("episodes", {})
    relations = graph.get("relations", {})
    
    # Entidades
    entity_analysis = analyze_entities(entities)
    print_section("👤 ENTIDADES", {
        "Total": entity_analysis["total"],
        "Tipos": entity_analysis["types"],
        "Access Count (min/avg/max)": f"{entity_analysis['access_distribution']['min']} / {entity_analysis['access_distribution']['avg']:.1f} / {entity_analysis['access_distribution']['max']}",
    })
    
    print("\n  Top 10 Entidades Mais Acessadas:")
    for name, count in entity_analysis["top_accessed"][:10]:
        print(f"    - {name}: {count} acessos")
    
    # Episódios
    episode_analysis = analyze_episodes(episodes)
    print_section("📝 EPISÓDIOS", {
        "Total": episode_analysis["total"],
        "Consolidados": episode_analysis["consolidated"],
        "Taxa de Consolidação": f"{episode_analysis['consolidation_rate']:.1f}%",
        "Occurrence Count (min/avg/max)": f"{episode_analysis['occurrence_distribution']['min']} / {episode_analysis['occurrence_distribution']['avg']:.1f} / {episode_analysis['occurrence_distribution']['max']}",
        "Participantes/Episódio (min/avg/max)": f"{episode_analysis['participants_per_episode']['min']} / {episode_analysis['participants_per_episode']['avg']:.1f} / {episode_analysis['participants_per_episode']['max']}",
    })
    
    print("\n  Top 10 Ações:")
    for action, count in episode_analysis["top_actions"][:10]:
        print(f"    - {action}: {count}")
    
    # Relações
    relation_analysis = analyze_relations(relations, entities)
    print_section("🔗 RELAÇÕES", {
        "Total": relation_analysis["total"],
        "Tipos": relation_analysis["types"],
        "Strength (min/avg/max)": f"{relation_analysis['strength_distribution']['min']:.2f} / {relation_analysis['strength_distribution']['avg']:.2f} / {relation_analysis['strength_distribution']['max']:.2f}",
        "Entidades com conexões entrantes": relation_analysis["centrality"]["total_entities_with_incoming"],
        "Entidades com conexões saintes": relation_analysis["centrality"]["total_entities_with_outgoing"],
        "Média incoming/outgoing": f"{relation_analysis['centrality']['avg_incoming']:.1f} / {relation_analysis['centrality']['avg_outgoing']:.1f}",
    })
    
    print("\n  Top 10 Hubs (entidades centrais):")
    for name, count in relation_analysis["hubs"][:10]:
        print(f"    - {name}: {count} conexões entrantes")
    
    # Qualidade geral
    quality = analyze_graph_quality(graph)
    print_section("📊 QUALIDADE DO GRAFO", {
        "Densidade": f"{quality['density_pct']:.4f}%",
        "Entidades/Episódio": f"{quality['entity_episode_ratio']:.2f}",
        "Relações/Nó": f"{quality['relation_per_node']:.2f}",
        "Total de Nós": quality["graph_size"]["total_nodes"],
    })
    
    # Insights
    print("\n" + "=" * 80)
    print(" 💡 INSIGHTS")
    print("=" * 80)
    
    insights = []
    
    # Token economy
    token_diff_pct = summary['token_metrics']['comparison']['token_difference_pct']
    if token_diff_pct > 0:
        insights.append(f"✅ Cortex economizou {token_diff_pct:.1f}% de tokens vs baseline")
    
    # Memory hit rate
    hit_rate = summary['memory_metrics']['memory_hit_rate']
    if hit_rate >= 40:
        insights.append(f"✅ Taxa de acerto de memória boa: {hit_rate:.0f}%")
    elif hit_rate < 20:
        insights.append(f"⚠️  Taxa de acerto baixa: {hit_rate:.0f}% - possível falta de contexto entre sessões")
    
    # Consolidation
    consol_rate = episode_analysis["consolidation_rate"]
    if consol_rate > 5:
        insights.append(f"✅ Consolidação ativa: {consol_rate:.1f}% dos episódios consolidados")
    elif consol_rate == 0:
        insights.append("⚠️  Nenhum episódio consolidado - possível falta de padrões repetidos")
    
    # Graph density
    if quality["density_pct"] > 0.1:
        insights.append(f"✅ Grafo bem conectado: densidade de {quality['density_pct']:.4f}%")
    
    # Hubs
    top_hub_count = relation_analysis["hubs"][0][1] if relation_analysis["hubs"] else 0
    if top_hub_count >= 5:
        insights.append(f"✅ Entidades centrais identificadas: top hub com {top_hub_count} conexões")
    
    for insight in insights:
        print(f"  {insight}")
    
    print("\n" + "=" * 80)
    print(" ✅ Análise concluída!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
