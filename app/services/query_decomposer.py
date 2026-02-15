"""Rule-based query decomposition engine. No LLM required — runs in <5ms."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from app.models.reasoning import DecomposedQuery, ReasoningType
from app.services.confidence import ConfidenceScorer, ConfidenceSignals
from app.services.label_mapping import TypedEntity

logger = logging.getLogger(__name__)

# ── Lazy spaCy loader (graceful degradation) ─────────────────────────

_spacy_extractor = None  # type: ignore[assignment]
_spacy_attempted = False


def _get_spacy_extractor():
    """Return the global ``EntityExtractor`` or ``None`` if unavailable."""
    global _spacy_extractor, _spacy_attempted
    if _spacy_attempted:
        return _spacy_extractor
    _spacy_attempted = True
    try:
        from app.services.processing.entity_extractor import get_entity_extractor

        _spacy_extractor = get_entity_extractor()
        # Force model load so we catch errors early
        _ = _spacy_extractor.nlp
        logger.info("QueryDecomposer: spaCy NER available")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "QueryDecomposer: spaCy NER unavailable (%s), using regex fallback", exc
        )
        _spacy_extractor = None
    return _spacy_extractor


class QueryDecomposer:
    """
    Rule-based + pattern classifier for query intent.

    Decomposes a natural-language query into a structured
    ``DecomposedQuery`` that the template router can map to Cypher.
    """

    # ── Pattern Definitions ──────────────────────────────────────────

    TEMPORAL_PATTERNS: list[tuple[str, str]] = [
        (
            r"last\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            "day_of_week",
        ),
        (r"last\s+(week|month|year)", "relative_period"),
        (r"yesterday", "yesterday"),
        (r"today", "today"),
        (r"(\d{4}-\d{2}-\d{2})", "iso_date"),
        (
            r"(january|february|march|april|may|june|july|august|september"
            r"|october|november|december)\s+\d{4}",
            "month_year",
        ),
        (r"(\d+)\s+(days?|weeks?|months?|hours?)\s+ago", "relative_ago"),
        (r"between\s+(.+)\s+and\s+(.+)", "range"),
        (r"since\s+(.+)", "since"),
        (r"before\s+(.+)", "before"),
    ]

    AGGREGATION_KEYWORDS: dict[str, str] = {
        "how many": "count",
        "count": "count",
        "total": "sum",
        "average": "avg",
        "most": "max",
        "least": "min",
        "top": "max",
        "bottom": "min",
        "frequently": "count",
        "often": "count",
    }

    RELATIONSHIP_KEYWORDS: list[str] = [
        "related to",
        "connected to",
        "associated with",
        "linked to",
        "about",
        "mentions",
        "involves",
        "works on",
        "worked on",
        "belongs to",
        "part of",
    ]

    MULTI_HOP_INDICATORS: list[str] = [
        r"how does .* connect to",
        r"what's the relationship between .* and",
        r"how are .* and .* related",
        r"path from .* to",
        r"connection between",
        r"link between .* and",
    ]

    CAUSAL_INDICATORS: list[str] = [
        r"why did",
        r"what caused",
        r"what led to",
        r"reason for",
        r"because of what",
        r"what triggered",
        r"how did .* start",
    ]

    EXPLORATION_INDICATORS: list[str] = [
        r"what's related to",
        r"explore",
        r"show me everything about",
        r"what do I know about",
        r"tell me about",
        r"what's connected to",
        r"neighborhood of",
    ]

    # Non-entity capitalised words to ignore
    _COMMON_NON_ENTITIES = frozenset(
        {
            "i",
            "the",
            "a",
            "an",
            "my",
            "what",
            "how",
            "who",
            "where",
            "when",
            "why",
            "which",
            "is",
            "are",
            "was",
            "were",
            "do",
            "does",
            "did",
            "can",
            "could",
            "will",
            "would",
            "should",
            "have",
            "has",
            "had",
            "been",
            "being",
            "it",
            "its",
            "this",
            "that",
            "these",
            "those",
            "and",
            "or",
            "but",
            "not",
            "no",
            "yes",
            "to",
            "of",
            "in",
            "on",
            "at",
            "for",
            "with",
            "from",
            "by",
            "about",
            "between",
            "through",
            "after",
            "before",
            "during",
            "all",
            "each",
            "any",
            "some",
            "more",
            "most",
            "much",
            "many",
            "show",
            "find",
            "get",
            "me",
            "tell",
        }
    )

    # ── Public API ───────────────────────────────────────────────────

    def decompose(self, query: str) -> DecomposedQuery:
        """Decompose a natural-language query into structured intent."""
        query_lower = query.lower().strip()

        time_range = self._extract_time_range(query_lower)
        agg_fn = self._detect_aggregation(query_lower)

        # Try spaCy first — typed entities with Neo4j labels
        typed_entities = self._extract_entities_spacy(query)
        if typed_entities:
            entities = [te.text for te in typed_entities]
            entity_types = [te.neo4j_label for te in typed_entities]
        else:
            entities = self._extract_entities(query)
            entity_types = []

        reasoning_type, confidence = self._classify_intent(
            query_lower, time_range, agg_fn, entities
        )
        hop_limit = self._estimate_hop_limit(reasoning_type)
        relationships = self._extract_relationships(query_lower)

        return DecomposedQuery(
            reasoning_type=reasoning_type,
            entities=entities,
            relationships=relationships,
            time_range=time_range,
            aggregation_fn=agg_fn,
            hop_limit=hop_limit,
            confidence=confidence,
            entity_types=entity_types,
        )

    # ── Private helpers ──────────────────────────────────────────────

    def _classify_intent(
        self,
        query: str,
        time_range: tuple[datetime, datetime] | None,
        agg_fn: str | None,
        entities: list[str],
    ) -> tuple[ReasoningType, float]:
        """Priority-ordered intent classification with algorithmic confidence."""
        scorer = ConfidenceScorer()
        signals = ConfidenceSignals()

        # Count total patterns checked for specificity
        total_patterns = (
            len(self.CAUSAL_INDICATORS)
            + len(self.MULTI_HOP_INDICATORS)
            + len(self.EXPLORATION_INDICATORS)
            + len(self.RELATIONSHIP_KEYWORDS)
        )
        signals.patterns_checked = total_patterns

        # Count causal matches
        causal_hits = sum(1 for p in self.CAUSAL_INDICATORS if re.search(p, query))
        if causal_hits:
            signals.pattern_matches = causal_hits
            return ReasoningType.CAUSAL, scorer.classification_confidence(signals)

        # Count multi-hop matches
        multi_hop_hits = sum(
            1 for p in self.MULTI_HOP_INDICATORS if re.search(p, query)
        )
        if multi_hop_hits:
            signals.pattern_matches = multi_hop_hits
            return ReasoningType.MULTI_HOP, scorer.classification_confidence(signals)

        if time_range and not agg_fn:
            signals.pattern_matches = 1
            signals.temporal_parsed = True
            return ReasoningType.TEMPORAL, scorer.classification_confidence(signals)

        if agg_fn:
            signals.pattern_matches = 1
            if len(entities) >= 2:
                return ReasoningType.COMPARISON, scorer.classification_confidence(
                    signals
                )
            return ReasoningType.AGGREGATION, scorer.classification_confidence(signals)

        # Count exploration matches
        explore_hits = sum(
            1 for p in self.EXPLORATION_INDICATORS if re.search(p, query)
        )
        if explore_hits:
            signals.pattern_matches = explore_hits
            return ReasoningType.EXPLORATION, scorer.classification_confidence(signals)

        # Count relationship keyword matches
        rel_hits = sum(1 for kw in self.RELATIONSHIP_KEYWORDS if kw in query)
        if rel_hits:
            signals.pattern_matches = rel_hits
            return ReasoningType.RELATIONSHIP, scorer.classification_confidence(signals)

        if entities:
            # Entity found but no specific intent pattern → entity lookup
            signals.pattern_matches = 0
            signals.is_fallback_classification = False
            return ReasoningType.ENTITY_LOOKUP, scorer.classification_confidence(
                signals
            )

        # True fallback — nothing matched
        signals.is_fallback_classification = True
        return ReasoningType.EXPLORATION, scorer.classification_confidence(signals)

    def _extract_entities(self, query: str) -> list[str]:
        """
        Lightweight NER:
        1. Quoted strings
        2. Capitalised word sequences (proper nouns)
        """
        entities: list[str] = []

        # Quoted strings — highest confidence
        quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', query)
        for match in quoted:
            entities.append(match[0] or match[1])

        # Capitalised sequences (skip sentence-initial position)
        words = query.split()
        i = 0
        while i < len(words):
            word = words[i]
            if not word:
                i += 1
                continue
            if i > 0 and word[0].isupper():
                entity_parts = [word]
                j = i + 1
                while j < len(words) and words[j] and words[j][0].isupper():
                    entity_parts.append(words[j])
                    j += 1
                entity = " ".join(entity_parts).rstrip("?!.,;:")
                if entity and entity.lower() not in self._COMMON_NON_ENTITIES:
                    entities.append(entity)
                i = j
            else:
                i += 1

        return entities

    def _extract_entities_spacy(self, query: str) -> list[TypedEntity]:
        """Extract entities via spaCy NER, returning typed entities.

        Returns an empty list if spaCy is unavailable — caller will
        fall back to the regex-based ``_extract_entities``.
        """
        extractor = _get_spacy_extractor()
        if extractor is None:
            return []

        try:
            labeled = extractor.extract_entities_with_labels(query)
        except Exception:  # noqa: BLE001
            logger.debug("spaCy extraction failed, falling back to regex")
            return []

        if not labeled:
            return []

        # De-duplicate while preserving order
        seen: set[str] = set()
        result: list[TypedEntity] = []
        for ent in labeled:
            key = ent["text"].lower()
            if key in seen or key in self._COMMON_NON_ENTITIES:
                continue
            seen.add(key)
            te = TypedEntity.from_spacy(ent["text"], ent["label"])
            if te is not None:
                result.append(te)

        return result

    def _extract_time_range(self, query: str) -> tuple[datetime, datetime] | None:
        """Parse temporal expressions into ``(start, end)`` tuples."""
        now = datetime.now()

        for pattern, ptype in self.TEMPORAL_PATTERNS:
            match = re.search(pattern, query)
            if not match:
                continue

            if ptype == "yesterday":
                start = (now - timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                end = start.replace(hour=23, minute=59, second=59)
                return (start, end)

            if ptype == "today":
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end = now.replace(hour=23, minute=59, second=59)
                return (start, end)

            if ptype == "relative_period":
                period = match.group(1)
                deltas = {
                    "week": timedelta(weeks=1),
                    "month": timedelta(days=30),
                    "year": timedelta(days=365),
                }
                return (now - deltas.get(period, timedelta(weeks=1)), now)

            if ptype == "relative_ago":
                amount = int(match.group(1))
                unit = match.group(2).rstrip("s")
                delta_map = {
                    "day": timedelta(days=amount),
                    "week": timedelta(weeks=amount),
                    "month": timedelta(days=amount * 30),
                    "hour": timedelta(hours=amount),
                }
                delta = delta_map.get(unit, timedelta(days=amount))
                return (now - delta, now)

        return None

    def _detect_aggregation(self, query: str) -> str | None:
        for keyword, fn in self.AGGREGATION_KEYWORDS.items():
            if keyword in query:
                return fn
        return None

    def _estimate_hop_limit(self, reasoning_type: ReasoningType) -> int:
        limits = {
            ReasoningType.ENTITY_LOOKUP: 0,
            ReasoningType.RELATIONSHIP: 1,
            ReasoningType.MULTI_HOP: 4,
            ReasoningType.AGGREGATION: 1,
            ReasoningType.TEMPORAL: 1,
            ReasoningType.COMPARISON: 1,
            ReasoningType.CAUSAL: 5,
            ReasoningType.EXPLORATION: 2,
        }
        return limits.get(reasoning_type, 2)

    def _extract_relationships(self, query: str) -> list[str]:
        return [kw for kw in self.RELATIONSHIP_KEYWORDS if kw in query]
