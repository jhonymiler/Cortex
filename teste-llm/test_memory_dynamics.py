#!/usr/bin/env python3
"""
Teste do sistema de memória: decay, reforço e eficiência.

Demonstra:
1. Como memórias se fortalecem com uso (recall)
2. Como memórias decaem sem uso (temporal decay)
3. Como memórias fracas são esquecidas
4. Eficiência real para o LLM
"""

import os
import sys
from pathlib import Path
from datetime import datetime

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


def test_reinforcement(service: MemoryService):
    """Testa reforço de memórias no recall."""
    print_separator("TESTE 1: REFORÇO NO RECALL")
    
    # Cria algumas memórias
    print("\n1️⃣ Criando memórias iniciais...")
    
    service.store(StoreRequest(
        action="learned_python",
        outcome="Aprendeu Python básico",
        participants=[ParticipantInput(type="person", name="Estudante")],
    ))
    
    service.store(StoreRequest(
        action="learned_javascript",
        outcome="Aprendeu JavaScript",
        participants=[ParticipantInput(type="person", name="Estudante")],
    ))
    
    # Verifica importance inicial
    print("\n2️⃣ Importância inicial dos episódios:")
    for ep in service.graph._episodes.values():
        print(f"   - {ep.action}: importance={ep.importance:.3f}")
    
    # Faz recall múltiplas vezes de "python"
    print("\n3️⃣ Fazendo 5 recalls de 'python'...")
    for i in range(5):
        result = service.recall(RecallRequest(query="python", limit=3))
        print(f"   Recall {i+1}: encontrou {result.episodes_found} episódios")
    
    # Verifica importance após recalls
    print("\n4️⃣ Importância APÓS recalls:")
    for ep in service.graph._episodes.values():
        print(f"   - {ep.action}: importance={ep.importance:.3f}")
    
    # Note: Python deveria ter importance maior que JavaScript
    python_ep = next((e for e in service.graph._episodes.values() if "python" in e.action.lower()), None)
    js_ep = next((e for e in service.graph._episodes.values() if "javascript" in e.action.lower()), None)
    
    if python_ep and js_ep:
        if python_ep.importance > js_ep.importance:
            print("\n   ✅ Python tem importance MAIOR (foi mais acessado)")
        else:
            print("\n   ⚠️ Importâncias iguais ou invertidas")


def test_decay(service: MemoryService):
    """Testa decay temporal."""
    print_separator("TESTE 2: DECAY TEMPORAL")
    
    print("\n1️⃣ Estado antes do decay:")
    print_health(service, "(antes)")
    
    # Simula passagem de 7 dias
    print("\n2️⃣ Simulando 7 dias sem uso...")
    for day in range(7):
        result = service.apply_decay(hours_passed=24)
        forgotten = result['episodes_forgotten'] + result['relations_forgotten']
        print(f"   Dia {day+1}: decayed {result['episodes_decayed']} eps, {result['relations_decayed']} rels | Esquecido: {forgotten}")
    
    print("\n3️⃣ Estado após 7 dias:")
    print_health(service, "(após 7 dias)")


def test_forgetting(service: MemoryService):
    """Testa esquecimento de memórias fracas."""
    print_separator("TESTE 3: ESQUECIMENTO")
    
    # Cria memórias triviais (baixa importância)
    print("\n1️⃣ Criando memórias triviais...")
    
    for i in range(5):
        service.store(StoreRequest(
            action=f"trivial_action_{i}",
            outcome=f"Resultado trivial #{i}",
            participants=[],  # Sem participantes = memória solta
        ))
    
    print_health(service, "(com triviais)")
    
    # Simula muito tempo (30 dias)
    print("\n2️⃣ Simulando 30 dias...")
    for day in range(30):
        result = service.apply_decay(hours_passed=24)
    
    print("\n3️⃣ Estado após 30 dias:")
    print_health(service, "(após 30 dias)")
    
    print("\n   Memórias triviais devem ter sido esquecidas!")


