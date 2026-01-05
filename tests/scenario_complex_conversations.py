#!/usr/bin/env python3
"""
Teste de conversas complexas para popular o grafo de memória.

Este script simula várias interações para testar:
- Criação de entidades e episódios
- Formação de relações
- Consolidação de memórias
- Peso baseado em conexões
"""

import os
import sys
from pathlib import Path

# Adiciona o src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cortex.services.memory_service import (
    MemoryService,
    StoreRequest,
    RecallRequest,
    ParticipantInput,
)
from cortex.core.relation import Relation


def get_service(data_dir: str = "./data") -> MemoryService:
    """Cria serviço de memória."""
    return MemoryService(storage_path=Path(data_dir))


def create_relation(from_name: str, rel_type: str, to_name: str) -> dict:
    """Helper para criar dict de relação compatível com Pydantic alias."""
    return {"from": from_name, "type": rel_type, "to": to_name}


def test_scenario_1_projeto_ia(service: MemoryService):
    """Cenário 1: Desenvolvimento de projeto de IA."""
    print("\n" + "="*60)
    print("📁 CENÁRIO 1: Projeto de IA")
    print("="*60)
    
    # Interação 1: Início do projeto
    print("\n1️⃣ Iniciando projeto...")
    result = service.store(StoreRequest(
        action="created_project",
        outcome="Criou projeto Cortex - sistema de memória cognitiva para LLMs",
        context="Janeiro 2026, início do desenvolvimento",
        participants=[
            ParticipantInput(type="person", name="Jhony"),
            ParticipantInput(type="project", name="Cortex"),
            ParticipantInput(type="concept", name="Memória Cognitiva"),
        ],
        relations=[
            create_relation("Jhony", "created", "Cortex"),
            create_relation("Cortex", "implements", "Memória Cognitiva"),
        ],
    ))
    print(f"   ✓ Episódio: {result.episode_id[:8]}... | Entidades: +{result.entities_created}")
    
    # Interação 2: Definição de arquitetura
    print("\n2️⃣ Definindo arquitetura...")
    result = service.store(StoreRequest(
        action="designed_architecture",
        outcome="Definiu arquitetura em 3 camadas: Core, Services, API/MCP",
        context="Discussão sobre estrutura do projeto",
        participants=[
            ParticipantInput(type="person", name="Jhony"),
            ParticipantInput(type="project", name="Cortex"),
            ParticipantInput(type="concept", name="Entity-Episode-Relation"),
            ParticipantInput(type="concept", name="Grafo de Memória"),
        ],
        relations=[
            create_relation("Cortex", "uses", "Entity-Episode-Relation"),
            create_relation("Cortex", "based_on", "Grafo de Memória"),
        ],
    ))
    print(f"   ✓ Episódio: {result.episode_id[:8]}... | Entidades: +{result.entities_created}")
    
    # Interação 3: Implementação do Core
    print("\n3️⃣ Implementando core...")
    result = service.store(StoreRequest(
        action="implemented_core",
        outcome="Implementou Entity, Episode, Relation e MemoryGraph",
        participants=[
            ParticipantInput(type="person", name="Jhony"),
            ParticipantInput(type="file", name="memory_graph.py"),
            ParticipantInput(type="file", name="entity.py"),
        ],
        relations=[
            create_relation("Jhony", "coded", "memory_graph.py"),
            create_relation("memory_graph.py", "depends_on", "entity.py"),
        ],
    ))
    print(f"   ✓ Episódio: {result.episode_id[:8]}... | Entidades: +{result.entities_created}")
    
    # Interação 4: Bug encontrado
    print("\n4️⃣ Encontrando bug...")
    result = service.store(StoreRequest(
        action="found_bug",
        outcome="Descobriu que MCP não estava persistindo - env PATH não herdado",
        context="Debug de persistência",
        participants=[
            ParticipantInput(type="person", name="Jhony"),
            ParticipantInput(type="error", name="MCP Persistence Bug"),
            ParticipantInput(type="file", name="agent_with_mcp.py"),
        ],
        relations=[
            create_relation("MCP Persistence Bug", "found_in", "agent_with_mcp.py"),
        ],
    ))
    print(f"   ✓ Episódio: {result.episode_id[:8]}... | Entidades: +{result.entities_created}")
    
    # Interação 5: Bug resolvido
    print("\n5️⃣ Resolvendo bug...")
    result = service.store(StoreRequest(
        action="resolved_bug",
        outcome="Corrigiu herdando env completo com os.environ.copy()",
        participants=[
            ParticipantInput(type="person", name="Jhony"),
            ParticipantInput(type="error", name="MCP Persistence Bug"),
        ],
        relations=[
            create_relation("Jhony", "fixed", "MCP Persistence Bug"),
        ],
    ))
    print(f"   ✓ Episódio: {result.episode_id[:8]}... | Entidades: +{result.entities_created}")


def test_scenario_2_conversas_usuario(service: MemoryService):
    """Cenário 2: Conversas com usuário (simula chat)."""
    print("\n" + "="*60)
    print("💬 CENÁRIO 2: Conversas com Usuário")
    print("="*60)
    
    conversas = [
        ("Olá, meu nome é Jhony", "Prazer em conhecê-lo!"),
        ("Trabalho com IA e machine learning", "Interessante área!"),
        ("Estou desenvolvendo um sistema de memória", "Parece um projeto fascinante"),
        ("Uso Python e FastMCP", "Ótimas escolhas tecnológicas"),
        ("O projeto se chama Cortex", "Nome muito apropriado para memória"),
    ]
    
    for i, (msg, resp) in enumerate(conversas, 1):
        print(f"\n{i}️⃣ '{msg[:30]}...'")
        result = service.store(StoreRequest(
            action=f"conversed_about: {msg[:40]}",
            outcome=resp,
            participants=[
                ParticipantInput(type="person", name="Jhony"),
            ],
        ))
        print(f"   ✓ Episódio: {result.episode_id[:8]}... | Consolidado: {result.consolidated}")


