"""Tests for entity extraction pipeline.

Covers:
  • EntityExtractor core methods (extract_entities, extract_entities_with_labels,
    extract_key_entities, extract_batch, extract_relationships)
  • Label mapping (SPACY_TO_NEO4J, TypedEntity, confidence priors)
  • QueryDecomposer spaCy integration (_extract_entities_spacy)
  • TextProcessor._extract_typed_entities helper
  • Integration tests against sample_onthological_relation*.txt ground-truth
"""

from __future__ import annotations

import pathlib
import textwrap

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TESTS_DIR = pathlib.Path(__file__).parent
SAMPLE1 = TESTS_DIR / "sample_onthological_relation1.txt"
SAMPLE2 = TESTS_DIR / "sample_onthological_relation2.txt"


def _read_notes_section(path: pathlib.Path) -> str:
    """Return only the *notes* section (before '=== EXPECTED')."""
    text = path.read_text(encoding="utf-8")
    marker = "=== EXPECTED ONTOLOGICAL RELATIONS ==="
    idx = text.find(marker)
    return text[:idx].strip() if idx != -1 else text.strip()


@pytest.fixture(scope="module")
def extractor():
    """Shared EntityExtractor instance (loads spaCy model once)."""
    from app.services.processing.entity_extractor import EntityExtractor

    return EntityExtractor("en_core_web_sm")


@pytest.fixture(scope="module")
def sample1_text() -> str:
    if not SAMPLE1.exists():
        pytest.skip("sample_onthological_relation1.txt not found")
    return _read_notes_section(SAMPLE1)


@pytest.fixture(scope="module")
def sample2_text() -> str:
    if not SAMPLE2.exists():
        pytest.skip("sample_onthological_relation2.txt not found")
    return _read_notes_section(SAMPLE2)


# ===================================================================
# 1  ·  EntityExtractor – core unit tests
# ===================================================================

class TestExtractEntities:
    """extract_entities() – flat unique entity list."""

    def test_empty_string(self, extractor):
        assert extractor.extract_entities("") == []

    def test_whitespace_only(self, extractor):
        assert extractor.extract_entities("   \n\t  ") == []

    def test_no_entities(self, extractor):
        result = extractor.extract_entities("the quick brown fox jumped over the lazy dog")
        # spaCy *may* return nothing or a spurious hit — length should be small
        assert len(result) <= 1

    def test_person_extraction(self, extractor):
        text = "Barack Obama met with Angela Merkel in Berlin."
        entities = extractor.extract_entities(text)
        names = [e.lower() for e in entities]
        assert any("obama" in n for n in names)
        assert any("merkel" in n for n in names)

    def test_org_extraction(self, extractor):
        text = "Google and Microsoft announced a partnership."
        entities = extractor.extract_entities(text)
        lower = {e.lower() for e in entities}
        assert "google" in lower or "microsoft" in lower

    def test_filter_by_type(self, extractor):
        text = "Sarah Chen works at Google in New York."
        persons = extractor.extract_entities(text, entity_types=["PERSON"])
        labels_of_all = {
            ent["label"]
            for ent in extractor.extract_entities_with_labels(text)
            if ent["text"] in persons
        }
        # Every returned entity should have PERSON label
        assert all(l == "PERSON" for l in labels_of_all) if labels_of_all else True

    def test_uniqueness(self, extractor):
        text = "Alice met Bob. Then Alice called Bob again."
        entities = extractor.extract_entities(text)
        assert len(entities) == len(set(entities)), "duplicates found"


class TestExtractEntitiesWithLabels:
    """extract_entities_with_labels() – dicts with text/label/start/end."""

    def test_returns_dicts(self, extractor):
        text = "Elon Musk founded SpaceX in California."
        results = extractor.extract_entities_with_labels(text)
        assert isinstance(results, list)
        for ent in results:
            assert "text" in ent
            assert "label" in ent
            assert "start" in ent
            assert "end" in ent

    def test_span_offsets_match(self, extractor):
        text = "Barack Obama visited Paris last Monday."
        results = extractor.extract_entities_with_labels(text)
        for ent in results:
            assert text[ent["start"]:ent["end"]] == ent["text"]

    def test_empty_input(self, extractor):
        assert extractor.extract_entities_with_labels("") == []

    def test_type_filter(self, extractor):
        text = "Sarah works at Google in Berlin on January 5."
        orgs = extractor.extract_entities_with_labels(text, entity_types=["ORG"])
        for ent in orgs:
            assert ent["label"] == "ORG"


