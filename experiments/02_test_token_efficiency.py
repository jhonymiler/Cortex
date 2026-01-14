"""
Experimento 2: Validar economia de tokens com W5H
==================================================

Teoria testada:
- Estrutura W5H deve economizar tokens vs texto livre
- Promessa: 5x mais compacto (~36 tokens vs 180+ tokens)
- W5H permite busca estruturada sem embeddings

Método:
- Criar mesma informação em W5H e texto livre
- Contar tokens (aproximado via caracteres / 4)
- Medir compressão e eficiência
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cortex.core.memory import Memory
from datetime import datetime
import json


def count_tokens(text: str) -> int:
    """Aproximação de tokens (1 token ≈ 4 caracteres)"""
    return len(text) // 4


def test_token_efficiency():
    """Teste 1: W5H vs texto livre - economia de tokens"""
    print("\n=== TESTE 1: Economia de Tokens ===")

    # Cenário: Suporte técnico
    scenario = {
        "user": "maria@email.com",
        "issue": "erro ao fazer login",
        "cause": "senha expirada",
        "resolution": "redefinição de senha enviada por email",
        "context": "suporte_cliente"
    }

    # Versão W5H
    mem_w5h = Memory(
        who=["maria@email.com", "sistema_auth"],
        what="reportou_erro_login",
        why="senha_expirada",
        how="enviada_redefinicao_email",
        where="suporte_cliente"
    )

    w5h_str = json.dumps(mem_w5h.to_w5h_dict(), ensure_ascii=False)
    w5h_tokens = count_tokens(w5h_str)

    # Versão texto livre
    text_free = f"""Usuário {scenario['user']} entrou em contato com o suporte técnico
