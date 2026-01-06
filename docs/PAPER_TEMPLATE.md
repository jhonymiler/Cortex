# Cortex: Cognitive Memory Architecture for LLM Agents

## Abstract

Large Language Models (LLMs) are stateless by design, forgetting context between sessions. We present **Cortex**, a cognitive memory architecture using the novel **W5H model** (Who, What, Why, When, Where, How) with Ebbinghaus-inspired decay and emergent hub centrality. Our experiments show Cortex achieves [X]% improvement in multi-session coherence and [Y]% memory hit rate compared to baseline RAG systems.

**Keywords:** LLM Memory, Cognitive Architecture, Multi-Session Agents, W5H Model

---

## 1. Introduction

### 1.1 Motivation
LLM agents today suffer from "conversational amnesia"—each session starts from zero. Existing approaches like RAG focus on retrieval but lack cognitive modeling.

### 1.2 Contributions
1. **W5H Memory Model**: Unified representation capturing semantic essence
2. **Cognitive Decay**: Ebbinghaus-inspired forgetting with hub protection
3. **Emergent Importance**: Graph centrality determines memory retention
4. **Benchmarking**: Comprehensive evaluation on multi-session tasks

---

## 2. Related Work

| System | Approach | Limitation |
|--------|----------|------------|
| MemGPT | OS-like hierarchy | Complex, high latency |
| Mem0 | Salience extraction | No cognitive modeling |
| RAG | Vector similarity | No session continuity |
| **Cortex** | W5H + Decay + Centrality | (this work) |

---

## 3. Cortex Architecture

### 3.1 W5H Memory Model
```
Memory = {
  Who: participants[],      // Entities involved
  What: action,            // What happened
  Why: cause,              // Causal reasoning
  When: timestamp,         // Temporal context
  Where: namespace,        // Spatial/domain context
  How: outcome             // Result/method
}
```

### 3.2 Decay Mechanism
Based on Ebbinghaus (1885):
```
R = e^(-t/S)
S = base_stability × (1 + log(access_count)) × (1 + centrality)
```

### 3.3 Hub Centrality
Memories referenced by many others decay slower:
```
centrality(m) = log(1 + incoming_references + memories_pointing_to_m)
```

---

## 4. Experimental Setup

### 4.1 Datasets
- **MemoryAgentBench**: Multi-turn QA (public)
- **CortexBench**: 8 domains, 400+ conversations (ours)

### 4.2 Baselines
1. Baseline (no memory)
2. RAG (ChromaDB)
3. Mem0 (open source)

### 4.3 Metrics
| Metric | Definition |
|--------|------------|
| Precision@K | Relevant memories / K retrieved |
| Recall@K | Retrieved relevant / Total relevant |
| MRR | Mean Reciprocal Rank |
| Hit Rate | % messages with useful recall |
| Consistency | Factual coherence across sessions |

---

## 5. Results

### 5.1 Main Results

| System | P@3 | R@5 | MRR | Hit% | Consistency |
|--------|-----|-----|-----|------|-------------|
| Baseline | - | - | - | 0% | - |
| RAG | [X] | [X] | [X] | [X]% | [X]% |
| Mem0 | [X] | [X] | [X] | [X]% | [X]% |
| **Cortex** | **[X]** | **[X]** | **[X]** | **[X]%** | **[X]%** |

### 5.2 Ablation Study

| Variant | Hit% | Δ vs Full |
|---------|------|-----------|
| Full (W5H+Decay+Hub+Cons) | [X]% | - |
| No Decay | [X]% | [X]% |
| No Centrality | [X]% | [X]% |
| No Consolidation | [X]% | [X]% |
| Simple Episodic | [X]% | [X]% |

### 5.3 Efficiency
- Token overhead: [X]% increase
- Latency overhead: [X]ms (recall: [X]ms, store: [X]ms)

---

## 6. Discussion

### 6.1 Key Findings
- W5H provides richer semantic capture than simple episodic
- Decay prevents memory bloat while retaining important information
- Hub centrality naturally identifies critical memories

### 6.2 Limitations
- Requires LLM for semantic extraction
- Consolidation threshold is hyperparameter
- Not tested on very long conversations (100+ sessions)

---

## 7. Conclusion

Cortex demonstrates that cognitive-inspired memory modeling significantly improves LLM agent performance in multi-session scenarios.

---

## References

[1] MemGPT: Towards LLMs as Operating Systems (2023)
[2] Mem0: Building Production-Ready AI Agents (2025)
[3] CoALA: Cognitive Architectures for Language Agents (2023)
[4] Generative Agents: Interactive Simulacra (2023)
[5] A Survey on Memory Mechanism of LLM Agents (2024)
[6] Memory in the Age of AI Agents: A Survey (2025)
[7] Ebbinghaus: Memory: A Contribution (1885)
