"""
Belief graph system for tracking user beliefs and facts.

Uses NetworkX for in-memory graph storage and manipulation.
Tracks user beliefs, facts, and relationships between them.
"""

import networkx as nx
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from enum import Enum

class NodeType(Enum):
    """Types of nodes in the belief graph."""
    ENTITY = "entity"  # Stock, metric, company
    BELIEF = "belief"  # User belief
    FACT = "fact"      # Verified fact

class EdgeType(Enum):
    """Types of edges in the belief graph."""
    HAS_METRIC = "has_metric"
    BELIEVES = "believes"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CITED_BY = "cited_by"

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
