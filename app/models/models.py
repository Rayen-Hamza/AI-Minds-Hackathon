"""
Pydantic models for request/response schemas and internal data structures.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class ContentType(str, Enum):
    """Content type enumeration."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"


class FileType(str, Enum):
    """Supported file types."""
    # Text
    TXT = "txt"
    MD = "md"
    PDF = "pdf"
    PY = "py"
    JS = "js"
    TS = "ts"
    JSON = "json"
    CSV = "csv"

    # Images
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"
    GIF = "gif"
    BMP = "bmp"
    WEBP = "webp"

    # Audio
    MP3 = "mp3"
    WAV = "wav"
    M4A = "m4a"
    FLAC = "flac"
    OGG = "ogg"


class CollectionName(str, Enum):
    """Qdrant collection name (unified multimodal collection)."""
    UNIFIED = "multimodal_embeddings"


# ============================================================================
# Payload Schema (Qdrant Point Payload)
# ============================================================================

class VectorPayload(BaseModel):
    """
    Standard payload structure for all Qdrant points.
    This is stored with every vector in Qdrant.
    """
    source_path: str = Field(..., description="Original file path")
    content_type: ContentType = Field(..., description="Content type (text/image/audio)")
    file_type: str = Field(..., description="File extension/type")
    chunk_index: int = Field(0, ge=0, description="Chunk position within parent document")
    chunk_text: str = Field(..., description="Actual text content (chunk/caption/transcript)")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="Ingestion timestamp")
    content_hash: str = Field(..., description="Hash for differential updates")
    parent_doc_id: str = Field(..., description="UUID of parent document")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    creation_date: Optional[str] = Field(None, description="File creation date")
    last_modified: Optional[str] = Field(None, description="File last modified date")
    tags: list[str] = Field(default_factory=list, description="Extracted tags")
    extracted_entities: list[str] = Field(default_factory=list, description="NER entities")
    graph_node_id: Optional[str] = Field(None, description="Neo4j node ID for future linking")

    # Image-specific metadata
    image_width: Optional[int] = None
    image_height: Optional[int] = None
    exif_data: Optional[dict] = None
    ocr_text: Optional[str] = None
    caption: Optional[str] = None

    # Audio-specific metadata
    audio_duration: Optional[float] = None
    sample_rate: Optional[int] = None
    transcript: Optional[str] = None

    class Config:
        use_enum_values = True


# ============================================================================
# Processing Data Structures
# ============================================================================

class TextChunk(BaseModel):
    """Represents a processed text chunk ready for embedding."""
    text: str
    chunk_index: int
    parent_doc_id: str
    source_path: str
    file_type: str
    content_hash: str
    file_size: int
    creation_date: Optional[str] = None
    last_modified: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    extracted_entities: list[str] = Field(default_factory=list)


class ImageData(BaseModel):
    """Represents processed image data ready for embedding."""
    image_path: str
    parent_doc_id: str
    content_hash: str
    file_size: int
    width: Optional[int] = None
    height: Optional[int] = None
    exif_data: Optional[dict] = None
    ocr_text: Optional[str] = None
    caption: Optional[str] = None
    creation_date: Optional[str] = None
    last_modified: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    extracted_entities: list[str] = Field(default_factory=list)


class AudioChunk(BaseModel):
    """Represents a processed audio chunk ready for embedding."""
    text: str  # Transcript chunk
    chunk_index: int
    parent_doc_id: str
    source_path: str
    file_type: str
    content_hash: str
    file_size: int
    audio_duration: Optional[float] = None
    sample_rate: Optional[int] = None
    full_transcript: Optional[str] = None
    creation_date: Optional[str] = None
    last_modified: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    extracted_entities: list[str] = Field(default_factory=list)


# ============================================================================
# API Request Models
# ============================================================================

class IngestTextRequest(BaseModel):
    """Request model for text file ingestion."""
    content: Optional[str] = Field(None, description="Text content (if not uploading file)")
    source_path: Optional[str] = Field(None, description="Original file path")
    file_type: Optional[str] = Field("txt", description="File type")
    tags: list[str] = Field(default_factory=list, description="Custom tags")


class IngestImageRequest(BaseModel):
    """Request model for image ingestion."""
    source_path: Optional[str] = Field(None, description="Original file path")
    tags: list[str] = Field(default_factory=list, description="Custom tags")


class IngestAudioRequest(BaseModel):
    """Request model for audio ingestion."""
    source_path: Optional[str] = Field(None, description="Original file path")
    tags: list[str] = Field(default_factory=list, description="Custom tags")


class IngestDirectoryRequest(BaseModel):
    """Request model for directory ingestion."""
    directory_path: str = Field(..., description="Path to directory")
    recursive: bool = Field(True, description="Recursively process subdirectories")
    file_patterns: list[str] = Field(default_factory=lambda: ["*"], description="File patterns to match")
    exclude_patterns: list[str] = Field(default_factory=list, description="Patterns to exclude")
    tags: Optional[str] = Field(None, description="Comma-separated tags to apply to all files")


class SearchRequest(BaseModel):
    """Request model for semantic search."""
    query: str = Field(..., description="Search query text")
    collection: Optional[CollectionName] = Field(None, description="Specific collection to search")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")
    filters: Optional[dict] = Field(None, description="Qdrant filter conditions")
    score_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum similarity score")

    class Config:
        use_enum_values = True


class ImageSearchRequest(BaseModel):
    """Request model for image similarity search."""
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")
    filters: Optional[dict] = Field(None, description="Qdrant filter conditions")
    score_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum similarity score")


# ============================================================================
# API Response Models
# ============================================================================

class SearchResult(BaseModel):
    """Single search result with score and payload."""
    id: str = Field(..., description="Point ID")
    score: float = Field(..., description="Similarity score")
    collection: str = Field(..., description="Source collection")
    payload: VectorPayload = Field(..., description="Point payload with metadata")


class SearchResponse(BaseModel):
    """Response model for search operations."""
    results: list[SearchResult]
    query: str
    total_results: int
    collections_searched: list[str]


class IngestResponse(BaseModel):
    """Response model for ingestion operations."""
    success: bool
    message: str
    points_created: int
    parent_doc_id: str
    processing_time_ms: float
    skipped_unchanged: bool = False


class CollectionInfo(BaseModel):
    """Information about a Qdrant collection."""
    name: str
    vectors_count: int
    indexed_vectors_count: int
    points_count: int
    segments_count: int
    status: str
    optimizer_status: str
    vector_size: int


class CollectionStats(BaseModel):
    """Statistics for a collection."""
    name: str
    total_points: int
    total_vectors: int
    vector_dimension: int


class CollectionsResponse(BaseModel):
    """Response listing all collections."""
    collections: list[CollectionStats]


class HealthResponse(BaseModel):
    """Health check response."""
    status: Literal["healthy", "unhealthy"]
    qdrant_connected: bool
    qdrant_version: Optional[str] = None
    collections: list[str] = Field(default_factory=list)
    message: Optional[str] = None


class DeleteResponse(BaseModel):
    """Response for delete operations."""
    success: bool
    message: str
    deleted_count: int


# ============================================================================
# Internal Models
# ============================================================================

class EmbeddingResult(BaseModel):
    """Result from embedding generation."""
    vectors: list[list[float]]
    dimension: int
    model_name: str


class ProcessingResult(BaseModel):
    """Result from content processing pipeline."""
    chunks: list[TextChunk] | list[AudioChunk] | None = None
    image_data: Optional[ImageData] = None
    processing_time_ms: float
    success: bool
    error: Optional[str] = None
