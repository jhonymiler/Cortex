#!/usr/bin/env python3
"""
Validação do Benchmark - Garante que todos os dados necessários para o paper são coletados.
"""
import json
import sys
from pathlib import Path
from datetime import datetime


# Dados necessários para o paper (docs/PAPER_TEMPLATE.md)
PAPER_REQUIREMENTS = {
    "summary": {
        "required": [
            "total_conversations",
            "total_sessions", 
            "total_messages",
            "baseline_total_tokens",
            "rag_total_tokens",
            "mem0_total_tokens",
            "cortex_total_tokens",
            "rag_vs_baseline_pct",
            "mem0_vs_baseline_pct",
            "cortex_vs_baseline_pct",
            "rag_total_memories_retrieved",
            "mem0_total_memories_retrieved",
            "cortex_total_memories_retrieved",
        ],
        "optional": [
            "consolidated_conversations",
        ]
    },
    "conversations": {
        "required_per_conversation": [
            "domain",
            "user_id",
            "sessions",
        ],
        "required_per_session": [
            "session_idx",
            "is_returning_user",
            "messages",
            "total_tokens",
            "total_latency",
            "memories_retrieved",
        ],
        "required_per_message": [
            "role",
            "content",
            "baseline_tokens",
            "baseline_latency",
            "rag_tokens",
            "rag_latency",
            "mem0_tokens",
            "mem0_latency",
            "cortex_tokens",
            "cortex_latency",
            "cortex_memories",
        ]
    }
}


def validate_result(data: dict) -> tuple[bool, list[str]]:
    """Valida se o resultado contém todos os dados necessários."""
    errors = []
    
    # Valida summary
    summary = data.get("summary", {})
    for field in PAPER_REQUIREMENTS["summary"]["required"]:
        if field not in summary:
            errors.append(f"❌ Falta campo summary.{field}")
    
    # Valida conversations
    conversations = data.get("conversations", [])
    if not conversations:
        errors.append("❌ Nenhuma conversa encontrada")
    
    for i, conv in enumerate(conversations[:3]):  # Valida primeiras 3
        for field in PAPER_REQUIREMENTS["conversations"]["required_per_conversation"]:
            if field not in conv:
                errors.append(f"❌ Conversa {i}: falta {field}")
        
        sessions = conv.get("sessions", [])
        for j, session in enumerate(sessions[:2]):  # Valida primeiras 2
            for field in PAPER_REQUIREMENTS["conversations"]["required_per_session"]:
                if field not in session:
                    errors.append(f"❌ Conversa {i}, Sessão {j}: falta {field}")
            
            messages = session.get("messages", [])
            for k, msg in enumerate(messages[:2]):  # Valida primeiras 2
                for field in PAPER_REQUIREMENTS["conversations"]["required_per_message"]:
                    if field not in msg:
                        errors.append(f"❌ Conv {i}, Sess {j}, Msg {k}: falta {field}")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def validate_graph_data(data_dir: Path) -> tuple[int, int]:
    """Valida dados de grafo salvos."""
    saved = 0
    empty = 0
    
    for graph_dir in data_dir.glob("bench_*"):
        graph_file = graph_dir / "memory_graph.json"
        if graph_file.exists() and graph_file.stat().st_size > 100:
            saved += 1
        else:
            empty += 1
    
    return saved, empty


def check_requirements_for_paper():
    """Verifica requisitos do paper."""
    print("=" * 70)
    print(" 📝 VERIFICAÇÃO DE REQUISITOS PARA O PAPER")
    print("=" * 70)
    print()
    
    # Baseado em PAPER_TEMPLATE.md
    requirements = [
        ("Baselines comparados", ["Baseline", "RAG", "Mem0", "Cortex"], True),
        ("Métricas de tokens", ["total_tokens por agente", "% vs baseline"], True),
        ("Memórias recuperadas", ["total por agente"], True),
        ("Análise por domínio", ["tokens por domínio"], True),
        ("Teste de retorno", ["sessões de retorno", "taxa de lembrança"], True),
        ("Consolidação", ["DreamAgent executado"], True),
        ("Hit Rate", ["% mensagens com memória"], False),
        ("Latência de Recall", ["ms médio"], False),
        ("Precision@K, Recall@K, MRR", ["métricas científicas"], False),
        ("Ablation Study", ["variantes testadas"], False),
    ]
    
    for req, details, implemented in requirements:
        status = "✅" if implemented else "⏳"
        print(f"   {status} {req}")
        for detail in details:
            print(f"      - {detail}")
    
    print()


def main():
    print()
    check_requirements_for_paper()
    
    # Procura resultado mais recente
    results_dir = Path(__file__).parent / "results"
    json_files = sorted(results_dir.glob("full_comparison_*.json"), reverse=True)
    
    if json_files:
        latest = json_files[0]
        print(f"📄 Validando: {latest.name}")
        
        with open(latest) as f:
            data = json.load(f)
        
        is_valid, errors = validate_result(data)
        
        if is_valid:
            print("   ✅ Resultado válido para o paper!")
        else:
            print("   ⚠️  Problemas encontrados:")
            for error in errors[:10]:
                print(f"      {error}")
    else:
        print("⚠️  Nenhum arquivo de resultado encontrado")
    
    # Valida grafos
    data_dir = Path(__file__).parent.parent / "data"
    saved, empty = validate_graph_data(data_dir)
    
    print()
    print(f"📊 GRAFOS DE MEMÓRIA:")
    print(f"   ✅ Com dados: {saved}")
    print(f"   ⚠️  Vazios: {empty}")
    
    if empty > 0 and saved == 0:
        print("   ❌ ALERTA: Todos os grafos estão vazios!")
        print("   → Verificar bug de persistência")
    
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()

