"""Tests for the ReasoningChainBuilder — deterministic graph-to-chain logic."""

from __future__ import annotations

import pytest

from app.models.reasoning import ReasoningChain, ReasoningType
from app.services.reasoning_chain_builder import ReasoningChainBuilder


@pytest.fixture
def builder() -> ReasoningChainBuilder:
    return ReasoningChainBuilder()


# ─────────────────────────────────────────────────────────────────────
# Entity Lookup
# ─────────────────────────────────────────────────────────────────────


class TestEntityChain:
    def test_no_results(self, builder: ReasoningChainBuilder):
        chain = builder.build_chain("who is Alice?", ReasoningType.ENTITY_LOOKUP, [])
        assert chain.reasoning_type == "entity_lookup"
        assert len(chain.steps) == 1
        assert chain.steps[0].confidence == 0.0
        assert "not found" in chain.conclusion.lower()

    def test_found_entity(self, builder: ReasoningChainBuilder):
        results = [
            {
                "canonical_name": "Alice Johnson",
                "email": "alice@co.com",
                "role": "Engineer",
                "organizations": ["Acme"],
                "expertise": ["Python", "ML"],
                "projects": [],
            }
        ]
        chain = builder.build_chain("who is Alice?", ReasoningType.ENTITY_LOOKUP, results)
        assert chain.source_count == 1
        assert len(chain.steps) >= 1
        # Step confidence should be algorithmic (not hardcoded 0.9)
        assert chain.steps[0].confidence > 0.0
        assert chain.steps[0].confidence <= 1.0

    def test_connections_step_added(self, builder: ReasoningChainBuilder):
        results = [
            {
                "canonical_name": "Bob",
                "organizations": ["Acme Corp"],
                "expertise": ["Rust"],
                "projects": ["Backend"],
                "email": "",
            }
        ]
        chain = builder.build_chain("who is Bob?", ReasoningType.ENTITY_LOOKUP, results)
        # Should have step 1 (lookup) + step 2 (connections)
        assert len(chain.steps) == 2
        assert chain.steps[1].operation == "traverse"


# ─────────────────────────────────────────────────────────────────────
# Relationship
# ─────────────────────────────────────────────────────────────────────


class TestRelationshipChain:
    def test_no_results(self, builder: ReasoningChainBuilder):
        chain = builder.build_chain("connections?", ReasoningType.RELATIONSHIP, [])
        assert chain.conclusion == "No relationships found."

    def test_with_results(self, builder: ReasoningChainBuilder):
        results = [
            {"source": "Alice", "rel": "WORKS_ON", "target": "ML"},
            {"source": "Alice", "rel": "KNOWS", "target": "Bob"},
        ]
        chain = builder.build_chain("connections?", ReasoningType.RELATIONSHIP, results)
        assert len(chain.steps) == 2
        assert chain.source_count == 2
        assert "2" in chain.conclusion

    def test_caps_at_ten_steps(self, builder: ReasoningChainBuilder):
        results = [{"k": f"v{i}"} for i in range(20)]
        chain = builder.build_chain("conns?", ReasoningType.RELATIONSHIP, results)
        assert len(chain.steps) == 10


# ─────────────────────────────────────────────────────────────────────
# Multi-Hop
# ─────────────────────────────────────────────────────────────────────


class TestMultiHopChain:
    def test_no_path(self, builder: ReasoningChainBuilder):
        chain = builder.build_chain("path?", ReasoningType.MULTI_HOP, [])
        assert "No connection" in chain.conclusion
        assert chain.steps[0].confidence == 0.0

    def test_path_found(self, builder: ReasoningChainBuilder):
        results = [
            {
                "path_nodes": [
                    {"name": "Alice", "type": "Person"},
                    {"name": "ML", "type": "Topic"},
                    {"name": "Bob", "type": "Person"},
                ],
                "path_relationships": ["EXPERT_IN", "EXPERT_IN"],
                "path_length": 2,
            }
        ]
        chain = builder.build_chain("A→B?", ReasoningType.MULTI_HOP, results)
        assert len(chain.steps) == 1
        # Confidence should decay with hops (2 hops → ~0.90)
        assert 0.8 < chain.steps[0].confidence < 1.0
        assert "Alice" in chain.conclusion

    def test_longer_path_lower_confidence(self, builder: ReasoningChainBuilder):
        short_result = [
            {
                "path_nodes": [
                    {"name": "A", "type": "P"},
                    {"name": "B", "type": "P"},
                ],
                "path_relationships": ["R"],
                "path_length": 1,
            }
        ]
        long_result = [
            {
                "path_nodes": [{"name": f"N{i}", "type": "P"} for i in range(6)],
                "path_relationships": ["R"] * 5,
                "path_length": 5,
            }
        ]
        short_chain = builder.build_chain("?", ReasoningType.MULTI_HOP, short_result)
        long_chain = builder.build_chain("?", ReasoningType.MULTI_HOP, long_result)
        assert short_chain.steps[0].confidence > long_chain.steps[0].confidence


# ─────────────────────────────────────────────────────────────────────
# Aggregation
# ─────────────────────────────────────────────────────────────────────


