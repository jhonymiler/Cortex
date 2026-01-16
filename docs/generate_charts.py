#!/usr/bin/env python3
"""
Gerador de Gráficos para Paper do Cortex

Lê os dados de PERFORMANCE_DATA.json e gera todos os gráficos necessários
para os papers acadêmico e final.

Usage:
    python generate_charts.py

Gera:
    - comparison_bar_chart.png: Comparação entre sistemas
    - latency_comparison.png: Latência de memória
    - semantic_validation.png: Evolução da validação semântica
    - embedding_performance.png: Performance de embeddings
    - end_to_end_latency.png: Breakdown de latência
    - radar_chart.png: Dimensões de valor do Cortex
"""

import json
import matplotlib
matplotlib.use('Agg')  # Backend não-interativo para evitar problemas de display
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Configuração de estilo
plt.style.use('seaborn-v0_8-darkgrid')
COLORS = {
    'cortex': '#2E86AB',
    'rag': '#A23B72',
    'mem0': '#F18F01',
    'baseline': '#C73E1D'
}

def load_data():
    """Carrega dados de performance do JSON."""
    data_file = Path(__file__).parent / 'PERFORMANCE_DATA.json'
    with open(data_file, 'r') as f:
        return json.load(f)

def save_chart(filename):
    """Salva gráfico no diretório de resultados."""
    output_dir = Path(__file__).parent.parent / 'benchmark_results' / 'charts'
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / filename
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✅ Gráfico salvo: {output_path}")
    plt.close()

def generate_comparison_bar_chart(data):
    """Gera gráfico de barras comparando sistemas."""
    chart_data = data['chart_data']['comparison_bar_chart']

    x = np.arange(len(chart_data['x_labels']))
    width = 0.2

    fig, ax = plt.subplots(figsize=(12, 6))

    ax.bar(x - 1.5*width, chart_data['baseline'], width, label='Baseline', color=COLORS['baseline'])
    ax.bar(x - 0.5*width, chart_data['rag'], width, label='RAG', color=COLORS['rag'])
    ax.bar(x + 0.5*width, chart_data['mem0'], width, label='Mem0', color=COLORS['mem0'])
    ax.bar(x + 1.5*width, chart_data['cortex'], width, label='Cortex', color=COLORS['cortex'])

    ax.set_ylabel('Accuracy (%)', fontsize=12)
    ax.set_title('Cortex vs Alternatives: Benchmark Comparison', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(chart_data['x_labels'])
    ax.legend()
    ax.set_ylim(0, 110)
    ax.grid(axis='y', alpha=0.3)

    save_chart('comparison_bar_chart.png')

def generate_latency_comparison(data):
    """Gera gráfico de comparação de latência."""
    chart_data = data['chart_data']['latency_comparison']

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = [COLORS['cortex'], COLORS['rag'], COLORS['mem0']]
    bars = ax.bar(chart_data['systems'], chart_data['latency_ms'], color=colors)

    # Adiciona valores nas barras
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}ms',
                ha='center', va='bottom', fontweight='bold')

    ax.set_ylabel('Latency (ms)', fontsize=12)
    ax.set_title('Memory Retrieval Latency Comparison', fontsize=14, fontweight='bold')
    ax.set_ylim(0, max(chart_data['latency_ms']) * 1.2)
    ax.grid(axis='y', alpha=0.3)

    # Adiciona linha indicando "4x faster"
    ax.axhline(y=chart_data['latency_ms'][0] * 4, color='green', linestyle='--', alpha=0.5)
    ax.text(2, chart_data['latency_ms'][0] * 4 + 10, '4x faster threshold',
            color='green', fontsize=10)

    save_chart('latency_comparison.png')

def generate_semantic_validation_chart(data):
    """Gera gráfico de evolução da validação semântica."""
    chart_data = data['chart_data']['semantic_validation_improvement']

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = ['#C73E1D', '#F18F01', '#F4A259', '#2E86AB', '#A8DADC']
    bars = ax.bar(chart_data['thresholds'], chart_data['accuracy_percent'], color=colors)

    # Destaca o threshold ótimo
    bars[3].set_edgecolor('green')
    bars[3].set_linewidth(3)

    # Adiciona valores nas barras
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}%',
                ha='center', va='bottom', fontweight='bold')

    ax.set_ylabel('Personal Assistant Accuracy (%)', fontsize=12)
    ax.set_xlabel('Validation Approach / Threshold', fontsize=12)
    ax.set_title('Semantic Validation Evolution (0% → 100% Improvement)',
                 fontsize=14, fontweight='bold')
    ax.set_ylim(0, 110)
    ax.grid(axis='y', alpha=0.3)

    # Adiciona anotação para threshold ótimo
    ax.annotate('Optimal\nThreshold',
                xy=(3, 100), xytext=(3.5, 95),
                arrowprops=dict(arrowstyle='->', color='green', lw=2),
                fontsize=11, color='green', fontweight='bold')

    save_chart('semantic_validation.png')