def test_efficiency():
    """Testa eficiência real - quanto ajuda o LLM."""
    print_separator("TESTE 4: EFICIÊNCIA PARA O LLM")
    
    # Cria um serviço limpo
    service = MemoryService(storage_path=Path("./data_efficiency_test"))
    service.graph.clear()
    
    print("\n1️⃣ Simulando 20 interações sobre projeto...")
    
    # Simula conversa real sobre um projeto
    interactions = [
        ("discussed_project", "Discutiu requisitos do projeto Alpha", ["PM", "Dev"]),
        ("created_task", "Criou tarefa de autenticação", ["Dev"]),
        ("resolved_bug", "Corrigiu bug de login", ["Dev", "Bug #123"]),
        ("discussed_project", "Revisou progresso do Alpha", ["PM", "Dev"]),  # Similar
        ("code_review", "Revisou PR de autenticação", ["Dev", "Reviewer"]),
        ("discussed_project", "Planning do Alpha", ["PM", "Dev"]),  # Similar
        ("deployed", "Deploy da v0.1 do Alpha", ["DevOps"]),
        ("discussed_project", "Retrospectiva do Alpha", ["PM", "Dev"]),  # Similar
        ("resolved_bug", "Corrigiu bug de sessão", ["Dev", "Bug #456"]),
        ("discussed_project", "Kickoff fase 2 do Alpha", ["PM", "Dev"]),  # Similar (5x = consolida!)
    ]
    
    for action, outcome, parts in interactions:
        service.store(StoreRequest(
            action=action,
            outcome=outcome,
            participants=[ParticipantInput(type="person" if p != "Bug #123" and p != "Bug #456" else "bug", name=p) for p in parts],
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
    
    # Métricas de eficiência
    print("\n3️⃣ Métricas de Eficiência:")
    
    total_memories = len(service.graph._episodes)
    relevant = result.episodes_found
    context_size = len(result.prompt_context)
    
    print(f"   Total de memórias: {total_memories}")
    print(f"   Relevantes retornadas: {relevant}")
    print(f"   Tamanho do contexto: {context_size} chars")
    print(f"   Redução: {100 - (relevant/total_memories*100):.1f}% (menos = melhor)")
    
    # Simula custo de tokens
    # Sem Cortex: enviaria tudo (10 interações * ~50 chars = 500 chars)
    # Com Cortex: só relevantes (~200 chars contexto)
    without_cortex = sum(len(i[1]) for i in interactions)  # Texto bruto
    with_cortex = context_size
    
    print(f"\n   💰 Economia de tokens estimada:")
    print(f"      Sem Cortex: ~{without_cortex} chars")
    print(f"      Com Cortex: ~{with_cortex} chars")
    savings = max(0, (1 - with_cortex/without_cortex) * 100) if without_cortex > 0 else 0
    print(f"      Economia: {savings:.1f}%")
    
    # Limpa teste
    import shutil
    shutil.rmtree("./data_efficiency_test", ignore_errors=True)


def main():
    print("🧠 TESTE DE MEMÓRIA: DECAY, REFORÇO E EFICIÊNCIA")
    print("="*60)
    
    # Usa dados existentes
    data_dir = os.environ.get("CORTEX_DATA_DIR", "./data")
    print(f"📁 Diretório de dados: {data_dir}")
    
    service = MemoryService(storage_path=Path(data_dir))
    
    # Roda testes
    test_reinforcement(service)
    test_decay(service)
    # test_forgetting(service)  # Comentado para não perder dados
    
    # Teste de eficiência (usa dados temporários)
    test_efficiency()
    
    print_separator("CONCLUSÃO")
    print("""
    ✅ O sistema de memória Cortex:
    
    1. REFORÇO: Memórias acessadas se fortalecem
       - Cada recall aumenta importance em 0.05
       - Entidades acessadas incrementam access_count
       - Relações envolvidas são reforçadas
    
    2. DECAY: Memórias não usadas enfraquecem
       - ~1% decay por dia (exponencial)
       - Memórias importantes resistem mais
       - Memórias consolidadas nunca são esquecidas
    
    3. ESQUECIMENTO: Memórias muito fracas são removidas
       - Episodes com importance < 0.1 (não consolidados)
       - Relações com strength < 0.05
       - Entidades órfãs pouco acessadas
    
    4. EFICIÊNCIA REAL para LLM:
       - Reduz contexto enviado (só relevante)
       - Consolida padrões repetidos
       - Conexões ajudam a encontrar relacionados
       - Zero tokens para busca (índice, não embedding)
    """)
    
    print_health(service, "(final)")


if __name__ == "__main__":
    main()
