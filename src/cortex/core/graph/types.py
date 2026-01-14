"""
Types and data structures for MemoryGraph.

Contains RecallResult and shared types.
"""

from dataclasses import dataclass, field
from typing import Any

from cortex.core.entity import Entity
from cortex.core.episode import Episode
from cortex.core.relation import Relation


@dataclass
class RecallResult:
    """Resultado de uma busca de memória."""

    entities: list[Entity] = field(default_factory=list)
    episodes: list[Episode] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    context_summary: str = ""

    # Métricas de recall (para debug/análise)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [e.to_dict() for e in self.entities],
            "episodes": [e.to_dict() for e in self.episodes],
            "relations": [r.to_dict() for r in self.relations],
            "context_summary": self.context_summary,
            "metrics": self.metrics,
        }

    def to_prompt_context(self, format: str = "yaml") -> str:
        """
        Gera contexto compacto para injetar no prompt do LLM.

        Formato YAML: máxima densidade informacional com mínimo de tokens.
        Cada linha carrega significado, não estrutura.

        Args:
            format: "yaml" (default, compacto) ou "text" (legível)
        """
        if not self.entities and not self.episodes:
            return ""

        if format == "yaml":
            return self._to_yaml_context()
        return self._to_text_context()

    def _to_yaml_context(self, max_tokens: int = 150) -> str:
        """
        Formato ULTRA-COMPACTO para LLMs.

        OTIMIZAÇÃO v4 (V2.0): Context Packing Algorithm
        - Usa ContextPacker para 40-70% de redução de tokens
        - Priority scoring: importance × retrievability × recency
        - Grouping de episódios redundantes
        - Sumarização hierárquica
        """
        # V2.0: Use Context Packer if enabled
        if hasattr(self, '_config') and self._config.enable_context_packing:
            # Separate personal and collective episodes
            personal_episodes = [
                ep for ep in self.episodes
                if ep.metadata.get("visibility", "personal") == "personal"
                and not ep.metadata.get("inherited_from")
            ]

            collective_episodes = [
                ep for ep in self.episodes
                if ep.metadata.get("visibility") == "learned"
                or ep.metadata.get("inherited_from")
            ]

            # Use Context Packer
            packed = self._context_packer.pack_episodes(
                episodes=personal_episodes,
                entities=self.entities,
                collective_episodes=collective_episodes,
            )

            return packed

        # Legacy path (if Context Packing disabled)
        parts = []
        token_estimate = 0

        # Filtra entidades relevantes (ignora genéricos)
        skip_names = {"user", "assistant", "participant", "none", "", "undefined", "cliente", "sistema"}
        useful_entities = [
            e for e in self.entities[:3]  # Reduzido de 5 para 3
            if e.name.lower() not in skip_names
            and e.type.lower() not in skip_names
            and not e.name.startswith("[")
            and len(e.name) > 2  # Ignora nomes muito curtos
        ]

        if useful_entities:
            # Apenas o nome principal, sem prefixo verboso
            parts.append(f"Cliente: {useful_entities[0].name}")
            token_estimate += 5

        # Separa episódios por relevância (mais recente + maior importância)
        sorted_episodes = sorted(
            self.episodes[:10],  # Considera até 10
            key=lambda ep: (ep.importance, ep.timestamp.timestamp() if ep.timestamp else 0),
            reverse=True
        )

        personal_episodes = []
        collective_episodes = []

        for ep in sorted_episodes[:4]:  # Reduzido de 6 para 4
            visibility = ep.metadata.get("visibility", "personal")
            if visibility == "learned" or ep.metadata.get("inherited_from"):
                collective_episodes.append(ep)
            else:
                personal_episodes.append(ep)

        # Histórico pessoal - APENAS 2 episódios mais relevantes
        if personal_episodes and token_estimate < max_tokens:
            parts.append("Histórico:")
            for ep in personal_episodes[:2]:  # Reduzido de 3 para 2
                line = self._format_episode_compact(ep)
                if line and token_estimate < max_tokens:
                    parts.append(line)
                    token_estimate += len(line.split()) + 2

        # Conhecimento coletivo - APENAS 1 se sobrar espaço
        if collective_episodes and token_estimate < max_tokens - 20:
            line = self._format_collective_compact(collective_episodes[0])
            if line:
                parts.append(f"💡 {line}")
                token_estimate += len(line.split()) + 2

        return "\n".join(parts) if parts else ""

    def _format_episode_compact(self, ep: Episode) -> str:
        """Formato ultra-compacto: ação: resultado (max 60 chars)."""
        w5h = ep.metadata.get("w5h", {})
        action = self._sanitize_value(w5h.get("what") or ep.action)
        outcome = self._sanitize_value(w5h.get("how") or ep.outcome)

        if not action or action == "undefined":
            return ""

        # Formato compacto: "- ação: resultado"
        if outcome and outcome != "undefined":
            line = f"  - {action[:25]}: {outcome[:30]}"
        else:
            line = f"  - {action[:50]}"

        return line[:60]  # Hard limit

    def _format_collective_compact(self, ep: Episode) -> str:
        """Formato compacto para conhecimento coletivo (max 50 chars)."""
        w5h = ep.metadata.get("w5h", {})
        problema = self._sanitize_value(w5h.get("what") or ep.action)
        solucao = self._sanitize_value(w5h.get("how") or ep.outcome)

        if problema and solucao:
            return f"{problema[:20]}→{solucao[:25]}"
        return problema[:45] if problema else ""

    def _sanitize_value(self, value: Any) -> str:
        """Sanitiza valor para evitar undefined, null, arrays como string."""
        if value is None:
            return ""

        # Converte para string
        str_val = str(value).strip()

        # Remove valores inválidos
        if str_val.lower() in {"undefined", "null", "none", ""}:
            return ""

        # Detecta arrays serializados como string
        if str_val.startswith("[") and str_val.endswith("]"):
            try:
                # Tenta parsear como lista
                import ast
                parsed = ast.literal_eval(str_val)
                if isinstance(parsed, list):
                    return ", ".join(str(item) for item in parsed[:3])
            except Exception:
                # Se não conseguir, retorna os primeiros 50 chars
                return str_val[1:-1][:50]

        return str_val

    def _to_text_context(self) -> str:
        """Formato texto legível (mais tokens, mais claro)."""
        parts = ["[MEMORY CONTEXT]"]

        if self.entities:
            parts.append("\nEntidades conhecidas:")
            for entity in self.entities[:5]:
                parts.append(f"  - {entity.name} ({entity.type})")

        if self.episodes:
            parts.append("\nExperiências relevantes:")
            for episode in self.episodes[:3]:
                parts.append(f"  - {episode.to_summary()}")

        if self.context_summary:
            parts.append(f"\nResumo: {self.context_summary}")

        return "\n".join(parts)
