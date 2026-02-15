"""Tests for ConfidenceScorer — the algorithmic confidence engine."""

from __future__ import annotations

import pytest

from app.services.confidence import (
    ConfidenceScorer,
    ConfidenceSignals,
    MatchQuality,
    _clamp,
)


# ─────────────────────────────────────────────────────────────────────
# _clamp
# ─────────────────────────────────────────────────────────────────────


class TestClamp:
    def test_within_range(self):
        assert _clamp(0.5) == 0.5

    def test_below_floor(self):
        assert _clamp(-0.3) == 0.0

    def test_above_ceiling(self):
        assert _clamp(1.7) == 1.0

    def test_exact_boundaries(self):
        assert _clamp(0.0) == 0.0
        assert _clamp(1.0) == 1.0

    def test_custom_range(self):
        assert _clamp(0.2, lo=0.3, hi=0.8) == 0.3
        assert _clamp(0.9, lo=0.3, hi=0.8) == 0.8
        assert _clamp(0.5, lo=0.3, hi=0.8) == 0.5


# ─────────────────────────────────────────────────────────────────────
# Classification confidence
# ─────────────────────────────────────────────────────────────────────


class TestClassificationConfidence:
    scorer = ConfidenceScorer()

    def test_fallback_is_low(self):
        signals = ConfidenceSignals(is_fallback_classification=True)
        score = self.scorer.classification_confidence(signals)
        assert score == 0.35

    def test_single_pattern_match(self):
        signals = ConfidenceSignals(pattern_matches=1, patterns_checked=30)
        score = self.scorer.classification_confidence(signals)
        # 1 match → base ≈ 0.675, specificity bonus ≈ 0.097 → ~0.77
        assert 0.6 < score < 0.85

    def test_many_patterns_higher_than_one(self):
        s1 = ConfidenceSignals(pattern_matches=1, patterns_checked=30)
        s3 = ConfidenceSignals(pattern_matches=3, patterns_checked=30)
        assert self.scorer.classification_confidence(s3) > self.scorer.classification_confidence(s1)

    def test_result_always_between_0_and_1(self):
        for matches in range(0, 50):
            signals = ConfidenceSignals(
                pattern_matches=matches, patterns_checked=30
            )
            score = self.scorer.classification_confidence(signals)
            assert 0.0 <= score <= 1.0

    def test_zero_matches_non_fallback(self):
        signals = ConfidenceSignals(
            pattern_matches=0,
            patterns_checked=30,
            is_fallback_classification=False,
        )
        score = self.scorer.classification_confidence(signals)
        # base = 0.5 + 0.35*(1 - 1/(1+0)) = 0.5, + specificity_bonus 0.1
        assert 0.5 <= score <= 0.7


# ─────────────────────────────────────────────────────────────────────
# Entity resolution confidence
# ─────────────────────────────────────────────────────────────────────


class TestEntityResolutionConfidence:
    scorer = ConfidenceScorer()

    def test_no_entities_neutral(self):
        signals = ConfidenceSignals(entity_match_qualities=[])
        assert self.scorer.entity_resolution_confidence(signals) == 0.5

    def test_all_exact_is_highest(self):
        signals = ConfidenceSignals(
            entity_match_qualities=[MatchQuality.EXACT, MatchQuality.EXACT]
        )
        score = self.scorer.entity_resolution_confidence(signals)
        assert score == 1.0

    def test_all_miss_is_zero(self):
        signals = ConfidenceSignals(
            entity_match_qualities=[MatchQuality.MISS, MatchQuality.MISS]
        )
        score = self.scorer.entity_resolution_confidence(signals)
        assert score == 0.0

    def test_fuzzy_lower_than_exact(self):
        exact = ConfidenceSignals(
            entity_match_qualities=[MatchQuality.EXACT]
        )
        fuzzy = ConfidenceSignals(
            entity_match_qualities=[MatchQuality.FUZZY]
        )
        assert self.scorer.entity_resolution_confidence(exact) > \
               self.scorer.entity_resolution_confidence(fuzzy)

    def test_one_miss_drags_score_down(self):
        """A single miss among exacts should hurt significantly."""
        all_exact = ConfidenceSignals(
            entity_match_qualities=[MatchQuality.EXACT, MatchQuality.EXACT]
        )
        one_miss = ConfidenceSignals(
            entity_match_qualities=[MatchQuality.EXACT, MatchQuality.MISS]
        )
        score_all = self.scorer.entity_resolution_confidence(all_exact)
        score_miss = self.scorer.entity_resolution_confidence(one_miss)
        assert score_all - score_miss > 0.3  # worst-match penalty bites

    def test_ordering_exact_gt_alias_gt_fuzzy_gt_substring_gt_created_gt_miss(self):
        qualities = [
            MatchQuality.EXACT,
            MatchQuality.ALIAS,
            MatchQuality.FUZZY,
            MatchQuality.SUBSTRING,
            MatchQuality.CREATED,
            MatchQuality.MISS,
        ]
        scores = [
            self.scorer.entity_resolution_confidence(
                ConfidenceSignals(entity_match_qualities=[q])
            )
            for q in qualities
        ]
        for i in range(len(scores) - 1):
            assert scores[i] > scores[i + 1], (
                f"{qualities[i].value} ({scores[i]}) should be > "
                f"{qualities[i+1].value} ({scores[i+1]})"
            )