class TestAggregationChain:
    def test_results(self, builder: ReasoningChainBuilder):
        results = [
            {"topic": "Python", "count": 42},
            {"topic": "Rust", "count": 17},
        ]
        chain = builder.build_chain("counts?", ReasoningType.AGGREGATION, results)
        assert chain.source_count == 2
        assert len(chain.steps) == 2
        assert "2" in chain.conclusion


# ─────────────────────────────────────────────────────────────────────
# Temporal
# ─────────────────────────────────────────────────────────────────────


class TestTemporalChain:
    def test_no_results(self, builder: ReasoningChainBuilder):
        chain = builder.build_chain("last week?", ReasoningType.TEMPORAL, [])
        assert "No activity" in chain.conclusion

    def test_with_docs(self, builder: ReasoningChainBuilder):
        results = [
            {"title": "Doc1", "topics": ["ML"], "modified_at": "2025-01-01"},
            {"title": "Doc2", "topics": ["ML"], "modified_at": "2025-01-02"},
            {"title": "Doc3", "topics": ["DB"], "modified_at": "2025-01-01"},
        ]
        chain = builder.build_chain("last week?", ReasoningType.TEMPORAL, results)
        assert chain.source_count == 3
        assert "ML" in chain.conclusion  # most active topic


# ─────────────────────────────────────────────────────────────────────
# Comparison
# ─────────────────────────────────────────────────────────────────────


class TestComparisonChain:
    def test_not_enough_data(self, builder: ReasoningChainBuilder):
        chain = builder.build_chain("compare?", ReasoningType.COMPARISON, [{"a": 1}])
        assert "Not enough" in chain.conclusion

    def test_comparison(self, builder: ReasoningChainBuilder):
        results = [
            {"topic": "Python", "doc_count": 10, "mention_count": 50},
            {"topic": "Rust", "doc_count": 5, "mention_count": 30},
        ]
        chain = builder.build_chain("compare?", ReasoningType.COMPARISON, results)
        assert "Python" in chain.conclusion  # Python leads


# ─────────────────────────────────────────────────────────────────────
# Causal
# ─────────────────────────────────────────────────────────────────────


class TestCausalChain:
    def test_causal(self, builder: ReasoningChainBuilder):
        results = [
            {"event": "deploy", "time": "T1"},
            {"event": "crash", "time": "T2"},
        ]
        chain = builder.build_chain("why crash?", ReasoningType.CAUSAL, results)
        assert len(chain.steps) == 2
        assert all(s.operation == "infer" for s in chain.steps)


# ─────────────────────────────────────────────────────────────────────
# Exploration
# ─────────────────────────────────────────────────────────────────────


class TestExplorationChain:
    def test_groups_by_rel_type(self, builder: ReasoningChainBuilder):
        results = [
            {"rel_type": "KNOWS", "direction": "out", "node_name": "Bob", "node_type": "Person"},
            {"rel_type": "KNOWS", "direction": "out", "node_name": "Eve", "node_type": "Person"},
            {"rel_type": "WORKS_ON", "direction": "out", "node_name": "ML", "node_type": "Topic"},
        ]
        chain = builder.build_chain("explore?", ReasoningType.EXPLORATION, results)
        assert len(chain.steps) == 2  # KNOWS, WORKS_ON groups
        assert "3 connections" in chain.conclusion
        assert "2 relationship" in chain.conclusion


# ─────────────────────────────────────────────────────────────────────
# Generic / Fallback
# ─────────────────────────────────────────────────────────────────────


class TestGenericChain:
    def test_fallback(self, builder: ReasoningChainBuilder):
        results = [{"a": 1}, {"b": 2}]
        chain = builder.build_chain("?", ReasoningType.EXPLORATION, results)
        assert chain.source_count == 2


# ─────────────────────────────────────────────────────────────────────
# Chain confidence is algorithmic
# ─────────────────────────────────────────────────────────────────────


class TestChainConfidenceAlgorithmic:
    def test_confidence_always_in_range(self, builder: ReasoningChainBuilder):
        for rt in ReasoningType:
            chain = builder.build_chain("q", rt, [{"a": 1}])
            assert 0.0 <= chain.total_confidence <= 1.0

    def test_empty_results_low_confidence(self, builder: ReasoningChainBuilder):
        chain = builder.build_chain("q", ReasoningType.ENTITY_LOOKUP, [])
        assert chain.total_confidence < 0.3

    def test_full_results_higher_confidence(self, builder: ReasoningChainBuilder):
        empty = builder.build_chain("q", ReasoningType.ENTITY_LOOKUP, [])
        full = builder.build_chain(
            "q",
            ReasoningType.ENTITY_LOOKUP,
            [{"name": "Alice", "role": "Eng", "email": "a@b.com"}],
        )
        assert full.total_confidence > empty.total_confidence

    def test_measure_completeness(self, builder: ReasoningChainBuilder):
        assert builder._measure_completeness([]) == 0.0
        assert builder._measure_completeness(
            [{"a": "x", "b": "y"}]
        ) == 1.0
        assert builder._measure_completeness(
            [{"a": "x", "b": None, "c": ""}]
        ) == pytest.approx(1 / 3, abs=0.01)
