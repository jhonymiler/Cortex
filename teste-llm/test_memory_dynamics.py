#!/usr/bin/env python3
"""
Teste do sistema de memória: decay por ACESSO (não temporal).

Demonstra:
1. Como memórias ACESSADAS se fortalecem (recall)
2. Como memórias NÃO ACESSADAS decaem durante o uso
3. Competição natural - relevantes sobem, irrelevantes descem
4. Eficiência real para o LLM
"""

import os
import sys
from pathlib import Path
import shutil

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cortex.services.memory_service import (
    MemoryService,
    StoreRequest,
    RecallRequest,
    ParticipantInput,
)


def print_separator(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def print_health(service: MemoryService, label: str = ""):
    """Mostra saúde da memória."""
    health = service.get_health()
    print(f"\n📊 Saúde da Memória {label}")
    print(f"   Entidades: {health['total_entities']}")
    print(f"   Episódios: {health['total_episodes']}")
    print(f"   Relações: {health['total_relations']}")
    print(f"   Órfãos: {health['orphan_entities']} entidades")
    print(f"   Solitários: {health['lonely_episodes']} episódios")
    print(f"   Fracas: {health['weak_relations']} relações")
    print(f"   Importância média: {health['avg_episode_importance']:.3f}")
    print(f"   Força média: {health['avg_relation_strength']:.3f}")
    print(f"   🏥 Score de Saúde: {health['health_score']}%")


def print_episode_importance(service: MemoryService):
    """Mostra importância de cada episódio."""
    print("\n   Episódios ordenados por importância:")
    episodes = sorted(
        service.graph._episodes.values(),
        key=lambda e: e.importance,
        reverse=True
    )
    for ep in episodes[:10]:
        marker = "⭐" if ep.is_consolidated else "📝"
        print(f"      {marker} {ep.action}: importance={ep.importance:.3f}")


def test_access_based_decay():
    """Testa o sistema de decay baseado em ACESSO."""
    print_separator("TESTE: DECAY BASEADO EM ACESSO")
    
    # Cria serviço limpo
    test_dir = Path("./data_access_test")
    shutil.rmtree(test_dir, ignore_errors=True)
    service = MemoryService(storage_path=test_dir)
    
    print("\n1️⃣ Criando 5 memórias diferentes...")
    
    # Cria memórias sobre diferentes assuntos
    topics = [
        ("learned_python", "Aprendeu Python", "Python"),
        ("learned_javascript", "Aprendeu JavaScript", "JavaScript"),
        ("learned_rust", "Aprendeu Rust", "Rust"),
        ("learned_go", "Aprendeu Go", "Go"),
        ("learned_java", "Aprendeu Java", "Java"),
    ]
    
    for action, outcome, topic in topics:
        service.store(StoreRequest(
            action=action,
            outcome=outcome,
            participants=[ParticipantInput(type="language", name=topic)],
        ))
    
    print_episode_importance(service)
    
    print("\n2️⃣ Fazendo 10 recalls APENAS de 'Python'...")
    print("   (Outras memórias devem enfraquecer)")
    
    for i in range(10):
        result = service.recall(RecallRequest(query="Python programação", limit=3))
        if i % 3 == 0:
            print(f"   Recall {i+1}: {result.episodes_found} episódios, contexto: {len(result.context_summary)} chars")
    
    print("\n3️⃣ Estado após 10 recalls de Python:")
    print_episode_importance(service)
    
    # Verifica que Python está no topo
    episodes = list(service.graph._episodes.values())
    python_ep = next((e for e in episodes if "python" in e.action.lower()), None)
    others = [e for e in episodes if "python" not in e.action.lower()]
    
    if python_ep and others:
        avg_others = sum(e.importance for e in others) / len(others)
        print(f"\n   📈 Python importance: {python_ep.importance:.3f}")
        print(f"   📉 Média dos outros: {avg_others:.3f}")
        
        if python_ep.importance > avg_others * 1.5:
            print("   ✅ Python está SIGNIFICATIVAMENTE mais forte!")
        elif python_ep.importance > avg_others:
            print("   ✅ Python está mais forte (mas pouco)")
        else:
            print("   ⚠️ Algo errado - Python deveria estar mais forte")
    
    print("\n4️⃣ Agora fazendo recalls de outras linguagens...")
    
    for lang in ["JavaScript", "Rust", "Go"]:
        for _ in range(3):
            service.recall(RecallRequest(query=f"{lang} programming", limit=3))
    
    print_episode_importance(service)
    
    # Java não foi acessado, deve estar fraco
    java_ep = next((e for e in service.graph._episodes.values() if "java" in e.action.lower()), None)
    if java_ep:
        print(f"\n   🔍 Java (nunca acessado): importance={java_ep.importance:.3f}")
        if java_ep.importance < 0.3:
            print("   ✅ Java enfraqueceu (não foi acessado)")
    
    # Limpa
    shutil.rmtree(test_dir, ignore_errors=True)


def test_competitive_memory():
    """Testa competição entre memórias - relevantes sobem, outras descem."""
    print_separator("TESTE: COMPETIÇÃO ENTRE MEMÓRIAS")
    
    test_dir = Path("./data_competition_test")
    shutil.rmtree(test_dir, ignore_errors=True)
    service = MemoryService(storage_path=test_dir)
    
    print("\n1️⃣ Criando contexto de trabalho...")
    
    # Simula um desenvolvedor trabalhando em projeto
    service.store(StoreRequest(
        action="started_project",
        outcome="Iniciou projeto WebApp",
        participants=[
            ParticipantInput(type="project", name="WebApp"),
            ParticipantInput(type="person", name="Dev"),
        ],
    ))
    
    service.store(StoreRequest(
        action="fixed_bug",
        outcome="Corrigiu bug de login",
        participants=[
            ParticipantInput(type="project", name="WebApp"),
            ParticipantInput(type="bug", name="BUG-001"),
        ],
    ))
    
    service.store(StoreRequest(
        action="attended_meeting",
        outcome="Reunião de planejamento",
        participants=[
            ParticipantInput(type="person", name="Dev"),
            ParticipantInput(type="person", name="PM"),
        ],
    ))
    
    # Memória antiga/irrelevante
    service.store(StoreRequest(
        action="old_project_note",
        outcome="Notas do projeto antigo LegacyApp",
        participants=[
            ParticipantInput(type="project", name="LegacyApp"),
        ],
    ))
    
    print("   Memórias criadas: WebApp (2), Meeting (1), LegacyApp (1)")
    
    print("\n2️⃣ Simulando trabalho focado em WebApp (20 recalls)...")
    
    for i in range(20):
        service.recall(RecallRequest(query="WebApp projeto bug login", limit=3))
    
    print_episode_importance(service)
    
    # LegacyApp deve estar bem fraco
    legacy_ep = next(
        (e for e in service.graph._episodes.values() if "legacy" in e.action.lower()),
        None
    )
    webapp_eps = [
        e for e in service.graph._episodes.values() 
        if "webapp" in (e.outcome.lower() + e.action.lower())
    ]
    
    if legacy_ep and webapp_eps:
        avg_webapp = sum(e.importance for e in webapp_eps) / len(webapp_eps)
        print(f"\n   📈 WebApp média: {avg_webapp:.3f}")
        print(f"   📉 LegacyApp: {legacy_ep.importance:.3f}")
        
        ratio = avg_webapp / legacy_ep.importance if legacy_ep.importance > 0 else float('inf')
        print(f"   Razão: {ratio:.1f}x mais forte")
        
        if ratio > 2:
            print("   ✅ Memórias relevantes dominam!")
    
    # Limpa
    shutil.rmtree(test_dir, ignore_errors=True)


def test_efficiency():
    """Testa eficiência real - quanto ajuda o LLM."""
    print_separator("TESTE: EFICIÊNCIA PARA O LLM")
    
    test_dir = Path("./data_efficiency_test")
    shutil.rmtree(test_dir, ignore_errors=True)
    service = MemoryService(storage_path=test_dir)
    
    print("\n1️⃣ Simulando 20 interações sobre projeto...")
    
    interactions = [
        ("discussed_project", "Discutiu requisitos do projeto Alpha", ["PM", "Dev"]),
        ("created_task", "Criou tarefa de autenticação", ["Dev"]),
        ("resolved_bug", "Corrigiu bug de login", ["Dev", "Bug #123"]),
        ("discussed_project", "Revisou progresso do Alpha", ["PM", "Dev"]),
        ("code_review", "Revisou PR de autenticação", ["Dev", "Reviewer"]),
        ("discussed_project", "Planning do Alpha", ["PM", "Dev"]),
        ("deployed", "Deploy da v0.1 do Alpha", ["DevOps"]),
        ("discussed_project", "Retrospectiva do Alpha", ["PM", "Dev"]),
        ("resolved_bug", "Corrigiu bug de sessão", ["Dev", "Bug #456"]),
        ("discussed_project", "Kickoff fase 2 do Alpha", ["PM", "Dev"]),  # 5x = consolida!
    ]
    
    for action, outcome, parts in interactions:
        service.store(StoreRequest(
            action=action,
            outcome=outcome,
            participants=[
                ParticipantInput(
                    type="person" if not p.startswith("Bug") else "bug",
                    name=p
                ) for p in parts
            ],
        ))
    
    print(f"   Armazenadas {len(interactions)} interações")
    
    # Verifica consolidação
    consolidated = sum(1 for e in service.graph._episodes.values() if e.is_consolidated)
    print(f"   Consolidadas: {consolidated} (padrões detectados)")
    
    print("\n2️⃣ Recall de 'projeto Alpha':")
    result = service.recall(RecallRequest(query="projeto Alpha", limit=5))
    
    print(f"   Entidades relevantes: {result.entities_found}")
    print(f"   Episódios relevantes: {result.episodes_found}")
    print(f"\n   📝 Contexto gerado para LLM:")
    print("   " + "-"*50)
    for line in result.prompt_context.split("\n"):
        print(f"   {line}")
    print("   " + "-"*50)
    
    # Métricas
    total_memories = len(service.graph._episodes)
    relevant = result.episodes_found
    context_size = len(result.prompt_context)
    
    print("\n3️⃣ Métricas de Eficiência:")
    print(f"   Total de memórias: {total_memories}")
    print(f"   Relevantes retornadas: {relevant}")
    print(f"   Tamanho do contexto: {context_size} chars")
    
    without_cortex = sum(len(i[1]) for i in interactions)
    with_cortex = context_size
    
    print(f"\n   💰 Economia de tokens estimada:")
    print(f"      Sem Cortex (texto bruto): ~{without_cortex} chars")
    print(f"      Com Cortex (contexto): ~{with_cortex} chars")
    
    # Limpa
    shutil.rmtree(test_dir, ignore_errors=True)


def main():
    print("🧠 TESTE DE MEMÓRIA: DECAY POR ACESSO")
    print("="*60)
    print("""
    CONCEITO-CHAVE:
    ---------------
    O decay NÃO é por tempo - é por ACESSO.
    
    - Quando você faz um RECALL, as memórias encontradas FORTALECEM
    - As memórias NÃO encontradas ENFRAQUECEM um pouco
    - Isso cria competição natural: relevantes sobem, irrelevantes descem
    
    Por que não temporal?
    - Um agente pode ficar meses sem atender um usuário
    - Quando voltar, as memórias devem estar lá!
    - O decay acontece durante o USO, não pela passagem de tempo
    """)
    
    test_access_based_decay()
    test_competitive_memory()
    test_efficiency()
    
    print_separator("CONCLUSÃO")
    print("""
    ✅ O sistema de memória Cortex:
    
    1. REFORÇO POR ACESSO: Memórias usadas se fortalecem
       - Cada recall fortalece as memórias encontradas
       - Entidades acessadas incrementam access_count
       - Relações envolvidas são reforçadas
    
    2. DECAY POR ACESSO: Memórias ignoradas enfraquecem
       - Durante cada recall, o que NÃO foi encontrado decai
       - Cria competição natural entre memórias
       - Relevantes sobem, irrelevantes descem
    
    3. ESQUECIMENTO: Memórias muito fracas são removidas
       - Episodes com importance < 0.1 (não consolidados)
       - Relações com strength < 0.05
       - Limpeza automática durante recalls
    
    4. NÃO É TEMPORAL:
       - Agente pode ficar meses offline
       - Memórias preservadas até próximo uso
       - Decay só acontece durante interação ativa
    
    5. EFICIÊNCIA REAL para LLM:
       - Reduz contexto enviado (só relevante)
       - Consolida padrões repetidos
       - Zero tokens para busca (índice, não embedding)
    """)


if __name__ == "__main__":
    main()
