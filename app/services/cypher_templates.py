"""Parameterised Cypher query library.

All templates are aligned to the REAL Neo4j schema produced by graph_updater:
  Node labels : Chunk, Concept, Document, Event, Folder, Location,
                Organization, Person, Project, Tag, Task, Topic
  Relationships: MENTIONS, HAS_CHUNK, ABOUT, RELATED_TO

Person nodes carry ``canonical_name`` and ``name``.
Document nodes carry ``title``, ``indexed_at``, ``source``.
MENTIONS edges link Document→entity (mention_count, importance_score).
RELATED_TO edges link entity↔entity (strength).
"""

from __future__ import annotations

from dataclasses import dataclass
from app.models.reasoning import ReasoningType


@dataclass
class CypherTemplate:
    """A parameterised Cypher query with slot-based rendering."""

    template: str
    required_slots: list[str]
    reasoning_type: ReasoningType
    description: str = ""

    def render(self, slots: dict[str, object]) -> str:
        missing = [s for s in self.required_slots if s not in slots]
        if missing:
            raise ValueError(f"Missing slots: {missing}")
        result = self.template
        for key, value in slots.items():
            safe = str(value).replace("'", "\\'")
            result = result.replace(f"${key}", safe)
        return result


# =====================================================================
#  CYPHER TEMPLATES — aligned to real schema
# =====================================================================

