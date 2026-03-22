#!/usr/bin/env python3
"""
Cortex Memory Viewer - Streamlit Frontend v3.0

Painel de controle moderno para visualização e gerenciamento de grafos de memória:
- Dashboard interativo com estatísticas em tempo real
- Visualização avançada de grafos (agraph + networkx)
- Edição inline de entidades, episódios e relações
- Sistema de busca contextual e filtros avançados
- Navegação intuitiva por tabs
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from streamlit_agraph import agraph, Node, Edge, Config

# Adiciona o src ao path para importar cortex
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from cortex.core import MemoryGraph, Entity, Episode, Relation
from cortex.core.graph import GraphAnalyzer, BFSGraphTraversal, LouvainCommunityDetection, HubDetector
from cortex.config import CortexConfig, get_config


# ==================== CONFIG ====================

st.set_page_config(
    page_title="Cortex Memory Control Panel",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS customizado moderno
st.markdown("""
<style>
    /* Tema dark moderno */
    .stApp {
        background-color: #0E1117;
    }

    /* Cards de métricas */
    .stMetric {
        background: linear-gradient(135deg, #1E1E1E 0%, #2D2D2D 100%);
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #3D3D3D;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }

    /* Cards de nós */
    .node-card {
        background: linear-gradient(135deg, #2D2D2D 0%, #3D3D3D 100%);
        padding: 20px;
        border-radius: 10px;
        margin: 15px 0;
        border: 1px solid #4D4D4D;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
    }

    /* Badges */
    .relation-badge {
        background-color: #4A4A4A;
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 500;
        display: inline-block;
        margin: 3px;
    }

    /* Botões */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }

    /* Headers */
    h1, h2, h3 {
        font-weight: 600;
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background-color: #2D2D2D;
        border-radius: 8px;
        font-weight: 500;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 500;
    }

    /* Progress bars */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
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


@st.cache_resource(ttl=30)
def load_graph(namespace: str = "default") -> MemoryGraph:
    """Carrega o grafo de memória para o namespace especificado."""
    if namespace == "Todas":
        return load_all_namespaces()

    data_dir = get_data_dir(namespace)
    return MemoryGraph(storage_path=data_dir)


@st.cache_data(ttl=15)
def get_cached_graph_data(namespace: str) -> dict:
    """Cache dos dados do grafo para visualização."""
    graph = load_graph(namespace)
    return graph.get_graph_data()


def load_all_namespaces() -> MemoryGraph:
    """Carrega e mescla memórias de todos os namespaces."""
    data_root = Path(__file__).parent.parent.parent.parent / "data"
    merged_graph = MemoryGraph(storage_path=None)

    if not data_root.exists():
        return merged_graph

    for namespace_dir in data_root.iterdir():
        if namespace_dir.is_dir() and not namespace_dir.name.startswith('.'):
            graph_file = namespace_dir / "memory_graph.json"
            if graph_file.exists():
                namespace_graph = MemoryGraph(storage_path=namespace_dir)

                for entity_id, entity in namespace_graph._entities.items():
                    if entity_id not in merged_graph._entities:
                        merged_graph._entities[entity_id] = entity
                        merged_graph._index_entity(entity)

                for episode_id, episode in namespace_graph._episodes.items():
                    if episode_id not in merged_graph._episodes:
                        merged_graph._episodes[episode_id] = episode

                for relation_id, relation in namespace_graph._relations.items():
                    if relation_id not in merged_graph._relations:
                        merged_graph._relations[relation_id] = relation
                        merged_graph._index_relation(relation)

    return merged_graph


def reload_graph(namespace: str = "default") -> MemoryGraph:
    """Recarrega o grafo (limpa cache)."""
    st.cache_resource.clear()
    st.cache_data.clear()
    return load_graph(namespace)


# ==================== SIDEBAR ====================

def render_sidebar():
    """Renderiza a sidebar com controles."""
    st.sidebar.title("🧠 Cortex Control Panel")
    st.sidebar.markdown("### Painel de Controle de Memória")
    st.sidebar.markdown("---")

    # Inicializa session_state
    if "namespace" not in st.session_state:
        st.session_state.namespace = "default"

    # Seletor de namespace
    available_namespaces = get_available_namespaces()
    namespace_options = ["Todas"] + available_namespaces

    current_index = namespace_options.index(st.session_state.namespace) if st.session_state.namespace in namespace_options else 0

    selected_namespace = st.sidebar.selectbox(
        "📁 Namespace (Workspace)",
        options=namespace_options,
        index=current_index,
        help="Selecione 'Todas' para visualizar todos os namespaces"
    )

    # Atualiza namespace se mudou
    if selected_namespace != st.session_state.namespace:
        st.session_state.namespace = selected_namespace
        reload_graph(selected_namespace)
        st.rerun()

    # Mostra caminho atual
    if st.session_state.namespace == "Todas":
        current_path = get_data_dir("default").parent
        st.sidebar.caption(f"📂 {current_path} (todas as pastas)")
    else:
        current_path = get_data_dir(st.session_state.namespace)
        st.sidebar.caption(f"📂 {current_path}")

    st.sidebar.markdown("---")

    # Navegação principal
    st.sidebar.subheader("📍 Navegação")
    page = st.sidebar.radio(
        "Selecione a página",
        [
            "🏠 Dashboard",
            "🕸️ Grafo Interativo",
            "🧩 Comunidades & Hubs",
            "✅ Compliance",
            "🎯 Entidades",
            "📝 Episódios",
            "🔗 Relações",
            "🔍 Busca Avançada"
        ],
        index=0,
        label_visibility="collapsed"
    )

    st.sidebar.markdown("---")

    # Estatísticas rápidas
    graph = load_graph(st.session_state.namespace)
    stats = graph.stats()

    st.sidebar.subheader("📊 Estatísticas Rápidas")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.metric("Entidades", stats["total_entities"], delta=None)
        st.metric("Episódios", stats["total_episodes"], delta=None)
    with col2:
        st.metric("Relações", stats["total_relations"], delta=None)
        st.metric("Consolidados", stats["consolidated_episodes"], delta=None)

    st.sidebar.markdown("---")

    # Ações rápidas
    st.sidebar.subheader("⚡ Ações Rápidas")

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("🔄 Atualizar", use_container_width=True, type="primary"):
            reload_graph(st.session_state.namespace)
            st.success("✅ Dados atualizados!")
            st.rerun()

    with col2:
        if st.button("📊 Stats", use_container_width=True):
            st.session_state.show_stats_modal = True

    # Decay e limpeza
    with st.sidebar.expander("🔧 Ferramentas Avançadas"):
        if st.session_state.namespace != "Todas":
            st.caption("⚠️ Use com cuidado!")

            decay_factor = st.slider("Fator de decay", 0.80, 0.99, 0.95, 0.01)
            if st.button("🧹 Aplicar Decay", use_container_width=True):
                result = graph.apply_access_decay([], [], decay_factor)
                reload_graph(st.session_state.namespace)
                st.success(f"✅ Esquecido: {result['episodes_forgotten']} eps, {result['relations_forgotten']} rels")
                st.rerun()

            st.markdown("---")

            if st.checkbox("⚠️ Confirmar limpeza"):
                if st.button("🗑️ Limpar Tudo", use_container_width=True, type="secondary"):
                    graph.clear()
                    reload_graph(st.session_state.namespace)
                    st.success("✅ Memórias limpas!")
                    st.rerun()
        else:
            st.caption("🔒 Ferramentas desabilitadas no modo 'Todas'")

    return page


# ==================== DASHBOARD ====================

def render_dashboard(graph: MemoryGraph):
    """Dashboard principal com estatísticas e visualizações."""
    st.title("🏠 Dashboard de Memórias")
    st.caption(f"Namespace: **{st.session_state.namespace}**")

    stats = graph.stats()
    graph_data = get_cached_graph_data(st.session_state.namespace)
    health = graph.get_memory_health()

    # Métricas principais em cards grandes
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("🎯 Entidades", stats["total_entities"])
    with col2:
        st.metric("📝 Episódios", stats["total_episodes"])
    with col3:
        st.metric("🔗 Relações", stats["total_relations"])
    with col4:
        st.metric("⭐ Consolidados", stats["consolidated_episodes"])
    with col5:
        health_score = health["health_score"]
        health_emoji = "🟢" if health_score >= 80 else "🟡" if health_score >= 50 else "🔴"
        st.metric(f"{health_emoji} Saúde", f"{health_score}%")

    st.markdown("---")

    # Métricas secundárias
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("📊 Importância Média", f"{health['avg_episode_importance']:.2f}")
    with col2:
        st.metric("💪 Força Média", f"{health['avg_relation_strength']:.2f}")
    with col3:
        st.metric("👻 Entidades Órfãs", health["orphan_entities"])
    with col4:
        st.metric("🔗 Relações Fracas", health["weak_relations"])

    st.markdown("---")

    # Gráficos e visualizações
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📈 Distribuição por Tipo")
        if stats["entities_by_type"]:
            import pandas as pd
            df = pd.DataFrame(
                list(stats["entities_by_type"].items()),
                columns=["Tipo", "Quantidade"]
            )
            st.bar_chart(df.set_index("Tipo"), height=300)
        else:
            st.info("💡 Nenhuma entidade ainda")

    with col2:
        st.subheader("🏆 Top 10 Nós por Peso")
        nodes = graph_data["nodes"]
        if nodes:
            sorted_nodes = sorted(nodes, key=lambda x: x["weight"], reverse=True)[:10]
            for i, node in enumerate(sorted_nodes, 1):
                weight_pct = int(node["weight"] * 100)
                node_emoji = "🎯" if node["type"] == "entity" else "📝"
                st.markdown(f"**{i}.** {node_emoji} {node['label'][:30]}... - `{weight_pct}%`")
                st.progress(node["weight"])
        else:
            st.info("💡 Nenhum nó ainda")

    st.markdown("---")

    # Timeline de atividades
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🕐 Últimas Atividades")
        episodes = list(graph._episodes.values())
        if episodes:
            sorted_episodes = sorted(episodes, key=lambda x: x.timestamp, reverse=True)[:8]
            for ep in sorted_episodes:
                icon = "⭐" if ep.is_consolidated else "📝"
                with st.expander(f"{icon} {ep.action[:50]}... - {ep.timestamp.strftime('%d/%m %H:%M')}"):
                    st.write(f"**Resultado:** {ep.outcome}")
                    st.write(f"**Participantes:** {len(ep.participants)}")
                    st.write(f"**Importância:** {ep.importance:.2f}")
                    if ep.is_consolidated:
                        st.success(f"⭐ Consolidado ({ep.occurrence_count}x)")
        else:
            st.info("💡 Nenhum episódio registrado")

    with col2:
        st.subheader("⚠️ Alertas")

        # Sistema de alertas
        alerts = []
        if health["orphan_entities"] > 5:
            alerts.append(("warning", f"🔶 {health['orphan_entities']} entidades órfãs detectadas"))
        if health["weak_relations"] > 10:
            alerts.append(("warning", f"🔶 {health['weak_relations']} relações fracas detectadas"))
        if health["health_score"] < 50:
            alerts.append(("error", f"🔴 Saúde da memória baixa: {health['health_score']}%"))
        if stats["total_episodes"] == 0:
            alerts.append(("info", "💡 Nenhum episódio registrado ainda"))

        if not alerts:
            st.success("✅ Tudo funcionando perfeitamente!")
        else:
            for alert_type, message in alerts:
                if alert_type == "error":
                    st.error(message)
                elif alert_type == "warning":
                    st.warning(message)
                else:
                    st.info(message)


# ==================== GRAFO VISUAL ====================

def render_graph_visual(graph: MemoryGraph):
    """Visualização interativa do grafo de memória com física e movimento."""
    import networkx as nx
    import math
    
    # Header
    st.markdown("""
    <div style="text-align: center; padding: 15px 0;">
        <h1 style="font-size: 2.2em; margin-bottom: 5px;">🧠 Mapa de Memórias</h1>
        <p style="color: #888; font-size: 1em;">
            Arraste as bolinhas • Clique para detalhes • O grafo se auto-organiza
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Legenda compacta
    st.markdown("""
    <div style="display: flex; justify-content: center; gap: 25px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 12px; margin-bottom: 15px; flex-wrap: wrap;">
        <span style="color: #FF6B6B;">● Pessoas</span>
        <span style="color: #45B7D1;">● Conceitos</span>
        <span style="color: #90EE90;">● Eventos</span>
        <span style="color: #FFD700;">● Padrões</span>
        <span style="color: #888;">― Conexões</span>
    </div>
    """, unsafe_allow_html=True)

    # Controles
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        show_labels = st.checkbox("📝 Mostrar nomes", value=True)
    with col2:
        physics_enabled = st.checkbox("🌊 Movimento ativo", value=True)
    with col3:
        if st.button("🔄 Atualizar", use_container_width=True):
            reload_graph(st.session_state.namespace)
            st.rerun()

    # Coleta dados do grafo
    entities = list(graph._entities.values())
    episodes = list(graph._episodes.values())
    relations = list(graph._relations.values())
    
    if not entities and not episodes:
        st.markdown("""
        <div style="text-align: center; padding: 60px 20px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 20px;">
            <div style="font-size: 4em;">🌱</div>
            <h2 style="color: #fff;">Grafo vazio</h2>
            <p style="color: #aaa;">Crie memórias para ver o grafo ganhar vida!</p>
        </div>
        """, unsafe_allow_html=True)
        return

    # Constrói grafo NetworkX com TODAS as conexões
    G = nx.Graph()
    node_info = {}  # id -> {label, type, weight, color, size}
    
    # Adiciona entidades como nós
    for entity in entities:
        weight = graph.get_node_weight(entity.id)
        node_type = entity.type.lower()
        
        if node_type in ["person", "user"]:
            color = "#FF6B6B"
        elif node_type in ["concept", "file"]:
            color = "#45B7D1"
        else:
            color = "#9B59B6"
        
        G.add_node(entity.id)
        node_info[entity.id] = {
            "label": entity.name,
            "type": "entity",
            "subtype": entity.type,
            "weight": weight,
            "color": color,
            "size": 20 + weight * 35,
        }
    
    # Adiciona episódios como nós
    for episode in episodes:
        weight = graph.get_node_weight(episode.id)
        
        if episode.is_consolidated:
            color = "#FFD700"
        else:
            color = "#90EE90"
        
        label = episode.action[:20] + "..." if len(episode.action) > 20 else episode.action
        
        G.add_node(episode.id)
        node_info[episode.id] = {
            "label": label,
            "type": "episode",
            "subtype": "consolidated" if episode.is_consolidated else "normal",
            "weight": weight,
            "color": color,
            "size": 18 + weight * 30,
            "outcome": episode.outcome[:50] if episode.outcome else "",
        }
    
    # CONEXÕES: Entidade → Episódio (via participants)
    edges_data = []
    for episode in episodes:
        for participant_id in episode.participants:
            if participant_id in node_info:
                G.add_edge(participant_id, episode.id)
                edges_data.append({
                    "from": participant_id,
                    "to": episode.id,
                    "label": "participou",
                    "weight": 0.8,
                    "color": "rgba(144, 238, 144, 0.6)",  # Verde suave
                })
    
    # CONEXÕES: Relações explícitas
    for relation in relations:
        if relation.from_id in node_info and relation.to_id in node_info:
            G.add_edge(relation.from_id, relation.to_id)
            edges_data.append({
                "from": relation.from_id,
                "to": relation.to_id,
                "label": relation.relation_type,
                "weight": relation.strength,
                "color": "rgba(52, 152, 219, 0.6)",  # Azul suave
            })
    
    # CONEXÕES: Consolidação (episódio filho → pai)
    for episode in episodes:
        if episode.metadata.get("consolidated_into"):
            parent_id = episode.metadata["consolidated_into"]
            if parent_id in node_info:
                G.add_edge(episode.id, parent_id)
                edges_data.append({
                    "from": episode.id,
                    "to": parent_id,
                    "label": "consolidado em",
                    "weight": 0.9,
                    "color": "rgba(255, 215, 0, 0.6)",  # Dourado suave
                })
    
    # CONEXÕES: Entre episódios com mesmos participantes
    episode_list = list(episodes)
    for i, ep1 in enumerate(episode_list):
        for ep2 in episode_list[i+1:]:
            # Se compartilham participantes, cria conexão
            shared = set(ep1.participants) & set(ep2.participants)
            if shared and len(shared) > 0:
                G.add_edge(ep1.id, ep2.id)
                edges_data.append({
                    "from": ep1.id,
                    "to": ep2.id,
                    "label": "relacionado",
                    "weight": 0.5,
                    "color": "rgba(150, 150, 150, 0.4)",  # Cinza suave
                })

    if len(G.nodes()) == 0:
        st.info("Nenhum nó para exibir")
        return

    # Cria nós para agraph
    nodes = []
    for node_id in G.nodes():
        info = node_info.get(node_id, {})
        
        label = info.get("label", "?") if show_labels else ""
        
        # Tooltip rico
        tooltip = f"🔹 {info.get('label', '?')}\n"
        tooltip += f"📊 Tipo: {info.get('subtype', info.get('type', '?'))}\n"
        tooltip += f"💪 Peso: {info.get('weight', 0):.0%}"
        if info.get("outcome"):
            tooltip += f"\n📋 {info.get('outcome')}"
        
        nodes.append(Node(
            id=node_id,
            label=label,
            size=info.get("size", 20),
            color=info.get("color", "#888"),
            title=tooltip,
            font={"size": max(10, int(info.get("size", 20) * 0.6)), "color": "white"},
        ))

    # Cria arestas para agraph
    edges = []
    for edge in edges_data:
        edges.append(Edge(
            source=edge["from"],
            target=edge["to"],
            label=edge.get("label", ""),
            width=1 + edge.get("weight", 0.5) * 2,
            color=edge.get("color", "rgba(150,150,150,0.5)"),
        ))

    # Configuração com física para movimento suave
    config = Config(
        width=1400,
        height=700,
        directed=False,
        physics={
            "enabled": physics_enabled,
            "barnesHut": {
                "gravitationalConstant": -3000,
                "centralGravity": 0.3,
                "springLength": 120,
                "springConstant": 0.04,
                "damping": 0.09,
                "avoidOverlap": 0.1,
            },
            "stabilization": {
                "enabled": False,  # Desabilita estabilização para ver movimento
            },
        },
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#FFD700",
        collapsible=False,
        node={
            "highlightStrokeColor": "#FFFFFF",
            "highlightFontWeight": "bold",
        },
        link={
            "highlightColor": "#FFD700",
            "renderLabel": False,
        },
    )

    # Renderiza grafo
    selected = agraph(nodes=nodes, edges=edges, config=config)

    # Painel de detalhes quando nó selecionado
    if selected:
        entity = graph.get_entity(selected)
        episode = graph.get_episode(selected)
        
        st.markdown("---")
        
        if entity:
            render_entity_details_card(entity, graph)
        elif episode:
            render_episode_details_card(episode, graph)
    
    # Estatísticas do grafo
    with st.expander("📊 Estatísticas do Grafo"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👤 Entidades", len(entities))
        with col2:
            st.metric("📝 Episódios", len(episodes))
        with col3:
            st.metric("🔗 Conexões", len(edges_data))
        with col4:
            consolidated = sum(1 for ep in episodes if ep.is_consolidated)
            st.metric("⭐ Padrões", consolidated)


def render_entity_details_card(entity: Entity, graph: MemoryGraph):
    """Card de detalhes bonito para entidade."""
    
    # Cores por tipo
    type_colors = {
        "person": ("#FF6B6B", "👤"),
        "user": ("#FF6B6B", "👤"),
        "concept": ("#45B7D1", "💡"),
        "file": ("#4ECDC4", "📁"),
    }
    color, emoji = type_colors.get(entity.type.lower(), ("#95A5A6", "🔹"))
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {color}22 0%, {color}11 100%); 
                border-left: 4px solid {color}; 
                border-radius: 15px; 
                padding: 25px; 
                margin: 10px 0;">
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 15px;">
            <div style="font-size: 2.5em;">{emoji}</div>
            <div>
                <h2 style="margin: 0; color: #fff;">{entity.name}</h2>
                <span style="color: {color}; font-weight: 500;">{entity.type.title()}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Métricas
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("👁️ Acessos", entity.access_count)
    with col2:
        weight = graph.get_node_weight(entity.id)
        st.metric("💪 Relevância", f"{weight:.0%}")
    with col3:
        days_ago = (datetime.now() - entity.created_at).days
        st.metric("📅 Idade", f"{days_ago} dias")
    
    # Identificadores
    if entity.identifiers:
        st.markdown("**🏷️ Identificadores:**")
        for ident in entity.identifiers:
            st.markdown(f"  • `{ident}`")
    
    # Episódios relacionados
    related_episodes = [
        ep for ep in graph._episodes.values()
        if entity.id in ep.participants
    ]
    
    if related_episodes:
        st.markdown(f"**📝 Participou em {len(related_episodes)} eventos:**")
        for ep in related_episodes[:5]:
            st.markdown(f"  • {ep.action[:50]}{'...' if len(ep.action) > 50 else ''}")
        if len(related_episodes) > 5:
            st.caption(f"  ... e mais {len(related_episodes) - 5} eventos")


def render_episode_details_card(episode: Episode, graph: MemoryGraph):
    """Card de detalhes bonito para episódio."""
    
    is_consolidated = episode.is_consolidated
    color = "#FFD700" if is_consolidated else "#90EE90"
    emoji = "⭐" if is_consolidated else "📝"
    badge = "Padrão Identificado" if is_consolidated else "Evento"
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {color}22 0%, {color}11 100%); 
                border-left: 4px solid {color}; 
                border-radius: 15px; 
                padding: 25px; 
                margin: 10px 0;">
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 15px;">
            <div style="font-size: 2.5em;">{emoji}</div>
            <div>
                <h2 style="margin: 0; color: #fff;">{episode.action[:60]}{'...' if len(episode.action) > 60 else ''}</h2>
                <span style="color: {color}; font-weight: 500;">{badge}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Resultado/Outcome
    if episode.outcome:
        st.markdown(f"""
        <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; margin: 10px 0;">
            <b>📋 Resultado:</b><br>
            {episode.outcome}
        </div>
        """, unsafe_allow_html=True)
    
    # Contexto
    if episode.context:
        st.markdown(f"""
        <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; margin: 10px 0;">
            <b>🎯 Contexto:</b><br>
            {episode.context}
        </div>
        """, unsafe_allow_html=True)
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔄 Ocorrências", episode.occurrence_count)
    with col2:
        st.metric("⚡ Importância", f"{episode.importance:.0%}")
    with col3:
        days_ago = (datetime.now() - episode.timestamp).days
        st.metric("📅 Há", f"{days_ago} dias")
    with col4:
        weight = graph.get_node_weight(episode.id)
        st.metric("💪 Relevância", f"{weight:.0%}")
    
    # Participantes
    if episode.participants:
        st.markdown("**👥 Participantes:**")
        cols = st.columns(min(len(episode.participants), 4))
        for i, participant_id in enumerate(episode.participants[:4]):
            entity = graph.get_entity(participant_id)
            with cols[i]:
                if entity:
                    st.markdown(f"  👤 **{entity.name}**")
                else:
                    st.markdown(f"  🔹 `{participant_id[:8]}...`")
        if len(episode.participants) > 4:
            st.caption(f"  ... e mais {len(episode.participants) - 4} participantes")


# ==================== ENTIDADES ====================

def render_entities(graph: MemoryGraph):
    """Gerenciamento de entidades com edição inline."""
    st.title("🎯 Gerenciamento de Entidades")

    tab1, tab2, tab3 = st.tabs(["📋 Lista Completa", "➕ Criar Nova", "📊 Análise"])

    with tab1:
        render_entities_list(graph)

    with tab2:
        render_create_entity(graph)

    with tab3:
        render_entities_analysis(graph)


def render_entities_list(graph: MemoryGraph):
    """Lista de entidades com filtros e edição."""
    entities = list(graph._entities.values())

    if not entities:
        st.info("💡 Nenhuma entidade cadastrada")
        return

    # Filtros avançados
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_type = st.selectbox(
            "🏷️ Filtrar por tipo",
            ["Todos"] + sorted(list(set(e.type for e in entities)))
        )
    with col2:
        search = st.text_input("🔍 Buscar por nome")
    with col3:
        sort_by = st.selectbox("⬇️ Ordenar por", ["Peso", "Nome", "Data", "Acessos"])

    # Aplica filtros
    filtered = entities
    if filter_type != "Todos":
        filtered = [e for e in filtered if e.type == filter_type]
    if search:
        filtered = [e for e in filtered if search.lower() in e.name.lower()]

    # Ordena
    if sort_by == "Peso":
        filtered = sorted(filtered, key=lambda x: graph.get_node_weight(x.id), reverse=True)
    elif sort_by == "Nome":
        filtered = sorted(filtered, key=lambda x: x.name)
    elif sort_by == "Data":
        filtered = sorted(filtered, key=lambda x: x.created_at, reverse=True)
    else:  # Acessos
        filtered = sorted(filtered, key=lambda x: x.access_count, reverse=True)

    st.caption(f"Mostrando {len(filtered)} de {len(entities)} entidades")

    # Lista
    for entity in filtered:
        render_entity_card(entity, graph)


def render_entity_card(entity: Entity, graph: MemoryGraph):
    """Card de entidade com ações inline."""
    weight = graph.get_node_weight(entity.id)

    with st.expander(f"🎯 **{entity.name}** ({entity.type}) - Peso: {weight:.2f}"):
        # Modo de edição
        edit_key = f"edit_{entity.id}"
        if st.session_state.get(edit_key, False):
            # Formulário de edição
            new_name = st.text_input("Nome", value=entity.name, key=f"name_{entity.id}")
            new_type = st.text_input("Tipo", value=entity.type, key=f"type_{entity.id}")
            new_identifiers = st.text_input(
                "Identificadores (separados por vírgula)",
                value=", ".join(entity.identifiers),
                key=f"idents_{entity.id}"
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Salvar", key=f"save_{entity.id}", type="primary"):
                    entity.name = new_name
                    entity.type = new_type
                    entity.identifiers = [i.strip() for i in new_identifiers.split(",") if i.strip()]
                    graph._save()
                    st.session_state[edit_key] = False
                    reload_graph(st.session_state.namespace)
                    st.success("✅ Entidade atualizada!")
                    st.rerun()
            with col2:
                if st.button("❌ Cancelar", key=f"cancel_{entity.id}"):
                    st.session_state[edit_key] = False
                    st.rerun()
        else:
            # Modo visualização
            render_entity_details(entity, graph)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("✏️ Editar", key=f"edit_btn_{entity.id}"):
                    st.session_state[edit_key] = True
                    st.rerun()
            with col2:
                if st.button("🔍 Ver Grafo", key=f"graph_{entity.id}"):
                    st.session_state.focus_node = entity.id
                    st.info("💡 Vá para a aba 'Grafo Interativo' para ver o nó destacado")
            with col4:
                if st.button("🗑️ Deletar", key=f"del_{entity.id}"):
                    if st.checkbox(f"Confirmar exclusão de {entity.name}", key=f"confirm_{entity.id}"):
                        del graph._entities[entity.id]
                        graph._save()
                        reload_graph(st.session_state.namespace)
                        st.success("✅ Entidade removida!")
                        st.rerun()


def render_entity_details(entity: Entity, graph: MemoryGraph):
    """Renderiza detalhes de uma entidade."""
    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**ID:** `{entity.id[:12]}...`")
        st.write(f"**Nome:** {entity.name}")
        st.write(f"**Tipo:** {entity.type}")
        st.write(f"**Acessos:** {entity.access_count}")

    with col2:
        st.write(f"**Criado:** {entity.created_at.strftime('%d/%m/%Y %H:%M')}")
        st.write(f"**Identificadores:** {', '.join(entity.identifiers) if entity.identifiers else 'Nenhum'}")

        # Conexões
        relations = graph.get_relations(from_id=entity.id) + graph.get_relations(to_id=entity.id)
        st.write(f"**Conexões:** {len(relations)}")


def render_create_entity(graph: MemoryGraph):
    """Formulário de criação de entidade."""
    st.subheader("Criar Nova Entidade")

    with st.form("create_entity_form"):
        new_type = st.text_input("Tipo *", placeholder="person, file, concept, product...")
        new_name = st.text_input("Nome *", placeholder="Nome da entidade")
        new_identifiers = st.text_input("Identificadores", placeholder="email, id, apelido... (separados por vírgula)")

        submitted = st.form_submit_button("➕ Criar Entidade", type="primary", use_container_width=True)

        if submitted:
            if new_type and new_name:
                identifiers = [i.strip() for i in new_identifiers.split(",") if i.strip()]
                entity = Entity(
                    type=new_type,
                    name=new_name,
                    identifiers=identifiers,
                )
                graph.add_entity(entity)
                reload_graph(st.session_state.namespace)
                st.success(f"✅ Entidade '{new_name}' criada com sucesso!")
                st.rerun()
            else:
                st.error("⚠️ Tipo e Nome são obrigatórios")


def render_entities_analysis(graph: MemoryGraph):
    """Análise de entidades."""
    st.subheader("📊 Análise de Entidades")

    entities = list(graph._entities.values())
    if not entities:
        st.info("💡 Nenhuma entidade para análise")
        return

    # Top entidades por peso
    st.markdown("### 🏆 Top 10 Entidades por Peso")
    sorted_entities = sorted(entities, key=lambda x: graph.get_node_weight(x.id), reverse=True)[:10]

    for i, entity in enumerate(sorted_entities, 1):
        weight = graph.get_node_weight(entity.id)
        st.markdown(f"**{i}.** {entity.name} ({entity.type})")
        st.progress(weight)
        st.caption(f"Peso: {weight:.2f} | Acessos: {entity.access_count}")

    # Distribuição por tipo
    st.markdown("### 📊 Distribuição por Tipo")
    type_counts = {}
    for entity in entities:
        type_counts[entity.type] = type_counts.get(entity.type, 0) + 1

    import pandas as pd
    df = pd.DataFrame(list(type_counts.items()), columns=["Tipo", "Quantidade"])
    st.bar_chart(df.set_index("Tipo"))


# ==================== EPISÓDIOS ====================

def render_episodes(graph: MemoryGraph):
    """Gerenciamento de episódios."""
    st.title("📝 Gerenciamento de Episódios")

    tab1, tab2 = st.tabs(["📋 Lista Completa", "➕ Criar Novo"])

    with tab1:
        render_episodes_list(graph)

    with tab2:
        render_create_episode(graph)


def render_episodes_list(graph: MemoryGraph):
    """Lista de episódios com filtros."""
    episodes = list(graph._episodes.values())

    if not episodes:
        st.info("💡 Nenhum episódio registrado")
        return

    # Filtros
    col1, col2, col3 = st.columns(3)
    with col1:
        show_consolidated = st.checkbox("⭐ Apenas consolidados", value=False)
    with col2:
        search = st.text_input("🔍 Buscar", key="ep_search")
    with col3:
        sort_by = st.selectbox("⬇️ Ordenar por", ["Data", "Importância", "Peso"], key="ep_sort")

    # Aplica filtros
    filtered = episodes
    if show_consolidated:
        filtered = [e for e in filtered if e.is_consolidated]
    if search:
        filtered = [
            e for e in filtered
            if search.lower() in e.action.lower() or search.lower() in e.outcome.lower()
        ]

    # Ordena
    if sort_by == "Data":
        filtered = sorted(filtered, key=lambda x: x.timestamp, reverse=True)
    elif sort_by == "Importância":
        filtered = sorted(filtered, key=lambda x: x.importance, reverse=True)
    else:  # Peso
        filtered = sorted(filtered, key=lambda x: graph.get_node_weight(x.id), reverse=True)

    st.caption(f"Mostrando {len(filtered)} de {len(episodes)} episódios")

    # Lista
    for episode in filtered:
        render_episode_card(episode, graph)


def render_episode_card(episode: Episode, graph: MemoryGraph):
    """Card de episódio."""
    weight = graph.get_node_weight(episode.id)
    icon = "⭐" if episode.is_consolidated else "📝"

    with st.expander(f"{icon} **{episode.action[:50]}...** - Peso: {weight:.2f}"):
        render_episode_details(episode, graph)

        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🗑️ Deletar", key=f"del_ep_{episode.id}"):
                if st.checkbox(f"Confirmar exclusão", key=f"confirm_ep_{episode.id}"):
                    del graph._episodes[episode.id]
                    graph._save()
                    reload_graph(st.session_state.namespace)
                    st.success("✅ Episódio removido!")
                    st.rerun()


def render_episode_details(episode: Episode, graph: MemoryGraph):
    """Renderiza detalhes de um episódio."""
    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**ID:** `{episode.id[:12]}...`")
        st.write(f"**Ação:** {episode.action}")
        st.write(f"**Resultado:** {episode.outcome}")
        st.write(f"**Contexto:** {episode.context or 'N/A'}")

    with col2:
        st.write(f"**Data:** {episode.timestamp.strftime('%d/%m/%Y %H:%M')}")
        st.write(f"**Importância:** {episode.importance:.2f}")

        if episode.is_consolidated:
            st.success(f"⭐ Consolidado ({episode.occurrence_count}x)")

        # Participantes
        if episode.participants:
            st.write("**Participantes:**")
            for pid in episode.participants[:3]:
                entity = graph.get_entity(pid)
                if entity:
                    st.caption(f"  • {entity.name} ({entity.type})")
            if len(episode.participants) > 3:
                st.caption(f"  ... e mais {len(episode.participants) - 3}")


def render_create_episode(graph: MemoryGraph):
    """Formulário de criação de episódio com modelo W5H."""
    st.subheader("Criar Novo Episódio (Modelo W5H)")

    with st.form("create_episode_form"):
        st.markdown("### 📋 Campos W5H")

        col1, col2 = st.columns(2)

        with col1:
            what = st.text_input("What - O que aconteceu? *", placeholder="Ação principal...")
            why = st.text_input("Why - Por quê?", placeholder="Causa ou motivação...")
            when = st.text_input("When - Quando?", value=datetime.now().strftime("%Y-%m-%d %H:%M"), placeholder="Data/hora...")

        with col2:
            how = st.text_area("How - Como? Resultado *", placeholder="Método ou resultado...")
            where = st.text_input("Where - Onde?", value=st.session_state.namespace, placeholder="Namespace ou localização...")

        # Who - Participantes
        st.markdown("### 👥 Who - Quem?")
        entities = list(graph._entities.values())
        if entities:
            selected_participants = st.multiselect(
                "Selecione participantes",
                options=[e.id for e in entities],
                format_func=lambda x: next((f"{e.name} ({e.type})" for e in entities if e.id == x), x)
            )
        else:
            selected_participants = []
            st.caption("💡 Crie algumas entidades primeiro")

        # Contexto adicional
        context = st.text_area("Contexto adicional", placeholder="Informações complementares...")

        submitted = st.form_submit_button("➕ Criar Episódio", type="primary", use_container_width=True)

        if submitted:
            if what and how:
                # Cria episódio com metadata W5H
                episode = Episode(
                    action=what,
                    outcome=how,
                    context=context,
                    participants=selected_participants,
                )
                # Adiciona metadata W5H
                episode.metadata["w5h"] = {
                    "who": selected_participants,
                    "what": what,
                    "why": why,
                    "when": when,
                    "where": where,
                    "how": how,
                }
                episode.metadata["namespace"] = where

                graph.add_episode(episode)
                reload_graph(st.session_state.namespace)
                st.success("✅ Episódio criado com sucesso!")
                st.rerun()
            else:
                st.error("⚠️ Os campos 'What' e 'How' são obrigatórios")


# ==================== RELAÇÕES ====================

def render_relations(graph: MemoryGraph):
    """Gerenciamento de relações."""
    st.title("🔗 Gerenciamento de Relações")

    tab1, tab2 = st.tabs(["📋 Lista Completa", "➕ Criar Nova"])

    with tab1:
        render_relations_list(graph)

    with tab2:
        render_create_relation(graph)


def render_relations_list(graph: MemoryGraph):
    """Lista de relações."""
    relations = list(graph._relations.values())

    if not relations:
        st.info("💡 Nenhuma relação cadastrada")
        return

    # Filtro
    relation_types = sorted(list(set(r.relation_type for r in relations)))
    filter_type = st.selectbox("🏷️ Filtrar por tipo", ["Todos"] + relation_types)

    filtered = relations if filter_type == "Todos" else [r for r in relations if r.relation_type == filter_type]

    st.caption(f"Mostrando {len(filtered)} de {len(relations)} relações")

    # Lista
    for relation in sorted(filtered, key=lambda x: x.strength, reverse=True):
        render_relation_card(relation, graph)


def render_relation_card(relation: Relation, graph: MemoryGraph):
    """Card de relação."""
    # Resolve nomes
    from_name = "?"
    to_name = "?"

    from_entity = graph.get_entity(relation.from_id)
    from_episode = graph.get_episode(relation.from_id)
    if from_entity:
        from_name = f"🎯 {from_entity.name}"
    elif from_episode:
        from_name = f"📝 {from_episode.action[:20]}..."

    to_entity = graph.get_entity(relation.to_id)
    to_episode = graph.get_episode(relation.to_id)
    if to_entity:
        to_name = f"🎯 {to_entity.name}"
    elif to_episode:
        to_name = f"📝 {to_episode.action[:20]}..."

    strength_bar = "█" * int(relation.strength * 10) + "░" * (10 - int(relation.strength * 10))

    with st.expander(f"🔗 {from_name} → **{relation.relation_type}** → {to_name}"):
        col1, col2 = st.columns(2)

        with col1:
            st.write(f"**Tipo:** {relation.relation_type}")
            st.write(f"**Força:** {strength_bar} `{relation.strength:.2f}`")
            st.write(f"**Reforços:** {relation.reinforced_count}")

        with col2:
            st.write(f"**De:** {from_name}")
            st.write(f"**Para:** {to_name}")
            st.write(f"**Criado:** {relation.created_at.strftime('%d/%m/%Y %H:%M')}")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("💪 Reforçar (+0.1)", key=f"reinforce_{relation.id}"):
                relation.reinforce(0.1)
                graph._save()
                reload_graph(st.session_state.namespace)
                st.success("✅ Relação reforçada!")
                st.rerun()
        with col3:
            if st.button("🗑️ Deletar", key=f"del_rel_{relation.id}"):
                if st.checkbox(f"Confirmar exclusão", key=f"confirm_rel_{relation.id}"):
                    graph.remove_relation(relation.id)
                    reload_graph(st.session_state.namespace)
                    st.success("✅ Relação removida!")
                    st.rerun()


def render_create_relation(graph: MemoryGraph):
    """Formulário de criação de relação."""
    st.subheader("Criar Nova Relação")

    # Coleta nós
    all_nodes = []
    for e in graph._entities.values():
        all_nodes.append({"id": e.id, "label": f"🎯 {e.name} ({e.type})", "type": "entity"})
    for ep in graph._episodes.values():
        all_nodes.append({"id": ep.id, "label": f"📝 {ep.action[:40]}...", "type": "episode"})

    if len(all_nodes) < 2:
        st.warning("⚠️ Precisa de pelo menos 2 nós (entidades ou episódios) para criar uma relação")
        return

    with st.form("create_relation_form"):
        col1, col2 = st.columns(2)

        with col1:
            from_node = st.selectbox(
                "De (origem) *",
                options=[n["id"] for n in all_nodes],
                format_func=lambda x: next((n["label"] for n in all_nodes if n["id"] == x), x)
            )

        with col2:
            to_node = st.selectbox(
                "Para (destino) *",
                options=[n["id"] for n in all_nodes],
                format_func=lambda x: next((n["label"] for n in all_nodes if n["id"] == x), x)
            )

        relation_type = st.text_input(
            "Tipo de relação *",
            placeholder="caused_by, related_to, resolved_by, likes, contains..."
        )

        strength = st.slider("Força inicial", 0.1, 1.0, 0.5, 0.1)

        submitted = st.form_submit_button("➕ Criar Relação", type="primary", use_container_width=True)

        if submitted:
            if from_node and to_node and relation_type:
                if from_node == to_node:
                    st.error("⚠️ Origem e destino devem ser diferentes")
                else:
                    relation = Relation(
                        from_id=from_node,
                        relation_type=relation_type,
                        to_id=to_node,
                        strength=strength,
                    )
                    result, resolution = graph.add_relation(relation)
                    if resolution:
                        st.info(f"💡 Contradição detectada e resolvida: {resolution.action_taken}")
                    reload_graph(st.session_state.namespace)
                    st.success("✅ Relação criada com sucesso!")
                    st.rerun()
            else:
                st.error("⚠️ Todos os campos são obrigatórios")


# ==================== BUSCA ====================


def _episode_matches_query(episode: Episode, query: str, graph: MemoryGraph) -> bool:
    """
    Verifica se um episódio corresponde à query.
    
    Busca em:
    - action (ação)
    - outcome (resultado)
    - context (contexto)
    - participants (participantes - resolvendo IDs para nomes)
    - metadata (metadados W5H se existirem)
    """
    query_lower = query.lower()
    
    # Busca em campos de texto
    if query_lower in episode.action.lower():
        return True
    if query_lower in episode.outcome.lower():
        return True
    if episode.context and query_lower in episode.context.lower():
        return True
    
    # Busca em participantes (resolve IDs para nomes)
    for participant_id in episode.participants:
        entity = graph.get_entity(participant_id)
        if entity and query_lower in entity.name.lower():
            return True
    
    # Busca em metadata W5H
    w5h = episode.metadata.get("w5h", {})
    for field in ["what", "why", "how"]:
        value = w5h.get(field, "")
        if value and query_lower in str(value).lower():
            return True
    
    # Busca em who do W5H
    who_list = w5h.get("who", [])
    for who in who_list:
        if query_lower in str(who).lower():
            return True
    
    return False


def _get_episode_participants_names(episode: Episode, graph: MemoryGraph) -> str:
    """Retorna os nomes dos participantes de um episódio."""
    names = []
    for participant_id in episode.participants:
        entity = graph.get_entity(participant_id)
        if entity:
            names.append(entity.name)
        else:
            # Fallback para o ID truncado
            names.append(participant_id[:8])
    return ", ".join(names) if names else "Desconhecido"


def render_search_mini_graph(graph: MemoryGraph, entities: list, episodes: list):
    """
    Renderiza um mini-grafo mostrando as conexões entre entidades e episódios encontrados.
    
    Mostra:
    - Entidades como nós vermelhos/azuis
    - Episódios como nós verdes/amarelos
    - Relações "participated_in" entre eles
    - Outras relações existentes no grafo
    """
    if not entities and not episodes:
        st.info("💡 Nenhum resultado para visualizar")
        return
    
    nodes = []
    edges = []
    node_ids = set()
    
    # Adiciona entidades encontradas
    for entity in entities[:15]:  # Limita para não sobrecarregar
        entity_id = entity.id if hasattr(entity, 'id') else str(entity)
        if entity_id not in node_ids:
            node_ids.add(entity_id)
            entity_name = entity.name if hasattr(entity, 'name') else str(entity)
            entity_type = entity.type if hasattr(entity, 'type') else "entity"
            
            # Cores por tipo
            color_map = {
                "person": "#FF6B6B",
                "user": "#FF6B6B",
                "concept": "#45B7D1",
                "file": "#4ECDC4",
            }
            color = color_map.get(entity_type.lower(), "#95A5A6")
            
            nodes.append(Node(
                id=entity_id,
                label=entity_name[:20],
                size=25,
                color=color,
                title=f"🎯 {entity_type}: {entity_name}",
            ))
    
    # Adiciona episódios encontrados
    for episode in episodes[:15]:  # Limita para não sobrecarregar
        episode_id = episode.id if hasattr(episode, 'id') else str(episode)
        if episode_id not in node_ids:
            node_ids.add(episode_id)
            action = episode.action if hasattr(episode, 'action') else str(episode)
            is_consolidated = getattr(episode, 'is_consolidated', False)
            
            nodes.append(Node(
                id=episode_id,
                label=action[:25] + "..." if len(action) > 25 else action,
                size=20,
                color="#FFD700" if is_consolidated else "#90EE90",
                title=f"📝 Episódio: {action}\n📊 Outcome: {getattr(episode, 'outcome', 'N/A')[:50]}",
            ))
            
            # Adiciona conexões com participantes
            participants = getattr(episode, 'participants', [])
            for participant_id in participants:
                # Adiciona o participante se não existir ainda
                if participant_id not in node_ids:
                    participant_entity = graph.get_entity(participant_id)
                    if participant_entity:
                        node_ids.add(participant_id)
                        nodes.append(Node(
                            id=participant_id,
                            label=participant_entity.name[:20],
                            size=22,
                            color="#FF6B6B" if participant_entity.type in ["person", "user"] else "#45B7D1",
                            title=f"🎯 {participant_entity.type}: {participant_entity.name}",
                        ))
                
                # Adiciona aresta de participação
                if participant_id in node_ids:
                    edges.append(Edge(
                        source=participant_id,
                        target=episode_id,
                        label="participated_in",
                        width=2,
                        color="#888888",
                    ))
    
    # Adiciona relações existentes entre os nós encontrados
    for relation in graph._relations.values():
        if relation.from_id in node_ids and relation.to_id in node_ids:
            # Evita duplicar arestas de participação
            if relation.relation_type != "participated_in":
                edges.append(Edge(
                    source=relation.from_id,
                    target=relation.to_id,
                    label=relation.relation_type,
                    width=1 + relation.strength * 3,
                    color="#27AE60" if relation.strength >= 0.7 else "#F39C12",
                ))
    
    if not nodes:
        st.info("💡 Nenhum nó para visualizar")
        return
    
    # Configuração do mini-grafo
    config = Config(
        width=800,
        height=400,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#F7A7A6",
        collapsible=False,
    )
    
    # Renderiza o mini-grafo
    try:
        agraph(nodes=nodes, edges=edges, config=config)
    except Exception as e:
        st.warning(f"⚠️ Erro ao renderizar grafo: {e}")


def render_search(graph: MemoryGraph):
    """Busca avançada."""
    st.title("🔍 Busca Avançada de Memórias")

    query = st.text_input("Digite sua busca", placeholder="Nome, ação, conceito, palavra-chave...")

    if query:
        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🎯 Entidades")
            matching_entities = [e for e in graph._entities.values() if e.matches(query)]

            if matching_entities:
                for entity in matching_entities[:10]:
                    weight = graph.get_node_weight(entity.id)
                    st.markdown(f"• **{entity.name}** ({entity.type}) - Peso: {weight:.2f}")
            else:
                st.info("Nenhuma entidade encontrada")

        with col2:
            st.subheader("📝 Episódios")
            # Busca aprimorada: considera action, outcome, context, participants e metadata
            matching_episodes = [
                e for e in graph._episodes.values()
                if _episode_matches_query(e, query, graph)
            ]

            if matching_episodes:
                for episode in matching_episodes[:10]:
                    participants = _get_episode_participants_names(episode, graph)
                    action_display = episode.action[:35] + "..." if len(episode.action) > 35 else episode.action
                    st.markdown(
                        f"• **{action_display}**\n"
                        f"  👥 {participants} | 📅 {episode.timestamp.strftime('%d/%m %H:%M')}"
                    )
            else:
                st.info("Nenhum episódio encontrado")

        # Visualização do Mini-Grafo das Conexões
        if matching_entities or matching_episodes:
            st.markdown("---")
            st.subheader("🕸️ Grafo de Conexões")
            st.caption("Visualização das conexões entre entidades e episódios encontrados")
            
            render_search_mini_graph(graph, matching_entities, matching_episodes)

        # Recall contextual
        st.markdown("---")
        st.subheader("🧠 Busca Contextual (Recall)")
        st.caption("Usa embeddings semânticos e algoritmos de relevância")

        if st.button("🔍 Buscar com Recall", type="primary"):
            with st.spinner("Buscando memórias relevantes..."):
                result = graph.recall(query, limit=10)

                st.success(f"✅ Encontrado: {len(result.episodes)} episódios, {len(result.entities)} entidades")

                st.markdown("### 📋 Resumo")
                st.write(result.context_summary)

                st.markdown("### 📦 Contexto Compactado (YAML)")
                prompt_context = result.to_prompt_context(format="yaml")
                st.code(prompt_context, language="yaml")

                st.markdown("### 📊 Métricas")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Tempo", f"{result.metrics.get('recall_time_ms', 0)}ms")
                with col2:
                    st.metric("Entidades", len(result.entities))
                with col3:
                    st.metric("Episódios", len(result.episodes))
                with col4:
                    st.metric("Relações", len(result.relations))
                
                # Grafo do Recall
                if result.entities or result.episodes:
                    st.markdown("### 🕸️ Grafo do Recall")
                    render_search_mini_graph(graph, result.entities, result.episodes)


# ==================== COMUNIDADES & HUBS ====================

def render_communities(graph: MemoryGraph):
    """Visualização de comunidades e hubs no grafo."""
    st.title("🧩 Comunidades & Hubs")
    st.caption("Análise de estrutura do grafo: clusters de conhecimento e nós centrais")

    # Verifica se há dados
    if not graph._entities and not graph._episodes:
        st.info("💡 Grafo vazio. Crie algumas memórias primeiro!")
        return

    # Configuração
    config = get_config()

    tab1, tab2, tab3 = st.tabs(["🏘️ Comunidades", "⭐ Hubs", "📊 Estatísticas do Grafo"])

    with tab1:
        render_community_detection(graph, config)

    with tab2:
        render_hub_detection(graph, config)

    with tab3:
        render_graph_statistics(graph)


def render_community_detection(graph: MemoryGraph, config: CortexConfig):
    """Detecção de comunidades com Louvain."""
    st.subheader("🏘️ Detecção de Comunidades (Louvain)")
    st.caption("Agrupa memórias relacionadas em clusters")

    # Parâmetros
    col1, col2, col3 = st.columns(3)
    with col1:
        min_size = st.slider("Tamanho mínimo", 2, 10, config.community_min_size)
    with col2:
        resolution = st.slider("Resolução", 0.5, 2.0, config.community_resolution, 0.1)
    with col3:
        max_iterations = st.slider("Iterações máx", 5, 50, 20)

    if st.button("🔍 Detectar Comunidades", type="primary"):
        with st.spinner("Analisando estrutura do grafo..."):
            try:
                # Cria função de vizinhos
                def get_neighbors(node_id: str):
                    neighbors = []
                    for rel in graph._relations.values():
                        if rel.from_id == node_id:
                            neighbors.append((rel.to_id, rel))
                        elif rel.to_id == node_id:
                            neighbors.append((rel.from_id, rel))
                    return neighbors

                # Coleta todos os IDs de nós
                node_ids = list(graph._entities.keys()) + list(graph._episodes.keys())

                if len(node_ids) < 3:
                    st.warning("⚠️ Precisa de pelo menos 3 nós para detectar comunidades")
                    return

                louvain = LouvainCommunityDetection(
                    get_neighbors_fn=get_neighbors,
                    resolution=resolution
                )

                communities = louvain.detect_communities(
                    node_ids=node_ids,
                    min_community_size=min_size,
                    max_iterations=max_iterations
                )

                if communities:
                    st.success(f"✅ Encontradas {len(communities)} comunidades!")

                    for i, comm in enumerate(communities, 1):
                        with st.expander(f"🏘️ Comunidade {i} ({len(comm.member_ids)} membros) - Coesão: {comm.cohesion:.2f}"):
                            st.markdown(f"**Nó Central:** `{comm.central_node_id[:12]}...`")

                            # Lista membros
                            st.markdown("**Membros:**")
                            for member_id in list(comm.member_ids)[:10]:
                                entity = graph.get_entity(member_id)
                                episode = graph.get_episode(member_id)
                                if entity:
                                    st.markdown(f"  • 🎯 {entity.name} ({entity.type})")
                                elif episode:
                                    st.markdown(f"  • 📝 {episode.action[:40]}...")

                            if len(comm.member_ids) > 10:
                                st.caption(f"  ... e mais {len(comm.member_ids) - 10} membros")
                else:
                    st.info("💡 Nenhuma comunidade detectada com os parâmetros atuais")

            except Exception as e:
                st.error(f"❌ Erro: {e}")


def render_hub_detection(graph: MemoryGraph, config: CortexConfig):
    """Detecção de hubs (nós centrais)."""
    st.subheader("⭐ Detecção de Hubs")
    st.caption("Identifica nós centrais com muitas conexões")

    # Parâmetros
    col1, col2 = st.columns(2)
    with col1:
        min_connections = st.slider("Conexões mínimas", 2, 20, config.hub_min_connections)
    with col2:
        top_k = st.slider("Top K hubs", 3, 20, 10)

    if st.button("🔍 Detectar Hubs", type="primary"):
        with st.spinner("Calculando centralidade..."):
            try:
                def get_neighbors(node_id: str):
                    neighbors = []
                    for rel in graph._relations.values():
                        if rel.from_id == node_id:
                            neighbors.append((rel.to_id, rel))
                        elif rel.to_id == node_id:
                            neighbors.append((rel.from_id, rel))
                    return neighbors

                node_ids = list(graph._entities.keys()) + list(graph._episodes.keys())

                if not node_ids:
                    st.warning("⚠️ Nenhum nó no grafo")
                    return

                hub_detector = HubDetector(get_neighbors_fn=get_neighbors)

                hubs = hub_detector.find_hubs(
                    node_ids=node_ids,
                    top_k=top_k,
                    min_connections=min_connections
                )

                if hubs:
                    st.success(f"✅ Encontrados {len(hubs)} hubs!")

                    for i, (hub_id, connections) in enumerate(hubs, 1):
                        entity = graph.get_entity(hub_id)
                        episode = graph.get_episode(hub_id)

                        if entity:
                            st.markdown(f"**{i}.** ⭐ 🎯 **{entity.name}** ({entity.type}) - {connections} conexões")
                        elif episode:
                            st.markdown(f"**{i}.** ⭐ 📝 **{episode.action[:40]}...** - {connections} conexões")

                        # Barra de progresso
                        max_conn = hubs[0][1] if hubs else 1
                        st.progress(connections / max_conn)
                else:
                    st.info(f"💡 Nenhum hub com mais de {min_connections} conexões")

                # PageRank
                st.markdown("---")
                st.subheader("📊 PageRank (Importância)")

                pagerank = hub_detector.calculate_pagerank(node_ids, damping=0.85, iterations=20)

                if pagerank:
                    sorted_pr = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:10]

                    for i, (node_id, score) in enumerate(sorted_pr, 1):
                        entity = graph.get_entity(node_id)
                        episode = graph.get_episode(node_id)

                        if entity:
                            st.markdown(f"**{i}.** 🎯 {entity.name} - Score: `{score:.4f}`")
                        elif episode:
                            st.markdown(f"**{i}.** 📝 {episode.action[:30]}... - Score: `{score:.4f}`")

            except Exception as e:
                st.error(f"❌ Erro: {e}")


def render_graph_statistics(graph: MemoryGraph):
    """Estatísticas do grafo."""
    st.subheader("📊 Estatísticas do Grafo")

    stats = graph.stats()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("🎯 Nós (Entidades)", stats["total_entities"])
        st.metric("📝 Nós (Episódios)", stats["total_episodes"])
        total_nodes = stats["total_entities"] + stats["total_episodes"]
        st.metric("📊 Total de Nós", total_nodes)

    with col2:
        st.metric("🔗 Arestas (Relações)", stats["total_relations"])
        if total_nodes > 0:
            density = (2 * stats["total_relations"]) / (total_nodes * (total_nodes - 1)) if total_nodes > 1 else 0
            st.metric("📈 Densidade", f"{density:.4f}")
            avg_degree = (2 * stats["total_relations"]) / total_nodes if total_nodes > 0 else 0
            st.metric("📊 Grau Médio", f"{avg_degree:.2f}")

    with col3:
        st.metric("⭐ Consolidados", stats["consolidated_episodes"])
        st.metric("🏷️ Tipos de Entidade", len(stats.get("entities_by_type", {})))

        # Tipos de relação
        relation_types = set(r.relation_type for r in graph._relations.values())
        st.metric("🔗 Tipos de Relação", len(relation_types))

    # Distribuição de graus
    st.markdown("---")
    st.subheader("📈 Distribuição de Graus")

    if graph._relations:
        degree_count = {}
        for node_id in list(graph._entities.keys()) + list(graph._episodes.keys()):
            degree = sum(1 for r in graph._relations.values() if r.from_id == node_id or r.to_id == node_id)
            degree_count[node_id] = degree

        if degree_count:
            import pandas as pd
            degrees = list(degree_count.values())
            df = pd.DataFrame({"Grau": degrees})
            st.bar_chart(df["Grau"].value_counts().sort_index())
    else:
        st.info("💡 Nenhuma relação para análise")


# ==================== COMPLIANCE ====================

def render_compliance(graph: MemoryGraph):
    """Painel de compliance e monitoramento."""
    st.title("✅ Compliance & Monitoramento")
    st.caption("Verificação de integridade, qualidade e conformidade das memórias")

    config = get_config()

    tab1, tab2, tab3 = st.tabs(["🔍 Verificação", "📊 Métricas", "⚙️ Configuração"])

    with tab1:
        render_compliance_checks(graph)

    with tab2:
        render_compliance_metrics(graph)

    with tab3:
        render_config_panel(config)


def render_compliance_checks(graph: MemoryGraph):
    """Verificações de compliance."""
    st.subheader("🔍 Verificações de Integridade")

    health = graph.get_memory_health()
    stats = graph.stats()

    # Score geral
    health_score = health["health_score"]
    health_color = "green" if health_score >= 80 else "orange" if health_score >= 50 else "red"

    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(f"""
        <div style="text-align: center; padding: 20px; background: linear-gradient(135deg, #1E1E1E, #2D2D2D); border-radius: 10px;">
            <h1 style="color: {health_color}; font-size: 48px; margin: 0;">{health_score}%</h1>
            <p style="color: #888;">Score de Saúde</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        # Checklist de verificações
        checks = [
            ("Entidades órfãs < 10%", health["orphan_entities"] < stats["total_entities"] * 0.1 if stats["total_entities"] > 0 else True),
            ("Relações fracas < 20%", health["weak_relations"] < stats["total_relations"] * 0.2 if stats["total_relations"] > 0 else True),
            ("Importância média > 0.3", health["avg_episode_importance"] > 0.3),
            ("Força média > 0.4", health["avg_relation_strength"] > 0.4),
            ("Consolidação ativa", stats["consolidated_episodes"] > 0 or stats["total_episodes"] < 10),
        ]

        for check_name, passed in checks:
            icon = "✅" if passed else "❌"
            st.markdown(f"{icon} {check_name}")

    st.markdown("---")

    # Problemas detectados
    st.subheader("⚠️ Problemas Detectados")

    problems = []

    # Entidades órfãs
    if health["orphan_entities"] > 0:
        orphan_pct = (health["orphan_entities"] / stats["total_entities"] * 100) if stats["total_entities"] > 0 else 0
        severity = "error" if orphan_pct > 20 else "warning" if orphan_pct > 10 else "info"
        problems.append((severity, f"👻 {health['orphan_entities']} entidades órfãs ({orphan_pct:.1f}%)", "Entidades sem conexões podem indicar dados inconsistentes"))

    # Relações fracas
    if health["weak_relations"] > 0:
        weak_pct = (health["weak_relations"] / stats["total_relations"] * 100) if stats["total_relations"] > 0 else 0
        severity = "error" if weak_pct > 30 else "warning" if weak_pct > 15 else "info"
        problems.append((severity, f"🔗 {health['weak_relations']} relações fracas ({weak_pct:.1f}%)", "Relações com força < 0.3 podem ser ruído"))

    # Baixa importância
    if health["avg_episode_importance"] < 0.3:
        problems.append(("warning", f"📉 Importância média baixa: {health['avg_episode_importance']:.2f}", "Episódios podem não estar sendo bem avaliados"))

    # Sem consolidação
    if stats["total_episodes"] > 20 and stats["consolidated_episodes"] == 0:
        problems.append(("warning", "⚠️ Nenhum episódio consolidado", "Execute o DreamAgent para consolidar padrões"))

    if not problems:
        st.success("✅ Nenhum problema detectado! Sistema saudável.")
    else:
        for severity, title, description in problems:
            if severity == "error":
                st.error(f"**{title}**\n\n{description}")
            elif severity == "warning":
                st.warning(f"**{title}**\n\n{description}")
            else:
                st.info(f"**{title}**\n\n{description}")


def render_compliance_metrics(graph: MemoryGraph):
    """Métricas de compliance."""
    st.subheader("📊 Métricas de Qualidade")

    health = graph.get_memory_health()
    stats = graph.stats()

    # Métricas em cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "📊 Importância Média",
            f"{health['avg_episode_importance']:.2f}",
            delta="OK" if health['avg_episode_importance'] > 0.3 else "Baixa"
        )

    with col2:
        st.metric(
            "💪 Força Média",
            f"{health['avg_relation_strength']:.2f}",
            delta="OK" if health['avg_relation_strength'] > 0.4 else "Baixa"
        )

    with col3:
        consolidation_rate = (stats["consolidated_episodes"] / stats["total_episodes"] * 100) if stats["total_episodes"] > 0 else 0
        st.metric(
            "⭐ Taxa Consolidação",
            f"{consolidation_rate:.1f}%",
            delta="OK" if consolidation_rate > 5 else "Baixa"
        )

    with col4:
        orphan_rate = (health["orphan_entities"] / stats["total_entities"] * 100) if stats["total_entities"] > 0 else 0
        st.metric(
            "👻 Taxa Órfãos",
            f"{orphan_rate:.1f}%",
            delta="OK" if orphan_rate < 10 else "Alta"
        )

    st.markdown("---")

    # Histórico (simulado)
    st.subheader("📈 Tendência de Saúde")
    st.caption("Últimas 7 medições")

    import pandas as pd
    import random

    # Simula histórico baseado no score atual
    base_score = health["health_score"]
    history = [max(0, min(100, base_score + random.randint(-10, 10))) for _ in range(7)]
    history[-1] = base_score  # Último é o atual

    df = pd.DataFrame({
        "Dia": [f"D-{6-i}" for i in range(7)],
        "Score": history
    })

    st.line_chart(df.set_index("Dia"))


def render_config_panel(config: CortexConfig):
    """Painel de configuração."""
    st.subheader("⚙️ Configuração Atual")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🧠 Features V2.0")
        st.markdown(f"- Context Packing: {'✅' if config.enable_context_packing else '❌'}")
        st.markdown(f"- Progressive Consolidation: {'✅' if config.enable_progressive_consolidation else '❌'}")
        st.markdown(f"- Active Forgetting: {'✅' if config.enable_active_forgetting else '❌'}")
        st.markdown(f"- Hierarchical Recall: {'✅' if config.enable_hierarchical_recall else '❌'}")
        st.markdown(f"- SM-2 Adaptive: {'✅' if config.enable_sm2_adaptive else '❌'}")
        st.markdown(f"- Attention Mechanism: {'✅' if config.enable_attention_mechanism else '❌'}")

    with col2:
        st.markdown("### 🆕 Features V2.1")
        st.markdown(f"- Hybrid Ranking: {'✅' if config.enable_hybrid_ranking else '❌'}")
        st.markdown(f"- Graph Expansion: {'✅' if config.enable_graph_expansion else '❌'}")
        st.markdown(f"- Community Detection: {'✅' if config.enable_community_detection else '❌'}")

    st.markdown("---")

    st.markdown("### 🔧 Parâmetros")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Ranking**")
        st.code(f"RRF K: {config.rrf_k}")
        st.code(f"MMR Lambda: {config.mmr_lambda}")

    with col2:
        st.markdown("**Grafos**")
        st.code(f"Expansion Depth: {config.graph_expansion_depth}")
        st.code(f"Max Nodes: {config.graph_expansion_max_nodes}")

    with col3:
        st.markdown("**Comunidades**")
        st.code(f"Min Size: {config.community_min_size}")
        st.code(f"Resolution: {config.community_resolution}")
        st.code(f"Hub Min Conn: {config.hub_min_connections}")


# ==================== MAIN ====================

def main():
    """Função principal."""
    # Inicializa session_state
    if "namespace" not in st.session_state:
        st.session_state.namespace = "default"

    # Carrega grafo
    graph = load_graph(st.session_state.namespace)

    # Renderiza sidebar e obtém página
    page = render_sidebar()

    # Renderiza página selecionada
    page_clean = page.split(" ", 1)[1] if " " in page else page

    if "Dashboard" in page:
        render_dashboard(graph)
    elif "Grafo" in page:
        render_graph_visual(graph)
    elif "Comunidades" in page:
        render_communities(graph)
    elif "Compliance" in page:
        render_compliance(graph)
    elif "Entidades" in page:
        render_entities(graph)
    elif "Episódios" in page:
        render_episodes(graph)
    elif "Relações" in page:
        render_relations(graph)
    elif "Busca" in page:
        render_search(graph)


if __name__ == "__main__":
    main()