def test_scenario_3_consolidation(service: MemoryService):
    """Cenário 3: Teste de consolidação (5+ similares)."""
    print("\n" + "="*60)
    print("⭐ CENÁRIO 3: Teste de Consolidação")
    print("="*60)
    
    print("\nCriando 6 episódios similares (deve consolidar no 5º)...")
    
    for i in range(6):
        result = service.store(StoreRequest(
            action="asked_about_weather",
            outcome=f"Informou previsão do tempo #{i+1}",
            participants=[
                ParticipantInput(type="person", name="Usuário Teste"),
            ],
        ))
        status = "⭐ CONSOLIDADO" if result.consolidated else "normal"
        print(f"   {i+1}. Episódio: {result.episode_id[:8]}... | Count: {result.consolidation_count} | {status}")


def test_scenario_4_complex_relations(service: MemoryService):
    """Cenário 4: Relações complexas entre entidades."""
    print("\n" + "="*60)
    print("🔗 CENÁRIO 4: Relações Complexas")
    print("="*60)
    
    # Cria uma rede de conceitos relacionados
    print("\n1️⃣ Criando rede de conceitos de IA...")
    result = service.store(StoreRequest(
        action="learned_ml_concepts",
        outcome="Estudou conceitos fundamentais de ML",
        participants=[
            ParticipantInput(type="concept", name="Machine Learning"),
            ParticipantInput(type="concept", name="Deep Learning"),
            ParticipantInput(type="concept", name="Neural Networks"),
            ParticipantInput(type="concept", name="Transformers"),
            ParticipantInput(type="concept", name="Attention Mechanism"),
        ],
        relations=[
            create_relation("Deep Learning", "is_subset_of", "Machine Learning"),
            create_relation("Neural Networks", "enables", "Deep Learning"),
            create_relation("Transformers", "uses", "Attention Mechanism"),
            create_relation("Transformers", "is_type_of", "Neural Networks"),
        ],
    ))
    print(f"   ✓ Episódio: {result.episode_id[:8]}... | Relações: +{result.relations_created}")
    
    print("\n2️⃣ Conectando conceitos a projetos...")
    result = service.store(StoreRequest(
        action="applied_concepts",
        outcome="Aplicou conceitos de ML no Cortex",
        participants=[
            ParticipantInput(type="project", name="Cortex"),
            ParticipantInput(type="concept", name="Grafo de Memória"),
            ParticipantInput(type="concept", name="Neural Networks"),
        ],
        relations=[
            create_relation("Cortex", "inspired_by", "Neural Networks"),
            create_relation("Grafo de Memória", "similar_to", "Neural Networks"),
        ],
    ))
    print(f"   ✓ Episódio: {result.episode_id[:8]}... | Relações: +{result.relations_created}")


def test_recall(service: MemoryService):
    """Testa busca de memórias."""
    print("\n" + "="*60)
    print("🔍 TESTE DE RECALL")
    print("="*60)
    
    queries = [
        "Jhony",
        "Cortex projeto",
        "bug MCP",
        "machine learning",
    ]
    
    for query in queries:
        print(f"\n🔍 Query: '{query}'")
        result = service.recall(RecallRequest(query=query, limit=3))
        
        print(f"   Entidades: {result.entities_found}")
        print(f"   Episódios: {result.episodes_found}")
        print(f"   Resumo: {result.context_summary[:80]}...")


def show_stats(service: MemoryService):
    """Mostra estatísticas finais."""
    print("\n" + "="*60)
    print("📊 ESTATÍSTICAS FINAIS")
    print("="*60)
    
    stats = service.stats()
    
    print(f"\n   🎯 Entidades: {stats.total_entities}")
    print(f"   📝 Episódios: {stats.total_episodes}")
    print(f"   🔗 Relações: {stats.total_relations}")
    print(f"   ⭐ Consolidados: {stats.consolidated_episodes}")
    
    print("\n   📈 Por tipo:")
    for entity_type, count in stats.entities_by_type.items():
        print(f"      - {entity_type}: {count}")
    
    # Mostra top nós por peso
    print("\n   🏆 Top 5 nós por peso:")
    graph_data = service.graph.get_graph_data()
    sorted_nodes = sorted(graph_data["nodes"], key=lambda x: x["weight"], reverse=True)[:5]
    for i, node in enumerate(sorted_nodes, 1):
        print(f"      {i}. {node['label']} ({node['type']}) - {node['weight']:.2f}")


def main():
    """Executa todos os testes."""
    print("🧠 TESTE DE CONVERSAS COMPLEXAS - CORTEX")
    print("="*60)
    
    # Usa o diretório de dados do teste-llm
    data_dir = os.environ.get("CORTEX_DATA_DIR", "./data")
    print(f"📁 Diretório de dados: {data_dir}")
    
    service = get_service(data_dir)
    
    # Executa cenários
    test_scenario_1_projeto_ia(service)
    test_scenario_2_conversas_usuario(service)
    test_scenario_3_consolidation(service)
    test_scenario_4_complex_relations(service)
    
    # Testa recall
    test_recall(service)
    
    # Mostra estatísticas
    show_stats(service)
    
    print("\n" + "="*60)
    print("✅ TESTES CONCLUÍDOS!")
    print("="*60)
    print("\n👉 Abra o Streamlit UI para visualizar o grafo:")
    print("   streamlit run src/cortex/ui/app.py")


if __name__ == "__main__":
    main()
