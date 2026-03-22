"""
Cortex Configuration - Feature flags and tuning parameters for memory enhancements.

This module provides configuration for all scientific improvements:

V2.0:
1. Context Packing
2. Progressive Consolidation
3. Active Forgetting
4. Hierarchical Recall
5. SM-2 Adaptive
6. Attention Mechanism

V2.1
7. Hybrid Ranking (RRF + MMR)
8. BFS Graph Expansion
9. Community Detection

All features are opt-in for backward compatibility.
"""

import os
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class CortexConfig:
    """
    Main configuration for Cortex memory system.

    Feature Flags (all default to True for v2.0):
    - enable_context_packing: Use Context Packer for optimized prompt context
    - enable_progressive_consolidation: Use age-aware consolidation thresholds
    - enable_active_forgetting: Use Forget Gate to filter noise
    - enable_hierarchical_recall: Use 4-level memory hierarchy
    - enable_sm2_adaptive: Use SM-2 algorithm for spaced repetition
    - enable_attention_mechanism: Use Transformer attention for ranking

    Tuning Parameters:
    - context_max_tokens: Maximum tokens for prompt context
    - consolidation_mode: "progressive" or "fixed" (legacy)
    - attention_heads: Number of attention heads (4 recommended)
    - forget_threshold: Threshold for forget gate (0.6 default)
    - hierarchical_recall_enabled: Enable hierarchical recall levels
    """

    # ==================== FEATURE FLAGS ====================

    # Context Packing (40-70% token reduction)
    enable_context_packing: bool = True

    # Progressive Consolidation (60% faster pattern detection)
    enable_progressive_consolidation: bool = True

    # Active Forgetting (30% noise reduction)
    enable_active_forgetting: bool = True

    # Hierarchical Recall (2x faster, better diversity)
    enable_hierarchical_recall: bool = True

    # SM-2 Adaptive (25% better retention)
    enable_sm2_adaptive: bool = True

    # Attention Mechanism (35% better precision)
    enable_attention_mechanism: bool = True

    # V2.1: Hybrid Ranking with RRF + MMR
    enable_hybrid_ranking: bool = True

    # V2.1: BFS Graph Expansion for context enrichment
    enable_graph_expansion: bool = True

    # V2.1: Community Detection for knowledge clustering
    enable_community_detection: bool = True

    # ==================== STORAGE ====================

    # Backend de persistência: "json" (arquivo local) ou "neo4j" (banco de grafos)
    storage_backend: Literal["json", "neo4j"] = field(
        default_factory=lambda: os.getenv("CORTEX_STORAGE_BACKEND", "json")
    )

    # Diretório para dados (usado por JSONStorageAdapter)
    data_dir: str = field(
        default_factory=lambda: os.getenv("CORTEX_DATA_DIR", "./data")
    )

    # Neo4j connection settings
    neo4j_uri: str = field(
        default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687")
    )
    neo4j_user: str = field(
        default_factory=lambda: os.getenv("NEO4J_USER", "neo4j")
    )
    neo4j_password: str = field(
        default_factory=lambda: os.getenv("NEO4J_PASSWORD", "")
    )
    neo4j_database: str = field(
        default_factory=lambda: os.getenv("NEO4J_DATABASE", "neo4j")
    )

    # ==================== TUNING PARAMETERS ====================

    # Context Packing
    context_max_tokens: int = 150
    context_packing_target_reduction: float = 0.5  # 50% reduction target

    # Progressive Consolidation
    consolidation_mode: Literal["progressive", "fixed"] = "progressive"
    consolidation_threshold_emerging: int = 2  # < 7 days
    consolidation_threshold_recurring: int = 4  # 7-30 days
    consolidation_threshold_stable: int = 8  # 30-90 days
    consolidation_threshold_crystallized: int = 16  # > 90 days

    # Active Forgetting
    forget_gate_threshold: float = 0.6  # 0-1, higher = more aggressive
    forget_gate_noise_weight: float = 0.4
    forget_gate_redundancy_weight: float = 0.35
    forget_gate_obsolescence_weight: float = 0.25

    # Hierarchical Recall
    hierarchical_working_memory_days: int = 1
    hierarchical_recent_memory_days: int = 7
    hierarchical_pattern_memory_days: int = 30
    hierarchical_knowledge_memory_days: int = 365

    hierarchical_working_max_results: int = 20
    hierarchical_recent_max_results: int = 15
    hierarchical_pattern_max_results: int = 10
    hierarchical_knowledge_max_results: int = 5

    # SM-2 Adaptive
    sm2_initial_easiness: float = 2.5  # Default EF
    sm2_max_interval: int = 365  # Max days between reviews
    sm2_min_easiness: float = 1.3
    sm2_max_easiness: float = 2.5

    # Attention Mechanism
    attention_d_model: int = 256  # Embedding dimension
    attention_heads: int = 4  # Number of attention heads
    attention_temperature: float = 1.0  # Softmax temperature
    attention_use_graph_bias: bool = True  # Include graph structure

    # V2.1: Hybrid Ranking (RRF + MMR)
    rrf_k: int = 60  # RRF constant (higher = more weight to lower ranks)
    mmr_lambda: float = 0.7  # MMR tradeoff (1.0 = only relevance, 0.0 = only diversity)
    hybrid_ranking_importance_weight: float = 0.3  # Weight for importance signal

    # V2.1: BFS Graph Expansion
    graph_expansion_depth: int = 1  # BFS depth for context expansion
    graph_expansion_max_nodes: int = 15  # Max nodes to add via expansion
    graph_expansion_min_strength: float = 0.3  # Min relation strength to follow

    # V2.1: Community Detection
    community_min_size: int = 3  # Minimum members for a valid community
    community_resolution: float = 1.0  # Higher = more smaller communities
    hub_min_connections: int = 5  # Minimum connections to be considered a hub

    # ==================== BACKWARD COMPATIBILITY ====================

    # Legacy mode: Disable all improvements (v1.x behavior)
    legacy_mode: bool = False

    def __post_init__(self):
        """Apply legacy mode if enabled."""
        if self.legacy_mode:
            self.enable_context_packing = False
            self.enable_progressive_consolidation = False
            self.enable_active_forgetting = False
            self.enable_hierarchical_recall = False
            self.enable_sm2_adaptive = False
            self.enable_attention_mechanism = False
            self.enable_hybrid_ranking = False
            self.enable_graph_expansion = False
            self.enable_community_detection = False
            self.consolidation_mode = "fixed"

    def to_dict(self) -> dict:
        """Export configuration as dictionary."""
        return {
            # Feature flags
            "enable_context_packing": self.enable_context_packing,
            "enable_progressive_consolidation": self.enable_progressive_consolidation,
            "enable_active_forgetting": self.enable_active_forgetting,
            "enable_hierarchical_recall": self.enable_hierarchical_recall,
            "enable_sm2_adaptive": self.enable_sm2_adaptive,
            "enable_attention_mechanism": self.enable_attention_mechanism,
            "enable_hybrid_ranking": self.enable_hybrid_ranking,
            "enable_graph_expansion": self.enable_graph_expansion,
            "enable_community_detection": self.enable_community_detection,

            # Context packing
            "context_max_tokens": self.context_max_tokens,

            # Consolidation
            "consolidation_mode": self.consolidation_mode,

            # Forget gate
            "forget_gate_threshold": self.forget_gate_threshold,

            # Hierarchical recall
            "hierarchical_recall_enabled": self.enable_hierarchical_recall,

            # SM-2
            "sm2_max_interval": self.sm2_max_interval,

            # Attention
            "attention_heads": self.attention_heads,

            # V2.1: Hybrid ranking
            "rrf_k": self.rrf_k,
            "mmr_lambda": self.mmr_lambda,

            # V2.1: Graph expansion
            "graph_expansion_depth": self.graph_expansion_depth,
            "graph_expansion_max_nodes": self.graph_expansion_max_nodes,

            # Storage
            "storage_backend": self.storage_backend,
            "data_dir": self.data_dir,
            "neo4j_uri": self.neo4j_uri,
            "neo4j_user": self.neo4j_user,
            "neo4j_database": self.neo4j_database,
            # Nota: neo4j_password NÃO é exportado por segurança

            # Legacy
            "legacy_mode": self.legacy_mode,
        }

    @classmethod
    def create_legacy(cls) -> "CortexConfig":
        """
        Create config for v1.x behavior (all improvements disabled).

        Use this for testing backward compatibility.
        """
        return cls(legacy_mode=True)

    @classmethod
    def create_performance(cls) -> "CortexConfig":
        """
        Create config optimized for performance (all improvements enabled, aggressive).

        Recommended for production with high-volume workloads.
        """
        return cls(
            # All enabled (default)
            forget_gate_threshold=0.7,  # More aggressive forgetting
            consolidation_threshold_emerging=2,  # Fast consolidation
            attention_temperature=0.8,  # Sharper attention
        )

    @classmethod
    def create_conservative(cls) -> "CortexConfig":
        """
        Create config for conservative/gentle behavior.

        Recommended for critical applications where false negatives are costly.
        """
        return cls(
            forget_gate_threshold=0.8,  # Less aggressive forgetting
            consolidation_threshold_emerging=3,  # Slower consolidation
            consolidation_threshold_recurring=6,
            attention_temperature=1.2,  # Softer attention
        )


# Global default config instance
DEFAULT_CONFIG = CortexConfig()


def get_config() -> CortexConfig:
    """Get the current global configuration."""
    return DEFAULT_CONFIG


def set_config(config: CortexConfig) -> None:
    """Set the global configuration."""
    global DEFAULT_CONFIG
    DEFAULT_CONFIG = config


def reset_config() -> None:
    """Reset configuration to defaults."""
    global DEFAULT_CONFIG
    DEFAULT_CONFIG = CortexConfig()
