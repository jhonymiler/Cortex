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

from cortex.core.memory_graph import MemoryGraph
from cortex.core.entity import Entity
from cortex.core.episode import Episode
from cortex.core.relation import Relation


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

def get_data_dir() -> Path:
    """Retorna o diretório de dados do Cortex."""
    data_dir = os.environ.get("CORTEX_DATA_DIR")
    if data_dir:
        return Path(data_dir)
    return Path.home() / ".cortex"


@st.cache_resource
def load_graph() -> MemoryGraph:
    """Carrega o grafo de memória."""
    data_dir = get_data_dir()
    return MemoryGraph(storage_path=data_dir)


def reload_graph() -> MemoryGraph:
    """Recarrega o grafo (limpa cache)."""
    st.cache_resource.clear()
    return load_graph()


# ==================== SIDEBAR ====================

def render_sidebar():
    """Renderiza a sidebar com controles."""
    st.sidebar.title("🧠 Cortex")
    st.sidebar.markdown("---")
    
    # Seletor de diretório
    data_dir = st.sidebar.text_input(
        "📁 Diretório de dados",
        value=str(get_data_dir()),
        help="Caminho para os dados do Cortex"
    )
    
    if data_dir != str(get_data_dir()):
        os.environ["CORTEX_DATA_DIR"] = data_dir
        if st.sidebar.button("🔄 Recarregar"):
            reload_graph()
            st.rerun()
    
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
            reload_graph()
            st.rerun()
    with col2:
        if st.button("🗑️ Limpar", use_container_width=True, type="secondary"):
            if st.sidebar.checkbox("Confirmar limpeza"):
                graph = load_graph()
                graph.clear()
                reload_graph()
                st.success("Memórias limpas!")
                st.rerun()
    
    # Decay manual (para testes)
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔧 Decay Manual")
    st.sidebar.caption("⚠️ O decay acontece automaticamente durante o recall. Use apenas para testes.")
    decay_factor = st.sidebar.slider("Fator de decay", 0.80, 0.99, 0.95, 0.01)
    if st.sidebar.button("🧹 Aplicar Decay", use_container_width=True):
        graph = load_graph()
        result = graph.apply_access_decay([], [], decay_factor)
        reload_graph()
        st.sidebar.success(f"Decay aplicado! Esquecido: {result['episodes_forgotten']} eps, {result['relations_forgotten']} rels")
        st.rerun()
    
    return page


# ==================== PAGES ====================

def render_dashboard(graph: MemoryGraph):
    """Página principal com estatísticas."""
    st.title("📊 Dashboard")
    
    stats = graph.stats()
    graph_data = graph.get_graph_data()
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
    
    graph_data = graph.get_graph_data()
    
    if not graph_data["nodes"]:
        st.info("Grafo vazio. Crie algumas memórias primeiro!")
        return
    
    # Controles
    col1, col2, col3 = st.columns(3)
    with col1:
        show_entities = st.checkbox("🎯 Entidades", value=True)
    with col2:
        show_episodes = st.checkbox("📝 Episódios", value=True)
    with col3:
        physics_enabled = st.checkbox("🌀 Física", value=True)
    
    # Filtro por peso mínimo
    min_weight = st.slider("Peso mínimo", 0.0, 1.0, 0.0, 0.1)
    
    # Prepara nós e arestas
    nodes = []
    edges = []
    
    visible_ids = set()
    
    for node in graph_data["nodes"]:
        if node["weight"] < min_weight:
            continue
        if node["type"] == "entity" and not show_entities:
            continue
        if node["type"] == "episode" and not show_episodes:
            continue
        
        visible_ids.add(node["id"])
        nodes.append(Node(
            id=node["id"],
            label=node["label"],
            size=node["size"],
            color=node["color"],
            title=f"{node['type']}: {node['label']}\nPeso: {node['weight']:.2f}",
        ))
    
    for edge in graph_data["edges"]:
        if edge["from"] in visible_ids and edge["to"] in visible_ids:
            edges.append(Edge(
                source=edge["from"],
                target=edge["to"],
                label=edge["label"],
                width=edge["width"],
                color=edge["color"],
            ))
    
    # Configuração do grafo
    config = Config(
        width=1200,
        height=600,
        directed=True,
        physics=physics_enabled,
        hierarchical=False,
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
                    graph.add_relation(relation)
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
    # Carrega grafo
    graph = load_graph()
    
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
