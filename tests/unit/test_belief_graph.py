"""Tests for belief_graph: BeliefGraph, Belief, Fact, and graph operations."""

import pytest
from datetime import datetime

from backend.core.belief_graph import (
    BeliefGraph,
    Belief,
    Fact,
    NodeType,
    EdgeType,
)


class TestBeliefGraph:
    def test_empty_graph(self):
        g = BeliefGraph()
        assert g.get_all_beliefs() == []
        stats = g.get_stats()
        assert stats["belief_count"] == 0
        assert stats["fact_count"] == 0

    def test_add_belief(self):
        g = BeliefGraph()
        b = g.add_belief("AAPL has strong margins", confidence=0.8)
        assert b.id == "belief_1"
        assert b.content == "AAPL has strong margins"
        assert b.confidence == 0.8
        assert isinstance(b.timestamp, datetime)

    def test_add_multiple_beliefs(self):
        g = BeliefGraph()
        g.add_belief("Belief 1")
        g.add_belief("Belief 2")
        g.add_belief("Belief 3")
        assert len(g.get_all_beliefs()) == 3
        assert g.get_stats()["belief_count"] == 3

    def test_add_fact(self):
        g = BeliefGraph()
        f = g.add_fact("AAPL revenue is $400B", "SEC filing")
        assert f.id == "fact_1"
        assert f.content == "AAPL revenue is $400B"
        assert f.source == "SEC filing"

    def test_link_contradiction(self):
        g = BeliefGraph()
        b1 = g.add_belief("Stock is undervalued")
        b2 = g.add_belief("Stock is overvalued")
        g.link_contradiction(b1.id, b2.id)
        assert g.get_stats()["total_edges"] == 1

    def test_link_support(self):
        g = BeliefGraph()
        b = g.add_belief("Revenue is growing")
        f = g.add_fact("Revenue grew 15% YoY", "earnings report")
        g.link_support(b.id, f.id)
        assert g.get_stats()["total_edges"] == 1

    def test_find_contradictions_positive_vs_negative(self):
        g = BeliefGraph()
        g.add_belief("The company has strong growth")
        contradictions = g.find_contradictions("Growth is declining rapidly")
        assert len(contradictions) == 1

    def test_find_contradictions_no_match(self):
        g = BeliefGraph()
        g.add_belief("Revenue is $100B")
        contradictions = g.find_contradictions("The CEO is experienced")
        assert len(contradictions) == 0

    def test_update_belief_confidence(self):
        g = BeliefGraph()
        b = g.add_belief("Test", confidence=0.5)
        g.update_belief_confidence(b.id, 0.9)
        beliefs = g.get_all_beliefs()
        assert beliefs[0].confidence == 0.9

    def test_update_nonexistent_belief(self):
        g = BeliefGraph()
        g.update_belief_confidence("nonexistent", 0.9)  # should not raise

    def test_to_markdown_empty(self):
        g = BeliefGraph()
        assert "No user beliefs" in g.to_markdown()

    def test_to_markdown_with_beliefs(self):
        g = BeliefGraph()
        g.add_belief("Revenue is growing", confidence=0.8)
        md = g.to_markdown()
        assert "Revenue is growing" in md
        assert "80.0%" in md

    def test_to_dict_from_dict_round_trip(self):
        g = BeliefGraph()
        b1 = g.add_belief("Belief one", confidence=0.9)
        b2 = g.add_belief("Belief two", confidence=0.5)
        f = g.add_fact("Fact one", "source_url")
        g.link_contradiction(b1.id, b2.id)
        g.link_support(b1.id, f.id)

        d = g.to_dict()
        restored = BeliefGraph.from_dict(d)

        assert restored.get_stats()["belief_count"] == 2
        assert restored.get_stats()["fact_count"] == 1
        assert restored.get_stats()["total_edges"] == 2
        assert restored._belief_counter == 2
        assert restored._fact_counter == 1

    def test_from_dict_empty(self):
        g = BeliefGraph.from_dict({})
        assert g.get_stats()["total_nodes"] == 0

    def test_from_dict_none(self):
        g = BeliefGraph.from_dict(None)
        assert g.get_stats()["total_nodes"] == 0


class TestBelief:
    def test_to_dict(self):
        b = Belief(id="b1", content="Test", confidence=0.7, timestamp=datetime.now(), source="user")
        d = b.to_dict()
        assert d["id"] == "b1"
        assert d["confidence"] == 0.7
        assert "timestamp" in d


class TestFact:
    def test_to_dict(self):
        f = Fact(id="f1", content="Revenue is $100B", source="SEC", verified_at=datetime.now())
        d = f.to_dict()
        assert d["id"] == "f1"
        assert d["source"] == "SEC"
        assert "verified_at" in d