# ─────────────────────────────────────────────────────────────────────
# Result confidence
# ─────────────────────────────────────────────────────────────────────


class TestResultConfidence:
    scorer = ConfidenceScorer()

    def test_zero_results(self):
        signals = ConfidenceSignals(result_count=0, expected_result_count=5)
        assert self.scorer.result_confidence(signals) == 0.0

    def test_full_coverage_full_completeness(self):
        signals = ConfidenceSignals(
            result_count=5,
            expected_result_count=5,
            evidence_completeness=1.0,
        )
        assert self.scorer.result_confidence(signals) == 1.0

    def test_partial_coverage(self):
        signals = ConfidenceSignals(
            result_count=2,
            expected_result_count=10,
            evidence_completeness=1.0,
        )
        score = self.scorer.result_confidence(signals)
        # coverage = 2/10 = 0.2 → 0.6*0.2 + 0.4*1.0 = 0.52
        assert 0.5 <= score <= 0.55

    def test_low_completeness(self):
        signals = ConfidenceSignals(
            result_count=5,
            expected_result_count=5,
            evidence_completeness=0.3,
        )
        score = self.scorer.result_confidence(signals)
        # 0.6*1.0 + 0.4*0.3 = 0.72
        assert 0.7 <= score <= 0.75

    def test_over_delivery_capped(self):
        """Getting more results than expected should not exceed 1.0."""
        signals = ConfidenceSignals(
            result_count=100,
            expected_result_count=5,
            evidence_completeness=1.0,
        )
        score = self.scorer.result_confidence(signals)
        assert score <= 1.0


# ─────────────────────────────────────────────────────────────────────
# Path confidence
# ─────────────────────────────────────────────────────────────────────


class TestPathConfidence:
    scorer = ConfidenceScorer()

    def test_none_path_length(self):
        signals = ConfidenceSignals(shortest_path_length=None)
        assert self.scorer.path_confidence(signals) == 0.5

    def test_zero_path_length(self):
        signals = ConfidenceSignals(shortest_path_length=0)
        assert self.scorer.path_confidence(signals) == 0.5

    def test_one_hop_high(self):
        signals = ConfidenceSignals(shortest_path_length=1)
        score = self.scorer.path_confidence(signals)
        assert score == pytest.approx(0.95, abs=0.01)

    def test_decay_with_hops(self):
        scores = []
        for hops in range(1, 6):
            s = ConfidenceSignals(shortest_path_length=hops)
            scores.append(self.scorer.path_confidence(s))
        # Monotonically decreasing
        for i in range(len(scores) - 1):
            assert scores[i] > scores[i + 1]

    def test_floor_at_040(self):
        signals = ConfidenceSignals(shortest_path_length=100)
        assert self.scorer.path_confidence(signals) >= 0.40


# ─────────────────────────────────────────────────────────────────────
# Chain confidence (composite)
# ─────────────────────────────────────────────────────────────────────


