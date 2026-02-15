"""Tests for Pydantic request/response schemas — validation edge cases."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.reasoning import (
    ChunkPayload,
    EntityPayload,
    GraphStatsResponse,
    IngestDocumentRequest,
    IngestDocumentResponse,
    ReasoningRequest,
    ReasoningResponse,
)


# ─────────────────────────────────────────────────────────────────────
# ReasoningRequest
# ─────────────────────────────────────────────────────────────────────


class TestReasoningRequest:
    def test_valid_query(self):
        req = ReasoningRequest(query="who is Alice?")
        assert req.query == "who is Alice?"
        assert req.vector_results is None

    def test_with_vector_results(self):
        req = ReasoningRequest(
            query="q", vector_results=["chunk1", "chunk2"]
        )
        assert len(req.vector_results) == 2

    def test_empty_query_rejected(self):
        with pytest.raises(ValidationError):
            ReasoningRequest(query="")

    def test_too_long_query_rejected(self):
        with pytest.raises(ValidationError):
            ReasoningRequest(query="x" * 2001)

    def test_min_length_boundary(self):
        req = ReasoningRequest(query="a")
        assert req.query == "a"


# ─────────────────────────────────────────────────────────────────────
# ReasoningResponse
# ─────────────────────────────────────────────────────────────────────


class TestReasoningResponse:
    def test_valid_response(self):
        resp = ReasoningResponse(
            prompt="LLM prompt here",
            reasoning_type="entity_lookup",
            entities=["Alice"],
            confidence=0.85,
        )
        assert resp.prompt == "LLM prompt here"

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            ReasoningResponse(
                prompt="p", reasoning_type="x",
                entities=[], confidence=1.5,
            )
        with pytest.raises(ValidationError):
            ReasoningResponse(
                prompt="p", reasoning_type="x",
                entities=[], confidence=-0.1,
            )

    def test_confidence_boundaries(self):
        resp0 = ReasoningResponse(
            prompt="p", reasoning_type="x", confidence=0.0
        )
        resp1 = ReasoningResponse(
            prompt="p", reasoning_type="x", confidence=1.0
        )
        assert resp0.confidence == 0.0
        assert resp1.confidence == 1.0


# ─────────────────────────────────────────────────────────────────────
# IngestDocumentRequest
# ─────────────────────────────────────────────────────────────────────


class TestIngestDocumentRequest:
    def test_valid_request(self):
        req = IngestDocumentRequest(
            doc_id="doc-1",
            title="Test Doc",
            file_path="/docs/test.md",
            content_hash="abc123",
            chunks=[
                ChunkPayload(
                    id="c1",
                    content="Hello world",
                    chunk_index=0,
                    qdrant_point_id="qp-1",
                )
            ],
        )
        assert req.doc_id == "doc-1"
        assert len(req.chunks) == 1
        assert req.extracted_entities == []
        assert req.topics == []

    def test_with_entities_and_topics(self):
        req = IngestDocumentRequest(
            doc_id="d1",
            title="T",
            file_path="/f",
            content_hash="h",
            chunks=[
                ChunkPayload(
                    id="c1", content="x",
                    chunk_index=0, qdrant_point_id="q1",
                )
            ],
            extracted_entities=[
                EntityPayload(text="Alice", type="Person"),
            ],
            topics=["ML", "AI"],
        )
        assert len(req.extracted_entities) == 1
        assert req.extracted_entities[0].confidence == 1.0
        assert req.topics == ["ML", "AI"]

    def test_empty_chunks_allowed(self):
        req = IngestDocumentRequest(
            doc_id="d1",
            title="T",
            file_path="/f",
            content_hash="h",
            chunks=[],
        )
        assert req.chunks == []


# ─────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────


class TestResponseModels:
    def test_ingest_response_defaults(self):
        resp = IngestDocumentResponse(doc_id="d1")
        assert resp.status == "ok"
        assert resp.doc_id == "d1"

    def test_graph_stats_response(self):
        resp = GraphStatsResponse(
            stats=[
                {"kind": "node", "label": "Document", "count": 42},
            ]
        )
        assert len(resp.stats) == 1
        assert resp.stats[0]["count"] == 42
