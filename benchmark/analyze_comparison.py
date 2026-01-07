#!/usr/bin/env python3
"""
Análise de Benchmark de Comparação (Cortex vs RAG vs Mem0 vs Baseline)
"""
import json
import sys
from pathlib import Path
from collections import defaultdict


def load_latest_result():
    """Carrega o resultado mais recente."""
    results_dir = Path(__file__).parent / "results"
    
    # Procura por full_comparison primeiro
    files = sorted(results_dir.glob("full_comparison_*.json"), reverse=True)
    if not files:
        files = sorted(results_dir.glob("*.json"), reverse=True)
    
    if not files:
        return None
    
    with open(files[0]) as f:
        return json.load(f), files[0].name


def analyze_comparison(data: dict) -> None:
    """Analisa resultados de comparação."""
    summary = data.get("summary", {})
    conversations = data.get("conversations", [])
    
    print("=" * 70)
    print(" 📊 ANÁLISE DO BENCHMARK DE COMPARAÇÃO COMPLETA")
    print("=" * 70)
    print()
    
    # Métricas gerais
    print("📈 MÉTRICAS GERAIS")
    print(f"   Conversas: {summary.get('total_conversations', 0)}")
    print(f"   Sessões: {summary.get('total_sessions', 0)}")
    print(f"   Mensagens: {summary.get('total_messages', 0)}")
    print(f"   Consolidações: {summary.get('consolidated_conversations', 0)}")
    print()
    
    # Tokens por agente
    print("💰 TOKENS POR AGENTE")
    agents = ["baseline", "rag", "mem0", "cortex"]
    baseline_tokens = summary.get("baseline_total_tokens", 0)
    
    for agent in agents:
        tokens = summary.get(f"{agent}_total_tokens", 0)
        if agent == "baseline":
            print(f"   {agent:12s}: {tokens:>8,} tokens")
        else:
            diff = summary.get(f"{agent}_vs_baseline_pct", 0)
            emoji = "✅" if diff < 80 else "⚠️" if diff < 100 else "❌"
            print(f"   {agent:12s}: {tokens:>8,} tokens ({diff:+.1f}% vs baseline) {emoji}")
    print()
    
    # Memórias recuperadas
    print("🧠 MEMÓRIAS RECUPERADAS")
    for agent in ["rag", "mem0", "cortex"]:
        memories = summary.get(f"{agent}_total_memories_retrieved", 0)
        is_best = memories == max(
            summary.get(f"{a}_total_memories_retrieved", 0) for a in ["rag", "mem0", "cortex"]
        )
        emoji = "✅" if is_best else ""
        print(f"   {agent:12s}: {memories:>5} memórias {emoji}")
    print()
    
    # Por domínio
    print("📂 ANÁLISE POR DOMÍNIO")
    print("-" * 70)
    print(f"{'Domínio':<20} {'Baseline':>10} {'RAG':>10} {'Mem0':>10} {'Cortex':>10}")
    print("-" * 70)
    
    domain_stats = defaultdict(lambda: defaultdict(int))
    for conv in conversations:
        domain = conv["domain"]
        for session in conv["sessions"]:
            for agent in agents:
                domain_stats[domain][agent] += session["total_tokens"].get(agent, 0)
    
    for domain, stats in domain_stats.items():
        baseline = stats["baseline"]
        rag = stats["rag"]
        mem0 = stats["mem0"]
        cortex = stats["cortex"]
        
        # Destaca o melhor (menor tokens entre os com memória)
        best_memory = min(rag, mem0, cortex)
        
        rag_mark = "✅" if rag == best_memory else ""
        mem0_mark = "✅" if mem0 == best_memory else ""
        cortex_mark = "✅" if cortex == best_memory else ""
        
        print(f"{domain:<20} {baseline:>10,} {rag:>9,}{rag_mark} {mem0:>9,}{mem0_mark} {cortex:>9,}{cortex_mark}")
    
    print("-" * 70)
    print()
    
    # Análise de volta do usuário
    print("🔄 TESTE DE VOLTA DO USUÁRIO")
    returning_sessions = 0
    cortex_remembered = 0
    
    for conv in conversations:
        for session in conv["sessions"]:
            if session.get("is_returning_user"):
                returning_sessions += 1
                # Verifica se cortex usou memórias
                for msg in session["messages"]:
                    if msg.get("cortex_memories", 0) > 0:
                        cortex_remembered += 1
                        break
    
    if returning_sessions > 0:
        rate = (cortex_remembered / returning_sessions) * 100
        print(f"   Sessões de retorno: {returning_sessions}")
        print(f"   Cortex lembrou: {cortex_remembered}/{returning_sessions} ({rate:.0f}%)")
    print()
    
    # Vencedor final
    print("🏆 CONCLUSÃO")
    
    # Menor aumento de tokens
    diffs = {
        "rag": summary.get("rag_vs_baseline_pct", 999),
        "mem0": summary.get("mem0_vs_baseline_pct", 999),
        "cortex": summary.get("cortex_vs_baseline_pct", 999),
    }
    best_tokens = min(diffs, key=diffs.get)
    
    # Mais memórias
    mems = {
        "rag": summary.get("rag_total_memories_retrieved", 0),
        "mem0": summary.get("mem0_total_memories_retrieved", 0),
        "cortex": summary.get("cortex_total_memories_retrieved", 0),
    }
    best_memory = max(mems, key=mems.get)
    
    print(f"   📉 Menor aumento de tokens: {best_tokens.upper()} ({diffs[best_tokens]:+.1f}%)")
    print(f"   🧠 Mais contexto recuperado: {best_memory.upper()} ({mems[best_memory]} memórias)")
    print()
    
    if best_tokens == "cortex" and best_memory == "cortex":
        print("   ✅ CORTEX VENCEU EM AMBOS OS CRITÉRIOS!")
    elif best_tokens == "cortex" or best_memory == "cortex":
        print(f"   ⚠️ CORTEX venceu em {'tokens' if best_tokens == 'cortex' else 'contexto'}")
    
    print()
    print("=" * 70)


def main():
    result = load_latest_result()
    if not result:
        print("❌ Nenhum resultado encontrado em benchmark/results/")
        sys.exit(1)
    
    data, filename = result
    print(f"📄 Analisando: {filename}")
    print()
    
    analyze_comparison(data)


if __name__ == "__main__":
    main()

