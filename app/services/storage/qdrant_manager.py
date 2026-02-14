"""
Qdrant manager for all vector database operations.
Handles collection setup, CRUD operations, and semantic search.
"""

import logging
from typing import Optional
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    ScoredPoint,
    NamedVector,
)
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings
from app.models.models import (
    TextChunk,
    ImageData,
    AudioChunk,
    VectorPayload,
    CollectionName,
    SearchResult,
)
from ..embeddings import (
    get_text_embedder,
    get_image_embedder,
    get_caption_embedder,
)

logger = logging.getLogger(__name__)


class QdrantManager:
    """
    Manages all Qdrant vector database operations.
    Handles collections, embeddings, CRUD, and search.
    """

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        """
        Initialize Qdrant manager.

        Args:
            host: Qdrant host (defaults to settings)
            port: Qdrant port (defaults to settings)
        """
        self.host = host or settings.qdrant_host
        self.port = port or settings.qdrant_port

        # Initialize client
        self.client = QdrantClient(host=self.host, port=self.port)

        # Lazy-loaded embedders
        self._text_embedder = None
        self._image_embedder = None
        self._caption_embedder = None

        logger.info(f"Initialized QdrantManager connected to {self.host}:{self.port}")

    @property
    def text_embedder(self):
        """Lazy-load text embedder."""
        if self._text_embedder is None:
            self._text_embedder = get_text_embedder()
        return self._text_embedder

    @property
    def image_embedder(self):
        """Lazy-load image embedder."""
        if self._image_embedder is None:
            self._image_embedder = get_image_embedder()
        return self._image_embedder

    @property
    def caption_embedder(self):
        """Lazy-load caption embedder."""
        if self._caption_embedder is None:
            self._caption_embedder = get_caption_embedder(settings.text_to_image_model)
        return self._caption_embedder

    # ========================================================================
    # Collection Setup
    # ========================================================================

    def create_collections(self) -> None:
        """Create unified collection with named vectors for all modalities."""
        try:
            logger.info("Creating unified Qdrant collection...")

            # Create single collection with named vectors for all modalities
            if not self.client.collection_exists(settings.unified_collection):
                self.client.create_collection(
                    collection_name=settings.unified_collection,
                    vectors_config={
                        # Text chunks and audio transcripts use text embeddings
                        "text_vector": VectorParams(
                            size=settings.text_embedding_dim,
                            distance=Distance.COSINE,
                            hnsw_config={
                                "m": settings.hnsw_m,
                                "ef_construct": settings.hnsw_ef_construct,
                            },
                        ),
                        # Image similarity (DINOv2)
                        "image_vector": VectorParams(
                            size=settings.image_embedding_dim,
                            distance=Distance.COSINE,
                            hnsw_config={
                                "m": settings.hnsw_m,
                                "ef_construct": settings.hnsw_ef_construct,
                            },
                        ),
                        # Text-to-image search (SigLIP)
                        "text_to_image_vector": VectorParams(
                            size=settings.text_to_image_dim,
                            distance=Distance.COSINE,
                            hnsw_config={
                                "m": settings.hnsw_m,
                                "ef_construct": settings.hnsw_ef_construct,
                            },
                        ),
                    },
                )
                logger.info(
                    f"Created unified collection: {settings.unified_collection} with named vectors"
                )

                # Create payload indexes for efficient filtering
                self._create_payload_indexes(settings.unified_collection)
            else:
                logger.info(f"Collection {settings.unified_collection} already exists")

            logger.info("Collection setup completed successfully")

        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            raise

    def _create_payload_indexes(self, collection_name: str) -> None:
        """Create indexes on payload fields for efficient filtering."""
        try:
            # Index commonly filtered fields (especially content_type for filtering by modality)
            fields_to_index = [
                "content_type",  # Critical for filtering by text/image/audio
                "file_type",
                "content_hash",
                "parent_doc_id",
                "source_path",
            ]

            for field in fields_to_index:
                try:
                    self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field,
                        field_schema="keyword",
                    )
                    logger.debug(f"Created index on {collection_name}.{field}")
                except Exception as e:
                    logger.warning(f"Could not create index on {field}: {e}")

        except Exception as e:
            logger.warning(f"Error creating payload indexes: {e}")

    def delete_collection(self, name: str) -> bool:
        """
        Delete a collection.

        Args:
            name: Collection name

        Returns:
            True if deleted, False if not found
        """
        try:
            if self.client.collection_exists(name):
                self.client.delete_collection(name)
                logger.info(f"Deleted collection: {name}")
                return True
            else:
                logger.warning(f"Collection not found: {name}")
                return False
        except Exception as e:
            logger.error(f"Error deleting collection {name}: {e}")
            raise

    # ========================================================================
    # Write Operations
    # ========================================================================

    def upsert_text_chunks(self, chunks: list[TextChunk]) -> list[str]:
        """
        Upsert text chunks with embeddings.

        Args:
            chunks: List of TextChunk objects

        Returns:
            List of point IDs
        """
        try:
            if not chunks:
                return []

            logger.info(f"Upserting {len(chunks)} text chunks to Qdrant")

            # Extract text for embedding
            texts = [chunk.text for chunk in chunks]

            # Generate embeddings in batch
            embeddings = self.text_embedder.embed_batch(texts)

            # Create points
            points = []
            point_ids = []

            for chunk, embedding in zip(chunks, embeddings):
                point_id = str(uuid.uuid4())
                point_ids.append(point_id)

                # Create payload
                payload = VectorPayload(
                    source_path=chunk.source_path,
                    content_type="text",
                    file_type=chunk.file_type,
                    chunk_index=chunk.chunk_index,
                    chunk_text=chunk.text,
                    content_hash=chunk.content_hash,
                    parent_doc_id=chunk.parent_doc_id,
                    file_size=chunk.file_size,
                    creation_date=chunk.creation_date,
                    last_modified=chunk.last_modified,
                    tags=chunk.tags,
                    extracted_entities=chunk.extracted_entities,
                )

                # Use named vector for text content
                point = PointStruct(
                    id=point_id,
                    vector={"text_vector": embedding},
                    payload=payload.model_dump(),
                )
                points.append(point)

            # Upsert to Qdrant unified collection
            self.client.upsert(
                collection_name=settings.unified_collection, points=points
            )

            logger.info(f"Upserted {len(points)} text chunks successfully")
            return point_ids

        except Exception as e:
            logger.error(f"Error upserting text chunks: {e}")
            raise

    def upsert_image(self, image_data: ImageData) -> str:
        """
        Upsert image with DINOv2 (image similarity) and SigLIP (text-to-image) embeddings.

        Args:
            image_data: ImageData object

        Returns:
            Point ID
        """
        try:
            logger.info(f"Upserting image: {image_data.image_path}")

            # Generate DINOv2 image embedding for image-to-image similarity
            image_embedding = self.image_embedder.embed(image_data.image_path)

            # For text-to-image search, we need the caption embedder (SigLIP)
            # This embeds both the image and text in the same space
            caption_text = image_data.caption or image_data.ocr_text or "image"
            text_to_image_embedding = self.caption_embedder.embed(image_data.image_path)

            # Create point ID
            point_id = str(uuid.uuid4())

            # Create payload
            payload = VectorPayload(
                source_path=image_data.image_path,
                content_type="image",
                file_type=Path(image_data.image_path).suffix.lstrip("."),
                chunk_index=0,
                chunk_text=caption_text,
                content_hash=image_data.content_hash,
                parent_doc_id=image_data.parent_doc_id,
                file_size=image_data.file_size,
                creation_date=image_data.creation_date,
                last_modified=image_data.last_modified,
                tags=image_data.tags,
                extracted_entities=image_data.extracted_entities,
                # Image-specific
                image_width=image_data.width,
                image_height=image_data.height,
                exif_data=image_data.exif_data,
                ocr_text=image_data.ocr_text,
                caption=image_data.caption,
            )

            # Create point with named vectors
            point = PointStruct(
                id=point_id,
                vector={
                    "image_vector": image_embedding,  # DINOv2 for image similarity
                    "text_to_image_vector": text_to_image_embedding,  # SigLIP for text-to-image
                },
                payload=payload.model_dump(exclude_none=True),
            )

            # Upsert to unified collection
            self.client.upsert(
                collection_name=settings.unified_collection, points=[point]
            )

            logger.info(f"Upserted image successfully: {point_id}")
            return point_id

        except Exception as e:
            logger.error(f"Error upserting image: {e}")
            raise

    def upsert_audio_chunks(self, chunks: list[AudioChunk]) -> list[str]:
        """
        Upsert audio transcript chunks with embeddings.

        Args:
            chunks: List of AudioChunk objects

        Returns:
            List of point IDs
        """
        try:
            if not chunks:
                return []

            logger.info(f"Upserting {len(chunks)} audio chunks to Qdrant")

            # Extract transcript text for embedding
            texts = [chunk.text for chunk in chunks]

            # Generate embeddings in batch
            embeddings = self.text_embedder.embed_batch(texts)

            # Create points
            points = []
            point_ids = []

            for chunk, embedding in zip(chunks, embeddings):
                point_id = str(uuid.uuid4())
                point_ids.append(point_id)

                # Create payload
                payload = VectorPayload(
                    source_path=chunk.source_path,
                    content_type="audio",
                    file_type=chunk.file_type,
                    chunk_index=chunk.chunk_index,
                    chunk_text=chunk.text,
                    content_hash=chunk.content_hash,
                    parent_doc_id=chunk.parent_doc_id,
                    file_size=chunk.file_size,
                    creation_date=chunk.creation_date,
                    last_modified=chunk.last_modified,
                    tags=chunk.tags,
                    extracted_entities=chunk.extracted_entities,
                    # Audio-specific
                    audio_duration=chunk.audio_duration,
                    sample_rate=chunk.sample_rate,
                    transcript=chunk.full_transcript,
                )

                # Use named vector for audio transcript
                point = PointStruct(
                    id=point_id,
                    vector={"text_vector": embedding},
                    payload=payload.model_dump(exclude_none=True),
                )
                points.append(point)

            # Upsert to Qdrant unified collection
            self.client.upsert(
                collection_name=settings.unified_collection, points=points
            )

            logger.info(f"Upserted {len(points)} audio chunks successfully")
            return point_ids

        except Exception as e:
            logger.error(f"Error upserting audio chunks: {e}")
            raise

    def delete_by_source_path(self, collection: str, source_path: str) -> int:
        """
        Delete all points from a specific source file.

        Args:
            collection: Collection name
            source_path: Source file path

        Returns:
            Number of deleted points
        """
        try:
            # Delete with filter
            result = self.client.delete(
                collection_name=collection,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="source_path", match=MatchValue(value=source_path)
                        )
                    ]
                ),
            )

            logger.info(f"Deleted points from {source_path} in {collection}")
            return result.operation_id if result else 0

        except Exception as e:
            logger.error(f"Error deleting by source path: {e}")
            raise

    def delete_by_parent_doc(self, collection: str, parent_doc_id: str) -> int:
        """
        Delete all points from a specific parent document.

        Args:
            collection: Collection name
            parent_doc_id: Parent document ID

        Returns:
            Number of deleted points
        """
        try:
            result = self.client.delete(
                collection_name=collection,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="parent_doc_id", match=MatchValue(value=parent_doc_id)
                        )
                    ]
                ),
            )

            logger.info(
                f"Deleted points with parent_doc_id={parent_doc_id} from {collection}"
            )
            return result.operation_id if result else 0

        except Exception as e:
            logger.error(f"Error deleting by parent doc: {e}")
            raise

    # ========================================================================
    # Search Operations
    # ========================================================================

    def semantic_search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filters: Optional[dict] = None,
        score_threshold: Optional[float] = None,
        vector_name: Optional[str] = None,
    ) -> list[ScoredPoint]:
        """
        Perform semantic search in a collection.

        Args:
            collection: Collection name
            query_vector: Query embedding vector
            limit: Maximum results
            filters: Optional Qdrant filter dict
            score_threshold: Minimum similarity score
            vector_name: Named vector to search (for image collection)

        Returns:
            List of scored points
        """
        try:
            # Build search query filter
            search_filter = None
            if filters:
                search_filter = Filter(**filters)

            # Build query parameters for query_points
            query_params = {
                "collection_name": collection,
                "query": query_vector,  # Use 'query' parameter, not 'query_vector'
                "limit": limit,
                "with_payload": True,
            }

            # Add optional parameters
            if vector_name:
                query_params["using"] = vector_name

            if search_filter:
                query_params["query_filter"] = search_filter

            if score_threshold:
                query_params["score_threshold"] = score_threshold

            # Use query_points() method and extract points from response
            response = self.client.query_points(**query_params)
            results = response.points

            logger.debug(f"Search in {collection} returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            raise

    def search_text(
        self,
        query_text: str,
        content_types: Optional[list[str]] = None,
        limit: int = 10,
        filters: Optional[dict] = None,
        score_threshold: Optional[float] = None,
    ) -> list[SearchResult]:
        """
        Search using text query across text and/or audio content.

        Args:
            query_text: Text query
            content_types: Filter by content types (e.g., ["text", "audio"]), None = both
            limit: Max results
            filters: Optional additional filters
            score_threshold: Min score

        Returns:
            List of SearchResult objects
        """
        try:
            # Embed query
            query_embedding = self.text_embedder.embed(query_text)

            # Build filter to search text and audio content
            if content_types is None:
                content_types = ["text", "audio"]

            # Merge content_type filter with any existing filters
            search_filters = filters or {}
            if "must" not in search_filters:
                search_filters["must"] = []

            # Add content_type filter
            if len(content_types) == 1:
                search_filters["must"].append(
                    FieldCondition(
                        key="content_type", match=MatchValue(value=content_types[0])
                    )
                )
            else:
                # Multiple content types, use MatchAny
                search_filters["must"].append(
                    FieldCondition(
                        key="content_type", match=MatchAny(any=content_types)
                    )
                )

            scored_points = self.semantic_search(
                collection=settings.unified_collection,
                query_vector=query_embedding,
                limit=limit,
                filters=search_filters,
                score_threshold=score_threshold,
                vector_name="text_vector",
            )

            results = []
            for sp in scored_points:
                payload = VectorPayload(**sp.payload)
                result = SearchResult(
                    id=sp.id,
                    score=sp.score,
                    collection=settings.unified_collection,
                    payload=payload,
                )
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Error in text search: {e}")
            raise

    def search_image_by_text(
        self,
        query_text: str,
        limit: int = 10,
        filters: Optional[dict] = None,
        score_threshold: Optional[float] = None,
    ) -> list[SearchResult]:
        """
        Search images using text query (via SigLIP text-to-image embeddings).

        Args:
            query_text: Text query
            limit: Max results
            filters: Optional filters
            score_threshold: Min score

        Returns:
            List of SearchResult objects
        """
        try:
            # Embed query text using caption embedder (SigLIP)
            query_embedding = self.caption_embedder.embed_text(query_text)

            # Build filter for image content
            search_filters = filters or {}
            if "must" not in search_filters:
                search_filters["must"] = []

            search_filters["must"].append(
                FieldCondition(key="content_type", match=MatchValue(value="image"))
            )

            # Search using text_to_image_vector
            scored_points = self.semantic_search(
                collection=settings.unified_collection,
                query_vector=query_embedding,
                limit=limit,
                filters=search_filters,
                score_threshold=score_threshold,
                vector_name="text_to_image_vector",
            )

            results = []
            for sp in scored_points:
                payload = VectorPayload(**sp.payload)
                result = SearchResult(
                    id=sp.id,
                    score=sp.score,
                    collection=settings.unified_collection,
                    payload=payload,
                )
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Error in image text search: {e}")
            raise

    def search_image_by_image(
        self,
        image_path: str,
        limit: int = 10,
        filters: Optional[dict] = None,
        score_threshold: Optional[float] = None,
    ) -> list[SearchResult]:
        """
        Search similar images using image query (DINOv2 embeddings).

        Args:
            image_path: Path to query image
            limit: Max results
            filters: Optional filters
            score_threshold: Min score

        Returns:
            List of SearchResult objects
        """
        try:
            # Generate DINOv2 embedding for query image
            query_embedding = self.image_embedder.embed(image_path)

            # Build filter for image content
            search_filters = filters or {}
            if "must" not in search_filters:
                search_filters["must"] = []

            search_filters["must"].append(
                FieldCondition(key="content_type", match=MatchValue(value="image"))
            )

            # Search using image_vector
            scored_points = self.semantic_search(
                collection=settings.unified_collection,
                query_vector=query_embedding,
                limit=limit,
                filters=search_filters,
                score_threshold=score_threshold,
                vector_name="image_vector",
            )

            results = []
            for sp in scored_points:
                payload = VectorPayload(**sp.payload)
                result = SearchResult(
                    id=sp.id,
                    score=sp.score,
                    collection=settings.unified_collection,
                    payload=payload,
                )
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Error in image similarity search: {e}")
            raise

    def search_by_hash(self, collection: str, content_hash: str) -> list[ScoredPoint]:
        """
        Search for points with a specific content hash.

        Args:
            collection: Collection name
            content_hash: Content hash to search

        Returns:
            List of matching points
        """
        try:
            results = self.client.scroll(
                collection_name=collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="content_hash", match=MatchValue(value=content_hash)
                        )
                    ]
                ),
                limit=100,
                with_payload=True,
                with_vectors=False,
            )

            points = results[0] if results else []
            logger.debug(f"Hash search in {collection} found {len(points)} matches")
            return points

        except Exception as e:
            logger.error(f"Error searching by hash: {e}")
            return []

    # ========================================================================
    # Info & Stats
    # ========================================================================

    def collection_info(self, name: str) -> dict:
        """Get collection information."""
        try:
            info = self.client.get_collection(name)
            return {
                "name": name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status.value,
                "optimizer_status": info.optimizer_status.value,
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            raise

    def count_points(self, collection: str) -> int:
        """Count points in a collection."""
        try:
            info = self.client.get_collection(collection)
            return info.points_count
        except Exception as e:
            logger.error(f"Error counting points: {e}")
            return 0

    def get_by_id(self, collection: str, point_id: str):
        """Retrieve a specific point by ID."""
        try:
            points = self.client.retrieve(
                collection_name=collection,
                ids=[point_id],
                with_payload=True,
                with_vectors=False,
            )
            return points[0] if points else None
        except Exception as e:
            logger.error(f"Error retrieving point: {e}")
            return None

    def list_collections(self) -> list[str]:
        """List all collection names."""
        try:
            collections = self.client.get_collections()
            return [c.name for c in collections.collections]
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            return []

    def health_check(self) -> bool:
        """Check if Qdrant is accessible."""
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False


# Add missing import
from pathlib import Path


# Global singleton instance
_qdrant_manager: Optional[QdrantManager] = None


def get_qdrant_manager() -> QdrantManager:
    """Get or create global QdrantManager instance."""
    global _qdrant_manager
    if _qdrant_manager is None:
        _qdrant_manager = QdrantManager()
    return _qdrant_manager
