"""
Belief graph system for tracking user beliefs and facts.

Uses NetworkX for in-memory graph storage and manipulation.
Tracks user beliefs, facts, and relationships between them.
"""

import networkx as nx
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict
from enum import Enum

class NodeType(Enum):
    """
    Types of nodes in the belief graph.

    The graph tracks entities (stocks, companies), user beliefs about them,
    and verified facts from external sources.
    """
    ENTITY = "entity"  # Stock ticker, metric name, company name
    BELIEF = "belief"  # User-stated or LLM-inferred belief about an entity
    FACT = "fact"      # Externally verified fact (from API, news, filings)


class EdgeType(Enum):
    """
    Types of edges (relationships) in the belief graph.

    Edges connect nodes to represent relationships like ownership,
    support, contradiction, and citation references.
    """
    HAS_METRIC = "has_metric"    # Entity -> Metric (e.g., AAPL -> P/E ratio)
    BELIEVES = "believes"        # User -> Belief relationship
    SUPPORTS = "supports"        # Fact -> Belief (evidence supporting a belief)
    CONTRADICTS = "contradicts"  # Belief -> Belief (conflicting statements)
    CITED_BY = "cited_by"        # Source -> Section (citation reference)

@dataclass
class Belief:
    """Represents a user belief."""
    id: str
    content: str
    confidence: float  # 0.0 to 1.0
    timestamp: datetime
    source: str  # "user_statement", "llm_inference", etc.

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'content': self.content,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'source': self.source
        }

@dataclass
class Fact:
    """Represents a verified fact."""
    id: str
    content: str
    source: str  # URL, API, etc.
    verified_at: datetime

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'content': self.content,
            'source': self.source,
            'verified_at': self.verified_at.isoformat()
        }


