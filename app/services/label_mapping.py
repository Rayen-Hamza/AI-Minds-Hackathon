"""Unified label mapping — spaCy NER labels ↔ Neo4j node labels.

Single source of truth so every pipeline (query decomposition, content
ingestion, graph updates) uses the same mapping.

spaCy labels reference:
    https://spacy.io/models/en#en_core_web_sm-labels

Neo4j node labels are defined in ``graph_schema.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── spaCy label → Neo4j node label ──────────────────────────────────

SPACY_TO_NEO4J: dict[str, str] = {
    # People
    "PERSON": "Person",
    # Organisations / companies
    "ORG": "Organization",
    # Geopolitical entities (countries, cities, states)
    "GPE": "Location",
    # Non-GPE locations (mountain ranges, bodies of water)
    "LOC": "Location",
    # Facilities (airports, highways, bridges)
    "FAC": "Location",
    # Named events (battles, wars, sports events)
    "EVENT": "Event",
    # Date / time expressions
    "DATE": "Event",
    "TIME": "Event",
    # Creative works (books, songs, etc.)
    "WORK_OF_ART": "Concept",
    # Laws / legal acts
    "LAW": "Concept",
    # Languages
    "LANGUAGE": "Concept",
    # Products (vehicles, software, food)
    "PRODUCT": "Project",
    # Nationalities / religious / political groups
    "NORP": "Concept",
}

# spaCy labels that should be SKIPPED entirely — they produce noisy
# nodes (numbers, percentages, ordinals, etc.).
SKIP_SPACY_LABELS: set[str] = {
    "CARDINAL",
    "ORDINAL",
    "QUANTITY",
    "PERCENT",
    "MONEY",
}

# Reverse index — Neo4j label → list of spaCy labels that map to it
NEO4J_TO_SPACY: dict[str, list[str]] = {}
for _spacy, _neo4j in SPACY_TO_NEO4J.items():
    NEO4J_TO_SPACY.setdefault(_neo4j, []).append(_spacy)

# ── Default label for unmapped spaCy labels ─────────────────────────

DEFAULT_NEO4J_LABEL = "Topic"


def neo4j_label(spacy_label: str) -> str | None:
    """Map a spaCy entity label to the corresponding Neo4j node label.

    Returns ``None`` for labels that should be skipped (numerics, etc.).
    """
    if spacy_label in SKIP_SPACY_LABELS:
        return None
    return SPACY_TO_NEO4J.get(spacy_label, DEFAULT_NEO4J_LABEL)


# ── Confidence per spaCy label ──────────────────────────────────────
# spaCy's `en_core_web_sm` has varying precision per label.
# These are rough F1-derived priors — used to initialise entity
# confidence when the only signal is "spaCy said so".

_SPACY_LABEL_CONFIDENCE: dict[str, float] = {
    "PERSON": 0.92,
    "ORG": 0.80,
    "GPE": 0.88,
    "LOC": 0.72,
    "FAC": 0.65,
    "EVENT": 0.60,
    "DATE": 0.85,
    "TIME": 0.75,
    "WORK_OF_ART": 0.55,
    "LAW": 0.60,
    "LANGUAGE": 0.80,
    "PRODUCT": 0.55,
    "NORP": 0.78,
}


def spacy_label_confidence(spacy_label: str) -> float:
    """Return an a-priori confidence score for a spaCy entity label."""
    return _SPACY_LABEL_CONFIDENCE.get(spacy_label, 0.50)


# ── Typed entity dataclass ──────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TypedEntity:
    """An entity with its text, spaCy label, Neo4j label, and confidence."""

    text: str
    spacy_label: str
    neo4j_label: str
    confidence: float

    @classmethod
    def from_spacy(cls, text: str, spacy_label: str) -> TypedEntity | None:
        """Construct from spaCy extraction output.

        Returns ``None`` for labels that should be skipped.
        """
        mapped = neo4j_label(spacy_label)
        if mapped is None:
            return None
        return cls(
            text=text,
            spacy_label=spacy_label,
            neo4j_label=mapped,
            confidence=spacy_label_confidence(spacy_label),
        )

    def to_entity_payload_dict(self) -> dict:
        """Convert to the dict format expected by ``GraphUpdater.ingest_document``.

        Returns ``{"text": ..., "type": ..., "confidence": ...}``
        """
        return {
            "text": self.text,
            "type": self.neo4j_label,
            "confidence": self.confidence,
        }
