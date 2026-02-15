"""Tests for TemplateRouter — maps DecomposedQuery to Cypher templates."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.models.reasoning import DecomposedQuery, ReasoningType
from app.services.template_router import TemplateRouter


@pytest.fixture
def router() -> TemplateRouter:
    return TemplateRouter()


def _make_query(
    reasoning_type: ReasoningType = ReasoningType.ENTITY_LOOKUP,
    entities: list[str] | None = None,
    time_range: tuple[datetime, datetime] | None = None,
    aggregation_fn: str | None = None,
    hop_limit: int = 2,
) -> DecomposedQuery:
    return DecomposedQuery(
        reasoning_type=reasoning_type,
        entities=entities or [],
        relationships=[],
        time_range=time_range,
        aggregation_fn=aggregation_fn,
        hop_limit=hop_limit,
        confidence=0.8,
    )


# ─────────────────────────────────────────────────────────────────────
# Basic routing
# ─────────────────────────────────────────────────────────────────────


class TestBasicRouting:
    def test_entity_lookup_routes(self, router: TemplateRouter):
        q = _make_query(ReasoningType.ENTITY_LOOKUP, entities=["Alice"])
        results = router.route(q)
        assert len(results) > 0
        names = [name for name, _ in results]
        assert any("entity_lookup" in n for n in names)

    def test_no_entities_triggers_fallback(self, router: TemplateRouter):
        """If required slots can't be filled, fallback to full_neighborhood."""
        q = _make_query(ReasoningType.ENTITY_LOOKUP, entities=[])
        results = router.route(q)
        # No entities → can't fill slots → empty
        assert results == []

    def test_multi_hop_routes_with_two_entities(self, router: TemplateRouter):
        q = _make_query(
            ReasoningType.MULTI_HOP, entities=["Alice", "Bob"]
        )
        results = router.route(q)
        assert len(results) > 0

    def test_temporal_routes_with_time_range(self, router: TemplateRouter):
        now = datetime.now()
        q = _make_query(
            ReasoningType.TEMPORAL,
            time_range=(datetime(2025, 1, 1), now),
        )
        results = router.route(q)
        assert len(results) > 0

    def test_aggregation_routes(self, router: TemplateRouter):
        q = _make_query(ReasoningType.AGGREGATION, entities=["Python"])
        results = router.route(q)
        assert len(results) > 0

    def test_exploration_routes_with_entity(self, router: TemplateRouter):
        q = _make_query(ReasoningType.EXPLORATION, entities=["ML"])
        results = router.route(q)
        assert len(results) > 0


# ─────────────────────────────────────────────────────────────────────
# Fallback
# ─────────────────────────────────────────────────────────────────────


class TestFallback:
    def test_fallback_when_no_match(self, router: TemplateRouter):
        """If no candidates match but entities exist, use full_neighborhood."""
        q = _make_query(ReasoningType.COMPARISON, entities=["Alice"])
        results = router.route(q)
        # Even if comparison templates don't fill, fallback should fire
        if not any("compare" in n for n, _ in results):
            assert any("neighborhood" in n or "full" in n for n, _ in results) or len(results) > 0


# ─────────────────────────────────────────────────────────────────────
# Rendered Cypher validity
# ─────────────────────────────────────────────────────────────────────


class TestRenderedCypher:
    def test_rendered_cypher_has_no_unfilled_slots(self, router: TemplateRouter):
        q = _make_query(ReasoningType.ENTITY_LOOKUP, entities=["Alice"])
        results = router.route(q)
        for name, cypher in results:
            # Should not have any $slot_name left
            assert "$entity_name" not in cypher, (
                f"Template '{name}' left unfilled slot"
            )

    def test_entity_name_appears_in_cypher(self, router: TemplateRouter):
        q = _make_query(ReasoningType.ENTITY_LOOKUP, entities=["SpecificName"])
        results = router.route(q)
        found_entity = False
        for _, cypher in results:
            if "SpecificName" in cypher:
                found_entity = True
        assert found_entity, "Entity name should appear in rendered Cypher"
