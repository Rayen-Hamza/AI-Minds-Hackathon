"""Deterministic entity resolution — no LLM required."""

from __future__ import annotations

import logging
import uuid
from difflib import SequenceMatcher

from neo4j import Driver

from app.services.confidence import MatchQuality

logger = logging.getLogger(__name__)

# Minimum string length for substring matching to avoid noise
_MIN_SUBSTRING_LEN = 3
# Minimum SequenceMatcher ratio to accept a fuzzy match
_FUZZY_THRESHOLD = 0.85


class EntityResolver:
    """
    Resolves text mentions to canonical graph nodes using
    exact, alias, fuzzy, and substring matching.

    All matching runs against an in-memory cache loaded from Neo4j
    at startup (and refreshable on demand).
    """

    def __init__(self, driver: Driver) -> None:
        self.driver = driver
        self._entity_cache: dict[str, dict] = {}

    # ── Cache Management ─────────────────────────────────────────────

    def refresh_cache(self) -> None:
        """(Re)load all entity names + aliases into memory."""
        self._entity_cache.clear()

        with self.driver.session() as session:
            # Persons — include aliases
            result = session.run(
                "MATCH (p:Person) "
                "RETURN p.id AS id, p.canonical_name AS name, "
                "       p.aliases AS aliases, 'Person' AS label"
            )
            for record in result:
                name = record["name"]
                if not name:
                    continue
                entry = {
                    "id": record["id"],
                    "name": name,
                    "label": record["label"],
                }
                self._entity_cache[name.lower()] = entry
                for alias in record["aliases"] or []:
                    self._entity_cache[alias.lower()] = entry

            # Simple-name labels
            for label in (
                "Topic",
                "Concept",
                "Organization",
                "Project",
                "Event",
                "Location",
            ):
                result = session.run(
                    f"MATCH (n:{label}) "
                    f"RETURN n.id AS id, n.name AS name, '{label}' AS label"
                )
                for record in result:
                    name = record["name"]
                    if name:
                        self._entity_cache[name.lower()] = {
                            "id": record["id"],
                            "name": name,
                            "label": record["label"],
                        }

        logger.info(
            "EntityResolver cache refreshed: %d entries",
            len(self._entity_cache),
        )

    # ── Resolution ───────────────────────────────────────────────────

    def resolve(self, mention: str, expected_label: str | None = None) -> dict | None:
        """Resolve a text mention to a graph entity (backward compat)."""
        entity, _ = self.resolve_with_quality(mention, expected_label=expected_label)
        return entity

    def resolve_with_quality(
        self,
        mention: str,
        *,
        expected_label: str | None = None,
    ) -> tuple[dict | None, MatchQuality]:
        """
        Resolve a text mention to a graph entity **and** report how
        strong the match was.

        Args:
            mention: The text mention to resolve.
            expected_label: If provided (e.g. ``"Person"``), prefer cache
                entries whose ``label`` matches.  An exact-name match on the
                wrong label still succeeds, but a fuzzy/substring match is
                skipped if a better-typed candidate exists.

        Returns:
            ``(entity_dict, MatchQuality)`` — entity is ``None`` on miss.
        """
        mention_lower = mention.lower().strip()
        if not mention_lower:
            return None, MatchQuality.MISS

        # 1. Exact / alias match
        hit = self._entity_cache.get(mention_lower)
        if hit is not None:
            return hit, MatchQuality.EXACT

        # 2. Fuzzy match — optionally prefer same-label candidates
        best_match: dict | None = None
        best_score = 0.0
        for cached_name, entity in self._entity_cache.items():
            score = SequenceMatcher(None, mention_lower, cached_name).ratio()
            if score <= _FUZZY_THRESHOLD:
                continue
            # Type-aware boost: same label gets +0.05 bonus
            if expected_label and entity.get("label") == expected_label:
                score = min(score + 0.05, 1.0)
            if score > best_score:
                best_score = score
                best_match = entity

        if best_match is not None:
            self._entity_cache[mention_lower] = best_match
            return best_match, MatchQuality.FUZZY

        # 3. Substring match — prefer same-label candidates
        if len(mention_lower) >= _MIN_SUBSTRING_LEN:
            typed_hit: dict | None = None
            untyped_hit: dict | None = None
            for cached_name, entity in self._entity_cache.items():
                if mention_lower in cached_name or cached_name in mention_lower:
                    if expected_label and entity.get("label") == expected_label:
                        typed_hit = entity
                        break  # best possible substring
                    if untyped_hit is None:
                        untyped_hit = entity
            substring_hit = typed_hit or untyped_hit
            if substring_hit is not None:
                return substring_hit, MatchQuality.SUBSTRING

        return None, MatchQuality.MISS

    def resolve_or_create(
        self,
        mention: str,
        label: str = "Topic",
        properties: dict | None = None,
    ) -> str:
        """Resolve to existing entity or create a new one.  Returns entity id."""
        existing = self.resolve(mention)
        if existing:
            return existing["id"]

        new_id = str(uuid.uuid4())
        props = dict(properties) if properties else {}
        props["id"] = new_id
        props["name"] = mention
        props["mention_count"] = 1
        # Person nodes use canonical_name as primary name field
        if label == "Person":
            props["canonical_name"] = mention

        with self.driver.session() as session:
            session.run(f"CREATE (n:{label} $props)", props=props)

        self._entity_cache[mention.lower()] = {
            "id": new_id,
            "name": mention,
            "label": label,
        }
        return new_id