def generate_embedding_performance_chart(data):
    """Gera gráfico de performance de embeddings."""
    chart_data = data['chart_data']['embedding_performance']

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = ['#C73E1D', '#2E86AB']
    bars = ax.bar(chart_data['labels'], chart_data['latency_ms'], color=colors)

    # Adiciona valores nas barras
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}ms',
                ha='center', va='bottom', fontweight='bold', fontsize=12)

    ax.set_ylabel('Latency (ms)', fontsize=12)
    ax.set_title('Embedding Generation Performance', fontsize=14, fontweight='bold')
    ax.set_ylim(0, max(chart_data['latency_ms']) * 1.2)
    ax.grid(axis='y', alpha=0.3)

    # Adiciona anotação mostrando melhoria
    improvement_percent = data['embedding_performance']['improvement_after_warmup_percent']
    ax.annotate(f'{improvement_percent}% faster\nafter warm-up',
                xy=(1, chart_data['latency_ms'][1]), xytext=(0.5, 1500),
                arrowprops=dict(arrowstyle='->', color='green', lw=2),
                fontsize=11, color='green', fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    save_chart('embedding_performance.png')

def generate_end_to_end_latency_pie(data):
    """Gera gráfico de pizza mostrando breakdown de latência."""
    chart_data = data['chart_data']['end_to_end_latency_pie']

    fig, ax = plt.subplots(figsize=(10, 8))

    colors = ['#2E86AB', '#F18F01', '#A23B72']
    explode = (0.1, 0, 0)  # Destaca Memory Retrieval

    wedges, texts, autotexts = ax.pie(
        chart_data['percentages'],
        labels=chart_data['labels'],
        autopct='%1.0f%%',
        startangle=90,
        colors=colors,
        explode=explode,
        textprops={'fontsize': 12, 'fontweight': 'bold'}
    )

    ax.set_title('End-to-End Response Latency Breakdown\n(with Real LLM Integration)',
                 fontsize=14, fontweight='bold', pad=20)

    # Adiciona legenda com valores absolutos
    legend_labels = [
        f'Memory Retrieval: ~58ms ({chart_data["percentages"][0]}%)',
        f'LLM Generation: 2-5s ({chart_data["percentages"][1]}%)',
        f'Network Overhead: 200-300ms ({chart_data["percentages"][2]}%)'
    ]
    ax.legend(legend_labels, loc='upper left', bbox_to_anchor=(0, 0, 0.5, 1))

    save_chart('end_to_end_latency_pie.png')

def generate_radar_chart(data):
    """Gera radar chart com dimensões do Paper Benchmark."""
    dimensions_data = data['paper_benchmark_cortex_only']['dimensions']

    categories = [d['name'] for d in dimensions_data]
    values = [d['result_percent'] for d in dimensions_data]

    # Adiciona primeiro valor no final para fechar o polígono
    values += values[:1]

    # Ângulos para cada eixo
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))

    ax.plot(angles, values, 'o-', linewidth=2, color=COLORS['cortex'], label='Cortex')
    ax.fill(angles, values, alpha=0.25, color=COLORS['cortex'])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=11)
    ax.set_ylim(0, 110)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%'])
    ax.grid(True)

    ax.set_title('Cortex Paper Benchmark: 100% Across All Dimensions',
                 fontsize=14, fontweight='bold', pad=20)

    save_chart('radar_chart.png')

def generate_realistic_benchmark_chart(data):
    """Gera gráfico de resultados do benchmark realista com LLM."""
    scenarios = data['realistic_llm_integration']['scenarios']

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Context Retention
    names = [s['name'] for s in scenarios]
    retention = [s['context_retention_percent'] for s in scenarios]

    bars = ax1.bar(names, retention, color=[COLORS['cortex'], '#6C91BF'])
    ax1.set_ylabel('Context Retention (%)', fontsize=12)
    ax1.set_title('Context Retention in Realistic Scenarios', fontsize=13, fontweight='bold')
    ax1.set_ylim(0, 110)
    ax1.grid(axis='y', alpha=0.3)

    # Adiciona valores
    for bar in bars:
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}%',
                ha='center', va='bottom', fontweight='bold')

    # Response Time
    response_times = [s['avg_response_time_seconds'] for s in scenarios]
    memories = [s['memories_stored'] for s in scenarios]

    bars2 = ax2.bar(names, response_times, color=[COLORS['cortex'], '#6C91BF'])
    ax2.set_ylabel('Avg Response Time (seconds)', fontsize=12)
    ax2.set_title('End-to-End Response Time (with gemma3:4b)', fontsize=13, fontweight='bold')
    ax2.set_ylim(0, max(response_times) * 1.3)
    ax2.grid(axis='y', alpha=0.3)

    # Adiciona valores e número de memórias
    for i, bar in enumerate(bars2):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}s\n({memories[i]} memories)',
                ha='center', va='bottom', fontweight='bold')

    plt.tight_layout()
    save_chart('realistic_benchmark.png')

def generate_all_charts():
    """Gera todos os gráficos."""
    print("📊 Gerando gráficos de performance...\n")

    data = load_data()

    generate_comparison_bar_chart(data)
    generate_latency_comparison(data)
    generate_semantic_validation_chart(data)
    generate_embedding_performance_chart(data)
    generate_end_to_end_latency_pie(data)
    generate_radar_chart(data)
    generate_realistic_benchmark_chart(data)

    print("\n✅ Todos os gráficos foram gerados com sucesso!")
    print("📁 Localização: benchmark_results/charts/")

if __name__ == '__main__':
    generate_all_charts()
