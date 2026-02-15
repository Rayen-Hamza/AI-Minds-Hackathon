"""Maps DecomposedQuery to Cypher templates and fills slots."""

from __future__ import annotations

from app.models.reasoning import DecomposedQuery, ReasoningType
from app.services.cypher_templates import CYPHER_TEMPLATES, CypherTemplate


class TemplateRouter:
    """Maps a ``DecomposedQuery`` to the best Cypher template(s) and fills slots."""

    def __init__(
        self,
        templates: dict[str, CypherTemplate] | None = None,
    ) -> None:
        self.templates = templates or CYPHER_TEMPLATES
        self.type_index: dict[ReasoningType, list[str]] = {}
        for name, tmpl in self.templates.items():
            self.type_index.setdefault(tmpl.reasoning_type, []).append(name)

    def route(self, query: DecomposedQuery) -> list[tuple[str, str]]:
        """
        Return a list of ``(template_name, rendered_cypher)`` pairs.

        May return multiple queries for complex reasoning types.
        """
        candidates = self.type_index.get(query.reasoning_type, [])
        results: list[tuple[str, str]] = []

        for tmpl_name in candidates:
            tmpl = self.templates[tmpl_name]
            slots = self._fill_slots(tmpl, query)
            if slots is not None:
                try:
                    cypher = tmpl.render(slots)
                    results.append((tmpl_name, cypher))
                except ValueError:
                    continue

        # Fallback: if nothing matched but we have entities, explore
        if not results and query.entities:
            fallback = self.templates.get("full_neighborhood")
            if fallback:
                slots = {"entity_name": query.entities[0]}
                results.append(("full_neighborhood", fallback.render(slots)))

        return results

    # ── Private helpers ──────────────────────────────────────────────

    def _fill_slots(
        self,
        template: CypherTemplate,
        query: DecomposedQuery,
    ) -> dict[str, object] | None:
        """Attempt to fill template slots from decomposed query data."""
        slots: dict[str, object] = {}

        for slot in template.required_slots:
            value = self._resolve_slot(slot, query)
            if value is None:
                return None
            slots[slot] = value

        # Optional defaults
        slots.setdefault("limit", 10)
        slots.setdefault("max_hops", query.hop_limit)

        return slots

    def _resolve_slot(
        self,
        slot_name: str,
        query: DecomposedQuery,
    ) -> str | None:
        """Map slot names to query data."""

        _FIRST_ENTITY_SLOTS = {
            "entity_name",
            "person_name",
            "topic_name",
            "search_term",
            "event_name",
            "entity_a",
            "topic_a",
        }
        _SECOND_ENTITY_SLOTS = {"entity_b", "topic_b"}

        if slot_name in _FIRST_ENTITY_SLOTS:
            return query.entities[0] if query.entities else None

        if slot_name in _SECOND_ENTITY_SLOTS:
            return query.entities[1] if len(query.entities) > 1 else None

        # Temporal
        if slot_name == "start_time" and query.time_range:
            return query.time_range[0].isoformat()
        if slot_name == "end_time" and query.time_range:
            return query.time_range[1].isoformat()

        # Node label — prefer spaCy-derived entity type if available
        if slot_name == "node_label":
            # 1. If entity_types were populated by spaCy, use the first one
            if query.entity_types:
                return query.entity_types[0]

            # 2. Fall back to keyword matching in entity text
            label_map = {
                "person": "Person",
                "people": "Person",
                "topic": "Topic",
                "topics": "Topic",
                "document": "Document",
                "documents": "Document",
                "project": "Project",
                "projects": "Project",
                "concept": "Concept",
                "concepts": "Concept",
                "organization": "Organization",
                "organizations": "Organization",
                "location": "Location",
                "locations": "Location",
                "event": "Event",
                "events": "Event",
            }
            for entity in query.entities:
                mapped = label_map.get(entity.lower())
                if mapped:
                    return mapped
            return "Topic"  # sensible default

        return None