class BeliefGraph:
    """
    Knowledge graph for tracking user beliefs and facts.

    Uses NetworkX for graph operations like finding contradictions,
    tracking relationships, and managing belief evolution.

    Complexity Analysis:
        - add_belief/add_fact: O(1) node insertion
        - link_contradiction/link_support: O(1) edge insertion
        - find_contradictions: O(n) where n = number of belief nodes
        - get_all_beliefs: O(n) full scan of all nodes
        - to_dict/from_dict: O(n + e) where e = number of edges

    The graph is stored in-memory using NetworkX DiGraph. For large-scale
    applications with thousands of beliefs, consider migrating to a
    proper graph database (Neo4j, etc.).
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self._belief_counter = 0
        self._fact_counter = 0

    def add_belief(
        self,
        content: str,
        confidence: float = 0.7,
        source: str = "user_statement"
    ) -> Belief:
        """
        Add a new belief to the graph.

        Args:
            content: The belief statement
            confidence: Confidence score (0.0 to 1.0)
            source: Where the belief came from

        Returns:
            Belief: The created belief object
        """
        self._belief_counter += 1
        belief_id = f"belief_{self._belief_counter}"

        belief = Belief(
            id=belief_id,
            content=content,
            confidence=confidence,
            timestamp=datetime.now(),
            source=source
        )

        self.graph.add_node(
            belief_id,
            type=NodeType.BELIEF.value,
            data=belief.to_dict()
        )

        return belief

    def add_fact(self, content: str, source: str) -> Fact:
        """
        Add a verified fact to the graph.

        Args:
            content: The fact statement
            source: Source of the fact (URL, API, etc.)

        Returns:
            Fact: The created fact object
        """
        self._fact_counter += 1
        fact_id = f"fact_{self._fact_counter}"

        fact = Fact(
            id=fact_id,
            content=content,
            source=source,
            verified_at=datetime.now()
        )

        self.graph.add_node(
            fact_id,
            type=NodeType.FACT.value,
            data=fact.to_dict()
        )

        return fact

    def link_contradiction(self, belief_id1: str, belief_id2: str):
        """Mark two beliefs as contradictory."""
        self.graph.add_edge(
            belief_id1,
            belief_id2,
            type=EdgeType.CONTRADICTS.value
        )

    def link_support(self, belief_id: str, fact_id: str):
        """Link a belief to a supporting fact."""
        self.graph.add_edge(
            fact_id,
            belief_id,
            type=EdgeType.SUPPORTS.value
        )

    def find_contradictions(self, new_belief_content: str) -> List[Belief]:
        """
        Find existing beliefs that might contradict a new statement.

        This is a simple keyword-based approach for MVP.
        In production, would use semantic similarity via embeddings.

        Args:
            new_belief_content: The new belief to check

        Returns:
            List[Belief]: Potentially contradictory beliefs
        """
        contradictions = []

        # Simple keyword contradiction detection
        # TODO: Replace with semantic similarity using embeddings
        negative_keywords = ["not", "weak", "poor", "declining", "overvalued"]
        positive_keywords = ["strong", "good", "growing", "undervalued"]

        new_is_negative = any(kw in new_belief_content.lower() for kw in negative_keywords)
        new_is_positive = any(kw in new_belief_content.lower() for kw in positive_keywords)

        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get('type') == NodeType.BELIEF.value:
                existing_content = node_data['data']['content'].lower()

                # Check for opposite sentiment
                existing_is_negative = any(kw in existing_content for kw in negative_keywords)
                existing_is_positive = any(kw in existing_content for kw in positive_keywords)

                if (new_is_positive and existing_is_negative) or \
                   (new_is_negative and existing_is_positive):
                    belief_dict = node_data['data']
                    contradictions.append(Belief(
                        id=belief_dict['id'],
                        content=belief_dict['content'],
                        confidence=belief_dict['confidence'],
                        timestamp=datetime.fromisoformat(belief_dict['timestamp']),
                        source=belief_dict['source']
                    ))

        return contradictions

    def get_all_beliefs(self) -> List[Belief]:
        """Get all beliefs in the graph."""
        beliefs = []
        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get('type') == NodeType.BELIEF.value:
                belief_dict = node_data['data']
                beliefs.append(Belief(
                    id=belief_dict['id'],
                    content=belief_dict['content'],
                    confidence=belief_dict['confidence'],
                    timestamp=datetime.fromisoformat(belief_dict['timestamp']),
                    source=belief_dict['source']
                ))
        return beliefs

    def update_belief_confidence(self, belief_id: str, new_confidence: float):
        """Update the confidence score of a belief."""
        if self.graph.has_node(belief_id):
            self.graph.nodes[belief_id]['data']['confidence'] = new_confidence

    def to_markdown(self) -> str:
        """Export beliefs and facts as markdown for LLM context."""
        beliefs = self.get_all_beliefs()

        if not beliefs:
            return "No user beliefs recorded yet."

        md = "## User Beliefs\n\n"
        for belief in sorted(beliefs, key=lambda b: b.timestamp, reverse=True):
            md += f"- **{belief.content}** (confidence: {belief.confidence:.1%})\n"

        return md

    def get_stats(self) -> Dict:
        """Get statistics about the belief graph."""
        belief_count = sum(1 for _, data in self.graph.nodes(data=True)
                          if data.get('type') == NodeType.BELIEF.value)
        fact_count = sum(1 for _, data in self.graph.nodes(data=True)
                        if data.get('type') == NodeType.FACT.value)

        return {
            'belief_count': belief_count,
            'fact_count': fact_count,
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges()
        }

    def to_dict(self) -> Dict:
        """
        Serialize the belief graph to a dictionary.

        Preserves full graph structure including nodes, edges, and counters.
        Used for session persistence.

        Returns:
            Dict: Serialized graph data
        """
        nodes = []
        for node_id, node_data in self.graph.nodes(data=True):
            nodes.append({
                'id': node_id,
                'type': node_data.get('type'),
                'data': node_data.get('data', {})
            })

        edges = []
        for source, target, edge_data in self.graph.edges(data=True):
            edges.append({
                'source': source,
                'target': target,
                'type': edge_data.get('type')
            })

        return {
            'nodes': nodes,
            'edges': edges,
            'belief_counter': self._belief_counter,
            'fact_counter': self._fact_counter
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'BeliefGraph':
        """
        Reconstruct a belief graph from serialized dictionary.

        Args:
            data: Dictionary from to_dict()

        Returns:
            BeliefGraph: Reconstructed graph with all nodes and edges
        """
        graph = cls()

        if not data:
            return graph

        # Restore counters
        graph._belief_counter = data.get('belief_counter', 0)
        graph._fact_counter = data.get('fact_counter', 0)

        # Restore nodes
        for node in data.get('nodes', []):
            graph.graph.add_node(
                node['id'],
                type=node.get('type'),
                data=node.get('data', {})
            )

        # Restore edges
        for edge in data.get('edges', []):
            graph.graph.add_edge(
                edge['source'],
                edge['target'],
                type=edge.get('type')
            )

        return graph
