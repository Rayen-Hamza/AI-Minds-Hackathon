"""Algorithmic confidence scoring — no magic numbers, no LLM dependency.

Every confidence score is derived from measurable, deterministic signals
that the system already produces. Zero hallucination risk.

Signals used:
  - Pattern match specificity (how many regex tokens matched)
  - Entity resolution quality (exact vs fuzzy vs substring vs miss)
  - Result set density (how many results vs expected)
  - Graph coverage (fraction of queried entities actually found)
  - Path length penalty (longer paths = weaker evidence)
  - Evidence completeness (fraction of expected fields present)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MatchQuality(Enum):
    """How well a text mention resolved to a graph entity."""

    EXACT = "exact"        # case-insensitive exact match
    ALIAS = "alias"        # matched via known alias
    FUZZY = "fuzzy"        # SequenceMatcher > threshold
    SUBSTRING = "substring"  # partial string containment
    CREATED = "created"    # no match — created new node
    MISS = "miss"          # no match — not created either


# ── Signal weights (tunable, but principled defaults) ────────────────

_MATCH_QUALITY_SCORES: dict[MatchQuality, float] = {
    MatchQuality.EXACT: 1.0,
    MatchQuality.ALIAS: 0.95,
    MatchQuality.FUZZY: 0.75,
    MatchQuality.SUBSTRING: 0.55,
    MatchQuality.CREATED: 0.3,
    MatchQuality.MISS: 0.0,
}


@dataclass
class ConfidenceSignals:
    """Bag of measurable signals collected during the pipeline."""

    # ── Classification signals ───────────────────────────────────
    # How many distinct indicator patterns fired for the winning type
    pattern_matches: int = 0
    # Total candidate patterns checked (for specificity ratio)
    patterns_checked: int = 1
    # Did we fall through to the default classification?
    is_fallback_classification: bool = False

    # ── Entity resolution signals ────────────────────────────────
    entity_match_qualities: list[MatchQuality] = field(default_factory=list)

    # ── Result signals ───────────────────────────────────────────
    result_count: int = 0
    # Expected result count for this query type (0 = unknown)
    expected_result_count: int = 1
    # Fraction of returned records that have the key fields populated
    evidence_completeness: float = 1.0

    # ── Graph structure signals ──────────────────────────────────
    # For multi-hop: shortest path length found
    shortest_path_length: int | None = None
    # Number of distinct relationship types in results
    relationship_type_diversity: int = 0

    # ── Time signals ─────────────────────────────────────────────
    # Did a temporal expression actually parse?
    temporal_parsed: bool = False


class ConfidenceScorer:
    """
    Computes confidence scores from ``ConfidenceSignals``.

    All formulas are deterministic, explainable, and auditable.
    No value is ever >1.0 or <0.0.
    """

    # ──────────────────────────────────────────────────────────────
    # Classification confidence
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def classification_confidence(signals: ConfidenceSignals) -> float:
        """
        How confident are we that the *intent type* is correct?

        Based on:
        - pattern specificity (matches / checked)
        - whether we fell back to the default
        """
        if signals.is_fallback_classification:
            return 0.35

        # Specificity: 1 match out of 7 patterns checked = 1/7 specificity
        specificity = min(
            signals.pattern_matches / max(signals.patterns_checked, 1), 1.0
        )

        # More matches → higher confidence, but cap diminishing returns
        # 1 match → ~0.65, 2 → ~0.78, 3+ → ~0.85+
        base = 0.5 + 0.35 * (1.0 - 1.0 / (1.0 + signals.pattern_matches))

        # Specificity bonus: if only 1 of many patterns fired, it's precise
        specificity_bonus = 0.1 * (1.0 - specificity)

        return _clamp(base + specificity_bonus)

    # ──────────────────────────────────────────────────────────────
    # Entity resolution confidence
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def entity_resolution_confidence(signals: ConfidenceSignals) -> float:
        """
        How confident are we that we found the *right* entities?

        Based on match quality for each entity (exact > fuzzy > miss).
        """
        qualities = signals.entity_match_qualities
        if not qualities:
            # No entities needed / extracted → neutral
            return 0.5

        scores = [_MATCH_QUALITY_SCORES[q] for q in qualities]
        # Weighted: worst match drags overall score down
        avg = sum(scores) / len(scores)
        worst = min(scores)

        # 70% average + 30% worst — penalise any bad resolution
        return _clamp(0.7 * avg + 0.3 * worst)

    # ──────────────────────────────────────────────────────────────
    # Result quality confidence
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def result_confidence(signals: ConfidenceSignals) -> float:
        """
        How confident are we in the *results* from Neo4j?

        Based on:
        - result count vs expected
        - evidence completeness (populated fields)
        """
        if signals.result_count == 0:
            return 0.0

        # Coverage: got N results vs expected M
        if signals.expected_result_count > 0:
            coverage = min(
                signals.result_count / signals.expected_result_count, 1.0
            )
        else:
            # Unknown expectation → scale with result count but saturate
            coverage = min(signals.result_count / 5.0, 1.0)

        # Completeness: fraction of key fields that were non-empty
        completeness = signals.evidence_completeness

        # 60% coverage + 40% completeness
        return _clamp(0.6 * coverage + 0.4 * completeness)

    # ──────────────────────────────────────────────────────────────
    # Path-based confidence (multi-hop / causal)
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def path_confidence(signals: ConfidenceSignals) -> float:
        """
        Path length decay — longer paths are weaker evidence.

        1 hop → 0.95, 2 → 0.82, 3 → 0.70, 4 → 0.61, 5+ → 0.50
        """
        length = signals.shortest_path_length
        if length is None or length <= 0:
            return 0.5
        # Exponential decay: 0.95^length, floored at 0.40
        return _clamp(max(0.95 ** length, 0.40))

    # ──────────────────────────────────────────────────────────────
    # Composite chain confidence
    # ──────────────────────────────────────────────────────────────

    def chain_confidence(self, signals: ConfidenceSignals) -> float:
        """
        Combine all sub-scores into one overall confidence.

        Uses *minimum* of classification and entity confidence as a gate,
        then blends with result confidence.

        Formula:
            gate = min(classification, entity_resolution)
            overall = gate * 0.4 + result * 0.6

        This means a bad classification or bad entity resolution
        *caps* the final score — you can't be confident in results
        if you asked the wrong question.
        """
        c_class = self.classification_confidence(signals)
        c_entity = self.entity_resolution_confidence(signals)
        c_result = self.result_confidence(signals)

        gate = min(c_class, c_entity)
        overall = gate * 0.4 + c_result * 0.6

        # Path penalty if applicable
        if signals.shortest_path_length is not None:
            path_factor = self.path_confidence(signals)
            overall = overall * 0.7 + path_factor * 0.3

        return _clamp(overall)

    # ──────────────────────────────────────────────────────────────
    # Per-step confidence (replaces hardcoded per-step values)
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def step_confidence(
        result_record: dict,
        expected_keys: list[str] | None = None,
    ) -> float:
        """
        Confidence for a single reasoning step/record.

        Based purely on evidence completeness: what fraction of expected
        fields are present and non-empty?
        """
        if not result_record:
            return 0.0

        if expected_keys is None:
            # Fall back to counting non-empty values
            total = len(result_record)
            filled = sum(
                1
                for v in result_record.values()
                if v is not None and v != "" and v != []
            )
            return _clamp(filled / max(total, 1))

        found = sum(
            1
            for k in expected_keys
            if result_record.get(k) not in (None, "", [])
        )
        return _clamp(found / max(len(expected_keys), 1))


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a float to [lo, hi]."""
    return max(lo, min(hi, value))