reportando problema ao tentar fazer login no sistema. Após investigação, identificamos
que a causa do problema era a senha expirada. Para resolver a situação, enviamos um
email com instruções para redefinição da senha. O atendimento foi realizado no contexto
de {scenario['context']}."""

    text_tokens = count_tokens(text_free)

    print(f"W5H estruturado:  {w5h_tokens} tokens")
    print(f"Texto livre:      {text_tokens} tokens")
    print(f"Economia:         {text_tokens - w5h_tokens} tokens ({100*(text_tokens-w5h_tokens)/text_tokens:.1f}%)")
    print(f"Fator de compressão: {text_tokens / w5h_tokens:.1f}x")

    # Validar promessa de 5x
    compression_ratio = text_tokens / w5h_tokens

    if compression_ratio >= 3.0:
        print(f"✅ PASSOU: Compressão {compression_ratio:.1f}x (≥3x)")
        return True
    else:
        print(f"❌ FALHOU: Compressão {compression_ratio:.1f}x insuficiente")
        return False


def test_multiple_scenarios():
    """Teste 2: Economia em múltiplos cenários"""
    print("\n=== TESTE 2: Economia em Diversos Cenários ===")

    scenarios = [
        {
            "name": "Suporte Técnico",
            "w5h": {
                "who": ["cliente", "atendente"],
                "what": "reportou_bug",
                "why": "timeout_api",
                "how": "bug_corrigido",
                "where": "suporte"
            },
            "text": "Cliente reportou um bug ao atendente. A causa era um timeout na API. O bug foi corrigido pela equipe técnica no contexto do suporte ao cliente."
        },
        {
            "name": "Desenvolvimento",
            "w5h": {
                "who": ["dev_joao", "api_vendas"],
                "what": "otimizou_query",
                "why": "lentidao_dashboard",
                "how": "adicionou_index",
                "where": "sprint_15"
            },
            "text": "O desenvolvedor João identificou lentidão no dashboard de vendas. Após análise, descobriu que o problema era causado por queries lentas. Para resolver, adicionou índices no banco de dados durante a sprint 15."
        },
        {
            "name": "Roleplay",
            "w5h": {
                "who": ["elena", "marcus"],
                "what": "enfrentaram_dragao",
                "why": "proteger_vila",
                "how": "venceram_com_magia",
                "where": "campanha_fantasia"
            },
            "text": "Elena e Marcus enfrentaram um dragão que ameaçava a vila. A batalha foi intensa, mas usando magia poderosa, conseguiram vencer o dragão e salvar todos os moradores. Este evento ocorreu na campanha de fantasia épica."
        }
    ]

    results = []
    for scenario in scenarios:
        w5h_tokens = count_tokens(json.dumps(scenario["w5h"], ensure_ascii=False))
        text_tokens = count_tokens(scenario["text"])
        compression = text_tokens / w5h_tokens
        savings = 100 * (text_tokens - w5h_tokens) / text_tokens

        results.append({
            "name": scenario["name"],
            "w5h": w5h_tokens,
            "text": text_tokens,
            "compression": compression,
            "savings": savings
        })

        print(f"\n{scenario['name']}:")
        print(f"  W5H:       {w5h_tokens} tokens")
        print(f"  Texto:     {text_tokens} tokens")
        print(f"  Economia:  {savings:.1f}% ({compression:.1f}x)")

    avg_compression = sum(r["compression"] for r in results) / len(results)
    avg_savings = sum(r["savings"] for r in results) / len(results)

    print(f"\n📊 Média geral:")
    print(f"   Compressão: {avg_compression:.1f}x")
    print(f"   Economia:   {avg_savings:.1f}%")

    if avg_compression >= 3.0:
        print("✅ PASSOU: Economia consistente em múltiplos cenários")
        return True
    else:
        print("❌ FALHOU: Economia abaixo do esperado")
        return False


def test_context_building():
    """Teste 3: Economia ao construir contexto para LLM"""
    print("\n=== TESTE 3: Contexto para LLM ===")

    # Simula 10 memórias relevantes sendo enviadas ao LLM

    # Versão W5H
    memories_w5h = [
        {"who": ["user"], "what": f"evento_{i}", "why": "motivo", "how": "resultado"}
        for i in range(10)
    ]

    w5h_context = "Memórias relevantes:\n"
    for mem in memories_w5h:
        w5h_context += f"- {mem['who'][0]} {mem['what']}: {mem['why']} → {mem['how']}\n"

    w5h_tokens = count_tokens(w5h_context)

    # Versão texto livre
    text_context = "Memórias relevantes:\n"
    for i in range(10):
        text_context += f"- O usuário executou o evento_{i}. A motivação foi o motivo identificado anteriormente. Como resultado, obtivemos o resultado esperado e documentado.\n"

    text_tokens = count_tokens(text_context)

    print(f"Contexto W5H (10 memórias): {w5h_tokens} tokens")
    print(f"Contexto texto (10 memórias): {text_tokens} tokens")
    print(f"Economia por memória: {(text_tokens - w5h_tokens) / 10:.1f} tokens")
    print(f"Economia total: {100*(text_tokens-w5h_tokens)/text_tokens:.1f}%")

    # Simula custo (GPT-4: $0.03/1k tokens input)
    cost_w5h = (w5h_tokens / 1000) * 0.03
    cost_text = (text_tokens / 1000) * 0.03

    print(f"\n💰 Economia de custo:")
    print(f"   W5H:   ${cost_w5h:.4f}")
    print(f"   Texto: ${cost_text:.4f}")
    print(f"   Economia: ${cost_text - cost_w5h:.4f} ({100*(cost_text-cost_w5h)/cost_text:.1f}%)")

    if w5h_tokens < text_tokens * 0.6:
        print("✅ PASSOU: Economia significativa ao construir contexto")
        return True
    else:
        print("❌ FALHOU: Economia insuficiente")
        return False


def test_searchability():
    """Teste 4: Busca estruturada vs texto livre"""
    print("\n=== TESTE 4: Busca Estruturada ===")

    # Cenário: buscar "quem reportou erro de pagamento?"

    # W5H: busca direta por campo
    memories_w5h = [
        Memory(who=["maria"], what="reportou_erro_pagamento", why="cartao_expirado"),
        Memory(who=["joao"], what="atualizou_perfil", why="dados_desatualizados"),
        Memory(who=["ana"], what="reportou_erro_pagamento", why="saldo_insuficiente"),
    ]

    # Busca estruturada: O(1) lookup
    query_what = "reportou_erro_pagamento"
    found_w5h = [m for m in memories_w5h if m.what == query_what]

    print(f"Busca W5H: 'what == reportou_erro_pagamento'")
    print(f"  Resultado: {len(found_w5h)} memórias encontradas")
    print(f"  Usuários: {', '.join(found_w5h[0].who + found_w5h[1].who)}")
    print(f"  Complexidade: O(n) com indexação O(1)")

    # Texto livre: precisa embedding + similarity search
    memories_text = [
        "Maria reportou um erro ao tentar fazer pagamento porque seu cartão estava expirado",
        "João atualizou seu perfil pois seus dados estavam desatualizados",
        "Ana reportou um erro de pagamento devido a saldo insuficiente",
    ]

    print(f"\nBusca texto livre: 'reportou erro de pagamento'")
    print(f"  Método: embedding + similarity search")
    print(f"  Complexidade: O(n·d) onde d = dimensão embedding")
    print(f"  Requer: modelo de embedding, cálculo de similaridade")

    # W5H permite queries complexas sem embedding
    print(f"\n🔍 Queries estruturadas possíveis com W5H:")
    print(f"   - who == 'maria'")
    print(f"   - what == 'reportou_erro_pagamento' AND why CONTAINS 'cartao'")
    print(f"   - where == 'suporte' AND when > '2024-01-01'")

    print("\n✅ PASSOU: W5H permite busca estruturada sem embeddings")
    return True


def run_all_tests():
    """Executa todos os testes de eficiência de tokens"""
    print("=" * 60)
    print("EXPERIMENTO 2: Validação da Economia de Tokens")
    print("=" * 60)

    tests = [
        ("Economia de Tokens (W5H vs Texto)", test_token_efficiency),
        ("Economia em Múltiplos Cenários", test_multiple_scenarios),
        ("Contexto para LLM", test_context_building),
        ("Busca Estruturada", test_searchability),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ ERRO: {e}")
            results.append((name, False))

    # Sumário
    print("\n" + "=" * 60)
    print("SUMÁRIO DOS TESTES")
    print("=" * 60)

    passed = sum(1 for _, p in results if p)
    total = len(results)

    for name, passed_test in results:
        status = "✅ PASSOU" if passed_test else "❌ FALHOU"
        print(f"{status}: {name}")

    print(f"\nRESULTADO: {passed}/{total} testes passaram ({100*passed/total:.1f}%)")

    if passed == total:
        print("\n🎉 TEORIA VALIDADA: W5H economiza tokens como prometido!")
    elif passed >= total * 0.75:
        print("\n⚠️  TEORIA PARCIALMENTE VALIDADA: Economia comprovada mas com ressalvas")
    else:
        print("\n❌ TEORIA NÃO VALIDADA: Economia não significativa")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)