"""
CanonicalValidator V2 — preventive normative validation for Memory writes.

Closes the correctness-norm gap (elem. 3) of the 5-element detector.

3 DETECTION LEVELS:
  1. Heuristic: negation words + polarity inversion (free, instant)
  2. Token Jaccard: detects near-duplicates that may indicate
     semantically equivalent claims with subtle differences
  3. Embedding similarity: optional, requires sentence-transformers.
     Catches semantic contradictions not visible at token level
     (e.g., "loves pizza" vs "hates pizza" — same words, opposite meaning)

POLICIES:
  - WARN: never blocks, just marks metadata (backwards compat)
  - BLOCK: blocks on hard violations

DETECTION CATEGORIES:
  1. Schema violation: required W5H fields empty
  2. Redundancy: high similarity with existing memory
  3. Contradiction: opposing claims about same who+where
  4. Ambiguity: who-field matches multiple distinct entities (homonyms)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from cortex_v5.core.memory import Memory, Entity
    from cortex_v5.core.graph import MemoryGraph


class ValidationStatus(str, Enum):
    """Status of a validation result."""

    OK = "OK"
    WARN = "WARN"
    BLOCKED = "BLOCKED"


class ValidationPolicy(str, Enum):
    """Policy for handling validation issues."""

    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass
class ValidationResult:
    """
    Result of validating a candidate Memory.

    Attributes:
        status: OK, WARN, or BLOCKED
        reason: human-readable explanation
        conflicting_memory: Memory that contradicts the candidate
        similar_memory: Memory very similar to the candidate
        ambiguous_entities: Entity candidates for ambiguous who-field
        suggestions: actionable suggestions
        detection_level: which level of the 3-tier system caught this
                        (heuristic | token | embedding | none)
    """

    status: ValidationStatus
    reason: str = ""
    conflicting_memory: Optional["Memory"] = None
    similar_memory: Optional["Memory"] = None
    ambiguous_entities: list["Entity"] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    detection_level: str = "none"

    @property
    def is_blocking(self) -> bool:
        return self.status == ValidationStatus.BLOCKED

    @property
    def is_clean(self) -> bool:
        return self.status == ValidationStatus.OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "conflicting_memory_id": self.conflicting_memory.id if self.conflicting_memory else None,
            "similar_memory_id": self.similar_memory.id if self.similar_memory else None,
            "ambiguous_entity_ids": [e.id for e in self.ambiguous_entities],
            "suggestions": self.suggestions,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "detection_level": self.detection_level,
        }


# === Detection helpers (language-agnostic) ===

# Negation signals across multiple languages
_NEGATION_SIGNALS = {
    # Portuguese
    "não", "nao", "nunca", "jamais", "rejeitou", "rejeita", "recusou",
    "recusa", "negou", "nega", "reprovou", "reprova", "detestou", "odeia",
    "abomina", "nenhum", "nenhuma", "impossível", "impossivel",
    "sem",  # "without" (sem açúcar = no sugar)
    # English
    "not", "no", "never", "rejected", "refused", "denied", "hates",
    "detests", "abominates", "dislikes", "neither", "none", "impossible",
    "without",
    # Spanish
    "no", "nunca", "jamás", "rechazó", "rechaza", "negó", "niega", "odia",
    "detesta", "abomina", "ninguno", "ninguna", "imposible",
    "sin",  # "without" (sin azúcar = no sugar)
}


def _has_negation(text: str) -> bool:
    """Check if text contains any negation signal (language-agnostic)."""
    if not text:
        return False
    words = set(text.lower().split())
    return bool(words & _NEGATION_SIGNALS)


def _jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Jaccard similarity between two string sets."""
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _tokenize(text: str) -> set[str]:
    """Simple whitespace tokenizer with lowercase."""
    if not text:
        return set()
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) > 1}


def _who_overlap(memory_a: "Memory", memory_b: "Memory") -> float:
    """Jaccard overlap of who-fields."""
    a = set(memory_a.who or [])
    b = set(memory_b.who or [])
    return _jaccard(a, b)


def _what_overlap(memory_a: "Memory", memory_b: "Memory") -> float:
    """Token overlap of what-fields."""
    return _jaccard(_tokenize(memory_a.what), _tokenize(memory_b.what))