class TestExtractKeyEntities:
    """extract_key_entities() – categorised dict."""

    def test_categories_present(self, extractor):
        text = "Marcus Rivera at Microsoft in Berlin on January 14, 2026."
        result = extractor.extract_key_entities(text)
        assert "persons" in result
        assert "organizations" in result
        assert "locations" in result
        assert "dates" in result
        assert "other" in result

    def test_empty_input(self, extractor):
        assert extractor.extract_key_entities("") == {}

    def test_person_categorised(self, extractor):
        text = "James Thornton is a professor at MIT."
        cat = extractor.extract_key_entities(text)
        lower_persons = [p.lower() for p in cat.get("persons", [])]
        assert any("thornton" in p for p in lower_persons)

    def test_no_duplicates_in_categories(self, extractor):
        text = "Alice and Bob. Alice and Bob again."
        cat = extractor.extract_key_entities(text)
        for key, vals in cat.items():
            assert len(vals) == len(set(vals)), f"duplicates in {key}"


class TestExtractBatch:
    """extract_batch() – efficient multi-text extraction."""

    def test_empty_list(self, extractor):
        assert extractor.extract_batch([]) == []

    def test_one_to_one(self, extractor):
        texts = [
            "Obama is the president.",
            "Google is a company.",
        ]
        results = extractor.extract_batch(texts)
        assert len(results) == 2
        assert all(isinstance(r, list) for r in results)

    def test_batch_matches_individual(self, extractor):
        texts = ["Alice met Bob.", "Charlie visited Paris."]
        batch = extractor.extract_batch(texts)
        individual = [extractor.extract_entities(t) for t in texts]
        for b, i in zip(batch, individual):
            assert set(b) == set(i)


class TestExtractRelationships:
    """extract_relationships() – subject/predicate/object triples."""

    def test_simple_triple(self, extractor):
        text = "Marcus Rivera presented the latest progress on Project Atlas."
        rels = extractor.extract_relationships(text)
        assert isinstance(rels, list)
        # Should find at least one triple
        if rels:
            assert "subject" in rels[0]
            assert "predicate" in rels[0]
            assert "object" in rels[0]

    def test_empty_input(self, extractor):
        assert extractor.extract_relationships("") == []

    def test_multiple_sentences(self, extractor):
        text = (
            "Alice runs the team. Bob manages the budget. "
            "Charlie deployed the service."
        )
        rels = extractor.extract_relationships(text)
        assert len(rels) >= 2

    def test_combined_extraction(self, extractor):
        text = "Sarah Chen leads the AI team at Nexus Technologies."
        result = extractor.extract_entities_and_relationships(text)
        assert "entities" in result
        assert "relationships" in result


# ===================================================================
# 2  ·  Label Mapping
# ===================================================================

