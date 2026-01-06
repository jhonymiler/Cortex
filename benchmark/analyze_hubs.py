#!/usr/bin/env python3
"""
Análise detalhada dos Hubs do Grafo de Memória
Mostra quais entidades e episódios são centrais
"""
import json
from pathlib import Path
from collections import defaultdict


def load_graph(graph_path: Path):
    with open(graph_path) as f:
        return json.load(f)


def analyze_hubs(graph):
    """Identifica e analisa hubs (nós centrais) no grafo."""
    entities = graph.get("entities", {})
    episodes = graph.get("episodes", {})
    relations = graph.get("relations", {})
    
    # Mapeia incoming/outgoing por nó
    incoming = defaultdict(list)  # node_id -> [relation_ids]
    outgoing = defaultdict(list)
    
    for rel_id, relation in relations.items():
        from_id = relation.get("from_id", "")
        to_id = relation.get("to_id", "")
        
        if from_id:
            outgoing[from_id].append(rel_id)
        if to_id:
            incoming[to_id].append(rel_id)
    
    print("\n" + "=" * 80)
    print(" 🌟 ANÁLISE DE HUBS (NÓS CENTRAIS)")
    print("=" * 80)
    
    # Top 10 episódios por incoming (mais referenciados)
    episode_hubs = sorted(
        [(ep_id, len(incoming[ep_id])) for ep_id in episodes.keys()],
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    print("\n📌 Top 10 Episódios Mais Referenciados (Hubs):")
    print("=" * 80)
    for i, (ep_id, count) in enumerate(episode_hubs, 1):
        episode = episodes[ep_id]
        action = episode.get("action", "unknown")
        participants = episode.get("participants", [])
        context = episode.get("context", "")[:100]
        
        print(f"\n{i}. Episódio: {action}")
        print(f"   ID: {ep_id}")
        print(f"   Conexões entrantes: {count}")
        print(f"   Participantes: {len(participants)}")
        print(f"   Contexto: {context}...")
        
        # Mostra quem aponta para este episódio
        incoming_rels = incoming[ep_id]
        incoming_entities = set()
        for rel_id in incoming_rels[:5]:  # Primeiras 5
            rel = relations[rel_id]
            from_id = rel.get("from_id", "")
            if from_id in entities:
                incoming_entities.add(entities[from_id].get("name", from_id[:8]))
        
        if incoming_entities:
            print(f"   Referenciado por: {', '.join(list(incoming_entities)[:5])}")
    
    # Top 10 entidades por outgoing (mais ativas)
    entity_hubs = sorted(
        [(ent_id, len(outgoing[ent_id])) for ent_id in entities.keys()],
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    print("\n\n👤 Top 10 Entidades Mais Ativas (Mais Participações):")
    print("=" * 80)
    for i, (ent_id, count) in enumerate(entity_hubs, 1):
        entity = entities[ent_id]
        name = entity.get("name", "unknown")
        ent_type = entity.get("type", "unknown")
        access_count = entity.get("access_count", 0)
        
        print(f"\n{i}. Entidade: {name}")
        print(f"   Tipo: {ent_type}")
        print(f"   Participações: {count} episódios")
        print(f"   Acessos: {access_count}")
        
        # Mostra em quais episódios participou
        outgoing_rels = outgoing[ent_id]
        participated_episodes = []
        for rel_id in outgoing_rels[:3]:  # Primeiros 3
            rel = relations[rel_id]
            to_id = rel.get("to_id", "")
            if to_id in episodes:
                action = episodes[to_id].get("action", "unknown")
                participated_episodes.append(action)
        
        if participated_episodes:
            print(f"   Participou em: {', '.join(participated_episodes[:3])}")
    
    # Estatísticas gerais
    print("\n\n📊 Estatísticas de Centralidade:")
    print("=" * 80)
    
    avg_incoming = sum(len(v) for v in incoming.values()) / len(incoming) if incoming else 0
    avg_outgoing = sum(len(v) for v in outgoing.values()) / len(outgoing) if outgoing else 0
    
    print(f"Média de conexões entrantes: {avg_incoming:.2f}")
    print(f"Média de conexões saintes: {avg_outgoing:.2f}")
    print(f"Episódios com conexões: {len([e for e in episodes.keys() if incoming[e]])}")
    print(f"Entidades com participações: {len([e for e in entities.keys() if outgoing[e]])}")
    
    # Identifica padrões
    print("\n\n💡 Padrões Identificados:")
    print("=" * 80)
    
    # Ações mais comuns
    action_counts = defaultdict(int)
    for episode in episodes.values():
        action_counts[episode.get("action", "unknown")] += 1
    
    top_actions = sorted(action_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    print("\nAções mais frequentes:")
    for action, count in top_actions:
        print(f"  - {action}: {count}x")
    
    # Entidades mais mencionadas
    entity_names = defaultdict(int)
    for entity in entities.values():
        entity_names[entity.get("name", "unknown")] += 1
    
    duplicates = {name: count for name, count in entity_names.items() if count > 1}
    if duplicates:
        print(f"\n⚠️  Possíveis duplicatas detectadas ({len(duplicates)} nomes):")
        for name, count in sorted(duplicates.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  - {name}: {count} entidades")
    
    print("\n" + "=" * 80)


def main():
    graph_path = Path("data/benchmark/memory_graph.json")
    graph = load_graph(graph_path)
    analyze_hubs(graph)


if __name__ == "__main__":
    main()