class CanonicalValidator:
    """
    Validates Memory writes against the canonical reading of the graph.

    Runs 4 checks in order:
      1. Schema: required W5H fields populated
      2. Ambiguity: who-field not associated with multiple entities
      3. Redundancy: not near-duplicate of existing memory
      4. Contradiction: not opposing claim about same referent

    Detection levels (priority: blocking > warn > clean):
      - Heuristic: negation words + polarity (free, instant)
      - Token: Jaccard similarity (free, fast)
      - Embedding: semantic similarity (optional, requires sentence-transformers)
    """

    REDUNDANCY_THRESHOLD = 0.85
    CONTRADICTION_WHO_OVERLAP = 0.5
    CONTRADICTION_WHAT_OVERLAP = 0.3  # lowered from 0.4 to catch "loves pizza" vs "hates pizza"

    def __init__(
        self,
        policy: ValidationPolicy = ValidationPolicy.WARN,
        enable_embedding_check: bool = True,
    ) -> None:
        """
        Args:
            policy: WARN (default) or BLOCK
            enable_embedding_check: if True and sentence-transformers available,
                use embeddings for semantic contradiction detection
        """
        self.policy = policy
        self.enable_embedding_check = enable_embedding_check
        self._history: list[ValidationResult] = []
        self._embedding_recall = None
        if enable_embedding_check:
            try:
                from cortex_v5.core.recall.embedding import EmbeddingRecall
                self._embedding_recall = EmbeddingRecall()
            except ImportError:
                self._embedding_recall = None

    def validate_write(
        self,
        new_memory: "Memory",
        graph: "MemoryGraph",
    ) -> ValidationResult:
        """Validate a candidate Memory before writing it."""
        # 1. Schema check (highest priority)
        schema_result = self._check_schema(new_memory)
        if schema_result.is_blocking:
            return self._finalize(schema_result)

        # 2. Ambiguity check
        ambiguity_result = self._check_ambiguity(new_memory, graph)

        # 3. Find overlapping memories
        overlapping = self._find_overlapping(new_memory, graph)

        # 4. Check each overlapping memory
        best_similar: Optional[tuple[float, "Memory"]] = None
        best_conflict: Optional["Memory"] = None
        conflict_level = "none"

        for existing in overlapping:
            sim = _what_overlap(new_memory, existing)

            # 4a. Redundancy (token-based)
            if sim >= self.REDUNDANCY_THRESHOLD:
                if best_similar is None or sim > best_similar[0]:
                    best_similar = (sim, existing)

            # 4b. Contradiction (heuristic: negation + polarity)
            who_overlap = _who_overlap(new_memory, existing)
            if (
                who_overlap >= self.CONTRADICTION_WHO_OVERLAP
                and sim >= self.CONTRADICTION_WHAT_OVERLAP
            ):
                if self._is_heuristic_contradiction(new_memory, existing):
                    best_conflict = existing
                    conflict_level = "heuristic"
                    break

                # 4c. Contradiction (embedding: semantic opposition)
                if (
                    self.enable_embedding_check
                    and self._embedding_recall
                    and self._embedding_recall.is_available()
                ):
                    emb_sim = self._embedding_similarity(new_memory, existing)
                    # High token overlap + low embedding similarity = contradiction
                    if sim >= self.CONTRADICTION_WHAT_OVERLAP and emb_sim < 0.4:
                        best_conflict = existing
                        conflict_level = "embedding"
                        break

        # Build result (priority: conflict > similar > ambiguity > schema)
        if best_conflict is not None:
            return self._finalize(ValidationResult(
                status=ValidationStatus.BLOCKED,
                reason=f"Contradicts existing memory {best_conflict.id}: same referent, opposing claim",
                conflicting_memory=best_conflict,
                suggestions=[
                    "Update the existing memory instead of creating a new one",
                    "Or rephrase the new memory to avoid the contradiction",
                    f"Existing: {best_conflict.what!r}",
                ],
                metadata={
                    "who_overlap": _who_overlap(new_memory, best_conflict),
                    "what_overlap": _what_overlap(new_memory, best_conflict),
                },
                detection_level=conflict_level,
            ))

        if best_similar is not None:
            sim_score, sim_memory = best_similar
            return self._finalize(ValidationResult(
                status=ValidationStatus.WARN,
                reason=f"High similarity ({sim_score:.2f}) with existing memory {sim_memory.id}",
                similar_memory=sim_memory,
                suggestions=[
                    "Consider updating the existing memory if this is a refinement",
                    "Or rephrase to distinguish from the existing one",
                    f"Existing: {sim_memory.what!r}",
                ],
                metadata={"similarity_score": sim_score},
                detection_level="token",
            ))

        if ambiguity_result.status == ValidationStatus.WARN:
            return self._finalize(ambiguity_result)

        if schema_result.status == ValidationStatus.WARN:
            return self._finalize(schema_result)

        return self._finalize(ValidationResult(
            status=ValidationStatus.OK,
            reason="No issues found",
        ))

    def _finalize(self, result: ValidationResult) -> ValidationResult:
        """Apply policy (downgrade BLOCKED to WARN if policy is WARN)."""
        if result.status == ValidationStatus.BLOCKED and self.policy == ValidationPolicy.WARN:
            result = ValidationResult(
                status=ValidationStatus.WARN,
                reason=result.reason,
                conflicting_memory=result.conflicting_memory,
                similar_memory=result.similar_memory,
                ambiguous_entities=result.ambiguous_entities,
                suggestions=result.suggestions,
                timestamp=result.timestamp,
                metadata={**result.metadata, "downgraded_from": "BLOCKED"},
                detection_level=result.detection_level,
            )
        self._history.append(result)
        return result

    def _check_schema(self, memory: "Memory") -> ValidationResult:
        """Check required W5H fields are populated."""
        if not memory.what or not memory.what.strip():
            return ValidationResult(
                status=ValidationStatus.BLOCKED,
                reason="Schema violation: 'what' field is required and cannot be empty",
                suggestions=["Provide a non-empty 'what' describing the event or fact"],
                metadata={"missing_field": "what"},
                detection_level="heuristic",
            )
        if memory.when and memory.when.year > 2200:
            return ValidationResult(
                status=ValidationStatus.WARN,
                reason=f"Schema warning: 'when' is far in the future ({memory.when.year})",
                suggestions=["Verify the timestamp is correct"],
                detection_level="heuristic",
            )
        return ValidationResult(status=ValidationStatus.OK, detection_level="heuristic")

    def _check_ambiguity(
        self, memory: "Memory", graph: "MemoryGraph"
    ) -> ValidationResult:
        """Check who-field for homonyms."""
        if not memory.who:
            return ValidationResult(status=ValidationStatus.OK)

        ambiguous: list["Entity"] = []
        for who_name in memory.who:
            if not who_name:
                continue
            candidates = self._find_entities_by_name(who_name, graph)
            if len(candidates) > 1:
                ambiguous.extend(candidates)

        if ambiguous:
            return ValidationResult(
                status=ValidationStatus.WARN,
                reason=f"Ambiguous who-field: {len(ambiguous)} entities match",
                ambiguous_entities=ambiguous,
                suggestions=[
                    "Use a more specific identifier (email, ID, etc.)",
                    f"Candidates: {[e.name for e in ambiguous]}",
                ],
                detection_level="heuristic",
            )
        return ValidationResult(status=ValidationStatus.OK)

    def _find_entities_by_name(
        self, name: str, graph: "MemoryGraph"
    ) -> list["Entity"]:
        """Find entities whose name matches (case-insensitive)."""
        if not hasattr(graph, "_entities"):
            return []
        name_lower = name.lower()
        return [
            entity
            for entity in graph._entities.values()
            if entity.name and entity.name.lower() == name_lower
        ]

    def _find_overlapping(
        self, memory: "Memory", graph: "MemoryGraph"
    ) -> list["Memory"]:
        """Find existing memories sharing who + where."""
        if not hasattr(graph, "_memories"):
            return []
        new_who = set(getattr(memory, "who", None) or [])
        new_where = getattr(memory, "where", None) or "default"

        overlapping: list["Memory"] = []
        for existing in graph._memories.values():
            existing_where = getattr(existing, "where", None) or "default"
            if existing_where != new_where:
                continue
            existing_who = set(getattr(existing, "who", None) or [])
            if new_who and existing_who and not (new_who & existing_who):
                continue
            overlapping.append(existing)
        return overlapping

    def _is_heuristic_contradiction(
        self, new_memory: "Memory", existing: "Memory"
    ) -> bool:
        """Heuristic: one has negation, the other doesn't."""
        new_neg = _has_negation(new_memory.what) or _has_negation(getattr(new_memory, "why", "") or "")
        existing_what = getattr(existing, "what", "") or ""
        existing_why = getattr(existing, "why", "") or ""
        existing_neg = _has_negation(existing_what) or _has_negation(existing_why)
        return new_neg != existing_neg

    def _embedding_similarity(
        self, memory_a: "Memory", memory_b: "Memory"
    ) -> float:
        """Compute embedding similarity (returns 1.0 if unavailable)."""
        if not self._embedding_recall or not self._embedding_recall.is_available():
            return 1.0  # Can't measure, assume similar
        try:
            a_emb = self._embedding_recall.embed(memory_a.what)
            b_emb = self._embedding_recall.embed(memory_b.what)
            if a_emb is None or b_emb is None:
                return 1.0
            from cortex_v5.core.recall.embedding import cosine_similarity
            return cosine_similarity(a_emb, b_emb)
        except Exception:
            return 1.0

    def get_history(self) -> list[ValidationResult]:
        return self._history.copy()

    def get_blocked(self) -> list[ValidationResult]:
        return [r for r in self._history if r.status == ValidationStatus.BLOCKED]

    def get_warnings(self) -> list[ValidationResult]:
        return [r for r in self._history if r.status == ValidationStatus.WARN]

    def clear_history(self) -> None:
        self._history.clear()

    def stats(self) -> dict[str, Any]:
        return {
            "total": len(self._history),
            "ok": sum(1 for r in self._history if r.status == ValidationStatus.OK),
            "warn": sum(1 for r in self._history if r.status == ValidationStatus.WARN),
            "blocked": sum(1 for r in self._history if r.status == ValidationStatus.BLOCKED),
            "policy": self.policy.value,
            "embedding_check_enabled": self.enable_embedding_check and self._embedding_recall is not None and self._embedding_recall.is_available(),
        }


def create_default_validator() -> CanonicalValidator:
    """Create validator with default WARN policy."""
    return CanonicalValidator(policy=ValidationPolicy.WARN)


def create_strict_validator() -> CanonicalValidator:
    """Create validator with BLOCK policy."""
    return CanonicalValidator(policy=ValidationPolicy.BLOCK)