class TestLabelMapping:
    """SPACY_TO_NEO4J mapping and helper functions."""

    def test_person_mapping(self):
        from app.services.label_mapping import neo4j_label
        assert neo4j_label("PERSON") == "Person"

    def test_org_mapping(self):
        from app.services.label_mapping import neo4j_label
        assert neo4j_label("ORG") == "Organization"

    def test_gpe_and_loc_both_map_to_location(self):
        from app.services.label_mapping import neo4j_label
        assert neo4j_label("GPE") == "Location"
        assert neo4j_label("LOC") == "Location"
        assert neo4j_label("FAC") == "Location"

    def test_event_and_date_map_to_event(self):
        from app.services.label_mapping import neo4j_label
        assert neo4j_label("EVENT") == "Event"
        assert neo4j_label("DATE") == "Event"
        assert neo4j_label("TIME") == "Event"

    def test_product_maps_to_project(self):
        from app.services.label_mapping import neo4j_label
        assert neo4j_label("PRODUCT") == "Project"

    def test_unmapped_label_gives_default(self):
        from app.services.label_mapping import neo4j_label, DEFAULT_NEO4J_LABEL
        assert neo4j_label("CARDINAL") == DEFAULT_NEO4J_LABEL
        assert neo4j_label("QUANTITY") == DEFAULT_NEO4J_LABEL
        assert neo4j_label("SOME_UNKNOWN") == DEFAULT_NEO4J_LABEL

    def test_reverse_index(self):
        from app.services.label_mapping import NEO4J_TO_SPACY
        assert "Person" in NEO4J_TO_SPACY
        assert "PERSON" in NEO4J_TO_SPACY["Person"]
        assert "ORG" in NEO4J_TO_SPACY["Organization"]

    def test_all_mapped_labels_have_confidence(self):
        from app.services.label_mapping import SPACY_TO_NEO4J, spacy_label_confidence
        for spacy_lbl in SPACY_TO_NEO4J:
            conf = spacy_label_confidence(spacy_lbl)
            assert 0.0 < conf <= 1.0, f"{spacy_lbl} has bad confidence {conf}"


class TestTypedEntity:
    """TypedEntity frozen dataclass."""

    def test_from_spacy(self):
        from app.services.label_mapping import TypedEntity
        te = TypedEntity.from_spacy("Google", "ORG")
        assert te.text == "Google"
        assert te.spacy_label == "ORG"
        assert te.neo4j_label == "Organization"
        assert 0.0 < te.confidence <= 1.0

    def test_to_entity_payload_dict(self):
        from app.services.label_mapping import TypedEntity
        te = TypedEntity.from_spacy("Berlin", "GPE")
        d = te.to_entity_payload_dict()
        assert d["text"] == "Berlin"
        assert d["type"] == "Location"
        assert isinstance(d["confidence"], float)

    def test_frozen(self):
        from app.services.label_mapping import TypedEntity
        te = TypedEntity.from_spacy("Alice", "PERSON")
        with pytest.raises(AttributeError):
            te.text = "Bob"  # type: ignore[misc]

    def test_default_label_for_unknown(self):
        from app.services.label_mapping import TypedEntity, DEFAULT_NEO4J_LABEL
        te = TypedEntity.from_spacy("42", "CARDINAL")
        assert te.neo4j_label == DEFAULT_NEO4J_LABEL


# ===================================================================
# 3  ·  QueryDecomposer – spaCy entity integration
# ===================================================================

class TestDecomposerSpacy:
    """QueryDecomposer should use spaCy for entity extraction when available."""

    def test_decompose_finds_person(self):
        from app.services.query_decomposer import QueryDecomposer
        qd = QueryDecomposer()
        result = qd.decompose("What did Sarah Chen work on?")
        lower_ents = [e.lower() for e in result.entities]
        assert any("sarah" in e for e in lower_ents)

    def test_decompose_finds_org(self):
        from app.services.query_decomposer import QueryDecomposer
        qd = QueryDecomposer()
        result = qd.decompose("Tell me about Google DeepMind research")
        lower_ents = [e.lower() for e in result.entities]
        assert any("google" in e or "deepmind" in e for e in lower_ents)

    def test_entity_types_parallel_to_entities(self):
        from app.services.query_decomposer import QueryDecomposer
        qd = QueryDecomposer()
        result = qd.decompose("Sarah Chen works at Google in Berlin")
        if result.entity_types:
            assert len(result.entity_types) == len(result.entities)

    def test_entity_types_contain_valid_neo4j_labels(self):
        from app.services.query_decomposer import QueryDecomposer
        from app.services.label_mapping import SPACY_TO_NEO4J, DEFAULT_NEO4J_LABEL
        valid_labels = set(SPACY_TO_NEO4J.values()) | {DEFAULT_NEO4J_LABEL}
        qd = QueryDecomposer()
        result = qd.decompose("Marcus Rivera at Microsoft in Berlin")
        for lbl in result.entity_types:
            assert lbl in valid_labels, f"unexpected Neo4j label: {lbl}"

    def test_no_entities_for_generic_query(self):
        from app.services.query_decomposer import QueryDecomposer
        qd = QueryDecomposer()
        result = qd.decompose("what is the meaning of life?")
        # Could be 0 or a few — just no crash
        assert isinstance(result.entities, list)

    def test_regex_fallback_with_quoted_entities(self):
        """Even if spaCy misses it, quoted strings should be caught."""
        from app.services.query_decomposer import QueryDecomposer
        qd = QueryDecomposer()
        result = qd.decompose('find notes about "Project Atlas"')
        lower = [e.lower() for e in result.entities]
        assert any("project atlas" in e for e in lower)


