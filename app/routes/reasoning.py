"""Reasoning API routes — graph queries, document ingestion, stats."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.schemas.reasoning import (
    GraphStatsResponse,
    IngestDocumentRequest,
    IngestDocumentResponse,
    ReasoningRequest,
    ReasoningResponse,
)
from app.services.neo4j import get_driver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reasoning", tags=["reasoning"])


# ── Query ────────────────────────────────────────────────────────────


@router.post("/query", response_model=ReasoningResponse)
async def reasoning_query(body: ReasoningRequest) -> ReasoningResponse:
    """
    Accept a natural-language query, run it through the graph reasoning
    pipeline, and return an LLM-ready prompt.
    """
    from app.services.graph_reasoning import GraphReasoningOrchestrator

    driver = get_driver()
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j is not available.")

    orchestrator = GraphReasoningOrchestrator(driver)
    try:
        prompt = orchestrator.process_query(
            body.query,
            vector_results=body.vector_results,
        )
    except Exception as exc:
        logger.exception("Reasoning pipeline error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    decomposed = orchestrator.decomposer.decompose(body.query)

    return ReasoningResponse(
        prompt=prompt,
        reasoning_type=decomposed.reasoning_type.value,
        entities=decomposed.entities,
        confidence=decomposed.confidence,
    )


# ── Document Ingestion ───────────────────────────────────────────────


@router.post("/ingest", response_model=IngestDocumentResponse)
async def ingest_document(
    body: IngestDocumentRequest,
) -> IngestDocumentResponse:
    """
    Ingest a document (with chunks + entities) into the knowledge graph.
    """
    from app.services.entity_resolver import EntityResolver
    from app.services.graph_updater import GraphUpdater

    driver = get_driver()
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j is not available.")

    resolver = EntityResolver(driver)
    updater = GraphUpdater(driver, resolver)

    try:
        updater.ingest_document(
            doc_id=body.doc_id,
            title=body.title,
            file_path=body.file_path,
            content_hash=body.content_hash,
            chunks=[c.model_dump() for c in body.chunks],
            extracted_entities=[e.model_dump() for e in body.extracted_entities],
            topics=body.topics,
        )
    except Exception as exc:
        logger.exception("Ingestion error")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return IngestDocumentResponse(doc_id=body.doc_id)


# ── Graph Stats ──────────────────────────────────────────────────────


@router.get("/stats", response_model=GraphStatsResponse)
async def graph_stats() -> GraphStatsResponse:
    """Return node / relationship counts grouped by label / type."""
    driver = get_driver()
    if driver is None:
        raise HTTPException(status_code=503, detail="Neo4j is not available.")

    stats: list[dict] = []
    with driver.session() as session:
        # Node counts by label
        result = session.run(
            """
            CALL db.labels() YIELD label
            CALL {
                WITH label
                CALL db.stats.retrieve('GRAPH COUNTS') YIELD data
                UNWIND data.nodes AS nc
                WITH nc WHERE nc.label = label
                RETURN nc.count AS cnt
            }
            RETURN label, cnt
            """
        )
        for record in result:
            stats.append(
                {
                    "kind": "node",
                    "label": record["label"],
                    "count": record["cnt"],
                }
            )

    # Fallback: simpler stats query if the above fails on community edition
    if not stats:
        with driver.session() as session:
            for label in [
                "Document",
                "Chunk",
                "Person",
                "Topic",
                "Concept",
                "Organization",
                "Event",
                "Project",
            ]:
                result = session.run(
                    f"MATCH (n:{label}) RETURN count(n) AS cnt"
                )
                record = result.single()
                if record and record["cnt"] > 0:
                    stats.append(
                        {
                            "kind": "node",
                            "label": label,
                            "count": record["cnt"],
                        }
                    )

    return GraphStatsResponse(stats=stats)
