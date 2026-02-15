"""Neo4j schema initialisation — constraints, indexes, full-text indexes."""

from __future__ import annotations

import logging

from neo4j import Driver

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# All DDL statements executed at startup to ensure the schema is ready.
# Each statement is idempotent (IF NOT EXISTS).
# ═══════════════════════════════════════════════════════════════════════

_CONSTRAINTS: list[str] = [
    "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT folder_path IF NOT EXISTS FOR (f:Folder) REQUIRE f.path IS UNIQUE",
    "CREATE CONSTRAINT org_id IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE",
    "CREATE CONSTRAINT location_id IF NOT EXISTS FOR (l:Location) REQUIRE l.id IS UNIQUE",
    "CREATE CONSTRAINT tag_id IF NOT EXISTS FOR (t:Tag) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT task_id IF NOT EXISTS FOR (t:Task) REQUIRE t.id IS UNIQUE",
]

_INDEXES: list[str] = [
    "CREATE INDEX doc_hash IF NOT EXISTS FOR (d:Document) ON (d.content_hash)",
    "CREATE INDEX doc_path IF NOT EXISTS FOR (d:Document) ON (d.file_path)",
    "CREATE INDEX doc_modified IF NOT EXISTS FOR (d:Document) ON (d.modified_at)",
    "CREATE INDEX chunk_doc IF NOT EXISTS FOR (c:Chunk) ON (c.document_id)",
    "CREATE INDEX chunk_hash IF NOT EXISTS FOR (c:Chunk) ON (c.content_hash)",
    "CREATE INDEX chunk_qdrant IF NOT EXISTS FOR (c:Chunk) ON (c.qdrant_point_id)",
    "CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.canonical_name)",
    "CREATE INDEX topic_name IF NOT EXISTS FOR (t:Topic) ON (t.name)",
    "CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name)",
    "CREATE INDEX event_time IF NOT EXISTS FOR (e:Event) ON (e.occurred_at)",
    "CREATE INDEX task_status IF NOT EXISTS FOR (t:Task) ON (t.status)",
    "CREATE INDEX project_status IF NOT EXISTS FOR (p:Project) ON (p.status)",
    "CREATE INDEX org_name IF NOT EXISTS FOR (o:Organization) ON (o.name)",
    "CREATE INDEX location_name IF NOT EXISTS FOR (l:Location) ON (l.name)",
]

_FULLTEXT_INDEXES: list[str] = [
    (
        "CREATE FULLTEXT INDEX ft_chunk_content IF NOT EXISTS "
        "FOR (c:Chunk) ON EACH [c.content]"
    ),
    (
        "CREATE FULLTEXT INDEX ft_doc_title IF NOT EXISTS "
        "FOR (d:Document) ON EACH [d.title, d.summary]"
    ),
    (
        "CREATE FULLTEXT INDEX ft_person_name IF NOT EXISTS "
        "FOR (p:Person) ON EACH [p.canonical_name]"
    ),
]


def ensure_schema(driver: Driver) -> None:
    """Create all constraints, indexes, and full-text indexes idempotently."""
    with driver.session() as session:
        for stmt in _CONSTRAINTS:
            try:
                session.run(stmt)
            except Exception:
                logger.debug("Constraint may already exist: %s", stmt[:60])

        for stmt in _INDEXES:
            try:
                session.run(stmt)
            except Exception:
                logger.debug("Index may already exist: %s", stmt[:60])

        for stmt in _FULLTEXT_INDEXES:
            try:
                session.run(stmt)
            except Exception:
                logger.debug("Fulltext index may already exist: %s", stmt[:60])

    logger.info("Neo4j schema initialisation complete.")