# ===================================================================
# 4  ·  TextProcessor – typed entity extraction helper
# ===================================================================

class TestTextProcessorTypedEntities:
    """TextProcessor._extract_typed_entities via direct call."""

    @pytest.fixture()
    def processor(self):
        from app.services.processing.text_processor import TextProcessor
        return TextProcessor(chunk_size=256, chunk_overlap=0)

    def test_returns_tuple(self, processor):
        flat, typed = processor._extract_typed_entities(
            "Barack Obama visited Berlin."
        )
        assert isinstance(flat, list)
        assert isinstance(typed, list)

    def test_flat_names_unique(self, processor):
        flat, _ = processor._extract_typed_entities(
            "Alice met Bob. Alice again."
        )
        assert len(flat) == len(set(flat))

    def test_typed_dict_shape(self, processor):
        _, typed = processor._extract_typed_entities(
            "Sarah Chen works at Google."
        )
        for d in typed:
            assert "text" in d
            assert "type" in d
            assert "confidence" in d

    def test_empty_input(self, processor):
        flat, typed = processor._extract_typed_entities("")
        assert flat == []
        assert typed == []


# ===================================================================
# 5  ·  Integration — sample_onthological_relation1.txt
# ===================================================================

class TestSample1PersonExtraction:
    """Verify that the key PERSON entities from sample 1 are found."""

    EXPECTED_PERSONS = [
        "Sarah Chen",
        "Marcus Rivera",
        "Priya Kapoor",
        "David Okonkwo",
        "Emily Zhang",
        "James Thornton",
        "Robert Kim",
    ]

    def test_persons_found(self, extractor, sample1_text):
        entities = extractor.extract_entities(sample1_text, entity_types=["PERSON"])
        lower = {e.lower() for e in entities}
        found = [p for p in self.EXPECTED_PERSONS if p.lower() in lower]
        # At least 5 of 7 persons should be detected
        assert len(found) >= 5, (
            f"Only found {found}, missing: "
            f"{set(self.EXPECTED_PERSONS) - {f for f in found}}"
        )

    def test_key_entities_persons(self, extractor, sample1_text):
        cat = extractor.extract_key_entities(sample1_text)
        lower = {p.lower() for p in cat.get("persons", [])}
        assert any("sarah chen" in p for p in lower)
        assert any("marcus rivera" in p or "rivera" in p for p in lower)


class TestSample1OrgExtraction:
    """Verify ORG entities from sample 1."""

    EXPECTED_ORGS = [
        "MIT",  # may appear as "MIT CSAIL" or "MIT"
        "Anthropic",
        "OpenAI",
        "Microsoft",
        "Google DeepMind",
        "Amazon Web Services",
        "Google Cloud Platform",
    ]

    def test_orgs_found(self, extractor, sample1_text):
        entities = extractor.extract_entities(sample1_text, entity_types=["ORG"])
        lower = " ".join(entities).lower()
        found = [o for o in self.EXPECTED_ORGS if o.lower() in lower]
        # At least 4 of 7 should be recognised
        assert len(found) >= 4, f"Only found: {found}"


