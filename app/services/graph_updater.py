"""Differential graph updates — keeps Neo4j in sync with content."""

from __future__ import annotations

import logging

from neo4j import Driver

from app.services.entity_resolver import EntityResolver

logger = logging.getLogger(__name__)


class GraphUpdater:
    """
    Handles differential graph updates when documents change.

    Maintains consistency between Qdrant vectors and Neo4j graph.
    """

    def __init__(
        self, driver: Driver, entity_resolver: EntityResolver
    ) -> None:
        self.driver = driver
        self.resolver = entity_resolver

    # ── Full Ingestion ───────────────────────────────────────────────

    def ingest_document(
        self,
        doc_id: str,
        title: str,
        file_path: str,
        content_hash: str,
        chunks: list[dict],
        extracted_entities: list[dict],
        topics: list[str],
    ) -> None:
        """
        Ingest a document into the knowledge graph.

        Args:
            chunks: ``[{"id": str, "content": str, "chunk_index": int,
                        "qdrant_point_id": str, ...}]``
            extracted_entities: ``[{"text": str, "type": str,
                                    "confidence": float}]``
            topics: list of auto-detected topic names
        """
        with self.driver.session() as session:
            # 1. Upsert Document node
            session.run(
                """
                MERGE (d:Document {id: $id})
                SET d.title        = $title,
                    d.file_path    = $file_path,
                    d.content_hash = $content_hash,
                    d.indexed_at   = datetime(),
                    d.chunk_count  = $chunk_count
                """,
                id=doc_id,
                title=title,
                file_path=file_path,
                content_hash=content_hash,
                chunk_count=len(chunks),
            )

            # 2. Create / update Chunk nodes
            for chunk in chunks:
                session.run(
                    """
                    MERGE (c:Chunk {id: $chunk_id})
                    SET c.document_id    = $doc_id,
                        c.chunk_index    = $index,
                        c.content        = $content,
                        c.content_hash   = $hash,
                        c.qdrant_point_id = $qdrant_id
                    WITH c
                    MATCH (d:Document {id: $doc_id})
                    MERGE (d)-[:HAS_CHUNK {order: $index}]->(c)
                    """,
                    chunk_id=chunk["id"],
                    doc_id=doc_id,
                    index=chunk["chunk_index"],
                    content=chunk["content"],
                    hash=chunk.get("content_hash", ""),
                    qdrant_id=chunk["qdrant_point_id"],
                )

            # 3. Link extracted entities
            for entity in extracted_entities:
                entity_id = self.resolver.resolve_or_create(
                    entity["text"], label=entity["type"]
                )
                session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                    MATCH (e {id: $entity_id})
                    MERGE (d)-[r:MENTIONS]->(e)
                    SET r.confidence = $confidence
                    """,
                    doc_id=doc_id,
                    entity_id=entity_id,
                    confidence=entity["confidence"],
                )

            # 4. Link topics
            for topic_name in topics:
                topic_id = self.resolver.resolve_or_create(
                    topic_name, label="Topic"
                )
                session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                    MATCH (t:Topic {id: $topic_id})
                    MERGE (d)-[r:ABOUT]->(t)
                    SET r.is_primary = $is_first
                    """,
                    doc_id=doc_id,
                    topic_id=topic_id,
                    is_first=(topic_name == topics[0]),
                )

        logger.info("Ingested document %s (%d chunks)", doc_id, len(chunks))

    # ── Differential Update ──────────────────────────────────────────

    def update_document(
        self,
        doc_id: str,
        new_content_hash: str,
        changed_chunks: list[dict],
        new_entities: list[dict],
        removed_entity_ids: list[str],
    ) -> None:
        """
        Apply a differential update — only process what changed.

        - Unchanged chunks are skipped.
        - Only new entity edges are created.
        - Stale edges are removed.
        """
        with self.driver.session() as session:
            # Update document hash
            session.run(
                """
                MATCH (d:Document {id: $id})
                SET d.content_hash = $hash,
                    d.modified_at  = datetime()
                """,
                id=doc_id,
                hash=new_content_hash,
            )

            # Update only changed chunks
            for chunk in changed_chunks:
                session.run(
                    """
                    MATCH (c:Chunk {id: $chunk_id})
                    SET c.content        = $content,
                        c.content_hash   = $hash,
                        c.qdrant_point_id = $qdrant_id
                    """,
                    chunk_id=chunk["id"],
                    content=chunk["content"],
                    hash=chunk["content_hash"],
                    qdrant_id=chunk["qdrant_point_id"],
                )

            # Add new entities
            for entity in new_entities:
                entity_id = self.resolver.resolve_or_create(
                    entity["text"], label=entity["type"]
                )
                session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                    MATCH (e {id: $entity_id})
                    MERGE (d)-[r:MENTIONS]->(e)
                    SET r.confidence = $confidence
                    """,
                    doc_id=doc_id,
                    entity_id=entity_id,
                    confidence=entity["confidence"],
                )

            # Remove stale entity links
            for entity_id in removed_entity_ids:
                session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                          -[r:MENTIONS]->(e {id: $entity_id})
                    DELETE r
                    """,
                    doc_id=doc_id,
                    entity_id=entity_id,
                )

        logger.info(
            "Updated document %s (%d changed chunks, %d new entities, "
            "%d removed links)",
            doc_id,
            len(changed_chunks),
            len(new_entities),
            len(removed_entity_ids),
        )

    # ── Batch Maintenance ────────────────────────────────────────────

    def compute_topic_relationships(self) -> None:
        """
        Compute ``RELATED_TO`` edges between topics based on document
        co-occurrence.  Intended to run periodically.
        """
        with self.driver.session() as session:
            session.run(
                """
                MATCH (t1:Topic)<-[:ABOUT]-(d:Document)-[:ABOUT]->(t2:Topic)
                WHERE id(t1) < id(t2)
                WITH t1, t2, count(d) AS co_occurrence
                WHERE co_occurrence >= 2
                MERGE (t1)-[r:RELATED_TO]-(t2)
                SET r.co_occurrence_count = co_occurrence,
                    r.strength            = 1.0 - (1.0 / (1 + co_occurrence)),
                    r.computed_at         = datetime()
                """
            )
        logger.info("Topic co-occurrence relationships updated.")

    def compute_importance_scores(self) -> None:
        """
        Lightweight PageRank approximation using degree centrality.
        """
        with self.driver.session() as session:
            session.run(
                """
                MATCH (t:Topic)
                OPTIONAL MATCH (t)<-[:ABOUT]-(d:Document)
                OPTIONAL MATCH (t)-[:RELATED_TO]-(other:Topic)
                WITH t,
                     count(DISTINCT d)     AS doc_count,
                     count(DISTINCT other)  AS topic_connections
                SET t.importance_score =
                    (doc_count * 0.6 + topic_connections * 0.4) /
                    (doc_count + topic_connections + 1.0)
                """
            )
        logger.info("Topic importance scores updated.")
