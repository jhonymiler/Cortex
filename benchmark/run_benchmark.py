"""
Run Benchmark - Script principal para executar o benchmark

Uso:
    python run_benchmark.py                    # Benchmark rápido (teste)
    python run_benchmark.py --full             # Benchmark completo
    python run_benchmark.py --domain education # Apenas um domínio
    python run_benchmark.py --help             # Ajuda
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Adiciona SDK ao path
sdk_path = Path(__file__).parent.parent / "sdk" / "python"
sys.path.insert(0, str(sdk_path))

from dotenv import load_dotenv

# Carrega .env se existir
load_dotenv()

# Imports condicionais para funcionar como script e como módulo
try:
    from .conversation_generator import ConversationGenerator
    from .benchmark import BenchmarkRunner, MetricsEvaluator
except ImportError:
    from conversation_generator import ConversationGenerator
    from benchmark import BenchmarkRunner, MetricsEvaluator


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Cortex vs Baseline com LLM Real (Ollama)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
    python run_benchmark.py                       # Benchmark rápido (1 conv/domínio)
    python run_benchmark.py --full                # Benchmark completo (3 conv/domínio)
    python run_benchmark.py --domain education    # Apenas domínio educação
    python run_benchmark.py --conversations 5     # 5 conversas por domínio
    python run_benchmark.py --sessions 7          # 7 sessões por conversa

Métricas coletadas:
    - Tokens usados (prompt + completion)
    - Tempo de resposta
    - Taxa de recuperação de memória
    - Qualidade contextual (memórias recuperadas)

Requisitos:
    1. Ollama rodando: ollama serve
    2. Cortex API rodando: cortex-api
        """,
    )
    
    # Configuração do benchmark
    parser.add_argument(
        "--full",
        action="store_true",
        help="Executa benchmark completo (3 conversas/domínio, 5 sessões/conversa)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Executa benchmark rápido (1 conversa/domínio, 2 sessões/conversa)",
    )
    parser.add_argument(
        "--conversations",
        type=int,
        default=None,
        help="Número de conversas por domínio",
    )
    parser.add_argument(
        "--sessions",
        type=int,
        default=None,
        help="Número de sessões por conversa",
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        choices=[
            "customer_support",
            "code_assistant",
            "roleplay",
            "education",
            "personal_assistant",
            "sales_crm",
            "healthcare",
            "financial",
        ],
        help="Executa apenas para um domínio específico",
    )
    
    # Configuração de serviços
    parser.add_argument(
        "--model",
        type=str,
        default=os.getenv("OLLAMA_MODEL", "stheno:latest"),
        help="Modelo Ollama a usar",
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        default=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        help="URL do Ollama",
    )
    parser.add_argument(
        "--cortex-url",
        type=str,
        default=os.getenv("CORTEX_API_URL", "http://localhost:8000"),
        help="URL da API Cortex",
    )
    
    # Output
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Arquivo de saída (JSON)",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Não limpar memória do Cortex antes do benchmark",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Modo silencioso (menos output)",
    )
    
    args = parser.parse_args()
    
    # Determina configuração
    if args.full:
        conv_per_domain = 3
        sessions = 5
    elif args.quick:
        conv_per_domain = 1
        sessions = 2
    else:
        conv_per_domain = args.conversations or 1
        sessions = args.sessions or 3
    
    # Override manual
    if args.conversations:
        conv_per_domain = args.conversations
    if args.sessions:
        sessions = args.sessions
    
    print("=" * 70)
    print("🚀 CORTEX BENCHMARK - LLM Real (Ollama)")
    print("=" * 70)
    print(f"\n📋 Configuração:")
    print(f"   Modelo: {args.model}")
    print(f"   Ollama: {args.ollama_url}")
    print(f"   Cortex: {args.cortex_url}")
    print(f"   Conversas/domínio: {conv_per_domain}")
    print(f"   Sessões/conversa: {sessions}")
    if args.domain:
        print(f"   Domínio: {args.domain}")
    else:
        print(f"   Domínios: todos (8)")
    
    # Gera conversas
    print("\n🔄 Gerando conversas...")
    generator = ConversationGenerator()
    
    if args.domain:
        conversations = generator.generate_domain(
            domain=args.domain,
            count=conv_per_domain,
            sessions=sessions,
        )
    else:
        conversations = generator.generate_all(
            conversations_per_domain=conv_per_domain,
            sessions_per_conversation=sessions,
        )
    
    total_sessions = sum(len(c.sessions) for c in conversations)
    total_messages = sum(
        sum(1 for s in c.sessions for m in s.messages if m.role == "user")
        for c in conversations
    )
    
    print(f"   ✅ {len(conversations)} conversas")
    print(f"   ✅ {total_sessions} sessões")
    print(f"   ✅ ~{total_messages} mensagens de usuário")
    
    # Estima tempo
    est_time_per_msg = 5  # segundos (aproximado)
    est_total_time = total_messages * est_time_per_msg * 2  # x2 para ambos agentes
    print(f"\n⏱️ Tempo estimado: {est_total_time // 60} min {est_total_time % 60} seg")
    
    # Confirma
    try:
        input("\n⏸️ Pressione ENTER para iniciar (Ctrl+C para cancelar)...")
    except KeyboardInterrupt:
        print("\n\n❌ Cancelado pelo usuário.")
        return
    
    # Cria runner
    runner = BenchmarkRunner(
        model=args.model,
        ollama_url=args.ollama_url,
        cortex_url=args.cortex_url,
        verbose=not args.quiet,
    )
    
    # Verifica serviços
    if not runner.verify_services():
        print("\n❌ Serviços não disponíveis!")
        print("\nCertifique-se de que:")
        print("   1. Ollama está rodando:")
        print("      ollama serve")
        print("")
        print("   2. Modelo está disponível:")
        print(f"      ollama pull {args.model}")
        print("")
        print("   3. Cortex API está rodando:")
        print("      source venv/bin/activate && cortex-api")
        return
    
    # Executa benchmark
    try:
        result = runner.run_benchmark(
            conversations=conversations,
            clear_memory_before=not args.no_clear,
        )
    except KeyboardInterrupt:
        print("\n\n⚠️ Benchmark interrompido pelo usuário.")
        return
    except Exception as e:
        print(f"\n❌ Erro durante benchmark: {e}")
        raise
    
    # Salva resultado
    if args.output:
        output_path = Path(args.output)
    else:
        output_dir = Path(__file__).parent / "results"
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"benchmark_{timestamp}.json"
    
    runner.save_result(result, output_path)
    
    # Avalia e imprime resumo
    evaluator = MetricsEvaluator(result)
    evaluator.print_summary()
    
    # Salva resumo
    summary_path = output_path.with_suffix(".summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(evaluator.generate_summary(), f, ensure_ascii=False, indent=2)
    
    print(f"\n📁 Arquivos salvos:")
    print(f"   Dados completos: {output_path}")
    print(f"   Resumo: {summary_path}")
    
    print("\n✅ Benchmark concluído com sucesso!")


if __name__ == "__main__":
    main()