class TestSample1LocationExtraction:
    """Verify GPE/LOC entities from sample 1."""

    EXPECTED_LOCATIONS = [
        "Berlin", "Las Vegas", "Dublin", "Paris", "Toronto",
        "Barcelona", "Vienna", "Amsterdam",
    ]

    def test_locations_found(self, extractor, sample1_text):
        entities = extractor.extract_entities(
            sample1_text, entity_types=["GPE", "LOC"]
        )
        lower = {e.lower() for e in entities}
        found = [l for l in self.EXPECTED_LOCATIONS if l.lower() in lower]
        assert len(found) >= 5, f"Only found: {found}"

    def test_key_entities_locations(self, extractor, sample1_text):
        cat = extractor.extract_key_entities(sample1_text)
        lower = {loc.lower() for loc in cat.get("locations", [])}
        assert any("berlin" in l for l in lower)


class TestSample1LabeledExtraction:
    """extract_entities_with_labels on sample 1 — verify label mapping."""

    def test_labeled_entities_have_valid_labels(self, extractor, sample1_text):
        labeled = extractor.extract_entities_with_labels(sample1_text)
        spacy_labels = {ent["label"] for ent in labeled}
        # Should see at least PERSON and ORG
        assert "PERSON" in spacy_labels, f"No PERSON label in {spacy_labels}"
        assert "ORG" in spacy_labels, f"No ORG label in {spacy_labels}"

    def test_neo4j_label_mapping_for_sample1(self, extractor, sample1_text):
        from app.services.label_mapping import TypedEntity
        labeled = extractor.extract_entities_with_labels(sample1_text)
        neo4j_labels = set()
        for ent in labeled:
            te = TypedEntity.from_spacy(ent["text"], ent["label"])
            neo4j_labels.add(te.neo4j_label)
        assert "Person" in neo4j_labels
        assert "Organization" in neo4j_labels

    def test_typed_entity_payload_format(self, extractor, sample1_text):
        from app.services.label_mapping import TypedEntity
        labeled = extractor.extract_entities_with_labels(sample1_text)
        for ent in labeled[:10]:
            te = TypedEntity.from_spacy(ent["text"], ent["label"])
            d = te.to_entity_payload_dict()
            assert isinstance(d["text"], str)
            assert isinstance(d["type"], str)
            assert isinstance(d["confidence"], float)


class TestSample1Relationships:
    """Relationship extraction from sample 1."""

    def test_relationships_extracted(self, extractor, sample1_text):
        rels = extractor.extract_relationships(sample1_text)
        assert len(rels) >= 5, f"Only {len(rels)} relationships extracted"

    def test_relationship_subjects_include_known_entities(self, extractor, sample1_text):
        rels = extractor.extract_relationships(sample1_text)
        subjects = " ".join(r["subject"].lower() for r in rels)
        # At least some known names should appear as subjects
        known = ["marcus", "priya", "emily", "david", "sarah"]
        found = [n for n in known if n in subjects]
        assert len(found) >= 2, f"Only found subjects: {found}"

    def test_combined_extraction_shape(self, extractor, sample1_text):
        result = extractor.extract_entities_and_relationships(sample1_text)
        assert len(result["entities"]) > 0
        assert len(result["relationships"]) > 0


# ===================================================================
# 6  ·  Integration — sample_onthological_relation2.txt
# ===================================================================

class TestSample2PersonExtraction:
    """Verify PERSON entities from sample 2."""

    EXPECTED_PERSONS = [
        "Lena Vasquez",
        "Yuki Tanaka",
        "Carlos Mendez",
        "Amara Osei",
        "Elena Rossi",
        "Jin Park",
        "Fatima Al-Rashidi",
        "Lisa Nguyen",
    ]

    def test_persons_found(self, extractor, sample2_text):
        entities = extractor.extract_entities(sample2_text, entity_types=["PERSON"])
        lower = {e.lower() for e in entities}
        found = [p for p in self.EXPECTED_PERSONS if p.lower() in lower]
        assert len(found) >= 5, (
            f"Only found {found}, missing: "
            f"{set(self.EXPECTED_PERSONS) - {f for f in found}}"
        )


class TestSample2OrgExtraction:
    """Verify ORG entities from sample 2."""

    EXPECTED_ORGS = [
        "CoreWeave",
        "Scale AI",
        "Hugging Face",
        "University of Edinburgh",
    ]

    def test_orgs_found(self, extractor, sample2_text):
        entities = extractor.extract_entities(sample2_text, entity_types=["ORG"])
        lower = " ".join(entities).lower()
        found = [o for o in self.EXPECTED_ORGS if o.lower() in lower]
        assert len(found) >= 2, f"Only found: {found}"


