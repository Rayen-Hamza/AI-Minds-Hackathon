"""Tests for CypherTemplate rendering and the template library."""

from __future__ import annotations

import pytest

from app.models.reasoning import ReasoningType
from app.services.cypher_templates import CYPHER_TEMPLATES, CypherTemplate


# ─────────────────────────────────────────────────────────────────────
# CypherTemplate rendering
# ─────────────────────────────────────────────────────────────────────


class TestCypherTemplateRender:
    def test_render_simple(self):
        tmpl = CypherTemplate(
            template="MATCH (n:Person {name: '$name'}) RETURN n",
            required_slots=["name"],
            reasoning_type=ReasoningType.ENTITY_LOOKUP,
        )
        result = tmpl.render({"name": "Alice"})
        assert "Alice" in result
        assert "$name" not in result

    def test_missing_slot_raises(self):
        tmpl = CypherTemplate(
            template="MATCH (n {name: '$name'}) RETURN n",
            required_slots=["name"],
            reasoning_type=ReasoningType.ENTITY_LOOKUP,
        )
        with pytest.raises(ValueError, match="Missing slots"):
            tmpl.render({})

    def test_sanitizes_quotes(self):
        tmpl = CypherTemplate(
            template="MATCH (n {name: '$name'}) RETURN n",
            required_slots=["name"],
            reasoning_type=ReasoningType.ENTITY_LOOKUP,
        )
        result = tmpl.render({"name": "O'Brien"})
        assert "\\'" in result  # escaped

    def test_extra_slots_ignored(self):
        tmpl = CypherTemplate(
            template="MATCH (n {name: '$name'}) RETURN n",
            required_slots=["name"],
            reasoning_type=ReasoningType.ENTITY_LOOKUP,
        )
        result = tmpl.render({"name": "Alice", "extra": "ignored"})
        assert "Alice" in result

    def test_non_string_slot(self):
        tmpl = CypherTemplate(
            template="MATCH (n) RETURN n LIMIT $limit",
            required_slots=["limit"],
            reasoning_type=ReasoningType.AGGREGATION,
        )
        result = tmpl.render({"limit": 10})
        assert "10" in result


# ─────────────────────────────────────────────────────────────────────
# Template Library Integrity
# ─────────────────────────────────────────────────────────────────────


class TestTemplateLibrary:
    def test_all_templates_have_valid_reasoning_type(self):
        for name, tmpl in CYPHER_TEMPLATES.items():
            assert isinstance(tmpl.reasoning_type, ReasoningType), (
                f"Template '{name}' has invalid reasoning_type"
            )

    def test_all_templates_have_required_slots(self):
        for name, tmpl in CYPHER_TEMPLATES.items():
            assert isinstance(tmpl.required_slots, list), (
                f"Template '{name}' required_slots should be a list"
            )

    def test_all_templates_contain_cypher(self):
        """Templates should have at least MATCH or CALL."""
        for name, tmpl in CYPHER_TEMPLATES.items():
            upper = tmpl.template.upper()
            assert "MATCH" in upper or "CALL" in upper or "RETURN" in upper, (
                f"Template '{name}' doesn't look like valid Cypher"
            )

    def test_entity_lookup_templates_exist(self):
        assert "entity_lookup_person" in CYPHER_TEMPLATES
        assert "entity_lookup_topic" in CYPHER_TEMPLATES
        assert "entity_lookup_document" in CYPHER_TEMPLATES

    def test_all_reasoning_types_covered(self):
        """Every ReasoningType should have at least one template."""
        covered = {tmpl.reasoning_type for tmpl in CYPHER_TEMPLATES.values()}
        for rt in ReasoningType:
            assert rt in covered, f"No template for {rt.value}"

    def test_slot_placeholders_match_required(self):
        """Every required slot should appear as $slot in the template."""
        for name, tmpl in CYPHER_TEMPLATES.items():
            for slot in tmpl.required_slots:
                assert f"${slot}" in tmpl.template, (
                    f"Template '{name}' requires slot '{slot}' "
                    f"but '${ slot }' not found in template body"
                )
