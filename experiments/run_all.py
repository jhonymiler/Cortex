#!/usr/bin/env python3
"""
Script principal para executar todos os experimentos de validação do Cortex
===========================================================================

Este script executa todos os experimentos de forma isolada e gera um relatório
consolidado sobre a viabilidade do projeto.

Experimentos:
1. Decaimento Cognitivo (Ebbinghaus)
2. Economia de Tokens (W5H vs texto livre)
3. Memory Firewall (Identity Kernel)
4. Consolidação de Memórias

Uso:
    python experiments/run_all.py
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

# Cores ANSI para output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Imprime cabeçalho formatado"""
    width = 70
    print(f"\n{Colors.HEADER}{Colors.BOLD}")
    print("=" * width)
    print(text.center(width))
    print("=" * width)
    print(f"{Colors.ENDC}")


def print_section(text: str):
    """Imprime seção formatada"""
    print(f"\n{Colors.OKCYAN}{Colors.BOLD}{text}{Colors.ENDC}")
    print("-" * 70)


def run_experiment(script_name: str, description: str) -> Tuple[bool, str]:
    """
    Executa um experimento e retorna resultado.

    Returns:
        (sucesso, output)
    """
    print(f"\n{Colors.OKBLUE}▶ Executando: {description}{Colors.ENDC}")

    script_path = Path(__file__).parent / script_name

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=60
        )

        success = result.returncode == 0

        if success:
            print(f"{Colors.OKGREEN}✅ PASSOU{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}❌ FALHOU{Colors.ENDC}")

        return success, result.stdout + result.stderr

    except subprocess.TimeoutExpired:
        print(f"{Colors.FAIL}❌ TIMEOUT (>60s){Colors.ENDC}")
        return False, "Timeout"
    except Exception as e:
        print(f"{Colors.FAIL}❌ ERRO: {e}{Colors.ENDC}")
        return False, str(e)


