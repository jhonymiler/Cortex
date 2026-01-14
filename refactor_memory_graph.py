#!/usr/bin/env python3
"""
Script para dividir memory_graph.py em módulos menores organizados.
"""

import re
from pathlib import Path

# Ler o arquivo original
original_file = Path("src/cortex/core/memory_graph.py")
content = original_file.read_text()

# Dividir por linhas para análise
lines = content.split("\n")

# Definir ranges de métodos para cada módulo (baseado na análise anterior)
MODULES = {
    "entities.py": {
        "methods": [
            "add_entity", "get_entity", "find_entities", "resolve_entity",
            "_index_entity", "find_entity_by_name", "_find_orphan_entities",
            "_forget_entity"
        ],
        "docstring": "Entity management methods for MemoryGraph."
    },
    "episodes.py": {
        "methods": [
            "add_episode", "_index_episode", "get_episode", "find_episodes",
            "_calculate_retrievability", "_find_similar_episodes",
            "add_episode_with_consolidation", "_create_episode_relations",
            "_forget_episode"
        ],
        "docstring": "Episode management methods for MemoryGraph."
    },
    "relations.py": {
        "methods": [
            "add_relation", "add_relation_simple", "remove_relation",
            "get_relations", "get_connected", "_find_existing_relation",
            "_index_relation", "_add_relation_internal", "_forget_relation"
        ],
        "docstring": "Relation management methods for MemoryGraph."
    },
    "recall.py": {
        "methods": [
            "recall", "_generate_context_summary"
        ],
        "docstring": "Recall and query methods for MemoryGraph."
    },
    "storage.py": {
        "methods": [
            "store", "_save", "_load", "clear", "_rebuild_inverted_index"
        ],
        "docstring": "Storage and persistence methods for MemoryGraph."
    },
    "decay.py": {
        "methods": [
            "apply_access_decay", "reinforce_on_recall"
        ],
        "docstring": "Memory decay and reinforcement methods for MemoryGraph."
    },
    "contradictions.py": {
        "methods": [
            "set_contradiction_strategy", "find_contradictions",
            "get_contradiction_history", "get_pending_contradictions"
        ],
        "docstring": "Contradiction detection and resolution methods for MemoryGraph."
    },
    "visualization.py": {
        "methods": [
            "get_node_weight", "get_graph_data", "_get_node_color",
            "_get_edge_color", "get_memory_health", "_get_frequent_participants",
            "_get_conversation_participants", "_calculate_health_score", "stats"
        ],
        "docstring": "Visualization and analysis methods for MemoryGraph."
    },
}

def extract_method(lines, method_name):
    """Extrai um método completo das linhas do arquivo."""
    start_pattern = rf"^\s+def {re.escape(method_name)}\("
    method_lines = []
    in_method = False
    indent_level = None

    for i, line in enumerate(lines):
        if re.match(start_pattern, line):
            in_method = True
            indent_level = len(line) - len(line.lstrip())
            method_lines.append(line)
        elif in_method:
            if line.strip() and not line.startswith(" " * indent_level) and line[0] not in " \t":
                # Saiu do método (volta ao nível de classe ou menos)
                break
            if line.strip() and line[0] != " " and line[0] != "\t":
                # Encontrou próxima definição no mesmo nível
                if line.strip().startswith("def ") or line.strip().startswith("class "):
                    break
            method_lines.append(line)

    return method_lines

# Extrair imports do arquivo original (linhas 1-50)
imports_section = "\n".join(lines[:51])

print("Começando extração dos módulos...")

# Para cada módulo, extrair métodos
for module_name, module_info in MODULES.items():
    print(f"\nProcessando {module_name}...")
    module_path = Path(f"src/cortex/core/graph/{module_name}")

    # Começar com imports e docstring
    module_content = f'''"""
{module_info["docstring"]}

This module contains methods extracted from MemoryGraph.
"""

from typing import Any
from cortex.core.entity import Entity
from cortex.core.episode import Episode
from cortex.core.relation import Relation

# Import TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from cortex.core.graph.core import MemoryGraph


class MemoryGraphMixin:
    """Mixin class with MemoryGraph methods for {module_name.replace(".py", "")}."""

'''

    # Extrair cada método
    for method_name in module_info["methods"]:
        print(f"  - Extraindo {method_name}...")
        method_lines = extract_method(lines, method_name)
        if method_lines:
            module_content += "\n".join(method_lines) + "\n\n"
        else:
            print(f"    ⚠️  Método {method_name} não encontrado!")

    # Escrever arquivo
    module_path.write_text(module_content)
    print(f"✓ {module_name} criado com sucesso!")

print("\n✓ Extração concluída!")
print("\nPróximo passo: criar core.py com a classe MemoryGraph principal que herda todos os mixins.")
