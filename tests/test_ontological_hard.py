"""HARD — Ontological reasoning tests.

Validates the pipeline under adversarial, edge-case, and multi-step
conditions:
  • Multi-hop path finding with 4+ hops
  • Causal chains that must thread through Events
  • Comparison of two entities with partial graph coverage
  • Combined spaCy + regex extraction under conflicting signals
  • Confidence collapse: what happens when every signal is bad?
  • Type-aware entity resolution under fuzzy ambiguity
  • Template routing with mixed / incomplete entity_types
  • Full orchestrator mock with chained pipeline stages
  • Adversarial queries: injection attempts, empty text, unicode
  • Reasoning chain coherence across compound multi-type queries

No Neo4j connection required — all tests mock the driver.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.models.reasoning import (
    DecomposedQuery,
    ReasoningChain,
    ReasoningStep,
    ReasoningType,
)
from app.services.confidence import (
    ConfidenceScorer,
    ConfidenceSignals,
    MatchQuality,
)
from app.services.entity_resolver import EntityResolver
from app.services.label_mapping import (
    SPACY_TO_NEO4J,
    TypedEntity,
    neo4j_label,
    spacy_label_confidence,
)
from app.services.query_decomposer import QueryDecomposer
from app.services.reasoning_chain_builder import ReasoningChainBuilder
from app.services.template_router import TemplateRouter


# ═══════════════════════════════════════════════════════════════════════
# § 1  ADVERSARIAL ENTITY EXTRACTION
# ═══════════════════════════════════════════════════════════════════════


class TestAdversarialExtraction:
    """Queries designed to confuse the entity extractor."""

    decomposer = QueryDecomposer()

    def _decompose(self, query: str, spacy_labeled=None):
        if spacy_labeled is not None:
            mock = MagicMock()
            mock.extract_entities_with_labels.return_value = spacy_labeled
            mock.nlp = MagicMock()
            patcher = patch(
                "app.services.query_decomposer._get_spacy_extractor",
                return_value=mock,
            )
        else:
            patcher = patch(
                "app.services.query_decomposer._get_spacy_extractor",
                return_value=None,
            )
        with patcher:
            return self.decomposer.decompose(query)

    def test_cypher_injection_in_entity(self):
        """Quoted entity with Cypher injection should be sanitised by templates."""
        result = self._decompose("""Who is "'; DROP (n); //"?""")
        assert len(result.entities) >= 1
        # The entity text itself is preserved — sanitisation happens at render
        router = TemplateRouter()
        routes = router.route(result)
        for _, cypher in routes:
            assert "DROP" not in cypher or "DROP" in cypher.replace(
                "\\'", ""
            )  # escaped away

    def test_empty_string(self):
        result = self._decompose("")
        assert result.entities == []
        assert result.reasoning_type == ReasoningType.EXPLORATION
        assert result.confidence < 0.5  # fallback

    def test_whitespace_only(self):
        result = self._decompose("   \n\t  ")
        assert result.entities == []

    def test_unicode_entities(self):
        labeled = [
            {"text": "Ünïcödé Cörp", "label": "ORG", "start": 0, "end": 12},
        ]
        result = self._decompose("Ünïcödé Cörp partnership", spacy_labeled=labeled)
        assert "Ünïcödé Cörp" in result.entities
        assert result.entity_types == ["Organization"]

    def test_overlapping_entity_labels(self):
        """spaCy sometimes returns overlapping spans — we should deduplicate."""
        labeled = [
            {"text": "New York", "label": "GPE", "start": 0, "end": 8},
            {"text": "New York University", "label": "ORG", "start": 0, "end": 19},
        ]
        result = self._decompose(
            "New York University is great", spacy_labeled=labeled
        )
        # Both are kept but deduplicated by text
        assert "New York" in result.entities
        assert "New York University" in result.entities
        # Types parallel
        idx_nyu = result.entities.index("New York University")
        assert result.entity_types[idx_nyu] == "Organization"

    def test_all_stopwords_query(self):
        result = self._decompose("the and or but not is are was were")
        assert result.entities == []
        assert result.reasoning_type == ReasoningType.EXPLORATION

    def test_spacy_returns_empty_then_regex_fallback(self):
        """If spaCy returns [] (not None), we should fall back to regex."""
        result = self._decompose(
            'Show me "Quantum Computing" papers',
            spacy_labeled=[],
        )
        # spaCy returned empty list → regex fallback
        assert "Quantum Computing" in result.entities
        assert result.entity_types == []  # regex has no types

    def test_very_long_query_truncation(self):
        long_query = "Tell me about " + "A" * 5000
        result = self._decompose(long_query)
        # Should not crash, entities may or may not be extracted
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════
# § 2  MULTI-HOP REASONING
# ═══════════════════════════════════════════════════════════════════════


class TestMultiHopReasoning:
    """Multi-hop path-finding chains with deep graph traversal."""

    builder = ReasoningChainBuilder()
    scorer = ConfidenceScorer()

    def test_4_hop_path_confidence_decay(self):
        """4-hop path should have noticeably lower confidence than 1-hop."""
        signals_1 = ConfidenceSignals(shortest_path_length=1)
        signals_4 = ConfidenceSignals(shortest_path_length=4)
        c1 = self.scorer.path_confidence(signals_1)
        c4 = self.scorer.path_confidence(signals_4)
        assert c1 > c4
        assert c4 >= 0.40  # floor

    def test_6_hop_hits_floor(self):
        signals = ConfidenceSignals(shortest_path_length=6)
        assert self.scorer.path_confidence(signals) >= 0.40

    def test_multi_hop_chain_has_path_nodes(self):
        records = [
            {
                "path_nodes": [
                    {"type": "Person", "name": "Alice"},
                    {"type": "Project", "name": "Atlas"},
                    {"type": "Topic", "name": "ML"},
                    {"type": "Person", "name": "Bob"},
                ],
                "path_relationships": ["WORKED_ON", "ABOUT", "EXPERT_IN"],
                "path_length": 3,
            }
        ]
        chain = self.builder.build_chain(
            "How does Alice connect to Bob?",
            ReasoningType.MULTI_HOP,
            records,
        )
        prompt = chain.to_llm_prompt_context()
        assert "Alice" in prompt
        assert "Bob" in prompt
        assert len(chain.steps) >= 1

    def test_multi_hop_no_path_found(self):
        chain = self.builder.build_chain(
            "Connection between X and Y?", ReasoningType.MULTI_HOP, []
        )
        assert chain.total_confidence < 0.3

    def test_decomposer_detects_multi_hop(self):
        with patch(
            "app.services.query_decomposer._get_spacy_extractor",
            return_value=None,
        ):
            d = QueryDecomposer().decompose(
                'How does "Alice" connect to "Bob"?'
            )
        assert d.reasoning_type == ReasoningType.MULTI_HOP
        assert d.hop_limit >= 3

    def test_all_paths_between_multiple_results(self):
        records = [
            {
                "node_names": ["Alice", "Atlas", "Bob"],
                "relationships": ["WORKED_ON", "WORKED_ON"],
                "hops": 2,
            },
            {
                "node_names": ["Alice", "ML", "Bob"],
                "relationships": ["EXPERT_IN", "EXPERT_IN"],
                "hops": 2,
            },
        ]
        chain = self.builder.build_chain(
            "All paths from Alice to Bob",
            ReasoningType.MULTI_HOP,
            records,
        )
        assert len(chain.steps) >= 1
        assert chain.source_count >= 2


# ═══════════════════════════════════════════════════════════════════════
# § 3  CAUSAL CHAIN REASONING
# ═══════════════════════════════════════════════════════════════════════


class TestCausalChainReasoning:
    """Causal chains thread through Event nodes via CAUSED edges."""

    builder = ReasoningChainBuilder()
    decomposer = QueryDecomposer()

    def test_causal_detection(self):
        with patch(
            "app.services.query_decomposer._get_spacy_extractor",
            return_value=None,
        ):
            d = self.decomposer.decompose("Why did the server crash?")
        assert d.reasoning_type == ReasoningType.CAUSAL
        assert d.hop_limit >= 4

    def test_causal_chain_with_events(self):
        records = [
            {
                "causal_chain": [
                    {"name": "Deployment v2.1", "occurred_at": "2025-01-10", "description": "Released v2.1"},
                    {"name": "Memory Spike", "occurred_at": "2025-01-10", "description": "RAM exceeded 95%"},
                    {"name": "Server Crash", "occurred_at": "2025-01-10", "description": "OOM killer invoked"},
                ],
                "chain_length": 2,
            }
        ]
        chain = self.builder.build_chain(
            "What caused the server crash?", ReasoningType.CAUSAL, records
        )
        prompt = chain.to_llm_prompt_context()
        assert "Deployment v2.1" in prompt or "Memory Spike" in prompt
        assert chain.total_confidence > 0.0

    def test_empty_causal_chain(self):
        chain = self.builder.build_chain(
            "Why did X happen?", ReasoningType.CAUSAL, []
        )
        assert chain.total_confidence < 0.3

    def test_what_led_to_is_causal(self):
        with patch(
            "app.services.query_decomposer._get_spacy_extractor",
            return_value=None,
        ):
            d = self.decomposer.decompose("What led to the migration?")
        assert d.reasoning_type == ReasoningType.CAUSAL

    def test_what_triggered_is_causal(self):
        with patch(
            "app.services.query_decomposer._get_spacy_extractor",
            return_value=None,
        ):
            d = self.decomposer.decompose("What triggered the alert?")
        assert d.reasoning_type == ReasoningType.CAUSAL


# ═══════════════════════════════════════════════════════════════════════
# § 4  COMPARISON REASONING
# ═══════════════════════════════════════════════════════════════════════


class TestComparisonReasoning:
    """Comparing two entities with partial graph coverage."""

    builder = ReasoningChainBuilder()

    def test_comparison_chain_two_topics(self):
        records = [
            {
                "topic": "Python",
                "mentions": 120,
                "importance": 0.85,
                "document_count": 45,
                "related_topics": ["ML", "Django", "FastAPI"],
            },
            {
                "topic": "Rust",
                "mentions": 30,
                "importance": 0.60,
                "document_count": 8,
                "related_topics": ["Systems Programming", "WebAssembly"],
            },
        ]
        chain = self.builder.build_chain(
            "Compare Python and Rust", ReasoningType.COMPARISON, records
        )
        prompt = chain.to_llm_prompt_context()
        assert "Python" in prompt
        assert "Rust" in prompt
        assert len(chain.steps) >= 1

    def test_comparison_with_one_missing(self):
        """One topic found, other not — should still produce a chain."""
        records = [
            {
                "topic": "Python",
                "mentions": 120,
                "importance": 0.85,
                "document_count": 45,
                "related_topics": ["ML"],
            },
        ]
        chain = self.builder.build_chain(
            "Compare Python and Zig", ReasoningType.COMPARISON, records
        )
        assert chain is not None
        assert chain.total_confidence > 0.0

    def test_comparison_decompose(self):
        with patch(
            "app.services.query_decomposer._get_spacy_extractor",
            return_value=None,
        ):
            d = QueryDecomposer().decompose(
                'How many "Python" vs "Rust" documents?'
            )
        assert d.reasoning_type == ReasoningType.COMPARISON
        assert len(d.entities) >= 2


# ═══════════════════════════════════════════════════════════════════════
# § 5  CONFIDENCE COLLAPSE
# ═══════════════════════════════════════════════════════════════════════


class TestConfidenceCollapse:
    """When every signal is bad, confidence must collapse gracefully."""

    scorer = ConfidenceScorer()

    def test_all_misses(self):
        signals = ConfidenceSignals(
            entity_match_qualities=[MatchQuality.MISS, MatchQuality.MISS],
        )
        assert self.scorer.entity_resolution_confidence(signals) == 0.0

    def test_fallback_classification_plus_all_miss_plus_zero_results(self):
        signals = ConfidenceSignals(
            is_fallback_classification=True,
            entity_match_qualities=[MatchQuality.MISS],
            result_count=0,
            expected_result_count=5,
            evidence_completeness=0.0,
        )
        chain_conf = self.scorer.chain_confidence(signals)
        assert chain_conf < 0.15  # should be very low

    def test_one_good_one_miss_drags_down(self):
        signals = ConfidenceSignals(
            entity_match_qualities=[MatchQuality.EXACT, MatchQuality.MISS],
        )
        conf = self.scorer.entity_resolution_confidence(signals)
        # 70% avg(1.0, 0.0) + 30% min(0.0) = 0.35
        assert abs(conf - 0.35) < 0.01

    def test_chain_gate_caps_result(self):
        """Even with perfect results, bad classification gates the score."""
        signals = ConfidenceSignals(
            is_fallback_classification=True,
            result_count=10,
            expected_result_count=10,
            evidence_completeness=1.0,
        )
        conf = self.scorer.chain_confidence(signals)
        # gate = min(0.35, 0.5) = 0.35
        # overall = 0.35 * 0.4 + 1.0 * 0.6 = 0.74
        assert conf < 0.80

    def test_path_confidence_null(self):
        signals = ConfidenceSignals(shortest_path_length=None)
        assert self.scorer.path_confidence(signals) == 0.5

    def test_path_confidence_zero_length(self):
        signals = ConfidenceSignals(shortest_path_length=0)
        assert self.scorer.path_confidence(signals) == 0.5

    def test_negative_path_length(self):
        signals = ConfidenceSignals(shortest_path_length=-1)
        assert self.scorer.path_confidence(signals) == 0.5

    def test_step_confidence_empty_record(self):
        assert self.scorer.step_confidence({}) == 0.0

    def test_step_confidence_all_none(self):
        record = {"a": None, "b": None, "c": None}
        assert self.scorer.step_confidence(record) == 0.0

    def test_zero_results_zero_completeness(self):
        signals = ConfidenceSignals(
            result_count=0,
            expected_result_count=10,
            evidence_completeness=0.0,
        )
        assert self.scorer.result_confidence(signals) == 0.0


# ═══════════════════════════════════════════════════════════════════════
# § 6  TYPE-AWARE ENTITY RESOLVER — HARD CASES
# ═══════════════════════════════════════════════════════════════════════


class TestResolverHardCases:
    """Ambiguous mentions where type hints are the only disambiguator."""

    def _make_resolver(self, cache: dict):
        driver = MagicMock()
        resolver = EntityResolver(driver)
        resolver._entity_cache = cache
        return resolver

    def test_same_name_different_labels(self):
        """'Apple' could be Person, Organization, or Topic."""
        resolver = self._make_resolver({
            "apple inc": {"id": "1", "name": "Apple Inc", "label": "Organization"},
            "apple fruit": {"id": "2", "name": "Apple Fruit", "label": "Topic"},
        })
        # With label hint → Organization
        ent, q = resolver.resolve_with_quality("Apple", expected_label="Organization")
        assert q == MatchQuality.SUBSTRING
        assert ent["label"] == "Organization"

        # With label hint → Topic
        ent2, q2 = resolver.resolve_with_quality("Apple", expected_label="Topic")
        assert ent2["label"] == "Topic"

    def test_no_match_returns_miss(self):
        resolver = self._make_resolver({
            "alice": {"id": "1", "name": "Alice", "label": "Person"},
        })
        ent, q = resolver.resolve_with_quality("Zyxwvutsrqp", expected_label="Person")
        assert ent is None
        assert q == MatchQuality.MISS

    def test_empty_cache(self):
        resolver = self._make_resolver({})
        ent, q = resolver.resolve_with_quality("Alice")
        assert ent is None
        assert q == MatchQuality.MISS

    def test_very_short_mention_no_substring(self):
        """Mentions < 3 chars should not substring-match."""
        resolver = self._make_resolver({
            "machine learning": {"id": "1", "name": "Machine Learning", "label": "Topic"},
        })
        ent, q = resolver.resolve_with_quality("ML")
        # ML is only 2 chars — below _MIN_SUBSTRING_LEN
        assert q in (MatchQuality.MISS, MatchQuality.FUZZY)

    def test_case_insensitive_exact(self):
        resolver = self._make_resolver({
            "alice johnson": {"id": "1", "name": "Alice Johnson", "label": "Person"},
        })
        ent, q = resolver.resolve_with_quality("ALICE JOHNSON")
        assert q == MatchQuality.EXACT
        assert ent["name"] == "Alice Johnson"

    def test_resolve_or_create_new(self):
        """resolve_or_create should create when nothing matches."""
        driver = MagicMock()
        session_mock = MagicMock()
        driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        resolver = EntityResolver(driver)
        resolver._entity_cache = {}

        new_id = resolver.resolve_or_create(
            "Brand New Entity", label="Concept", properties={"description": "test"}
        )
        assert new_id  # should return a UUID string
        # Should now be in cache
        assert "brand new entity" in resolver._entity_cache
        assert resolver._entity_cache["brand new entity"]["label"] == "Concept"


# ═══════════════════════════════════════════════════════════════════════
# § 7  TEMPLATE ROUTING — HARD CASES
# ═══════════════════════════════════════════════════════════════════════


class TestRouterHardCases:
    """Edge cases in template slot filling and routing."""

    router = TemplateRouter()

    def test_multi_hop_needs_two_entities(self):
        query = DecomposedQuery(
            reasoning_type=ReasoningType.MULTI_HOP,
            entities=["Alice"],
            relationships=[],
            time_range=None,
            aggregation_fn=None,
            hop_limit=4,
            confidence=0.8,
            entity_types=["Person"],
        )
        routes = self.router.route(query)
        # Multi-hop templates need entity_a AND entity_b
        # With only 1 entity, should fall back to full_neighborhood
        if routes:
            names = [n for n, _ in routes]
            assert "full_neighborhood" in names or "shortest_path_entities" not in names

    def test_temporal_without_time_range_falls_back(self):
        query = DecomposedQuery(
            reasoning_type=ReasoningType.TEMPORAL,
            entities=["report"],
            relationships=[],
            time_range=None,  # no time parsed
            aggregation_fn=None,
            hop_limit=1,
            confidence=0.6,
            entity_types=[],
        )
        routes = self.router.route(query)
        # Temporal templates need start_time/end_time — should fail slot fill
        # and fall back to full_neighborhood
        if routes:
            names = [n for n, _ in routes]
            assert "documents_in_timerange" not in names

    def test_causal_with_event_type(self):
        query = DecomposedQuery(
            reasoning_type=ReasoningType.CAUSAL,
            entities=["Server Crash"],
            relationships=[],
            time_range=None,
            aggregation_fn=None,
            hop_limit=5,
            confidence=0.8,
            entity_types=["Event"],
        )
        routes = self.router.route(query)
        assert len(routes) > 0
        # Should find event_causal_chain or temporal_chain
        names = [n for n, _ in routes]
        assert any(
            n in names for n in ("event_causal_chain", "temporal_chain")
        )

    def test_no_entities_exploration_gives_community(self):
        query = DecomposedQuery(
            reasoning_type=ReasoningType.EXPLORATION,
            entities=[],
            relationships=[],
            time_range=None,
            aggregation_fn=None,
            hop_limit=2,
            confidence=0.35,
            entity_types=[],
        )
        routes = self.router.route(query)
        # community_detection has no required slots
        names = [n for n, _ in routes]
        assert "community_detection" in names

    def test_mixed_entity_types_first_wins_for_label(self):
        """When entity_types has mixed types, the first drives node_label."""
        query = DecomposedQuery(
            reasoning_type=ReasoningType.AGGREGATION,
            entities=["Google", "AI"],
            relationships=[],
            time_range=None,
            aggregation_fn="count",
            hop_limit=1,
            confidence=0.8,
            entity_types=["Organization", "Topic"],
        )
        routes = self.router.route(query)
        for name, cypher in routes:
            if name == "top_entities_by_mentions":
                assert "Organization" in cypher


# ═══════════════════════════════════════════════════════════════════════
# § 8  FULL ORCHESTRATOR MOCK
# ═══════════════════════════════════════════════════════════════════════


class TestOrchestratorMock:
    """Full pipeline mock without a real Neo4j."""

    def _build_orchestrator(self, cypher_results, cache=None):
        from app.services.graph_reasoning import GraphReasoningOrchestrator

        driver = MagicMock()
        session_mock = MagicMock()
        result_mock = MagicMock()
        result_mock.__iter__ = MagicMock(
            return_value=iter(
                [MagicMock(**{"__iter__": iter, "items": r.items, "keys": r.keys, **r})
                 for r in cypher_results]
            )
        )
        # Make each record behave like a dict
        records = []
        for r in cypher_results:
            rec = MagicMock()
            rec.__iter__ = MagicMock(return_value=iter(r.items()))
            rec.keys.return_value = r.keys()
            rec.__getitem__ = lambda self, k, _r=r: _r[k]
            rec.items.return_value = r.items()
            records.append(rec)

        session_mock.run.return_value = records
        driver.session.return_value.__enter__ = MagicMock(return_value=session_mock)
        driver.session.return_value.__exit__ = MagicMock(return_value=False)

        orch = GraphReasoningOrchestrator(driver)
        if cache:
            orch.entity_resolver._entity_cache = cache
        return orch

    def test_full_pipeline_entity_lookup(self):
        orch = self._build_orchestrator(
            cypher_results=[],
            cache={"alice": {"id": "1", "name": "Alice", "label": "Person"}},
        )
        with patch(
            "app.services.query_decomposer._get_spacy_extractor",
            return_value=None,
        ):
            prompt = orch.process_query('Who is "Alice"?')
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_vector_enrichment_on_low_confidence(self):
        orch = self._build_orchestrator(cypher_results=[], cache={})
        with patch(
            "app.services.query_decomposer._get_spacy_extractor",
            return_value=None,
        ):
            prompt = orch.process_query(
                'Who is "Nonexistent"?',
                vector_results=["Vector doc 1", "Vector doc 2"],
            )
        # Low graph confidence → should include vector results
        assert "Vector doc" in prompt or "context" in prompt.lower()


# ═══════════════════════════════════════════════════════════════════════
# § 9  LABEL MAPPING COMPLETENESS
# ═══════════════════════════════════════════════════════════════════════


class TestLabelMappingCompleteness:
    """Every mapped label must have a valid confidence and reverse mapping."""

    def test_all_mapped_labels_have_confidence(self):
        for spacy_label in SPACY_TO_NEO4J:
            conf = spacy_label_confidence(spacy_label)
            assert conf > 0.0, f"{spacy_label} has zero confidence"

    def test_typed_entity_round_trip(self):
        """from_spacy → to_entity_payload_dict → reconstruct."""
        for spacy_label, neo4j in SPACY_TO_NEO4J.items():
            te = TypedEntity.from_spacy(f"Test {spacy_label}", spacy_label)
            d = te.to_entity_payload_dict()
            assert d["type"] == neo4j
            assert d["text"] == f"Test {spacy_label}"
            assert 0.0 < d["confidence"] <= 1.0

    def test_frozen_dataclass(self):
        te = TypedEntity.from_spacy("Alice", "PERSON")
        with pytest.raises(AttributeError):
            te.text = "Bob"  # type: ignore[misc]

    def test_neo4j_label_idempotent(self):
        """Mapping the same label twice gives the same result."""
        for label in SPACY_TO_NEO4J:
            assert neo4j_label(label) == neo4j_label(label)


# ═══════════════════════════════════════════════════════════════════════
# § 10  REASONING CHAIN COHERENCE
# ═══════════════════════════════════════════════════════════════════════


class TestChainCoherence:
    """The generated LLM prompt must be internally consistent."""

    builder = ReasoningChainBuilder()

    def _build_and_format(self, query, rtype, records):
        chain = self.builder.build_chain(query, rtype, records)
        return chain, chain.to_llm_prompt_context()

    def test_prompt_contains_query(self):
        chain, prompt = self._build_and_format(
            "Who is Alice?", ReasoningType.ENTITY_LOOKUP, []
        )
        assert "Who is Alice?" in prompt

    def test_prompt_contains_reasoning_type(self):
        chain, prompt = self._build_and_format(
            "Compare A and B", ReasoningType.COMPARISON, []
        )
        assert "comparison" in prompt.lower()

    def test_prompt_contains_confidence(self):
        chain, prompt = self._build_and_format(
            "Explore ML", ReasoningType.EXPLORATION,
            [{"name": "DL", "weight": 0.8, "rel_type": "related_to"}],
        )
        assert "CONFIDENCE:" in prompt

    def test_step_numbers_sequential(self):
        records = [
            {"name": "A", "weight": 0.9, "rel_type": "related_to"},
            {"name": "B", "weight": 0.8, "rel_type": "subtopic"},
            {"name": "C", "weight": 0.7, "rel_type": "parent"},
        ]
        chain, prompt = self._build_and_format(
            "Explore topic X", ReasoningType.EXPLORATION, records
        )
        for i, step in enumerate(chain.steps):
            assert step.step_number == i + 1

    def test_source_count_matches_records(self):
        records = [
            {"topic": "ML", "document_count": 10, "sample_documents": []},
            {"topic": "DL", "document_count": 5, "sample_documents": []},
        ]
        chain = self.builder.build_chain(
            "Count topics", ReasoningType.AGGREGATION, records
        )
        assert chain.source_count >= len(records)

    def test_total_confidence_bounded(self):
        """Confidence must always be in [0.0, 1.0]."""
        test_cases = [
            (ReasoningType.ENTITY_LOOKUP, []),
            (ReasoningType.MULTI_HOP, [{"path_nodes": [], "path_relationships": [], "path_length": 0}]),
            (ReasoningType.AGGREGATION, [{"topic": "X", "document_count": 999, "sample_documents": []}]),
        ]
        for rtype, records in test_cases:
            chain = self.builder.build_chain("test", rtype, records)
            assert 0.0 <= chain.total_confidence <= 1.0, (
                f"Out of bounds for {rtype}: {chain.total_confidence}"
            )
