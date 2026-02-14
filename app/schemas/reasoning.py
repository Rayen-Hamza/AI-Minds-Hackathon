"""Request / response schemas for the reasoning API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReasoningRequest(BaseModel):
    """Payload for the ``/reasoning/query`` endpoint."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural-language user query.",
    )
    vector_results: list[str] | None = Field(
        default=None,
        description=(
            "Optional pre-fetched vector search results "
            "to supplement graph reasoning."
        ),
    )


class ReasoningResponse(BaseModel):
    """Response returned by the reasoning endpoint."""

    prompt: str = Field(
        ...,
        description="LLM-ready prompt containing the reasoning chain.",
    )
    reasoning_type: str = Field(
        ...,
        description="Detected query reasoning type.",
    )
    entities: list[str] = Field(
        default_factory=list,
        description="Entities extracted / resolved from the query.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Decomposition confidence score.",
    )


class ChunkPayload(BaseModel):
    id: str
    content: str
    chunk_index: int
    qdrant_point_id: str
    content_hash: str = ""


class EntityPayload(BaseModel):
    text: str
    type: str  # "Person", "Organization", …
    confidence: float = 1.0


class IngestDocumentRequest(BaseModel):
    """Payload for ``/reasoning/ingest``."""

    doc_id: str
    title: str
    file_path: str
    content_hash: str
    chunks: list[ChunkPayload]
    extracted_entities: list[EntityPayload] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class IngestDocumentResponse(BaseModel):
    status: str = "ok"
    doc_id: str


class GraphStatsResponse(BaseModel):
    """Counts of nodes / relationships in the graph."""

    stats: list[dict]