class TestSample2LocationExtraction:
    """Verify location entities from sample 2."""

    EXPECTED_LOCATIONS = ["Stockholm", "Amsterdam", "Toronto", "London"]

    def test_locations_found(self, extractor, sample2_text):
        entities = extractor.extract_entities(
            sample2_text, entity_types=["GPE", "LOC"]
        )
        lower = {e.lower() for e in entities}
        found = [l for l in self.EXPECTED_LOCATIONS if l.lower() in lower]
        assert len(found) >= 2, f"Only found: {found}"


class TestSample2LabeledExtraction:
    """Labeled extraction + Neo4j mapping for sample 2."""

    def test_multiple_label_types(self, extractor, sample2_text):
        labeled = extractor.extract_entities_with_labels(sample2_text)
        labels = {ent["label"] for ent in labeled}
        # Should have at least 3 different spaCy label types
        assert len(labels) >= 3, f"Only {labels}"

    def test_entity_count_reasonable(self, extractor, sample2_text):
        labeled = extractor.extract_entities_with_labels(sample2_text)
        # Sample 2 has 58 expected entities; spaCy won't catch all
        # but should find at least 20 distinct entity texts
        unique_texts = {ent["text"].lower() for ent in labeled}
        assert len(unique_texts) >= 20, (
            f"Only {len(unique_texts)} unique entities, expected ≥ 20"
        )


class TestSample2Relationships:
    """Relationship extraction from sample 2."""

    def test_relationships_extracted(self, extractor, sample2_text):
        rels = extractor.extract_relationships(sample2_text)
        assert len(rels) >= 5

    def test_training_related_predicates(self, extractor, sample2_text):
        rels = extractor.extract_relationships(sample2_text)
        predicates = {r["predicate"].lower() for r in rels}
        # Should capture action verbs from the research log
        action_verbs = {"start", "complete", "deploy", "train", "approve",
                        "report", "flag", "deliver", "resume", "use",
                        "run", "begin", "discover", "implement", "file"}
        found = predicates & action_verbs
        assert len(found) >= 2, f"Only found predicates: {predicates}"


# ===================================================================
# 7  ·  Cross-sample consistency
# ===================================================================

class TestCrossSampleConsistency:
    """Both samples should produce structurally consistent output."""

    def test_both_produce_persons(self, extractor, sample1_text, sample2_text):
        p1 = extractor.extract_entities(sample1_text, entity_types=["PERSON"])
        p2 = extractor.extract_entities(sample2_text, entity_types=["PERSON"])
        assert len(p1) >= 3
        assert len(p2) >= 3

    def test_labeled_schema_consistent(self, extractor, sample1_text, sample2_text):
        for text in (sample1_text, sample2_text):
            labeled = extractor.extract_entities_with_labels(text)
            for ent in labeled:
                assert set(ent.keys()) == {"text", "label", "start", "end"}

    def test_batch_on_both_samples(self, extractor, sample1_text, sample2_text):
        results = extractor.extract_batch([sample1_text, sample2_text])
        assert len(results) == 2
        assert len(results[0]) >= 5
        assert len(results[1]) >= 5


# ===================================================================
# 8  ·  Edge cases & robustness
# ===================================================================

