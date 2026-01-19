"""
Graph Algorithms for Memory Network Analysis.

Implements advanced graph algorithms for knowledge discovery:

1. BFS Graph Traversal: Explores neighborhood connections
2. Community Detection (Louvain): Groups related nodes
3. Hub Detection: Identifies central/important nodes

These algorithms enhance Cortex's ability to:
- Discover indirect relationships between memories
- Identify clusters of related knowledge
- Find important "hub" memories that connect many concepts
"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Iterator
import math
import random


@dataclass
class TraversalResult:
    """Result of a graph traversal operation."""

    visited_ids: set[str] = field(default_factory=set)
    paths: dict[str, list[str]] = field(default_factory=dict)  # id -> path from start
    distances: dict[str, int] = field(default_factory=dict)  # id -> hop distance
    neighbors_by_depth: dict[int, set[str]] = field(default_factory=dict)  # depth -> ids


@dataclass
class Community:
    """A detected community/cluster of nodes."""

    id: str
    member_ids: set[str] = field(default_factory=set)
    central_node_id: str | None = None
    cohesion: float = 0.0  # Internal edge density
    summary: str = ""


class BFSGraphTraversal:
    """
    Breadth-First Search Graph Traversal.

    Explores the memory graph starting from seed nodes,
    discovering connected memories up to a specified depth.

    Use cases:
    - Find all memories related to a topic (within N hops)
    - Discover indirect connections between entities
    - Expand recall results with related context

    The algorithm respects relation types and strengths,
    allowing filtered traversal (e.g., only causal relations).
    """

    def __init__(
        self,
        get_neighbors_fn: Any = None,  # Will be bound to MemoryGraph
    ):
        """
        Args:
            get_neighbors_fn: Function(node_id) -> list[(neighbor_id, relation)]
        """
        self.get_neighbors = get_neighbors_fn

    def traverse(
        self,
        start_ids: set[str] | list[str],
        max_depth: int = 2,
        max_nodes: int = 50,
        relation_types: set[str] | None = None,
        min_strength: float = 0.0,
        exclude_ids: set[str] | None = None,
    ) -> TraversalResult:
        """
        Perform BFS traversal from starting nodes.

        Args:
            start_ids: Initial node IDs to start traversal from
            max_depth: Maximum number of hops from start nodes
            max_nodes: Maximum total nodes to visit
            relation_types: Only follow these relation types (None = all)
            min_strength: Minimum relation strength to follow
            exclude_ids: Node IDs to skip

        Returns:
            TraversalResult with visited nodes, paths, and distances
        """
        if not self.get_neighbors:
            raise ValueError("get_neighbors function not set")

        start_ids = set(start_ids) if isinstance(start_ids, list) else start_ids
        exclude_ids = exclude_ids or set()

        result = TraversalResult()
        result.neighbors_by_depth[0] = start_ids.copy()

        # Initialize
        queue: deque[tuple[str, int, list[str]]] = deque()  # (node_id, depth, path)
        for start_id in start_ids:
            if start_id not in exclude_ids:
                queue.append((start_id, 0, [start_id]))
                result.visited_ids.add(start_id)
                result.distances[start_id] = 0
                result.paths[start_id] = [start_id]

        # BFS
        while queue and len(result.visited_ids) < max_nodes:
            current_id, depth, path = queue.popleft()

            if depth >= max_depth:
                continue

            # Get neighbors
            neighbors = self.get_neighbors(current_id)

            for neighbor_id, relation in neighbors:
                # Skip if already visited or excluded
                if neighbor_id in result.visited_ids or neighbor_id in exclude_ids:
                    continue

                # Filter by relation type
                if relation_types and relation.relation_type not in relation_types:
                    continue

                # Filter by strength
                if relation.strength < min_strength:
                    continue

                # Add to results
                new_depth = depth + 1
                new_path = path + [neighbor_id]

                result.visited_ids.add(neighbor_id)
                result.distances[neighbor_id] = new_depth
                result.paths[neighbor_id] = new_path

                # Track by depth
                if new_depth not in result.neighbors_by_depth:
                    result.neighbors_by_depth[new_depth] = set()
                result.neighbors_by_depth[new_depth].add(neighbor_id)

                # Add to queue for further exploration
                if new_depth < max_depth:
                    queue.append((neighbor_id, new_depth, new_path))

                if len(result.visited_ids) >= max_nodes:
                    break

        return result

    def find_path(
        self,
        from_id: str,
        to_id: str,
        max_depth: int = 5,
    ) -> list[str] | None:
        """
        Find shortest path between two nodes.

        Args:
            from_id: Starting node ID
            to_id: Target node ID
            max_depth: Maximum path length

        Returns:
            List of node IDs forming the path, or None if no path exists
        """
        if from_id == to_id:
            return [from_id]

        result = self.traverse(
            start_ids={from_id},
            max_depth=max_depth,
            max_nodes=1000,  # Allow more nodes for pathfinding
        )

        return result.paths.get(to_id)

    def expand_context(
        self,
        seed_ids: set[str],
        depth: int = 1,
        max_expansion: int = 20,
    ) -> set[str]:
        """
        Expand a set of IDs by adding their immediate neighbors.

        Useful for enriching recall results with related context.

        Args:
            seed_ids: Initial IDs to expand
            depth: How many hops to expand
            max_expansion: Maximum new IDs to add

        Returns:
            Expanded set of IDs (including original seeds)
        """
        result = self.traverse(
            start_ids=seed_ids,
            max_depth=depth,
            max_nodes=len(seed_ids) + max_expansion,
        )
        return result.visited_ids


class LouvainCommunityDetection:
    """
    Louvain Algorithm for Community Detection.

    Detects clusters of densely connected nodes in the memory graph.
    Uses modularity optimization to find natural groupings.

    Use cases:
    - Group related memories into topics
    - Identify "collective knowledge" clusters
    - Find isolated vs central memory regions

    The algorithm works in two phases:
    1. Local modularity optimization (move nodes between communities)
    2. Community aggregation (treat communities as single nodes)

    Reference: Blondel et al., "Fast unfolding of communities in large
    networks" (2008)
    """

    def __init__(
        self,
        get_neighbors_fn: Any = None,
        resolution: float = 1.0,
    ):
        """
        Args:
            get_neighbors_fn: Function(node_id) -> list[(neighbor_id, relation)]
            resolution: Higher = more smaller communities, lower = fewer larger
        """
        self.get_neighbors = get_neighbors_fn
        self.resolution = resolution

    def detect_communities(
        self,
        node_ids: list[str],
        min_community_size: int = 2,
        max_iterations: int = 10,
    ) -> list[Community]:
        """
        Detect communities in the graph.

        Args:
            node_ids: All node IDs to consider
            min_community_size: Minimum members for a valid community
            max_iterations: Maximum optimization iterations

        Returns:
            List of detected communities
        """
        if not self.get_neighbors or len(node_ids) < min_community_size:
            return []

        # Build adjacency and weights
        adjacency: dict[str, dict[str, float]] = defaultdict(dict)
        degrees: dict[str, float] = defaultdict(float)
        total_weight = 0.0

        for node_id in node_ids:
            neighbors = self.get_neighbors(node_id)
            for neighbor_id, relation in neighbors:
                if neighbor_id in node_ids:
                    weight = relation.strength
                    adjacency[node_id][neighbor_id] = weight
                    adjacency[neighbor_id][node_id] = weight
                    degrees[node_id] += weight
                    degrees[neighbor_id] += weight
                    total_weight += weight

        if total_weight == 0:
            return []

        total_weight /= 2  # Each edge counted twice

        # Initialize: each node in its own community
        node_to_community: dict[str, int] = {nid: i for i, nid in enumerate(node_ids)}
        community_nodes: dict[int, set[str]] = {i: {nid} for i, nid in enumerate(node_ids)}

        # Phase 1: Local modularity optimization
        improved = True
        iteration = 0

        while improved and iteration < max_iterations:
            improved = False
            iteration += 1

            # Shuffle nodes for randomization
            shuffled_nodes = list(node_ids)
            random.shuffle(shuffled_nodes)

            for node_id in shuffled_nodes:
                current_community = node_to_community[node_id]

                # Calculate modularity gain for moving to each neighbor's community
                best_community = current_community
                best_gain = 0.0

                # Get unique neighbor communities
                neighbor_communities: set[int] = set()
                for neighbor_id in adjacency[node_id]:
                    neighbor_communities.add(node_to_community[neighbor_id])

                for target_community in neighbor_communities:
                    if target_community == current_community:
                        continue

                    gain = self._modularity_gain(
                        node_id,
                        target_community,
                        node_to_community,
                        adjacency,
                        degrees,
                        total_weight,
                    )

                    if gain > best_gain:
                        best_gain = gain
                        best_community = target_community

                # Move node if gain is positive
                if best_community != current_community:
                    community_nodes[current_community].discard(node_id)
                    community_nodes[best_community].add(node_id)
                    node_to_community[node_id] = best_community
                    improved = True

        # Build result communities
        communities = []
        for comm_id, members in community_nodes.items():
            if len(members) >= min_community_size:
                # Find central node (highest degree within community)
                central_id = max(
                    members,
                    key=lambda nid: sum(
                        adjacency[nid].get(m, 0) for m in members if m != nid
                    ),
                )

                # Calculate internal cohesion
                internal_edges = sum(
                    adjacency[n1].get(n2, 0)
                    for n1 in members
                    for n2 in members
                    if n1 < n2
                )
                max_edges = len(members) * (len(members) - 1) / 2
                cohesion = internal_edges / max_edges if max_edges > 0 else 0.0

                communities.append(Community(
                    id=f"community_{comm_id}",
                    member_ids=members,
                    central_node_id=central_id,
                    cohesion=cohesion,
                ))

        # Sort by size (largest first)
        communities.sort(key=lambda c: len(c.member_ids), reverse=True)

        return communities

    def _modularity_gain(
        self,
        node_id: str,
        target_community: int,
        node_to_community: dict[str, int],
        adjacency: dict[str, dict[str, float]],
        degrees: dict[str, float],
        total_weight: float,
    ) -> float:
        """Calculate modularity gain from moving node to target community."""
        # Sum of weights to nodes in target community
        sum_in = 0.0
        # Sum of degrees in target community
        sum_tot = 0.0

        for other_id, comm_id in node_to_community.items():
            if comm_id == target_community:
                sum_in += adjacency[node_id].get(other_id, 0)
                sum_tot += degrees[other_id]

        k_i = degrees[node_id]

        # Modularity gain formula
        gain = (
            sum_in / total_weight -
            self.resolution * (sum_tot * k_i) / (2 * total_weight ** 2)
        )

        return gain


class HubDetector:
    """
    Hub Detection - Finds central/important nodes.

    Identifies "hub" nodes that connect many other nodes,
    making them important for knowledge retrieval.

    Metrics used:
    - Degree centrality: Number of connections
    - Betweenness: How often node appears on shortest paths
    - PageRank-like: Importance from connected nodes

    Hub nodes should be protected from forgetting (decay).
    """

    def __init__(self, get_neighbors_fn: Any = None):
        self.get_neighbors = get_neighbors_fn

    def find_hubs(
        self,
        node_ids: list[str],
        top_k: int = 10,
        min_connections: int = 3,
    ) -> list[tuple[str, float]]:
        """
        Find hub nodes by degree centrality.

        Args:
            node_ids: All node IDs to consider
            top_k: Number of top hubs to return
            min_connections: Minimum connections to be a hub

        Returns:
            List of (node_id, hub_score) sorted by score
        """
        if not self.get_neighbors:
            return []

        # Calculate degree for each node
        hub_scores: list[tuple[str, float]] = []

        for node_id in node_ids:
            neighbors = self.get_neighbors(node_id)
            degree = len(neighbors)

            if degree >= min_connections:
                # Weighted by average relation strength
                if neighbors:
                    avg_strength = sum(r.strength for _, r in neighbors) / len(neighbors)
                else:
                    avg_strength = 0.5

                # Hub score = degree * avg_strength
                score = degree * avg_strength
                hub_scores.append((node_id, score))

        # Sort by score
        hub_scores.sort(key=lambda x: x[1], reverse=True)

        return hub_scores[:top_k]

    def calculate_pagerank(
        self,
        node_ids: list[str],
        damping: float = 0.85,
        iterations: int = 20,
    ) -> dict[str, float]:
        """
        Calculate PageRank-like importance scores.

        Args:
            node_ids: All node IDs
            damping: Damping factor (0.85 is standard)
            iterations: Number of iterations

        Returns:
            Dict of {node_id: pagerank_score}
        """
        if not self.get_neighbors or not node_ids:
            return {}

        n = len(node_ids)
        scores = {nid: 1.0 / n for nid in node_ids}

        # Build outgoing edges
        outgoing: dict[str, list[str]] = defaultdict(list)
        for node_id in node_ids:
            neighbors = self.get_neighbors(node_id)
            for neighbor_id, _ in neighbors:
                if neighbor_id in node_ids:
                    outgoing[node_id].append(neighbor_id)

        # Iterate
        for _ in range(iterations):
            new_scores = {}

            for node_id in node_ids:
                # Sum of scores from incoming edges
                incoming_sum = 0.0
                for other_id in node_ids:
                    if node_id in outgoing[other_id]:
                        out_degree = len(outgoing[other_id])
                        if out_degree > 0:
                            incoming_sum += scores[other_id] / out_degree

                # PageRank formula
                new_scores[node_id] = (1 - damping) / n + damping * incoming_sum

            scores = new_scores

        return scores

    def is_hub(self, node_id: str, threshold: int = 5) -> bool:
        """Check if a node is a hub (has many connections)."""
        if not self.get_neighbors:
            return False

        neighbors = self.get_neighbors(node_id)
        return len(neighbors) >= threshold


class GraphAnalyzer:
    """
    High-level graph analysis combining all algorithms.

    Provides unified interface for:
    - BFS exploration
    - Community detection
    - Hub identification
    - Graph statistics
    """

    def __init__(self, memory_graph: Any = None):
        """
        Args:
            memory_graph: MemoryGraph instance to analyze
        """
        self.graph = memory_graph

        # Create get_neighbors function
        if memory_graph:
            self._get_neighbors = self._create_neighbors_fn(memory_graph)
        else:
            self._get_neighbors = None

        self.bfs = BFSGraphTraversal(get_neighbors_fn=self._get_neighbors)
        self.communities = LouvainCommunityDetection(get_neighbors_fn=self._get_neighbors)
        self.hubs = HubDetector(get_neighbors_fn=self._get_neighbors)

    def _create_neighbors_fn(self, graph: Any):
        """Create a neighbors function from MemoryGraph."""
        def get_neighbors(node_id: str) -> list[tuple[str, Any]]:
            results = []

            # Get relations where this node is the source
            for rel_id in graph._relations_by_from.get(node_id, []):
                rel = graph._relations.get(rel_id)
                if rel:
                    results.append((rel.to_id, rel))

            # Get relations where this node is the target
            for rel_id in graph._relations_by_to.get(node_id, []):
                rel = graph._relations.get(rel_id)
                if rel:
                    results.append((rel.from_id, rel))

            return results

        return get_neighbors

    def bind_graph(self, memory_graph: Any) -> None:
        """Bind to a MemoryGraph instance."""
        self.graph = memory_graph
        self._get_neighbors = self._create_neighbors_fn(memory_graph)
        self.bfs.get_neighbors = self._get_neighbors
        self.communities.get_neighbors = self._get_neighbors
        self.hubs.get_neighbors = self._get_neighbors

    def expand_recall(
        self,
        seed_ids: set[str],
        max_expansion: int = 10,
        depth: int = 1,
    ) -> set[str]:
        """
        Expand recall results with related nodes.

        Args:
            seed_ids: Initial recall results
            max_expansion: Maximum new IDs to add
            depth: BFS depth

        Returns:
            Expanded ID set
        """
        return self.bfs.expand_context(seed_ids, depth, max_expansion)

    def find_related_memories(
        self,
        episode_id: str,
        max_results: int = 10,
        relation_types: set[str] | None = None,
    ) -> list[str]:
        """
        Find memories related to a given episode.

        Args:
            episode_id: Starting episode ID
            max_results: Maximum related memories
            relation_types: Filter by relation types

        Returns:
            List of related episode/entity IDs
        """
        result = self.bfs.traverse(
            start_ids={episode_id},
            max_depth=2,
            max_nodes=max_results + 1,
            relation_types=relation_types,
        )

        # Return all except the starting node
        return [nid for nid in result.visited_ids if nid != episode_id][:max_results]

    def detect_knowledge_clusters(
        self,
        min_size: int = 3,
    ) -> list[Community]:
        """
        Detect clusters of related knowledge.

        Returns:
            List of communities sorted by size
        """
        if not self.graph:
            return []

        # Collect all node IDs
        all_ids = list(self.graph._entities.keys()) + list(self.graph._episodes.keys())

        return self.communities.detect_communities(
            node_ids=all_ids,
            min_community_size=min_size,
        )

    def identify_hub_memories(
        self,
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """
        Identify hub memories that connect many concepts.

        Returns:
            List of (node_id, hub_score) tuples
        """
        if not self.graph:
            return []

        all_ids = list(self.graph._entities.keys()) + list(self.graph._episodes.keys())
        return self.hubs.find_hubs(all_ids, top_k=top_k)

    def get_graph_stats(self) -> dict[str, Any]:
        """Get statistics about the memory graph."""
        if not self.graph:
            return {}

        entities = len(self.graph._entities)
        episodes = len(self.graph._episodes)
        relations = len(self.graph._relations)

        # Average degree
        total_degree = 0
        node_count = entities + episodes
        if node_count > 0:
            for node_id in list(self.graph._entities.keys()) + list(self.graph._episodes.keys()):
                total_degree += len(self._get_neighbors(node_id)) if self._get_neighbors else 0
            avg_degree = total_degree / node_count
        else:
            avg_degree = 0

        return {
            "entities": entities,
            "episodes": episodes,
            "relations": relations,
            "total_nodes": node_count,
            "average_degree": round(avg_degree, 2),
            "density": relations / (node_count * (node_count - 1) / 2) if node_count > 1 else 0,
        }
