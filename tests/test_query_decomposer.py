"""Tests for the rule-based QueryDecomposer."""

from __future__ import annotations

import pytest

from app.models.reasoning import ReasoningType
from app.services.query_decomposer import QueryDecomposer


@pytest.fixture
def decomposer() -> QueryDecomposer:
    return QueryDecomposer()


# ─────────────────────────────────────────────────────────────────────
# Intent Classification
# ─────────────────────────────────────────────────────────────────────


class TestIntentClassification:
    def test_causal_why_did(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("why did the project fail?")
        assert result.reasoning_type == ReasoningType.CAUSAL

    def test_causal_what_caused(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("what caused the outage?")
        assert result.reasoning_type == ReasoningType.CAUSAL

    def test_causal_what_triggered(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("what triggered the deployment?")
        assert result.reasoning_type == ReasoningType.CAUSAL

    def test_multi_hop_connect(self, decomposer: QueryDecomposer):
        result = decomposer.decompose(
            "how does Alice connect to the ML project?"
        )
        assert result.reasoning_type == ReasoningType.MULTI_HOP

    def test_multi_hop_relationship_between(self, decomposer: QueryDecomposer):
        result = decomposer.decompose(
            "what's the relationship between Alice and Bob?"
        )
        assert result.reasoning_type == ReasoningType.MULTI_HOP

    def test_multi_hop_path(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("path from Alice to Bob")
        assert result.reasoning_type == ReasoningType.MULTI_HOP

    def test_temporal_yesterday(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("what happened yesterday?")
        assert result.reasoning_type == ReasoningType.TEMPORAL
        assert result.time_range is not None

    def test_temporal_last_week(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("what did I work on last week?")
        assert result.reasoning_type == ReasoningType.TEMPORAL
        assert result.time_range is not None

    def test_temporal_relative_ago(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("what changed 3 days ago?")
        assert result.reasoning_type == ReasoningType.TEMPORAL

    def test_aggregation_how_many(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("how many documents are there?")
        assert result.reasoning_type == ReasoningType.AGGREGATION
        assert result.aggregation_fn == "count"

    def test_aggregation_most(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("most referenced topic?")
        assert result.reasoning_type == ReasoningType.AGGREGATION
        assert result.aggregation_fn == "max"

    def test_comparison_with_two_entities(self, decomposer: QueryDecomposer):
        result = decomposer.decompose(
            'how many documents mention "Python" vs "Rust"?'
        )
        assert result.reasoning_type == ReasoningType.COMPARISON

    def test_exploration_tell_me_about(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("tell me about machine learning")
        assert result.reasoning_type == ReasoningType.EXPLORATION

    def test_exploration_show_everything(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("show me everything about Neo4j")
        assert result.reasoning_type == ReasoningType.EXPLORATION

    def test_relationship_related_to(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("what is related to Kubernetes?")
        assert result.reasoning_type == ReasoningType.RELATIONSHIP

    def test_relationship_works_on(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("who works on the backend?")
        assert result.reasoning_type == ReasoningType.RELATIONSHIP

    def test_entity_lookup_proper_noun(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("who is Alice Johnson?")
        assert result.reasoning_type == ReasoningType.ENTITY_LOOKUP
        assert "Alice Johnson" in result.entities

    def test_fallback_exploration(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("um hello?")
        assert result.reasoning_type == ReasoningType.EXPLORATION


# ─────────────────────────────────────────────────────────────────────
# Entity Extraction
# ─────────────────────────────────────────────────────────────────────


class TestEntityExtraction:
    def test_quoted_strings(self, decomposer: QueryDecomposer):
        result = decomposer.decompose('find documents about "machine learning"')
        assert "machine learning" in result.entities

    def test_single_quoted_strings(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("find documents about 'deep learning'")
        assert "deep learning" in result.entities

    def test_capitalised_proper_noun(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("what does Bob Smith work on?")
        assert "Bob Smith" in result.entities

    def test_ignores_common_words(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("What is the best practice?")
        # "What" is sentence-initial (skipped), "the" is common
        assert "What" not in result.entities
        assert "The" not in result.entities

    def test_multiple_entities(self, decomposer: QueryDecomposer):
        result = decomposer.decompose(
            'how does "Alice" connect to "Bob"?'
        )
        assert "Alice" in result.entities
        assert "Bob" in result.entities

    def test_no_entities_in_lowercase_query(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("what is going on?")
        assert result.entities == []


# ─────────────────────────────────────────────────────────────────────
# Temporal Extraction
# ─────────────────────────────────────────────────────────────────────


class TestTemporalExtraction:
    def test_yesterday(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("what happened yesterday?")
        assert result.time_range is not None
        start, end = result.time_range
        assert start.hour == 0 and start.minute == 0
        assert end.hour == 23 and end.minute == 59

    def test_today(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("what did I do today?")
        assert result.time_range is not None

    def test_last_week(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("last week activity")
        assert result.time_range is not None
        start, end = result.time_range
        assert (end - start).days <= 8

    def test_relative_ago(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("changes from 5 days ago")
        assert result.time_range is not None

    def test_no_temporal(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("who is Alice?")
        assert result.time_range is None


# ─────────────────────────────────────────────────────────────────────
# Aggregation Detection
# ─────────────────────────────────────────────────────────────────────


class TestAggregationDetection:
    def test_count(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("how many topics exist?")
        assert result.aggregation_fn == "count"

    def test_total(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("total documents in the system")
        assert result.aggregation_fn == "sum"

    def test_top(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("top contributors")
        assert result.aggregation_fn == "max"

    def test_no_aggregation(self, decomposer: QueryDecomposer):
        result = decomposer.decompose("who is Alice?")
        assert result.aggregation_fn is None


# ─────────────────────────────────────────────────────────────────────
# Confidence is algorithmic
# ─────────────────────────────────────────────────────────────────────


class TestDecomposerConfidence:
    def test_confidence_in_range(self, decomposer: QueryDecomposer):
        queries = [
            "why did the build fail?",
            "how does X connect to Y?",
            "what happened yesterday?",
            "how many documents?",
            "tell me about python",
            "hello",
        ]
        for q in queries:
            result = decomposer.decompose(q)
            assert 0.0 <= result.confidence <= 1.0, (
                f"Confidence {result.confidence} out of range for: {q}"
            )

    def test_strong_match_higher_than_fallback(self, decomposer: QueryDecomposer):
        strong = decomposer.decompose("why did the deployment fail?")
        fallback = decomposer.decompose("hmm ok whatever")
        assert strong.confidence > fallback.confidence

    def test_hop_limits(self, decomposer: QueryDecomposer):
        entity = decomposer.decompose("who is Alice?")
        multi = decomposer.decompose("how does A connect to B?")
        assert entity.hop_limit < multi.hop_limit
