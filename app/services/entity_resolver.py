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
            for label in ("Topic", "Concept", "Organization", "Project",
                          "Event", "Location"):
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

    def resolve(self, mention: str) -> dict | None:
        """Resolve a text mention to a graph entity (backward compat)."""
        entity, _ = self.resolve_with_quality(mention)
        return entity

    def resolve_with_quality(
        self, mention: str
    ) -> tuple[dict | None, MatchQuality]:
        """
        Resolve a text mention to a graph entity **and** report how
        strong the match was.

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

        # 2. Fuzzy match
        best_match: dict | None = None
        best_score = 0.0
        for cached_name, entity in self._entity_cache.items():
            score = SequenceMatcher(
                None, mention_lower, cached_name
            ).ratio()
            if score > best_score and score > _FUZZY_THRESHOLD:
                best_score = score
                best_match = entity

        if best_match is not None:
            self._entity_cache[mention_lower] = best_match
            return best_match, MatchQuality.FUZZY

        # 3. Substring match
        if len(mention_lower) >= _MIN_SUBSTRING_LEN:
            for cached_name, entity in self._entity_cache.items():
                if (
                    mention_lower in cached_name
                    or cached_name in mention_lower
                ):
                    return entity, MatchQuality.SUBSTRING

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

        with self.driver.session() as session:
            session.run(f"CREATE (n:{label} $props)", props=props)

        self._entity_cache[mention.lower()] = {
            "id": new_id,
            "name": mention,
            "label": label,
        }
        return new_id