def generate_report(results: List[Tuple[str, bool, str]]) -> str:
    """Gera relatório consolidado"""
    report = []

    report.append("=" * 70)
    report.append("RELATÓRIO DE VALIDAÇÃO DO CORTEX")
    report.append("=" * 70)
    report.append(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")

    # Sumário executivo
    total = len(results)
    passed = sum(1 for _, success, _ in results if success)
    pass_rate = 100 * passed / total if total > 0 else 0

    report.append("## SUMÁRIO EXECUTIVO")
    report.append("")
    report.append(f"Total de experimentos: {total}")
    report.append(f"Experimentos passaram: {passed}")
    report.append(f"Experimentos falharam: {total - passed}")
    report.append(f"Taxa de sucesso: {pass_rate:.1f}%")
    report.append("")

    # Veredicto
    report.append("## VEREDICTO")
    report.append("")

    if pass_rate == 100:
        report.append("🎉 TEORIA TOTALMENTE VALIDADA")
        report.append("")
        report.append("Todos os experimentos passaram! O Cortex funciona como prometido.")
        report.append("O projeto demonstra viabilidade técnica e científica sólida.")
        report.append("")
        report.append("Próximos passos recomendados:")
        report.append("- Implementar testes com usuários reais")
        report.append("- Comparar com soluções existentes (Mem0, RAG)")
        report.append("- Medir ROI em casos de uso reais")
        report.append("- Publicar paper científico")

    elif pass_rate >= 75:
        report.append("✅ TEORIA PARCIALMENTE VALIDADA")
        report.append("")
        report.append("A maioria dos experimentos passou. O conceito central é sólido,")
        report.append("mas há aspectos que precisam de refinamento.")
        report.append("")
        report.append("Próximos passos recomendados:")
        report.append("- Revisar experimentos que falharam")
        report.append("- Ajustar implementação onde necessário")
        report.append("- Executar testes adicionais")

    elif pass_rate >= 50:
        report.append("⚠️ TEORIA PARCIALMENTE VALIDADA COM RESSALVAS")
        report.append("")
        report.append("Aproximadamente metade dos experimentos passou. O projeto tem")
        report.append("potencial, mas precisa de melhorias significativas.")
        report.append("")
        report.append("Próximos passos recomendados:")
        report.append("- Análise profunda dos pontos de falha")
        report.append("- Refatoração de componentes críticos")
        report.append("- Revisão da proposta de valor")

    else:
        report.append("❌ TEORIA NÃO VALIDADA")
        report.append("")
        report.append("A maioria dos experimentos falhou. É necessário reavaliar")
        report.append("os fundamentos do projeto antes de prosseguir.")
        report.append("")
        report.append("Próximos passos recomendados:")
        report.append("- Revisão completa da arquitetura")
        report.append("- Validação de premissas básicas")
        report.append("- Considerar pivots ou mudanças de direção")

    report.append("")
    report.append("")

    # Detalhes por experimento
    report.append("## DETALHES DOS EXPERIMENTOS")
    report.append("")

    for i, (name, success, output) in enumerate(results, 1):
        status = "✅ PASSOU" if success else "❌ FALHOU"
        report.append(f"{i}. {name}: {status}")
        report.append("")

    report.append("")

    # Análise de potencial
    report.append("## POTENCIAL DO PROJETO")
    report.append("")
    report.append("Com base nos resultados dos experimentos:")
    report.append("")

    if pass_rate >= 75:
        report.append("POTENCIAL DE MERCADO: ALTO")
        report.append("")
        report.append("O Cortex demonstra capacidade de:")
        report.append("- Reduzir custos de tokens significativamente")
        report.append("- Melhorar experiência do usuário com memória persistente")
        report.append("- Proteger contra ataques de prompt injection")
        report.append("- Escalar eficientemente com consolidação")
        report.append("")
        report.append("Possíveis aplicações:")
        report.append("- Assistentes virtuais empresariais")
        report.append("- Sistemas de suporte ao cliente")
        report.append("- Agentes de desenvolvimento de software")
        report.append("- Aplicações de roleplay e entretenimento")

    elif pass_rate >= 50:
        report.append("POTENCIAL DE MERCADO: MÉDIO")
        report.append("")
        report.append("O Cortex tem fundamentos sólidos mas precisa de:")
        report.append("- Validação em casos de uso reais")
        report.append("- Comparação direta com concorrentes")
        report.append("- Melhorias em áreas específicas")

    else:
        report.append("POTENCIAL DE MERCADO: BAIXO (NO ESTADO ATUAL)")
        report.append("")
        report.append("Recomenda-se focar em:")
        report.append("- Validação de mercado antes de desenvolvimento adicional")
        report.append("- Prototipagem rápida de casos de uso específicos")
        report.append("- Feedback de usuários potenciais")

    report.append("")
    report.append("=" * 70)
    report.append("FIM DO RELATÓRIO")
    report.append("=" * 70)

    return "\n".join(report)


def main():
    """Executa todos os experimentos e gera relatório"""

    print_header("VALIDAÇÃO CIENTÍFICA DO CORTEX")

    print(f"\n{Colors.BOLD}Sobre estes experimentos:{Colors.ENDC}")
    print("Este conjunto de testes valida as teorias fundamentais do Cortex")
    print("sem modificar o código do projeto. Cada experimento testa uma")
    print("promessa específica feita na documentação.")
    print("")

    # Define experimentos
    experiments = [
        ("01_test_decay.py", "Experimento 1: Decaimento Cognitivo"),
        ("02_test_token_efficiency.py", "Experimento 2: Economia de Tokens"),
        ("03_test_memory_firewall.py", "Experimento 3: Memory Firewall"),
        ("04_test_consolidation.py", "Experimento 4: Consolidação de Memórias"),
    ]

    # Executa experimentos
    results = []

    print_section("EXECUTANDO EXPERIMENTOS")

    for script, description in experiments:
        success, output = run_experiment(script, description)
        results.append((description, success, output))

    # Gera relatório
    print_section("GERANDO RELATÓRIO")

    report = generate_report(results)

    # Salva relatório
    report_path = Path(__file__).parent / "VALIDATION_REPORT.txt"
    report_path.write_text(report, encoding="utf-8")

    print(f"\n{Colors.OKGREEN}✅ Relatório salvo em: {report_path}{Colors.ENDC}")

    # Exibe relatório
    print_header("RELATÓRIO FINAL")
    print(report)

    # Retorna código de saída
    total = len(results)
    passed = sum(1 for _, success, _ in results if success)

    if passed == total:
        return 0
    elif passed >= total * 0.75:
        return 1  # Parcialmente validado
    else:
        return 2  # Não validado


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}⚠️  Interrompido pelo usuário{Colors.ENDC}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.FAIL}❌ ERRO FATAL: {e}{Colors.ENDC}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
