#!/usr/bin/env python3
"""
Cortex Memory Viewer - Streamlit Frontend

Visualização interativa do grafo de memória:
- Dashboard com estatísticas
- Visualização do grafo (pyvis)
- CRUD de entidades, episódios e relações
- Busca e filtragem
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config

# Adiciona o src ao path para importar cortex
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cortex.core import MemoryGraph, Entity, Episode, Relation


# ==================== CONFIG ====================

st.set_page_config(
    page_title="Cortex Memory Viewer",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS customizado
st.markdown("""
<style>
    .stMetric {
        background-color: #1E1E1E;
        padding: 15px;
        border-radius: 10px;
    }
    .node-card {
        background-color: #2D2D2D;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
    .relation-badge {
        background-color: #4A4A4A;
        padding: 5px 10px;
        border-radius: 15px;
        font-size: 12px;
    }
</style>
""", unsafe_allow_html=True)


# ==================== DATA ====================

def get_available_namespaces() -> list[str]:
    """Retorna lista de namespaces disponíveis em ./data."""
    data_root = Path(__file__).parent.parent.parent.parent / "data"
    if not data_root.exists():
        return ["default"]
    
    namespaces = []
    for item in data_root.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            namespaces.append(item.name)
    
    return sorted(namespaces) if namespaces else ["default"]


def get_data_dir(namespace: str = "default") -> Path:
    """Retorna o diretório de dados do Cortex para o namespace especificado."""
    data_dir = os.environ.get("CORTEX_DATA_DIR")
    if data_dir:
        return Path(data_dir)
    
    # Usa ./data/<namespace> no projeto
    data_root = Path(__file__).parent.parent.parent.parent / "data" / namespace
    data_root.mkdir(parents=True, exist_ok=True)
    return data_root


@st.cache_resource(ttl=60)
def load_graph(namespace: str = "default") -> MemoryGraph:
    """Carrega o grafo de memória para o namespace especificado."""
    if namespace == "Todas":
        # Carrega e mescla todos os namespaces
        return load_all_namespaces()
    
    data_dir = get_data_dir(namespace)
    return MemoryGraph(storage_path=data_dir)


@st.cache_data(ttl=30)
def get_cached_graph_data(namespace: str) -> dict:
    """Cache dos dados do grafo para visualização."""
    graph = load_graph(namespace)
    return graph.get_graph_data()


def load_all_namespaces() -> MemoryGraph:
    """Carrega e mescla memórias de todos os namespaces."""
    data_root = Path(__file__).parent.parent.parent.parent / "data"
    merged_graph = MemoryGraph(storage_path=None)  # Grafo em memória
    
    if not data_root.exists():
        return merged_graph
    
    # Itera por todas as pastas em data/
    for namespace_dir in data_root.iterdir():
        if namespace_dir.is_dir() and not namespace_dir.name.startswith('.'):
            graph_file = namespace_dir / "memory_graph.json"
            if graph_file.exists():
                namespace_graph = MemoryGraph(storage_path=namespace_dir)
                
                # Adiciona todas as entidades
                for entity_id, entity in namespace_graph._entities.items():
                    if entity_id not in merged_graph._entities:
                        merged_graph._entities[entity_id] = entity
                        merged_graph._index_entity(entity)
                
                # Adiciona todos os episódios (sem método de indexação específico)
                for episode_id, episode in namespace_graph._episodes.items():
                    if episode_id not in merged_graph._episodes:
                        merged_graph._episodes[episode_id] = episode
                
                # Adiciona todas as relações
                for relation_id, relation in namespace_graph._relations.items():
                    if relation_id not in merged_graph._relations:
                        merged_graph._relations[relation_id] = relation
                        merged_graph._index_relation(relation)
    
    return merged_graph


def reload_graph(namespace: str = "default") -> MemoryGraph:
    """Recarrega o grafo (limpa cache)."""
    st.cache_resource.clear()
    return load_graph(namespace)


# ==================== SIDEBAR ====================

def render_sidebar():
    """Renderiza a sidebar com controles."""
    st.sidebar.title("🧠 Cortex")
    st.sidebar.markdown("---")
    
    # Inicializa session_state se não existir
    if "namespace" not in st.session_state:
        st.session_state.namespace = "default"
    
    # Seletor de namespace
    available_namespaces = get_available_namespaces()
    # Adiciona opção "Todas" no início
    namespace_options = ["Todas"] + available_namespaces
    
    # Determina o índice atual
    if st.session_state.namespace in namespace_options:
        current_index = namespace_options.index(st.session_state.namespace)
    else:
        current_index = 0
    
    selected_namespace = st.sidebar.selectbox(
        "📁 Namespace (Pasta de Dados)",
        options=namespace_options,
        index=current_index,
        help="Escolha 'Todas' para visualizar todos os namespaces, ou selecione uma pasta específica em ./data"
    )
    
    # Se mudou o namespace, atualiza e recarrega
    if selected_namespace != st.session_state.namespace:
        st.session_state.namespace = selected_namespace
        reload_graph(selected_namespace)
        st.rerun()
    
    # Mostra o caminho atual
    if st.session_state.namespace == "Todas":
        current_path = get_data_dir("default").parent  # Mostra ./data
        st.sidebar.caption(f"📂 {current_path} (todas as pastas)")
    else:
        current_path = get_data_dir(st.session_state.namespace)
        st.sidebar.caption(f"📂 {current_path}")
    
    st.sidebar.markdown("---")
    
    # Navegação
    page = st.sidebar.radio(
        "📍 Navegação",
        ["Dashboard", "Grafo Visual", "Entidades", "Episódios", "Relações", "Busca"],
        index=0,
    )
    
    st.sidebar.markdown("---")
    
    # Ações rápidas
    st.sidebar.subheader("⚡ Ações")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("🔄 Atualizar", use_container_width=True):
            reload_graph(st.session_state.namespace)
            st.rerun()
    with col2:
        if st.button("🗑️ Limpar", use_container_width=True, type="secondary"):
            # Não permite limpar quando "Todas" está selecionado
            if st.session_state.namespace == "Todas":
                st.sidebar.error("⚠️ Não é possível limpar quando 'Todas' está selecionado. Escolha um namespace específico.")
            elif st.sidebar.checkbox("Confirmar limpeza"):
                graph = load_graph(st.session_state.namespace)
                graph.clear()
                reload_graph(st.session_state.namespace)
                st.success("Memórias limpas!")
                st.rerun()
    
    # Decay manual (para testes)
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 Decay Manual")
    st.sidebar.caption("⚠️ O decay acontece automaticamente durante o recall. Use apenas para testes.")
    
    # Desabilita decay quando "Todas" está selecionado
    if st.session_state.namespace == "Todas":
        st.sidebar.caption("🔒 Decay desabilitado no modo 'Todas'")
    else:
        decay_factor = st.sidebar.slider("Fator de decay", 0.80, 0.99, 0.95, 0.01)
        if st.sidebar.button("🧹 Aplicar Decay", use_container_width=True):
            graph = load_graph(st.session_state.namespace)
            result = graph.apply_access_decay([], [], decay_factor)
            reload_graph(st.session_state.namespace)
            st.sidebar.success(f"Decay aplicado! Esquecido: {result['episodes_forgotten']} eps, {result['relations_forgotten']} rels")
            st.rerun()
    
    return page


# ==================== PAGES ====================

def render_dashboard(graph: MemoryGraph):
    """Página principal com estatísticas."""
    st.title("📊 Dashboard")
    
    # Cache stats para melhor performance
    stats = graph.stats()
    graph_data = get_cached_graph_data(st.session_state.namespace)
    health = graph.get_memory_health()
    
    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🎯 Entidades", stats["total_entities"])
    with col2:
        st.metric("📝 Episódios", stats["total_episodes"])
    with col3:
        st.metric("🔗 Relações", stats["total_relations"])
    with col4:
        st.metric("⭐ Consolidados", stats["consolidated_episodes"])
    
    # Saúde da memória
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        health_score = health["health_score"]
        health_color = "🟢" if health_score >= 80 else "🟡" if health_score >= 50 else "🔴"
        st.metric(f"{health_color} Saúde", f"{health_score}%")
    with col2:
        st.metric("📊 Importância Média", f"{health['avg_episode_importance']:.2f}")
    with col3:
        st.metric("💪 Força Média", f"{health['avg_relation_strength']:.2f}")
    
    # Problemas
    if health["orphan_entities"] > 0 or health["lonely_episodes"] > 0 or health["weak_relations"] > 0:
        st.warning(f"⚠️ Problemas: {health['orphan_entities']} órfãos, {health['lonely_episodes']} solitários, {health['weak_relations']} fracas")
    
    st.markdown("---")
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Entidades por Tipo")
        if stats["entities_by_type"]:
            import pandas as pd
            df = pd.DataFrame(
                list(stats["entities_by_type"].items()),
                columns=["Tipo", "Quantidade"]
            )
            st.bar_chart(df.set_index("Tipo"))
        else:
            st.info("Nenhuma entidade ainda")
    
    with col2:
        st.subheader("🏆 Top Nós por Peso")
        nodes = graph_data["nodes"]
        if nodes:
            sorted_nodes = sorted(nodes, key=lambda x: x["weight"], reverse=True)[:10]
            for i, node in enumerate(sorted_nodes, 1):
                weight_pct = int(node["weight"] * 100)
                st.markdown(f"**{i}.** {node['label']} ({node['type']}) - `{weight_pct}%`")
                st.progress(node["weight"])
        else:
            st.info("Nenhum nó ainda")
    
    # Últimas atividades
    st.markdown("---")
    st.subheader("🕐 Últimos Episódios")
    
    episodes = list(graph._episodes.values())
    if episodes:
        sorted_episodes = sorted(episodes, key=lambda x: x.timestamp, reverse=True)[:5]
        for ep in sorted_episodes:
            with st.expander(f"📝 {ep.action[:50]}... ({ep.timestamp.strftime('%d/%m %H:%M')})"):
                st.write(f"**Outcome:** {ep.outcome}")
                st.write(f"**Participantes:** {len(ep.participants)}")
                if ep.is_consolidated:
                    st.success(f"⭐ Consolidado ({ep.occurrence_count}x)")
    else:
        st.info("Nenhum episódio ainda")


def render_graph_visual(graph: MemoryGraph):
    """Visualização interativa do grafo."""
    st.title("🕸️ Grafo de Memória")
    
    # Usa cache para dados do grafo
    graph_data = get_cached_graph_data(st.session_state.namespace)
    
    if not graph_data["nodes"]:
        st.info("Grafo vazio. Crie algumas memórias primeiro!")
        return
    
    # Controles principais
    col1, col2, col3 = st.columns(3)
    with col1:
        show_entities = st.checkbox("🎯 Entidades", value=True)
    with col2:
        show_episodes = st.checkbox("📝 Episódios", value=True)
    with col3:
        min_weight = st.slider("Peso mín", 0.0, 1.0, 0.0, 0.1)
    
    # Controles de espaçamento
    with st.expander("⚙️ Ajustar Layout", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            layout_type = st.selectbox("🕸️ Tipo de Layout", [
                "spring",      # Força-direcionado (padrão)
                "kamada_kawai",  # Minimiza energia
                "shell",       # Anéis concêntricos
                "radial",      # Radial a partir do hub
                "circular",    # Círculo
            ], index=0)
        with col2:
            layout_scale = st.slider("📐 Escala", 1, 30, 15, 1)
        with col3:
            layout_k = st.slider("🔄 Espaçamento", 1.0, 15.0, 5.0, 0.5)
        with col4:
            layout_seed = st.number_input("🎲 Seed", 0, 9999, 42)
    
    # Prepara nós e arestas - COM POSIÇÕES PRÉ-CALCULADAS
    import networkx as nx
    import math
    
    # Cria grafo NetworkX para calcular layout
    G = nx.Graph()
    visible_ids = set()
    node_data = {}
    
    for node in graph_data["nodes"]:
        if node["weight"] < min_weight:
            continue
        if node["type"] == "entity" and not show_entities:
            continue
        if node["type"] == "episode" and not show_episodes:
            continue
        visible_ids.add(node["id"])
        node_data[node["id"]] = node
        G.add_node(node["id"])
    
    for edge in graph_data["edges"]:
        if edge["from"] in visible_ids and edge["to"] in visible_ids:
            G.add_edge(edge["from"], edge["to"])
    
    # Calcula posições baseado no layout escolhido
    if len(G.nodes()) > 0:
        scale = layout_scale * 50
        
        if layout_type == "spring":
            # Força-direcionado clássico
            pos = nx.spring_layout(
                G, 
                k=layout_k / math.sqrt(len(G.nodes())),
                iterations=100,
                seed=int(layout_seed),
                scale=scale,
            )
        elif layout_type == "kamada_kawai":
            # Minimiza energia - bom para ver estrutura
            try:
                pos = nx.kamada_kawai_layout(G, scale=scale)
            except ImportError:
                st.warning("⚠️ Layout kamada_kawai requer scipy. Usando spring.")
                pos = nx.spring_layout(G, scale=scale, seed=int(layout_seed))
        elif layout_type == "shell":
            # Anéis concêntricos - hubs no centro
            # Ordena nós por grau (mais conectados primeiro)
            degrees = dict(G.degree())
            sorted_nodes = sorted(degrees.keys(), key=lambda x: degrees[x], reverse=True)
            # Divide em shells (camadas)
            n_shells = min(5, len(sorted_nodes) // 3 + 1)
            shell_size = len(sorted_nodes) // n_shells
            shells = [sorted_nodes[i*shell_size:(i+1)*shell_size] for i in range(n_shells)]
            if len(sorted_nodes) % n_shells:
                shells[-1].extend(sorted_nodes[n_shells*shell_size:])
            pos = nx.shell_layout(G, nlist=shells, scale=scale)
        elif layout_type == "radial":
            # Radial a partir do nó mais conectado (hub)
            degrees = dict(G.degree())
            if degrees:
                center = max(degrees.keys(), key=lambda x: degrees[x])
                # Usa BFS para calcular distâncias
                try:
                    lengths = nx.single_source_shortest_path_length(G, center)
                    max_dist = max(lengths.values()) if lengths else 1
                    # Agrupa por distância
                    shells = [[] for _ in range(max_dist + 1)]
                    for node, dist in lengths.items():
                        shells[dist].append(node)
                    # Remove shells vazios
                    shells = [s for s in shells if s]
                    pos = nx.shell_layout(G, nlist=shells, scale=scale)
                except:
                    pos = nx.spring_layout(G, scale=scale, seed=int(layout_seed))
            else:
                pos = nx.spring_layout(G, scale=scale, seed=int(layout_seed))
        elif layout_type == "circular":
            # Todos em círculo
            pos = nx.circular_layout(G, scale=scale)
        else:
            pos = nx.spring_layout(G, scale=scale, seed=int(layout_seed))
    else:
        pos = {}
    
    # Cria nós COM posições fixas (x, y)
    nodes = []
    for node_id in visible_ids:
        node = node_data[node_id]
        x, y = pos.get(node_id, (0, 0))
        nodes.append(Node(
            id=node["id"],
            label=node["label"],
            size=node["size"],
            color=node["color"],
            title=f"{node['type']}: {node['label']}\nPeso: {node['weight']:.2f}",
            x=x * 10,  # Escala para pixels
            y=y * 10,
        ))
    
    edges = []
    for edge in graph_data["edges"]:
        if edge["from"] in visible_ids and edge["to"] in visible_ids:
            edges.append(Edge(
                source=edge["from"],
                target=edge["to"],
                label=edge["label"],
                width=edge["width"],
                color=edge["color"],
            ))
    
    # Configuração do grafo - ESTÁTICO com posições pré-calculadas
    config = Config(
        width=1600,
        height=1000,
        directed=True,
        physics=False,  # SEM física - posições já calculadas
        hierarchical=False,
        staticGraph=True,  # Grafo estático
        staticGraphWithDragAndDrop=True,  # Permite arrastar nós
        nodeHighlightBehavior=True,
        highlightColor="#F7A7A6",
        collapsible=False,
    )
    
    # Renderiza
    st.markdown("---")
    
    selected = agraph(nodes=nodes, edges=edges, config=config)
    
    # Info do nó selecionado
    if selected:
        st.markdown("---")
        st.subheader(f"📍 Nó Selecionado: {selected}")
        
        # Busca detalhes
        entity = graph.get_entity(selected)
        if entity:
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Tipo:** {entity.type}")
                st.write(f"**Nome:** {entity.name}")
                st.write(f"**Acessos:** {entity.access_count}")
            with col2:
                st.write(f"**Criado:** {entity.created_at}")
                st.write(f"**Identificadores:** {entity.identifiers}")
        
        episode = graph.get_episode(selected)
        if episode:
            st.write(f"**Ação:** {episode.action}")
            st.write(f"**Resultado:** {episode.outcome}")
            st.write(f"**Consolidado:** {'Sim' if episode.is_consolidated else 'Não'}")


def render_entities(graph: MemoryGraph):
    """Gerenciamento de entidades."""
    st.title("🎯 Entidades")
    
    tab1, tab2 = st.tabs(["📋 Lista", "➕ Criar"])
    
    with tab1:
        entities = list(graph._entities.values())
        
        if not entities:
            st.info("Nenhuma entidade ainda")
            return
        
        # Filtros
        col1, col2 = st.columns(2)
        with col1:
            filter_type = st.selectbox(
                "Filtrar por tipo",
                ["Todos"] + list(set(e.type for e in entities))
            )
        with col2:
            search = st.text_input("🔍 Buscar")
        
        # Lista
        filtered = entities
        if filter_type != "Todos":
            filtered = [e for e in filtered if e.type == filter_type]
        if search:
            filtered = [e for e in filtered if e.matches(search)]
        
        for entity in sorted(filtered, key=lambda x: x.access_count, reverse=True):
            weight = graph.get_node_weight(entity.id)
            
            with st.expander(f"🔹 {entity.name} ({entity.type}) - Peso: {weight:.2f}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**ID:** `{entity.id[:8]}...`")
                    st.write(f"**Tipo:** {entity.type}")
                    st.write(f"**Nome:** {entity.name}")
                    st.write(f"**Acessos:** {entity.access_count}")
                
                with col2:
                    st.write(f"**Criado:** {entity.created_at.strftime('%d/%m/%Y %H:%M')}")
                    st.write(f"**Identificadores:** {', '.join(entity.identifiers) or 'Nenhum'}")
                    
                    # Conexões
                    relations = graph.get_relations(from_id=entity.id) + graph.get_relations(to_id=entity.id)
                    st.write(f"**Conexões:** {len(relations)}")
                
                # Botões de ação
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("✏️ Editar", key=f"edit_{entity.id}"):
                        st.session_state.editing_entity = entity.id
                with col3:
                    if st.button("🗑️ Deletar", key=f"del_{entity.id}"):
                        del graph._entities[entity.id]
                        graph._save()
                        st.success("Entidade removida!")
                        st.rerun()
    
    with tab2:
        st.subheader("Criar Nova Entidade")
        
        new_type = st.text_input("Tipo", placeholder="person, file, concept...")
        new_name = st.text_input("Nome", placeholder="Nome da entidade")
        new_identifiers = st.text_input("Identificadores (separados por vírgula)", placeholder="email, id, apelido...")
        
        if st.button("➕ Criar Entidade", type="primary"):
            if new_type and new_name:
                identifiers = [i.strip() for i in new_identifiers.split(",") if i.strip()]
                entity = Entity(
                    type=new_type,
                    name=new_name,
                    identifiers=identifiers,
                )
                graph.add_entity(entity)
                st.success(f"Entidade '{new_name}' criada!")
                st.rerun()
            else:
                st.error("Tipo e Nome são obrigatórios")


def render_episodes(graph: MemoryGraph):
    """Gerenciamento de episódios."""
    st.title("📝 Episódios")
    
    tab1, tab2 = st.tabs(["📋 Lista", "➕ Criar"])
    
    with tab1:
        episodes = list(graph._episodes.values())
        
        if not episodes:
            st.info("Nenhum episódio ainda")
            return
        
        # Filtros
        col1, col2 = st.columns(2)
        with col1:
            show_consolidated = st.checkbox("Apenas consolidados", value=False)
        with col2:
            search = st.text_input("🔍 Buscar", key="ep_search")
        
        # Lista
        filtered = episodes
        if show_consolidated:
            filtered = [e for e in filtered if e.is_consolidated]
        if search:
            filtered = [e for e in filtered if search.lower() in e.action.lower() or search.lower() in e.outcome.lower()]
        
        for episode in sorted(filtered, key=lambda x: x.timestamp, reverse=True):
            weight = graph.get_node_weight(episode.id)
            icon = "⭐" if episode.is_consolidated else "📝"
            
            with st.expander(f"{icon} {episode.action[:40]}... - Peso: {weight:.2f}"):
                st.write(f"**ID:** `{episode.id[:8]}...`")
                st.write(f"**Ação:** {episode.action}")
                st.write(f"**Resultado:** {episode.outcome}")
                st.write(f"**Contexto:** {episode.context or 'Nenhum'}")
                st.write(f"**Data:** {episode.timestamp.strftime('%d/%m/%Y %H:%M')}")
                
                if episode.is_consolidated:
                    st.success(f"⭐ Consolidado ({episode.occurrence_count}x)")
                
                # Participantes
                if episode.participants:
                    st.write("**Participantes:**")
                    for pid in episode.participants:
                        entity = graph.get_entity(pid)
                        if entity:
                            st.write(f"  - {entity.name} ({entity.type})")
                
                if st.button("🗑️ Deletar", key=f"del_ep_{episode.id}"):
                    del graph._episodes[episode.id]
                    graph._save()
                    st.success("Episódio removido!")
                    st.rerun()
    
    with tab2:
        st.subheader("Criar Novo Episódio")
        
        new_action = st.text_input("Ação", placeholder="O que aconteceu...")
        new_outcome = st.text_area("Resultado", placeholder="Qual foi o resultado...")
        new_context = st.text_input("Contexto", placeholder="Situação/cenário (opcional)")
        
        # Seletor de participantes
        entities = list(graph._entities.values())
        if entities:
            selected_participants = st.multiselect(
                "Participantes",
                options=[e.id for e in entities],
                format_func=lambda x: next((e.name for e in entities if e.id == x), x)
            )
        else:
            selected_participants = []
        
        if st.button("➕ Criar Episódio", type="primary"):
            if new_action and new_outcome:
                episode = Episode(
                    action=new_action,
                    outcome=new_outcome,
                    context=new_context,
                    participants=selected_participants,
                )
                graph.add_episode(episode)
                st.success("Episódio criado!")
                st.rerun()
            else:
                st.error("Ação e Resultado são obrigatórios")


def render_relations(graph: MemoryGraph):
    """Gerenciamento de relações."""
    st.title("🔗 Relações")
    
    tab1, tab2 = st.tabs(["📋 Lista", "➕ Criar"])
    
    with tab1:
        relations = list(graph._relations.values())
        
        if not relations:
            st.info("Nenhuma relação ainda")
            return
        
        # Filtro por tipo
        relation_types = list(set(r.relation_type for r in relations))
        filter_type = st.selectbox(
            "Filtrar por tipo",
            ["Todos"] + relation_types
        )
        
        filtered = relations
        if filter_type != "Todos":
            filtered = [r for r in filtered if r.relation_type == filter_type]
        
        for relation in sorted(filtered, key=lambda x: x.strength, reverse=True):
            from_name = "?"
            to_name = "?"
            
            from_entity = graph.get_entity(relation.from_id)
            from_episode = graph.get_episode(relation.from_id)
            if from_entity:
                from_name = from_entity.name
            elif from_episode:
                from_name = from_episode.action[:20]
            
            to_entity = graph.get_entity(relation.to_id)
            to_episode = graph.get_episode(relation.to_id)
            if to_entity:
                to_name = to_entity.name
            elif to_episode:
                to_name = to_episode.action[:20]
            
            strength_bar = "█" * int(relation.strength * 10) + "░" * (10 - int(relation.strength * 10))
            
            with st.expander(f"🔗 {from_name} → {relation.relation_type} → {to_name}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Tipo:** {relation.relation_type}")
                    st.write(f"**Força:** {strength_bar} ({relation.strength:.2f})")
                    st.write(f"**Reforços:** {relation.reinforced_count}")
                
                with col2:
                    st.write(f"**De:** {from_name}")
                    st.write(f"**Para:** {to_name}")
                    st.write(f"**Criado:** {relation.created_at.strftime('%d/%m/%Y %H:%M')}")
                
                # Ações
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("💪 Reforçar", key=f"reinforce_{relation.id}"):
                        relation.reinforce(0.1)
                        graph._save()
                        st.success("Relação reforçada!")
                        st.rerun()
                with col3:
                    if st.button("🗑️ Deletar", key=f"del_rel_{relation.id}"):
                        del graph._relations[relation.id]
                        graph._save()
                        st.success("Relação removida!")
                        st.rerun()
    
    with tab2:
        st.subheader("Criar Nova Relação")
        
        # Coleta todos os nós (entidades + episódios)
        all_nodes = []
        for e in graph._entities.values():
            all_nodes.append({"id": e.id, "label": f"🎯 {e.name}", "type": "entity"})
        for ep in graph._episodes.values():
            all_nodes.append({"id": ep.id, "label": f"📝 {ep.action[:30]}", "type": "episode"})
        
        if len(all_nodes) < 2:
            st.warning("Precisa de pelo menos 2 nós para criar uma relação")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            from_node = st.selectbox(
                "De (origem)",
                options=[n["id"] for n in all_nodes],
                format_func=lambda x: next((n["label"] for n in all_nodes if n["id"] == x), x)
            )
        
        with col2:
            to_node = st.selectbox(
                "Para (destino)",
                options=[n["id"] for n in all_nodes],
                format_func=lambda x: next((n["label"] for n in all_nodes if n["id"] == x), x)
            )
        
        relation_type = st.text_input(
            "Tipo de relação",
            placeholder="caused_by, related_to, resolved_by, loves, hates..."
        )
        
        strength = st.slider("Força inicial", 0.1, 1.0, 0.5, 0.1)
        
        if st.button("➕ Criar Relação", type="primary"):
            if from_node and to_node and relation_type:
                if from_node == to_node:
                    st.error("Origem e destino devem ser diferentes")
                else:
                    relation = Relation(
                        from_id=from_node,
                        relation_type=relation_type,
                        to_id=to_node,
                        strength=strength,
                    )
                    result, resolution = graph.add_relation(relation)
                    if resolution:
                        st.info(f"Contradição detectada e resolvida: {resolution.action_taken}")
                    st.success("Relação criada!")
                    st.rerun()
            else:
                st.error("Todos os campos são obrigatórios")


def render_search(graph: MemoryGraph):
    """Página de busca."""
    st.title("🔍 Busca")
    
    query = st.text_input("Digite sua busca", placeholder="Nome, ação, conceito...")
    
    if query:
        st.markdown("---")
        
        # Busca em entidades
        st.subheader("🎯 Entidades encontradas")
        matching_entities = [e for e in graph._entities.values() if e.matches(query)]
        
        if matching_entities:
            for entity in matching_entities:
                st.write(f"- **{entity.name}** ({entity.type}) - Peso: {graph.get_node_weight(entity.id):.2f}")
        else:
            st.info("Nenhuma entidade encontrada")
        
        # Busca em episódios
        st.subheader("📝 Episódios encontrados")
        matching_episodes = [
            e for e in graph._episodes.values()
            if query.lower() in e.action.lower() or query.lower() in e.outcome.lower()
        ]
        
        if matching_episodes:
            for episode in matching_episodes:
                st.write(f"- **{episode.action[:50]}** - {episode.timestamp.strftime('%d/%m %H:%M')}")
        else:
            st.info("Nenhum episódio encontrado")
        
        # Busca contextual (recall)
        st.markdown("---")
        st.subheader("🧠 Recall Contextual")
        
        if st.button("Buscar com Recall"):
            from cortex.services.memory_service import MemoryService, RecallRequest
            
            service = MemoryService(storage_path=get_data_dir())
            result = service.recall(RecallRequest(query=query, limit=5))
            
            st.write("**Resumo:**", result.context_summary)
            st.write("**Prompt Context:**")
            st.code(result.prompt_context)


# ==================== MAIN ====================

def main():
    """Função principal."""
    # Inicializa session_state se não existir
    if "namespace" not in st.session_state:
        st.session_state.namespace = "default"
    
    # Carrega grafo
    graph = load_graph(st.session_state.namespace)
    
    # Renderiza sidebar e obtém página selecionada
    page = render_sidebar()
    
    # Renderiza página
    if page == "Dashboard":
        render_dashboard(graph)
    elif page == "Grafo Visual":
        render_graph_visual(graph)
    elif page == "Entidades":
        render_entities(graph)
    elif page == "Episódios":
        render_episodes(graph)
    elif page == "Relações":
        render_relations(graph)
    elif page == "Busca":
        render_search(graph)


if __name__ == "__main__":
    main()
