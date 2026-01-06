#!/usr/bin/env python3
"""
Script principal para executar benchmark LEVE (sem comparações LLM)

IMPORTANTE: Este script NÃO usa LLM para comparações durante a execução.
Ele apenas coleta dados brutos. Análise pode ser feita depois com outro script.

Uso:
    python run_lightweight_benchmark.py                  # Teste rápido
    python run_lightweight_benchmark.py --full           # Completo
    python run_lightweight_benchmark.py --domain education  # Um domínio
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from benchmark.lightweight_runner import LightweightBenchmarkRunner
from benchmark.conversation_generator import ConversationGenerator


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Cortex LEVE - Sem comparações LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
VANTAGENS deste modo:
  - Não gasta tokens em comparações
  - Não estoura rate limits
  - Coleta TODOS os dados brutos
  - Análise pode ser feita depois (1 chamada de LLM)

Exemplos:
    python run_lightweight_benchmark.py
    python run_lightweight_benchmark.py --full
    python run_lightweight_benchmark.py --domain education --conversations 3
        """,
    )
    
    parser.add_argument(
        "--full",
        action="store_true",
        help="Benchmark completo (3 conv/domínio, 5 sessões)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Benchmark rápido (1 conv/domínio, 2 sessões)",
    )
    parser.add_argument(
        "--conversations",
        type=int,
        default=None,
        help="Conversas por domínio",
    )
    parser.add_argument(
        "--sessions",
        type=int,
        default=None,
        help="Sessões por conversa",
    )
    parser.add_argument(
        "--domain",
        type=str,
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
        help="Apenas um domínio",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="ministral-3:3b",
        help="Modelo Ollama",
    )
    parser.add_argument(
        "--ollama-url",
        type=str,
        default="http://localhost:11434",
        help="URL do Ollama",
    )
    parser.add_argument(
        "--cortex-url",
        type=str,
        default="http://localhost:8000",
        help="URL da API Cortex",
    )
    parser.add_argument(
        "--namespace",
        type=str,
        default="benchmark",
        help="Namespace para isolamento",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Arquivo de saída (padrão: results/lightweight_TIMESTAMP.json)",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Não limpar memória antes",
    )
    parser.add_argument(
        "--resume",
        type=int,
        default=0,
        help="Continuar da conversa N (após falha)",
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        help="Arquivo de checkpoint para resume",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Modo silencioso",
    )
    
    args = parser.parse_args()
    
    # Determina config
    if args.full:
        conv_per_domain = 3
        sessions = 5
    elif args.quick:
        conv_per_domain = 1
        sessions = 2
    else:
        conv_per_domain = args.conversations or 1
        sessions = args.sessions or 3
    
    print("\n" + "=" * 80)
    print("🚀 BENCHMARK LEVE - SEM COMPARAÇÕES LLM")
    print("=" * 80)
    print(f"   Modelo: {args.model}")
    print(f"   Conversas/domínio: {conv_per_domain}")
    print(f"   Sessões/conversa: {sessions}")
    if args.domain:
        print(f"   Domínio: {args.domain}")
    print("=" * 80)
    
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
        sum(1 for m in s.messages if m.role == "user")
        for c in conversations
        for s in c.sessions
    )
    
    print(f"   ✅ {len(conversations)} conversas")
    print(f"   ✅ {total_sessions} sessões")
    print(f"   ✅ ~{total_messages} mensagens")
    
    # Estima tempo (sem overhead de comparações!)
    est_time_per_msg = 5  # segundos
    est_total_time = total_messages * est_time_per_msg * 2  # baseline + cortex
    print(f"\n⏱️  Tempo estimado: {est_total_time // 60} min")
    
    try:
        input("\n⏸️  Pressione ENTER para iniciar (Ctrl+C para cancelar)...")
    except KeyboardInterrupt:
        print("\n\n❌ Cancelado.")
        return
    
    # Cria runner
    runner = LightweightBenchmarkRunner(
        model=args.model,
        ollama_url=args.ollama_url,
        cortex_url=args.cortex_url,
        namespace=args.namespace,
        verbose=not args.quiet,
    )
    
    # Verifica serviços
    if not runner.verify_services():
        print("\n❌ Serviços não disponíveis!")
        print("\nCertifique-se:")
        print("   1. Ollama: ollama serve")
        print(f"   2. Modelo: ollama pull {args.model}")
        print("   3. Cortex: cortex-api")
        return
    
    # Executa
    try:
        result = runner.run_benchmark(
            conversations=conversations,
            clear_before=not args.no_clear,
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompido.")
        return
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        raise
    
    # Salva
    if args.output:
        output_path = Path(args.output)
    else:
        output_dir = Path(__file__).parent / "benchmark" / "results"
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = output_dir / f"lightweight_{timestamp}.json"
    
    # Checkpoint para resume
    checkpoint_path = Path(args.checkpoint) if args.checkpoint else output_path.with_suffix(".checkpoint.json")
    
    # Executa
    try:
        result = runner.run_benchmark(
            conversations=conversations,
            clear_before=not args.no_clear and args.resume == 0,
            checkpoint_file=checkpoint_path,
            resume_from=args.resume,
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompido.")
        print(f"   💾 Checkpoint em: {checkpoint_path}")
        print(f"   ⏩ Para continuar: python run_lightweight_benchmark.py --resume N --checkpoint {checkpoint_path}")
        return
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        print(f"   💾 Checkpoint em: {checkpoint_path}")
        print(f"   ⏩ Para continuar: verifique a mensagem de erro acima")
        raise
    
    # Salva resultado final
    runner.save_result(result, output_path)
    
    # Remove checkpoint se completou com sucesso
    if checkpoint_path.exists():
        checkpoint_path.unlink()
        print(f"   🗑️  Checkpoint removido")
    
    print("\n" + "=" * 80)
    print("📊 RESUMO")
    print("=" * 80)
    
    baseline_tokens = result["baseline_stats"]["total_tokens"]
    cortex_tokens = result["cortex_stats"]["total_tokens"]
    
    print(f"   Baseline tokens: {baseline_tokens}")
    print(f"   Cortex tokens: {cortex_tokens}")
    print(f"   Diferença: {baseline_tokens - cortex_tokens} ({(baseline_tokens - cortex_tokens) / baseline_tokens * 100:.1f}%)")
    
    print(f"\n   Entidades recuperadas: {result['cortex_stats']['total_memory_entities']}")
    print(f"   Episódios recuperados: {result['cortex_stats']['total_memory_episodes']}")
    
    print(f"\n📁 Dados salvos em: {output_path}")
    print("\n💡 Para análise completa, execute:")
    print(f"   python analyze_lightweight_results.py {output_path}")
    
    print("\n✅ Benchmark concluído!")


if __name__ == "__main__":
    main()