class TestEdgeCases:
    """Robustness tests for the entity extractor."""

    def test_very_short_text(self, extractor):
        # Single word — shouldn't crash
        result = extractor.extract_entities("Hello")
        assert isinstance(result, list)

    def test_unicode_text(self, extractor):
        text = "José García met François Hollande in São Paulo."
        entities = extractor.extract_entities(text)
        assert isinstance(entities, list)
        # Should handle accented characters
        lower = " ".join(entities).lower()
        assert any(name in lower for name in ["josé", "garcia", "garcía",
                                                "hollande", "françois",
                                                "são paulo", "paulo"])

    def test_very_long_text(self, extractor):
        text = "Alice met Bob in London. " * 500
        entities = extractor.extract_entities(text)
        assert isinstance(entities, list)
        # Should still deduplicate
        assert len(entities) <= 10

    def test_mixed_casing(self, extractor):
        text = "GOOGLE announced a partnership with MICROSOFT."
        entities = extractor.extract_entities(text)
        assert isinstance(entities, list)

    def test_numeric_heavy_text(self, extractor):
        text = "Revenue was $2.4M in Q1-Q2 across 150,000 units at 120ms latency."
        entities = extractor.extract_entities(text)
        # Shouldn't crash; may find monetary/quantity entities
        assert isinstance(entities, list)

    def test_special_characters(self, extractor):
        text = "C++ and C# are languages. Email: test@example.com, URL: https://x.com"
        entities = extractor.extract_entities(text)
        assert isinstance(entities, list)

    def test_newlines_and_markdown(self, extractor):
        text = textwrap.dedent("""\
        ## Heading

        - Bullet point with **bold** and *italic*
        - Alice and Bob at Google

        ### Subheading
        Some text about Microsoft in Seattle.
        """)
        entities = extractor.extract_entities(text)
        assert isinstance(entities, list)

    def test_none_input_graceful(self, extractor):
        """None input should return empty, not crash."""
        # extract_entities checks `not text` which covers None
        result = extractor.extract_entities(None)  # type: ignore[arg-type]
        assert result == []

    def test_batch_with_empty_strings(self, extractor):
        results = extractor.extract_batch(["", "Alice met Bob.", ""])
        assert len(results) == 3
        assert results[0] == []
        assert results[2] == []
        assert len(results[1]) >= 1


# ===================================================================
# 9  ·  QueryDecomposer integration on real notes
# ===================================================================

class TestDecomposerOnSampleQueries:
    """Queries referencing sample-doc entities should be correctly decomposed."""

    @pytest.fixture()
    def decomposer(self):
        from app.services.query_decomposer import QueryDecomposer
        return QueryDecomposer()

    def test_person_query(self, decomposer):
        r = decomposer.decompose("What did Marcus Rivera work on?")
        lower = [e.lower() for e in r.entities]
        assert any("marcus" in e or "rivera" in e for e in lower)

    def test_org_query(self, decomposer):
        r = decomposer.decompose("Tell me about MIT CSAIL's research")
        lower = [e.lower() for e in r.entities]
        assert any("mit" in e or "csail" in e for e in lower)

    def test_multi_entity_query(self, decomposer):
        r = decomposer.decompose(
            "How does Sarah Chen connect to Google DeepMind?"
        )
        assert len(r.entities) >= 2

    def test_temporal_query(self, decomposer):
        r = decomposer.decompose("What happened last week with Project Atlas?")
        # Should have time_range and entity
        from app.models.reasoning import ReasoningType
        assert r.time_range is not None or r.reasoning_type == ReasoningType.TEMPORAL

    def test_causal_query(self, decomposer):
        from app.models.reasoning import ReasoningType
        r = decomposer.decompose("What caused the GPU failure?")
        assert r.reasoning_type == ReasoningType.CAUSAL

    def test_comparison_query(self, decomposer):
        from app.models.reasoning import ReasoningType
        r = decomposer.decompose(
            "Compare the MMLU scores before and after the data mix change"
        )
        # "compare" triggers aggregation → comparison logic
        assert r.reasoning_type in (
            ReasoningType.COMPARISON, ReasoningType.AGGREGATION
        )

    def test_exploration_query(self, decomposer):
        from app.models.reasoning import ReasoningType
        r = decomposer.decompose("Tell me about Meridian-7B")
        assert r.reasoning_type in (
            ReasoningType.EXPLORATION, ReasoningType.ENTITY_LOOKUP
        )

    def test_multi_hop_query(self, decomposer):
        from app.models.reasoning import ReasoningType
        r = decomposer.decompose(
            "How does Fatima Al-Rashidi connect to Constitutional AI?"
        )
        assert r.reasoning_type == ReasoningType.MULTI_HOP
