"""MEDIUM — Ontological reasoning tests.

Validates the full pipeline's ability to handle:
  • Single-entity lookups with spaCy-typed resolution
  • 1-hop relationship traversals
  • Basic temporal gating
  • Simple aggregation queries
  • Exploration with neighbourhood expansion
  • Label mapping correctness (spaCy → Neo4j)
  • Confidence scoring under clean-signal conditions

No Neo4j connection required — all tests mock the driver.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.models.reasoning import DecomposedQuery, ReasoningType
from app.services.confidence import (
    ConfidenceScorer,
    ConfidenceSignals,
    MatchQuality,
)
from app.services.label_mapping import (
    DEFAULT_NEO4J_LABEL,
    SPACY_TO_NEO4J,
    TypedEntity,
    neo4j_label,
    spacy_label_confidence,
)
from app.services.query_decomposer import QueryDecomposer
from app.services.reasoning_chain_builder import ReasoningChainBuilder
from app.services.template_router import TemplateRouter


# ═══════════════════════════════════════════════════════════════════════
# § 1  LABEL MAPPING — spaCy → Neo4j
# ═══════════════════════════════════════════════════════════════════════


class TestLabelMapping:
    """Every spaCy label should deterministically map to a Neo4j label."""

    @pytest.mark.parametrize(
        "spacy_label, expected_neo4j",
        [
            ("PERSON", "Person"),
            ("ORG", "Organization"),
            ("GPE", "Location"),
            ("LOC", "Location"),
            ("FAC", "Location"),
            ("EVENT", "Event"),
            ("DATE", "Event"),
            ("TIME", "Event"),
            ("WORK_OF_ART", "Concept"),
            ("PRODUCT", "Project"),
            ("NORP", "Concept"),
            ("LANGUAGE", "Concept"),
            ("LAW", "Concept"),
        ],
    )
    def test_known_labels(self, spacy_label: str, expected_neo4j: str):
        assert neo4j_label(spacy_label) == expected_neo4j

    def test_unknown_label_defaults_to_topic(self):
        assert neo4j_label("CARDINAL") == DEFAULT_NEO4J_LABEL
        assert neo4j_label("QUANTITY") == DEFAULT_NEO4J_LABEL
        assert neo4j_label("PERCENT") == DEFAULT_NEO4J_LABEL

    def test_confidence_range(self):
        for label in SPACY_TO_NEO4J:
            conf = spacy_label_confidence(label)
            assert 0.0 < conf <= 1.0, f"Bad confidence for {label}: {conf}"

    def test_unknown_label_gets_default_confidence(self):
        assert spacy_label_confidence("CARDINAL") == 0.50

    def test_typed_entity_from_spacy(self):
        te = TypedEntity.from_spacy("Alice Johnson", "PERSON")
        assert te.text == "Alice Johnson"
        assert te.spacy_label == "PERSON"
        assert te.neo4j_label == "Person"
        assert te.confidence == spacy_label_confidence("PERSON")

    def test_typed_entity_payload_dict(self):
        te = TypedEntity.from_spacy("Google", "ORG")
        d = te.to_entity_payload_dict()
        assert d == {
            "text": "Google",
            "type": "Organization",
            "confidence": spacy_label_confidence("ORG"),
        }


# ═══════════════════════════════════════════════════════════════════════
# § 2  QUERY DECOMPOSER — Entity extraction + intent
# ═══════════════════════════════════════════════════════════════════════


class TestDecomposerEntityTypes:
    """When spaCy is available, entity_types should be populated."""

    decomposer = QueryDecomposer()

    def _mock_spacy(self, labeled: list[dict]):
        """Patch spaCy to return controlled labeled entities."""
        mock_extractor = MagicMock()
        mock_extractor.extract_entities_with_labels.return_value = labeled
        mock_extractor.nlp = MagicMock()  # pass the load check
        return mock_extractor

    def test_spacy_entities_populate_types(self):
        labeled = [
            {"text": "Alice", "label": "PERSON", "start": 0, "end": 5},
            {"text": "Google", "label": "ORG", "start": 18, "end": 24},
        ]
        with patch(
            "app.services.query_decomposer._get_spacy_extractor",
            return_value=self._mock_spacy(labeled),
        ):
            result = self.decomposer.decompose("Alice works at Google")
        assert result.entities == ["Alice", "Google"]
        assert result.entity_types == ["Person", "Organization"]

    def test_spacy_failure_falls_back_to_regex(self):
        with patch(
            "app.services.query_decomposer._get_spacy_extractor",
            return_value=None,
        ):
            result = self.decomposer.decompose('Tell me about "Neural Networks"')
        assert "Neural Networks" in result.entities
        # No spaCy → entity_types is empty
        assert result.entity_types == []

    def test_entity_types_parallel_to_entities(self):
        labeled = [
            {"text": "Paris", "label": "GPE", "start": 0, "end": 5},
            {"text": "2024", "label": "DATE", "start": 9, "end": 13},
        ]
        with patch(
            "app.services.query_decomposer._get_spacy_extractor",
            return_value=self._mock_spacy(labeled),
        ):
            result = self.decomposer.decompose("Paris in 2024")
        assert len(result.entities) == len(result.entity_types)
        assert result.entity_types[0] == "Location"
        assert result.entity_types[1] == "Event"

    def test_common_non_entities_filtered(self):
        labeled = [
            {"text": "The", "label": "MISC", "start": 0, "end": 3},
            {"text": "Microsoft", "label": "ORG", "start": 4, "end": 13},
        ]
        with patch(
            "app.services.query_decomposer._get_spacy_extractor",
            return_value=self._mock_spacy(labeled),
        ):
            result = self.decomposer.decompose("The Microsoft project")
        assert "Microsoft" in result.entities
        assert "The" not in result.entities

    def test_dedup_preserves_order(self):
        labeled = [
            {"text": "Alice", "label": "PERSON", "start": 0, "end": 5},
            {"text": "Alice", "label": "PERSON", "start": 20, "end": 25},
            {"text": "Bob", "label": "PERSON", "start": 10, "end": 13},
        ]
        with patch(
            "app.services.query_decomposer._get_spacy_extractor",
            return_value=self._mock_spacy(labeled),
        ):
            result = self.decomposer.decompose("Alice and Bob, Alice again")
        assert result.entities == ["Alice", "Bob"]
        assert result.entity_types == ["Person", "Person"]


# ═══════════════════════════════════════════════════════════════════════
# § 3  TEMPLATE ROUTER — Entity-type-aware slot resolution
# ═══════════════════════════════════════════════════════════════════════


class TestRouterEntityTypes:
    """entity_types should drive node_label slot resolution."""

    router = TemplateRouter()

    def test_node_label_from_entity_types(self):
        query = DecomposedQuery(
            reasoning_type=ReasoningType.AGGREGATION,
            entities=["Alice"],
            relationships=[],
            time_range=None,
            aggregation_fn="count",
            hop_limit=1,
            confidence=0.8,
            entity_types=["Person"],
        )
        results = self.router.route(query)
        # Should route to top_entities_by_mentions with node_label=Person
        names = [name for name, _ in results]
        assert "top_entities_by_mentions" in names
        # Verify the rendered Cypher uses Person label
        for name, cypher in results:
            if name == "top_entities_by_mentions":
                assert "Person" in cypher

    def test_node_label_fallback_when_no_types(self):
        query = DecomposedQuery(
            reasoning_type=ReasoningType.AGGREGATION,
            entities=["people"],
            relationships=[],
            time_range=None,
            aggregation_fn="count",
            hop_limit=1,
            confidence=0.7,
            entity_types=[],
        )
        results = self.router.route(query)
        for name, cypher in results:
            if name == "top_entities_by_mentions":
                assert "Person" in cypher

    def test_exploration_routes_with_typed_entity(self):
        query = DecomposedQuery(
            reasoning_type=ReasoningType.EXPLORATION,
            entities=["quantum computing"],
            relationships=[],
            time_range=None,
            aggregation_fn=None,
            hop_limit=2,
            confidence=0.75,
            entity_types=["Topic"],
        )
        results = self.router.route(query)
        assert len(results) > 0
        names = [n for n, _ in results]
        assert "topic_neighborhood" in names or "full_neighborhood" in names


# ═══════════════════════════════════════════════════════════════════════
# § 4  ENTITY RESOLVER — Type-aware resolution
# ═══════════════════════════════════════════════════════════════════════


class TestResolverTypeAware:
    """expected_label should boost same-type matches."""

    def _make_resolver(self, cache: dict):
        from app.services.entity_resolver import EntityResolver

        driver = MagicMock()
        resolver = EntityResolver(driver)
        resolver._entity_cache = cache
        return resolver

    def test_exact_match_ignores_label(self):
        resolver = self._make_resolver({
            "alice johnson": {"id": "1", "name": "Alice Johnson", "label": "Person"},
        })
        entity, quality = resolver.resolve_with_quality(
            "Alice Johnson", expected_label="Organization"
        )
        assert entity is not None
        assert entity["name"] == "Alice Johnson"
        assert quality == MatchQuality.EXACT

    def test_fuzzy_match_prefers_same_label(self):
        resolver = self._make_resolver({
            "alice johnsn": {"id": "1", "name": "Alice Johnsn", "label": "Person"},
            "alice johnsn org": {"id": "2", "name": "Alice Johnsn Org", "label": "Organization"},
        })
        entity, quality = resolver.resolve_with_quality(
            "Alice Johnson", expected_label="Person"
        )
        assert quality == MatchQuality.FUZZY
        assert entity["label"] == "Person"

    def test_substring_match_prefers_same_label(self):
        resolver = self._make_resolver({
            "introduction to deep learning and neural architectures": {
                "id": "1", "name": "Introduction to Deep Learning and Neural Architectures", "label": "Topic",
            },
            "the deep learning research organization of america": {
                "id": "2", "name": "The Deep Learning Research Organization of America", "label": "Organization",
            },
        })
        entity, quality = resolver.resolve_with_quality(
            "Deep Learning", expected_label="Topic"
        )
        assert quality == MatchQuality.SUBSTRING
        assert entity["label"] == "Topic"

    def test_no_label_provided_works_normally(self):
        resolver = self._make_resolver({
            "machine learning": {"id": "1", "name": "Machine Learning", "label": "Topic"},
        })
        entity, quality = resolver.resolve_with_quality("machine learning")
        assert quality == MatchQuality.EXACT
        assert entity["name"] == "Machine Learning"


# ═══════════════════════════════════════════════════════════════════════
# § 5  REASONING CHAIN BUILDER — Single-type chains
# ═══════════════════════════════════════════════════════════════════════


class TestReasoningChainSingleType:
    """Each reasoning type should produce a valid chain from records."""

    builder = ReasoningChainBuilder()

    def test_entity_chain_from_person_record(self):
        records = [
            {
                "person": {
                    "canonical_name": "Alice Johnson",
                    "email": "alice@example.com",
                    "role": "Engineer",
                    "organizations": ["Acme Corp"],
                    "expertise": ["ML", "NLP"],
                    "projects": ["Atlas"],
                }
            }
        ]
        chain = self.builder.build_chain(
            "Who is Alice Johnson?", ReasoningType.ENTITY_LOOKUP, records
        )
        assert len(chain.steps) >= 1
        assert chain.total_confidence > 0.0
        prompt = chain.to_llm_prompt_context()
        assert "Alice Johnson" in prompt

    def test_relationship_chain(self):
        records = [
            {
                "person": "Alice",
                "connections": [
                    {"name": "Bob", "relationship": "KNOWS", "strength": 0.9}
                ],
                "projects": ["Atlas"],
                "organizations": ["Acme"],
                "events": [],
            }
        ]
        chain = self.builder.build_chain(
            "Who does Alice know?", ReasoningType.RELATIONSHIP, records
        )
        assert len(chain.steps) >= 1
        prompt = chain.to_llm_prompt_context()
        assert "RELATIONSHIP" in prompt.upper() or "relationship" in prompt

    def test_temporal_chain(self):
        records = [
            {
                "document": {
                    "title": "Q4 Report",
                    "file_path": "/docs/q4.pdf",
                    "modified_at": "2025-12-01T10:00:00",
                    "topics": ["Finance"],
                }
            }
        ]
        chain = self.builder.build_chain(
            "What was modified last month?", ReasoningType.TEMPORAL, records
        )
        assert chain.total_confidence > 0.0

    def test_aggregation_chain(self):
        records = [
            {"topic": "ML", "document_count": 42, "sample_documents": ["Intro to ML"]},
        ]
        chain = self.builder.build_chain(
            "How many documents about ML?", ReasoningType.AGGREGATION, records
        )
        assert len(chain.steps) >= 1
        prompt = chain.to_llm_prompt_context()
        assert "42" in prompt or "ML" in prompt

    def test_exploration_chain_non_empty(self):
        records = [
            {"name": "Deep Learning", "weight": 0.9, "rel_type": "related_to"},
            {"name": "Neural Networks", "weight": 0.85, "rel_type": "subtopic"},
        ]
        chain = self.builder.build_chain(
            "Explore ML", ReasoningType.EXPLORATION, records
        )
        assert len(chain.steps) >= 1

    def test_empty_results_produce_chain(self):
        chain = self.builder.build_chain(
            "Find nothing", ReasoningType.ENTITY_LOOKUP, []
        )
        assert chain is not None
        assert chain.total_confidence == 0.0 or chain.total_confidence < 0.3


# ═══════════════════════════════════════════════════════════════════════
# § 6  CONFIDENCE SCORING — Clean signals
# ═══════════════════════════════════════════════════════════════════════


class TestConfidenceCleanSignals:
    """Under ideal conditions, confidence should be high."""

    scorer = ConfidenceScorer()

    def test_all_exact_entities(self):
        signals = ConfidenceSignals(
            entity_match_qualities=[MatchQuality.EXACT, MatchQuality.EXACT],
        )
        assert self.scorer.entity_resolution_confidence(signals) == 1.0

    def test_exact_plus_fuzzy(self):
        signals = ConfidenceSignals(
            entity_match_qualities=[MatchQuality.EXACT, MatchQuality.FUZZY],
        )
        conf = self.scorer.entity_resolution_confidence(signals)
        assert 0.7 < conf < 1.0

    def test_high_pattern_matches(self):
        signals = ConfidenceSignals(pattern_matches=3, patterns_checked=10)
        conf = self.scorer.classification_confidence(signals)
        assert conf > 0.7

    def test_full_results_high_confidence(self):
        signals = ConfidenceSignals(
            result_count=5,
            expected_result_count=5,
            evidence_completeness=1.0,
        )
        conf = self.scorer.result_confidence(signals)
        assert conf >= 0.9

    def test_step_confidence_complete_record(self):
        record = {"name": "Alice", "role": "Engineer", "org": "Acme"}
        conf = self.scorer.step_confidence(record, expected_keys=["name", "role", "org"])
        assert conf == 1.0

    def test_step_confidence_missing_keys(self):
        record = {"name": "Alice", "role": None, "org": ""}
        conf = self.scorer.step_confidence(record, expected_keys=["name", "role", "org"])
        assert abs(conf - 1 / 3) < 0.01


# ═══════════════════════════════════════════════════════════════════════
# § 7  END-TO-END DECOMPOSE → ROUTE — Medium scenarios
# ═══════════════════════════════════════════════════════════════════════


class TestEndToEndMedium:
    """Full decompose → route on representative queries."""

    decomposer = QueryDecomposer()
    router = TemplateRouter()

    def _decompose_and_route(self, query: str):
        with patch(
            "app.services.query_decomposer._get_spacy_extractor",
            return_value=None,
        ):
            decomposed = self.decomposer.decompose(query)
        return decomposed, self.router.route(decomposed)

    def test_person_lookup(self):
        d, routes = self._decompose_and_route('Who is "Alice Johnson"?')
        assert d.reasoning_type == ReasoningType.ENTITY_LOOKUP
        assert "Alice Johnson" in d.entities
        assert len(routes) > 0

    def test_topic_exploration(self):
        d, routes = self._decompose_and_route("Tell me about Machine Learning")
        assert d.reasoning_type == ReasoningType.EXPLORATION
        assert len(routes) > 0

    def test_temporal_query(self):
        d, routes = self._decompose_and_route("What changed yesterday?")
        assert d.reasoning_type == ReasoningType.TEMPORAL
        assert d.time_range is not None
        assert len(routes) > 0

    def test_count_aggregation(self):
        d, routes = self._decompose_and_route('How many documents about "Python"?')
        assert d.reasoning_type == ReasoningType.AGGREGATION
        assert len(routes) > 0

    def test_relationship_connected_to(self):
        d, routes = self._decompose_and_route(
            'What is "Deep Learning" related to?'
        )
        assert d.reasoning_type in (
            ReasoningType.RELATIONSHIP,
            ReasoningType.EXPLORATION,
        )
        assert len(routes) > 0