class TestChainConfidence:
    scorer = ConfidenceScorer()

    def test_zero_results_zero_confidence(self):
        signals = ConfidenceSignals(
            pattern_matches=3,
            patterns_checked=30,
            entity_match_qualities=[MatchQuality.EXACT],
            result_count=0,
        )
        score = self.scorer.chain_confidence(signals)
        # result_confidence = 0 → overall = gate * 0.4 ≈ 0.34
        # Gate stays nonzero because classification + entity were good
        assert score < 0.4

    def test_everything_perfect(self):
        signals = ConfidenceSignals(
            pattern_matches=3,
            patterns_checked=30,
            entity_match_qualities=[MatchQuality.EXACT],
            result_count=5,
            expected_result_count=5,
            evidence_completeness=1.0,
        )
        score = self.scorer.chain_confidence(signals)
        assert score > 0.7

    def test_bad_classification_caps_score(self):
        """Even with perfect results, bad classification limits confidence."""
        good_class = ConfidenceSignals(
            pattern_matches=3,
            patterns_checked=30,
            result_count=5,
            expected_result_count=5,
            evidence_completeness=1.0,
        )
        bad_class = ConfidenceSignals(
            is_fallback_classification=True,
            result_count=5,
            expected_result_count=5,
            evidence_completeness=1.0,
        )
        assert self.scorer.chain_confidence(good_class) > \
               self.scorer.chain_confidence(bad_class)

    def test_bad_entity_caps_score(self):
        """Even with perfect results, missed entities limit confidence."""
        good_entity = ConfidenceSignals(
            pattern_matches=2,
            patterns_checked=30,
            entity_match_qualities=[MatchQuality.EXACT],
            result_count=5,
            expected_result_count=5,
            evidence_completeness=1.0,
        )
        bad_entity = ConfidenceSignals(
            pattern_matches=2,
            patterns_checked=30,
            entity_match_qualities=[MatchQuality.MISS],
            result_count=5,
            expected_result_count=5,
            evidence_completeness=1.0,
        )
        assert self.scorer.chain_confidence(good_entity) > \
               self.scorer.chain_confidence(bad_entity)

    def test_path_penalty_applied(self):
        short = ConfidenceSignals(
            pattern_matches=2,
            patterns_checked=30,
            result_count=3,
            expected_result_count=3,
            evidence_completeness=1.0,
            shortest_path_length=1,
        )
        long = ConfidenceSignals(
            pattern_matches=2,
            patterns_checked=30,
            result_count=3,
            expected_result_count=3,
            evidence_completeness=1.0,
            shortest_path_length=5,
        )
        assert self.scorer.chain_confidence(short) > \
               self.scorer.chain_confidence(long)

    def test_always_between_0_and_1(self):
        combos = [
            ConfidenceSignals(),
            ConfidenceSignals(
                pattern_matches=100,
                entity_match_qualities=[MatchQuality.EXACT] * 10,
                result_count=1000,
                expected_result_count=1,
            ),
            ConfidenceSignals(
                is_fallback_classification=True,
                entity_match_qualities=[MatchQuality.MISS],
                result_count=0,
            ),
        ]
        for sig in combos:
            score = self.scorer.chain_confidence(sig)
            assert 0.0 <= score <= 1.0


# ─────────────────────────────────────────────────────────────────────
# Step confidence
# ─────────────────────────────────────────────────────────────────────


class TestStepConfidence:
    scorer = ConfidenceScorer()

    def test_empty_record(self):
        assert self.scorer.step_confidence({}) == 0.0

    def test_all_filled(self):
        record = {"name": "Alice", "role": "engineer", "email": "a@b.com"}
        assert self.scorer.step_confidence(record) == 1.0

    def test_partial_fill(self):
        record = {"name": "Alice", "role": "", "email": None}
        score = self.scorer.step_confidence(record)
        assert score == pytest.approx(1 / 3, abs=0.01)

    def test_with_expected_keys(self):
        record = {"name": "Alice", "role": "eng"}
        score = self.scorer.step_confidence(
            record, expected_keys=["name", "role", "email"]
        )
        assert score == pytest.approx(2 / 3, abs=0.01)

    def test_empty_list_counts_as_missing(self):
        record = {"items": [], "name": "X"}
        score = self.scorer.step_confidence(record)
        assert score == pytest.approx(0.5, abs=0.01)