CYPHER_TEMPLATES: dict[str, CypherTemplate] = {
    # ── ENTITY LOOKUP ────────────────────────────────────────────────
    "entity_lookup_person": CypherTemplate(
        template="""
MATCH (p:Person)
WHERE toLower(p.canonical_name) CONTAINS toLower('$person_name')
   OR toLower(p.name) CONTAINS toLower('$person_name')
OPTIONAL MATCH (d:Document)-[m:MENTIONS]->(p)
RETURN p.canonical_name AS name,
       p.name AS raw_name,
       labels(p) AS labels,
       count(d) AS document_count,
       collect(DISTINCT d.title)[..5] AS mentioned_in
LIMIT 5
""",
        required_slots=["person_name"],
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Look up a Person node by canonical_name or name.",
    ),
    "entity_lookup_topic": CypherTemplate(
        template="""
MATCH (t:Topic)
WHERE toLower(t.name) CONTAINS toLower('$topic_name')
OPTIONAL MATCH (d:Document)-[:ABOUT]->(t)
RETURN t.name AS topic,
       labels(t) AS labels,
       count(d) AS document_count,
       collect(DISTINCT d.title)[..5] AS documents
LIMIT 5
""",
        required_slots=["topic_name"],
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Look up a Topic node.",
    ),
    "entity_lookup_document": CypherTemplate(
        template="""
MATCH (d:Document)
WHERE toLower(d.title) CONTAINS toLower('$search_term')
OPTIONAL MATCH (d)-[:ABOUT]->(t:Topic)
OPTIONAL MATCH (d)-[:MENTIONS]->(e)
RETURN d.title AS title,
       d.source AS source,
       d.indexed_at AS indexed_at,
       collect(DISTINCT t.name) AS topics,
       count(DISTINCT e) AS entity_count
LIMIT 5
""",
        required_slots=["search_term"],
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Look up a Document by title.",
    ),
    "entity_lookup_general": CypherTemplate(
        template="""
MATCH (n)
WHERE toLower(n.name) CONTAINS toLower('$entity_name')
   OR toLower(n.canonical_name) CONTAINS toLower('$entity_name')
OPTIONAL MATCH (d:Document)-[:MENTIONS]->(n)
RETURN n.name AS name,
       coalesce(n.canonical_name, n.name) AS canonical_name,
       labels(n) AS labels,
       count(d) AS document_count
LIMIT 10
""",
        required_slots=["entity_name"],
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
        description="Look up any entity by name.",
    ),
    # ── RELATIONSHIP ─────────────────────────────────────────────────
    "person_connections": CypherTemplate(
        template="""
MATCH (d:Document)-[:MENTIONS]->(p:Person)
WHERE toLower(p.canonical_name) CONTAINS toLower('$person_name')
   OR toLower(p.name) CONTAINS toLower('$person_name')
WITH p, d
MATCH (d)-[:MENTIONS]->(other)
WHERE other <> p
RETURN p.canonical_name AS person,
       labels(other) AS connected_type,
       other.name AS connected_name,
       coalesce(other.canonical_name, other.name) AS connected_canonical,
       count(DISTINCT d) AS shared_documents,
       collect(DISTINCT d.title)[..3] AS via_documents
ORDER BY shared_documents DESC
LIMIT 20
""",
        required_slots=["person_name"],
        reasoning_type=ReasoningType.RELATIONSHIP,
        description="Find entities co-mentioned with a person via shared documents.",
    ),
    "entity_relationships": CypherTemplate(
        template="""
MATCH (n)-[r:RELATED_TO]-(m)
WHERE toLower(n.name) CONTAINS toLower('$entity_name')
   OR toLower(n.canonical_name) CONTAINS toLower('$entity_name')
RETURN n.name AS source,
       labels(n) AS source_labels,
       type(r) AS relationship,
       r.strength AS strength,
       m.name AS target,
       labels(m) AS target_labels
ORDER BY r.strength DESC
LIMIT 15
""",
        required_slots=["entity_name"],
        reasoning_type=ReasoningType.RELATIONSHIP,
        description="Find RELATED_TO edges for an entity.",
    ),
    # ── MULTI-HOP ────────────────────────────────────────────────────
    "full_neighborhood": CypherTemplate(
        template="""
MATCH (n)
WHERE toLower(n.name) CONTAINS toLower('$entity_name')
   OR toLower(n.canonical_name) CONTAINS toLower('$entity_name')
WITH n LIMIT 1
OPTIONAL MATCH (n)-[r]-(neighbor)
RETURN n.name AS entity,
       labels(n) AS entity_labels,
       type(r) AS rel_type,
       neighbor.name AS neighbor_name,
       labels(neighbor) AS neighbor_labels
LIMIT 25
""",
        required_slots=["entity_name"],
        reasoning_type=ReasoningType.MULTI_HOP,
        description="Get immediate neighborhood of any entity.",
    ),
    "all_paths_between": CypherTemplate(
        template="""
MATCH (a), (b)
WHERE (toLower(a.name) CONTAINS toLower('$entity_a')
       OR toLower(a.canonical_name) CONTAINS toLower('$entity_a'))
  AND (toLower(b.name) CONTAINS toLower('$entity_b')
       OR toLower(b.canonical_name) CONTAINS toLower('$entity_b'))
WITH a, b LIMIT 1
MATCH path = shortestPath((a)-[*..5]-(b))
RETURN [n IN nodes(path) | coalesce(n.canonical_name, n.name, n.title)] AS path_nodes,
       [r IN relationships(path) | type(r)] AS path_rels,
       length(path) AS hops
LIMIT 5
""",
        required_slots=["entity_a", "entity_b"],
        reasoning_type=ReasoningType.MULTI_HOP,
        description="Find shortest paths between two entities.",
    ),
    # ── AGGREGATION ──────────────────────────────────────────────────
    "content_stats": CypherTemplate(
        template="""
MATCH (d:Document)
WITH count(d) AS documents
OPTIONAL MATCH (p:Person)
WITH documents, count(p) AS persons
OPTIONAL MATCH (o:Organization)
WITH documents, persons, count(o) AS organizations
OPTIONAL MATCH (l:Location)
WITH documents, persons, organizations, count(l) AS locations
OPTIONAL MATCH (e:Event)
WITH documents, persons, organizations, locations, count(e) AS events
OPTIONAL MATCH (t:Topic)
RETURN documents, persons, organizations, locations, events, count(t) AS topics
""",
        required_slots=[],
        reasoning_type=ReasoningType.AGGREGATION,
        description="High-level content statistics for the knowledge graph.",
    ),
    "topic_distribution": CypherTemplate(
        template="""
MATCH (d:Document)-[:ABOUT]->(t:Topic)
RETURN t.name AS topic,
       count(d) AS document_count
ORDER BY document_count DESC
LIMIT $limit
""",
        required_slots=["limit"],
        reasoning_type=ReasoningType.AGGREGATION,
        description="Distribution of documents across topics.",
    ),
    "most_mentioned_entities": CypherTemplate(
        template="""
MATCH (d:Document)-[m:MENTIONS]->(e)
RETURN e.name AS entity,
       coalesce(e.canonical_name, e.name) AS canonical_name,
       labels(e) AS labels,
       count(DISTINCT d) AS document_count,
       sum(m.mention_count) AS total_mentions
ORDER BY total_mentions DESC
LIMIT $limit
""",
        required_slots=["limit"],
        reasoning_type=ReasoningType.AGGREGATION,
        description="Top entities by total mention count.",
    ),
    # ── TEMPORAL ─────────────────────────────────────────────────────
    "temporal_chain": CypherTemplate(
        template="""
MATCH (d:Document)
WHERE d.indexed_at >= '$start_time'
  AND d.indexed_at <= '$end_time'
OPTIONAL MATCH (d)-[:MENTIONS]->(e)
WITH d, collect(DISTINCT {name: e.name, labels: labels(e)}) AS entities
RETURN d.title AS document,
       d.indexed_at AS indexed_at,
       entities
ORDER BY d.indexed_at
LIMIT 20
""",
        required_slots=["start_time", "end_time"],
        reasoning_type=ReasoningType.TEMPORAL,
        description="Documents and their entities within a time window.",
    ),
    "recent_documents": CypherTemplate(
        template="""
MATCH (d:Document)
OPTIONAL MATCH (d)-[:ABOUT]->(t:Topic)
OPTIONAL MATCH (d)-[:MENTIONS]->(e)
RETURN d.title AS title,
       d.indexed_at AS indexed_at,
       collect(DISTINCT t.name) AS topics,
       count(DISTINCT e) AS entity_count
ORDER BY d.indexed_at DESC
LIMIT $limit
""",
        required_slots=["limit"],
        reasoning_type=ReasoningType.TEMPORAL,
        description="Most recently indexed documents.",
    ),
    # ── COMPARISON ───────────────────────────────────────────────────
    "entity_comparison": CypherTemplate(
        template="""
MATCH (d:Document)-[:MENTIONS]->(a)
WHERE toLower(a.name) CONTAINS toLower('$entity_a')
   OR toLower(a.canonical_name) CONTAINS toLower('$entity_a')
WITH a, collect(DISTINCT d) AS docs_a
MATCH (d2:Document)-[:MENTIONS]->(b)
WHERE toLower(b.name) CONTAINS toLower('$entity_b')
   OR toLower(b.canonical_name) CONTAINS toLower('$entity_b')
WITH a, docs_a, b, collect(DISTINCT d2) AS docs_b
RETURN a.name AS entity_a,
       labels(a) AS labels_a,
       size(docs_a) AS docs_a_count,
       b.name AS entity_b,
       labels(b) AS labels_b,
       size(docs_b) AS docs_b_count,
       size([d IN docs_a WHERE d IN docs_b]) AS shared_docs
""",
        required_slots=["entity_a", "entity_b"],
        reasoning_type=ReasoningType.COMPARISON,
        description="Compare two entities by their document co-occurrence.",
    ),
    "topic_overlap": CypherTemplate(
        template="""
MATCH (d1:Document)-[:ABOUT]->(t:Topic)<-[:ABOUT]-(d2:Document)
WHERE toLower(d1.title) CONTAINS toLower('$entity_a')
  AND toLower(d2.title) CONTAINS toLower('$entity_b')
  AND d1 <> d2
RETURN t.name AS shared_topic,
       d1.title AS doc_a,
       d2.title AS doc_b
LIMIT 10
""",
        required_slots=["entity_a", "entity_b"],
        reasoning_type=ReasoningType.COMPARISON,
        description="Topics shared between two documents.",
    ),
    # ── CAUSAL ───────────────────────────────────────────────────────
    "event_causal_chain": CypherTemplate(
        template="""
MATCH (d:Document)-[:MENTIONS]->(ev:Event)
WHERE toLower(ev.name) CONTAINS toLower('$event_name')
WITH ev, d
MATCH (d)-[:MENTIONS]->(co)
WHERE co <> ev
RETURN ev.name AS event,
       labels(co) AS co_mentioned_type,
       co.name AS co_mentioned_entity,
       d.title AS source_document,
       count(*) AS co_occurrence_count
ORDER BY co_occurrence_count DESC
LIMIT 20
""",
        required_slots=["event_name"],
        reasoning_type=ReasoningType.CAUSAL,
        description="Entities co-mentioned with an event (causal context).",
    ),
    # ── EXPLORATION ──────────────────────────────────────────────────
    "community_detection": CypherTemplate(
        template="""
MATCH (d:Document)-[:MENTIONS]->(e1)
MATCH (d)-[:MENTIONS]->(e2)
WHERE id(e1) < id(e2)
WITH e1, e2, count(d) AS shared_docs
WHERE shared_docs >= 2
RETURN e1.name AS entity_a,
       labels(e1) AS labels_a,
       e2.name AS entity_b,
       labels(e2) AS labels_b,
       shared_docs
ORDER BY shared_docs DESC
LIMIT 20
""",
        required_slots=[],
        reasoning_type=ReasoningType.EXPLORATION,
        description="Entity clusters based on document co-mention.",
    ),
    "knowledge_gaps": CypherTemplate(
        template="""
MATCH (e)
WHERE NOT (e)<-[:MENTIONS]-(:Document)
  AND NOT e:Document AND NOT e:Chunk
RETURN e.name AS orphan_entity,
       labels(e) AS labels
LIMIT 20
""",
        required_slots=[],
        reasoning_type=ReasoningType.EXPLORATION,
        description="Entities not mentioned by any document (orphans).",
    ),
}
