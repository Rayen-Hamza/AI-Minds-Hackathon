"""Parameterised Cypher template engine and pre-built template library."""

from __future__ import annotations

from string import Template
from typing import Any

from app.models.reasoning import ReasoningType


class CypherTemplate:
    """A parameterised Cypher query with slot-filling support."""

    def __init__(
        self,
        template: str,
        required_slots: list[str],
        reasoning_type: ReasoningType,
    ) -> None:
        self.template = template
        self.required_slots = required_slots
        self.reasoning_type = reasoning_type

    def render(self, slots: dict[str, Any]) -> str:
        """Fill template slots and return valid Cypher."""
        missing = [s for s in self.required_slots if s not in slots]
        if missing:
            raise ValueError(f"Missing slots: {missing}")

        sanitized: dict[str, Any] = {}
        for key, value in slots.items():
            if isinstance(value, str):
                sanitized[key] = value.replace("'", "\\'").replace('"', '\\"')
            else:
                sanitized[key] = value

        return Template(self.template).safe_substitute(sanitized)


# ═══════════════════════════════════════════════════════════════════════
# TEMPLATE LIBRARY — Organised by ReasoningType
# ═══════════════════════════════════════════════════════════════════════

CYPHER_TEMPLATES: dict[str, CypherTemplate] = {
    # ── ENTITY LOOKUP ────────────────────────────────────────────────
    "entity_lookup_person": CypherTemplate(
        template="""
        MATCH (p:Person)
        WHERE p.canonical_name =~ '(?i).*$entity_name.*'
           OR ANY(alias IN p.aliases WHERE alias =~ '(?i).*$entity_name.*')
        OPTIONAL MATCH (p)-[:AFFILIATED_WITH]->(org:Organization)
        OPTIONAL MATCH (p)-[:EXPERT_IN]->(topic:Topic)
        OPTIONAL MATCH (p)-[:WORKED_ON]->(proj:Project)
        RETURN p {
            .canonical_name, .email, .role, .mention_count,
            organizations: collect(DISTINCT org.name),
            expertise: collect(DISTINCT topic.name),
            projects: collect(DISTINCT proj.name)
        } AS person
        LIMIT 5
        """,
        required_slots=["entity_name"],
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
    ),
    "entity_lookup_topic": CypherTemplate(
        template="""
        MATCH (t:Topic)
        WHERE t.name =~ '(?i).*$topic_name.*'
        OPTIONAL MATCH (t)<-[:ABOUT]-(d:Document)
        OPTIONAL MATCH (t)-[:RELATED_TO]-(related:Topic)
        OPTIONAL MATCH (t)-[:SUBTOPIC_OF]->(parent:Topic)
        OPTIONAL MATCH (child:Topic)-[:SUBTOPIC_OF]->(t)
        RETURN t {
            .name, .description, .mention_count, .importance_score,
            document_count: count(DISTINCT d),
            related_topics: collect(DISTINCT related.name)[0..10],
            parent_topic: parent.name,
            subtopics: collect(DISTINCT child.name)[0..10]
        } AS topic
        LIMIT 5
        """,
        required_slots=["topic_name"],
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
    ),
    "entity_lookup_document": CypherTemplate(
        template="""
        MATCH (d:Document)
        WHERE d.title =~ '(?i).*$search_term.*'
           OR d.summary =~ '(?i).*$search_term.*'
        OPTIONAL MATCH (d)-[:ABOUT]->(t:Topic)
        OPTIONAL MATCH (d)-[:BELONGS_TO]->(p:Project)
        OPTIONAL MATCH (d)<-[:CONTAINS]-(f:Folder)
        RETURN d {
            .title, .file_path, .created_at, .modified_at, .summary,
            topics: collect(DISTINCT t.name),
            project: p.name,
            folder: f.path
        } AS document
        ORDER BY d.modified_at DESC
        LIMIT 10
        """,
        required_slots=["search_term"],
        reasoning_type=ReasoningType.ENTITY_LOOKUP,
    ),
    # ── RELATIONSHIP TRAVERSAL ───────────────────────────────────────
    "person_connections": CypherTemplate(
        template="""
        MATCH (p:Person)
        WHERE p.canonical_name =~ '(?i).*$person_name.*'
        OPTIONAL MATCH (p)-[r:KNOWS]->(other:Person)
        OPTIONAL MATCH (p)-[:WORKED_ON]->(proj:Project)
        OPTIONAL MATCH (p)-[:AFFILIATED_WITH]->(org:Organization)
        OPTIONAL MATCH (p)-[:ATTENDED]->(evt:Event)
        RETURN p.canonical_name AS person,
               collect(DISTINCT {
                   name: other.canonical_name,
                   relationship: r.relationship_type,
                   strength: r.strength
               }) AS connections,
               collect(DISTINCT proj.name) AS projects,
               collect(DISTINCT org.name) AS organizations,
               collect(DISTINCT {name: evt.name, date: evt.occurred_at}) AS events
        """,
        required_slots=["person_name"],
        reasoning_type=ReasoningType.RELATIONSHIP,
    ),
    "documents_about_topic": CypherTemplate(
        template="""
        MATCH (t:Topic)
        WHERE t.name =~ '(?i).*$topic_name.*'
        MATCH (d:Document)-[r:ABOUT]->(t)
        OPTIONAL MATCH (d)<-[:CONTAINS]-(f:Folder)
        RETURN d {
            .title, .file_path, .summary, .modified_at,
            relevance: r.relevance_score,
            folder: f.path
        } AS document
        ORDER BY r.relevance_score DESC
        LIMIT $limit
        """,
        required_slots=["topic_name"],
        reasoning_type=ReasoningType.RELATIONSHIP,
    ),
    # ── EXPLORATION ──────────────────────────────────────────────────
    "topic_neighborhood": CypherTemplate(
        template="""
        MATCH (t:Topic)
        WHERE t.name =~ '(?i).*$topic_name.*'
        CALL {
            WITH t
            MATCH (t)-[r:RELATED_TO]-(other:Topic)
            RETURN other.name AS name, r.strength AS weight,
                   'related_to' AS rel_type
            UNION
            WITH t
            MATCH (t)<-[:SUBTOPIC_OF]-(child:Topic)
            RETURN child.name AS name, 1.0 AS weight,
                   'subtopic' AS rel_type
            UNION
            WITH t
            MATCH (t)-[:SUBTOPIC_OF]->(parent:Topic)
            RETURN parent.name AS name, 1.0 AS weight,
                   'parent' AS rel_type
        }
        RETURN name, weight, rel_type
        ORDER BY weight DESC
        LIMIT 20
        """,
        required_slots=["topic_name"],
        reasoning_type=ReasoningType.EXPLORATION,
    ),
    "full_neighborhood": CypherTemplate(
        template="""
        MATCH (center)
        WHERE center.name =~ '(?i).*$entity_name.*'
           OR center.canonical_name =~ '(?i).*$entity_name.*'
           OR center.title =~ '(?i).*$entity_name.*'
        WITH center LIMIT 1
        CALL {
            WITH center
            MATCH (center)-[r]->(outgoing)
            RETURN type(r) AS rel_type,
                   'outgoing' AS direction,
                   labels(outgoing)[0] AS node_type,
                   coalesce(outgoing.name, outgoing.title,
                            outgoing.canonical_name) AS node_name,
                   properties(r) AS rel_props
            UNION
            WITH center
            MATCH (center)<-[r]-(incoming)
            RETURN type(r) AS rel_type,
                   'incoming' AS direction,
                   labels(incoming)[0] AS node_type,
                   coalesce(incoming.name, incoming.title,
                            incoming.canonical_name) AS node_name,
                   properties(r) AS rel_props
        }
        RETURN rel_type, direction, node_type, node_name, rel_props
        ORDER BY rel_type, direction
        LIMIT 50
        """,
        required_slots=["entity_name"],
        reasoning_type=ReasoningType.EXPLORATION,
    ),
    "community_detection": CypherTemplate(
        template="""
        MATCH (t:Topic)-[:RELATED_TO]-(neighbor:Topic)
        WITH t, collect(DISTINCT neighbor) AS neighbors
        WHERE size(neighbors) >= 3
        RETURN t.name AS hub_topic,
               [n IN neighbors | n.name] AS cluster_members,
               size(neighbors) AS cluster_size
        ORDER BY cluster_size DESC
        LIMIT 10
        """,
        required_slots=[],
        reasoning_type=ReasoningType.EXPLORATION,
    ),
    # ── MULTI-HOP PATH FINDING ───────────────────────────────────────
    "shortest_path_entities": CypherTemplate(
        template="""
        MATCH (source)
        WHERE (source:Topic OR source:Concept OR source:Person OR source:Project)
          AND (source.name =~ '(?i).*$entity_a.*'
               OR source.canonical_name =~ '(?i).*$entity_a.*')
        MATCH (target)
        WHERE (target:Topic OR target:Concept OR target:Person OR target:Project)
          AND (target.name =~ '(?i).*$entity_b.*'
               OR target.canonical_name =~ '(?i).*$entity_b.*')
        MATCH path = shortestPath((source)-[*..${max_hops}]-(target))
        RETURN [node IN nodes(path) |
            CASE
                WHEN node:Person THEN {type: 'Person', name: node.canonical_name}
                WHEN node:Topic THEN {type: 'Topic', name: node.name}
                WHEN node:Concept THEN {type: 'Concept', name: node.name}
                WHEN node:Document THEN {type: 'Document', name: node.title}
                WHEN node:Project THEN {type: 'Project', name: node.name}
                WHEN node:Organization THEN {type: 'Organization', name: node.name}
                ELSE {type: labels(node)[0], name: coalesce(node.name, node.title, node.canonical_name, 'unknown')}
            END
        ] AS path_nodes,
        [rel IN relationships(path) | type(rel)] AS path_relationships,
        length(path) AS path_length
        ORDER BY path_length ASC
        LIMIT 5
        """,
        required_slots=["entity_a", "entity_b"],
        reasoning_type=ReasoningType.MULTI_HOP,
    ),
    "all_paths_between": CypherTemplate(
        template="""
        MATCH (source)
        WHERE (source.name =~ '(?i).*$entity_a.*'
               OR source.canonical_name =~ '(?i).*$entity_a.*')
        MATCH (target)
        WHERE (target.name =~ '(?i).*$entity_b.*'
               OR target.canonical_name =~ '(?i).*$entity_b.*')
        MATCH path = allShortestPaths((source)-[*..${max_hops}]-(target))
        WITH path, length(path) AS len
        ORDER BY len ASC
        LIMIT 10
        RETURN [node IN nodes(path) |
            coalesce(node.canonical_name, node.name, node.title)
        ] AS node_names,
        [rel IN relationships(path) | type(rel)] AS relationships,
        len AS hops
        """,
        required_slots=["entity_a", "entity_b"],
        reasoning_type=ReasoningType.MULTI_HOP,
    ),
    # ── AGGREGATION ──────────────────────────────────────────────────
    "count_by_topic": CypherTemplate(
        template="""
        MATCH (t:Topic)<-[:ABOUT]-(d:Document)
        WHERE t.name =~ '(?i).*$topic_name.*'
        RETURN t.name AS topic, count(d) AS document_count,
               collect(d.title)[0..5] AS sample_documents
        ORDER BY document_count DESC
        """,
        required_slots=["topic_name"],
        reasoning_type=ReasoningType.AGGREGATION,
    ),
    "top_entities_by_mentions": CypherTemplate(
        template="""
        MATCH (n)
        WHERE n:$node_label AND n.mention_count IS NOT NULL
        RETURN coalesce(n.name, n.canonical_name) AS entity,
               n.mention_count AS mentions,
               labels(n)[0] AS type
        ORDER BY n.mention_count DESC
        LIMIT $limit
        """,
        required_slots=["node_label"],
        reasoning_type=ReasoningType.AGGREGATION,
    ),
    "content_stats": CypherTemplate(
        template="""
        CALL {
            MATCH (d:Document) RETURN 'Documents' AS type, count(d) AS cnt
            UNION ALL
            MATCH (i:Image) RETURN 'Images' AS type, count(i) AS cnt
            UNION ALL
            MATCH (v:Video) RETURN 'Videos' AS type, count(v) AS cnt
            UNION ALL
            MATCH (a:Audio) RETURN 'Audio' AS type, count(a) AS cnt
            UNION ALL
            MATCH (t:Topic) RETURN 'Topics' AS type, count(t) AS cnt
            UNION ALL
            MATCH (p:Person) RETURN 'People' AS type, count(p) AS cnt
            UNION ALL
            MATCH (c:Concept) RETURN 'Concepts' AS type, count(c) AS cnt
        }
        RETURN type, cnt
        ORDER BY cnt DESC
        """,
        required_slots=[],
        reasoning_type=ReasoningType.AGGREGATION,
    ),
    "pagerank_topics": CypherTemplate(
        template="""
        MATCH (t:Topic)-[r:RELATED_TO]-(other:Topic)
        WITH t, count(r) AS degree,
             sum(r.strength) AS total_strength
        RETURN t.name AS topic,
               degree,
               total_strength,
               t.mention_count AS mentions,
               total_strength / degree AS avg_connection_strength
        ORDER BY degree * coalesce(t.mention_count, 1) DESC
        LIMIT $limit
        """,
        required_slots=[],
        reasoning_type=ReasoningType.AGGREGATION,
    ),
    # ── TEMPORAL ─────────────────────────────────────────────────────
    "documents_in_timerange": CypherTemplate(
        template="""
        MATCH (d:Document)
        WHERE d.modified_at >= datetime('$start_time')
          AND d.modified_at <= datetime('$end_time')
        OPTIONAL MATCH (d)-[:ABOUT]->(t:Topic)
        OPTIONAL MATCH (d)-[:BELONGS_TO]->(p:Project)
        RETURN d {
            .title, .file_path, .modified_at, .summary,
            topics: collect(DISTINCT t.name),
            project: p.name
        } AS document
        ORDER BY d.modified_at DESC
        LIMIT 20
        """,
        required_slots=["start_time", "end_time"],
        reasoning_type=ReasoningType.TEMPORAL,
    ),
    "activity_timeline": CypherTemplate(
        template="""
        MATCH (d:Document)
        WHERE d.modified_at >= datetime('$start_time')
          AND d.modified_at <= datetime('$end_time')
        WITH d.modified_at.year AS year,
             d.modified_at.month AS month,
             d.modified_at.day AS day,
             count(d) AS activity_count,
             collect(d.title)[0..3] AS sample_docs
        RETURN year, month, day, activity_count, sample_docs
        ORDER BY year, month, day
        """,
        required_slots=["start_time", "end_time"],
        reasoning_type=ReasoningType.TEMPORAL,
    ),
    # ── COMPARISON ───────────────────────────────────────────────────
    "compare_topics": CypherTemplate(
        template="""
        UNWIND ['$topic_a', '$topic_b'] AS topic_name
        MATCH (t:Topic)
        WHERE t.name =~ '(?i).*' + topic_name + '.*'
        OPTIONAL MATCH (t)<-[:ABOUT]-(d:Document)
        OPTIONAL MATCH (t)-[:RELATED_TO]-(related:Topic)
        RETURN t.name AS topic,
               t.mention_count AS mentions,
               t.importance_score AS importance,
               count(DISTINCT d) AS document_count,
               collect(DISTINCT related.name)[0..5] AS related_topics
        """,
        required_slots=["topic_a", "topic_b"],
        reasoning_type=ReasoningType.COMPARISON,
    ),
    # ── CAUSAL CHAIN ─────────────────────────────────────────────────
    "temporal_chain": CypherTemplate(
        template="""
        MATCH (t:Topic)
        WHERE t.name =~ '(?i).*$topic_name.*'
        MATCH (d:Document)-[:ABOUT]->(t)
        WITH d ORDER BY d.created_at ASC
        WITH collect(d {.title, .created_at, .summary})[0..15] AS timeline
        RETURN timeline
        """,
        required_slots=["topic_name"],
        reasoning_type=ReasoningType.CAUSAL,
    ),
    "event_causal_chain": CypherTemplate(
        template="""
        MATCH (e:Event)
        WHERE e.name =~ '(?i).*$event_name.*'
        MATCH chain = (e)-[:CAUSED*0..5]->(effect:Event)
        RETURN [node IN nodes(chain) | node {.name, .occurred_at, .description}]
               AS causal_chain,
               length(chain) AS chain_length
        ORDER BY chain_length ASC
        """,
        required_slots=["event_name"],
        reasoning_type=ReasoningType.CAUSAL,
    ),
}
