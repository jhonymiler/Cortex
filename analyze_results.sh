#!/bin/bash
# Script para análise completa dos resultados do Cortex Paper Benchmark
# Usage: ./analyze_results.sh [resultado.json]

set -e

RESULTS_DIR="benchmark_results"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧠 CORTEX BENCHMARK - ANÁLISE DE RESULTADOS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Ativa ambiente virtual
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Ativando ambiente virtual..."
    source venv/bin/activate 2>/dev/null || true
fi

# Encontra o resultado mais recente
if [ -n "$1" ]; then
    RESULT_FILE="$1"
else
    RESULT_FILE=$(ls -t $RESULTS_DIR/paper_benchmark_*.json 2>/dev/null | head -1)
fi

if [ -z "$RESULT_FILE" ] || [ ! -f "$RESULT_FILE" ]; then
    echo "❌ Nenhum resultado de benchmark encontrado"
    echo ""
    echo "Execute primeiro:"
    echo "  ./start_benchmark.sh --paper"
    exit 1
fi

echo "📊 Analisando: $(basename $RESULT_FILE)"
echo ""

# Extrai e formata as métricas
python3 << EOF
import json
from datetime import datetime

with open("$RESULT_FILE") as f:
    data = json.load(f)

print("━" * 60)
print("📈 MÉTRICAS DE QUALIDADE")
print("━" * 60)
print()

categories = [
    ("semantic_accuracy", "Acurácia Semântica"),
    ("contextual_recall", "Recall Contextual"),
    ("collective_memory", "Memória Coletiva"),
    ("relevance", "Relevância"),
    ("efficiency", "Eficiência"),
]

for key, name in categories:
    cat = data.get(key, {})
    accuracy = cat.get("accuracy", 0) * 100
    passed = cat.get("passed_tests", 0)
    total = cat.get("total_tests", 0)
    latency = cat.get("avg_latency_ms", 0)
    
    status = "✅" if accuracy >= 80 else "⚠️" if accuracy >= 60 else "❌"
    print(f"{status} {name}: {accuracy:.0f}% ({passed}/{total} testes)")
    if latency > 0:
        print(f"   └─ Latência média: {latency:.0f}ms")
    print()

print("━" * 60)
print("📊 RESULTADO GERAL")
print("━" * 60)
print()

overall = data.get("overall_accuracy", 0) * 100
total_passed = data.get("total_passed", 0)
total_tests = data.get("total_tests", 0)
duration = data.get("duration_seconds", 0)

print(f"🎯 Acurácia Geral: {overall:.1f}%")
print(f"✅ Testes Passados: {total_passed}/{total_tests}")
print(f"⏱️  Duração: {duration:.1f}s")
print()

print("━" * 60)
print("📋 TESTES DETALHADOS")
print("━" * 60)
print()

for key, name in categories:
    cat = data.get(key, {})
    tests = cat.get("tests", [])
    
    if not tests:
        continue
    
    print(f"📌 {name}:")
    for test in tests:
        status = "✅" if test.get("passed") else "❌"
        test_name = test.get("name", "N/A")
        expected = test.get("expected", "")
        actual = test.get("actual", "")
        latency = test.get("latency_ms", 0)
        
        print(f"   {status} {test_name}")
        if not test.get("passed"):
            print(f"      Esperado: {expected}")
            print(f"      Obtido: {actual}")
    print()

print("━" * 60)
print("📊 MÉTRICAS PARA PAPER")
print("━" * 60)
print()

# Calcula médias
all_latencies = []
for key, _ in categories:
    cat = data.get(key, {})
    for test in cat.get("tests", []):
        if test.get("latency_ms", 0) > 0:
            all_latencies.append(test["latency_ms"])

avg_latency = sum(all_latencies) / len(all_latencies) if all_latencies else 0
p95_latency = sorted(all_latencies)[int(len(all_latencies) * 0.95)] if len(all_latencies) >= 20 else max(all_latencies) if all_latencies else 0

print(f"| Métrica | Valor |")
print(f"|---------|-------|")
print(f"| Acurácia Semântica | {data.get('semantic_accuracy', {}).get('accuracy', 0)*100:.0f}% |")
print(f"| Recall Contextual | {data.get('contextual_recall', {}).get('accuracy', 0)*100:.0f}% |")
print(f"| Memória Coletiva | {data.get('collective_memory', {}).get('accuracy', 0)*100:.0f}% |")
print(f"| Relevância | {data.get('relevance', {}).get('accuracy', 0)*100:.0f}% |")
print(f"| Latência Média | {avg_latency:.0f}ms |")
print(f"| Latência P95 | {p95_latency:.0f}ms |")
print(f"| **GERAL** | **{overall:.1f}%** |")
print()

print("━" * 60)
print("✅ Análise concluída!")
print("━" * 60)
EOF

echo ""
echo "📁 Arquivo analisado: $RESULT_FILE"
echo ""
