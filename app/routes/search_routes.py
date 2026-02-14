"""
FastAPI routes for search operations.
Handles semantic search across text, images, and audio.
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
import aiofiles

from ..models.models import (
    SearchRequest,
    ImageSearchRequest,
    SearchResponse,
    CollectionName,
)
from app.services.storage import get_qdrant_manager
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["Search"])

# Get global Qdrant manager
qdrant_manager = get_qdrant_manager()


# ============================================================================
# Text Search
# ============================================================================


@router.post("", response_model=SearchResponse)
async def search_all(request: SearchRequest):
    """
    Search across all collections using text query.

    Args:
        request: Search request with query text

    Returns:
        SearchResponse with ranked results
    """
    try:
        logger.info(f"Searching all collections for: '{request.query}'")

        # Search across content types using unified collection
        results = []

        if request.collection:
            # Search specific content type
            if request.collection == CollectionName.UNIFIED:
                # Search all content types (text, image, audio)
                text_results = qdrant_manager.search_text(
                    query_text=request.query,
                    content_types=["text", "audio"],
                    limit=request.limit,
                    filters=request.filters,
                    score_threshold=request.score_threshold,
                )
                image_results = qdrant_manager.search_image_by_text(
                    query_text=request.query,
                    limit=request.limit,
                    filters=request.filters,
                    score_threshold=request.score_threshold,
                )
                results = text_results + image_results
                results.sort(key=lambda x: x.score, reverse=True)
                results = results[: request.limit]
        else:
            # Search all content types
            text_results = qdrant_manager.search_text(
                query_text=request.query,
                content_types=["text", "audio"],
                limit=request.limit,
                filters=request.filters,
                score_threshold=request.score_threshold,
            )
            image_results = qdrant_manager.search_image_by_text(
                query_text=request.query,
                limit=request.limit,
                filters=request.filters,
                score_threshold=request.score_threshold,
            )
            results = text_results + image_results
            results.sort(key=lambda x: x.score, reverse=True)
            results = results[: request.limit]

        return SearchResponse(
            results=results,
            query=request.query,
            total_results=len(results),
            collections_searched=[settings.unified_collection],
        )

    except Exception as e:
        logger.error(f"Error in search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{collection}", response_model=SearchResponse)
async def search_collection(collection: CollectionName, request: SearchRequest):
    """
    Search the unified collection (maintained for API compatibility).

    Args:
        collection: Collection name (only UNIFIED is supported)
        request: Search request

    Returns:
        SearchResponse with results
    """
    try:
        logger.info(f"Searching unified collection for: '{request.query}'")

        # Search all content types in unified collection
        text_results = qdrant_manager.search_text(
            query_text=request.query,
            content_types=["text", "audio"],
            limit=request.limit,
            filters=request.filters,
            score_threshold=request.score_threshold,
        )
        image_results = qdrant_manager.search_image_by_text(
            query_text=request.query,
            limit=request.limit,
            filters=request.filters,
            score_threshold=request.score_threshold,
        )

        results = text_results + image_results
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[: request.limit]

        return SearchResponse(
            results=results,
            query=request.query,
            total_results=len(results),
            collections_searched=[settings.unified_collection],
        )

    except Exception as e:
        logger.error(f"Error searching collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Image Search
# ============================================================================


@router.post("/image", response_model=SearchResponse)
async def search_by_image(
    file: UploadFile = File(...),
    limit: int = Query(10, ge=1, le=100),
    score_threshold: Optional[float] = Query(None, ge=0.0, le=1.0),
):
    """
    Search for similar images using an uploaded image.

    Args:
        file: Query image file
        limit: Maximum results
        score_threshold: Minimum similarity score

    Returns:
        SearchResponse with similar images
    """
    try:
        logger.info(f"Image similarity search with uploaded file: {file.filename}")

        # Save uploaded file temporarily
        temp_path = Path(f"/tmp/query_{file.filename}")
        async with aiofiles.open(temp_path, "wb") as f:
            content_bytes = await file.read()
            await f.write(content_bytes)

        # Search for similar images
        results = qdrant_manager.search_image_by_image(
            image_path=str(temp_path),
            limit=limit,
            filters=None,
            score_threshold=score_threshold,
        )

        # Clean up
        temp_path.unlink()

        return SearchResponse(
            results=results,
            query=f"Image similarity: {file.filename}",
            total_results=len(results),
            collections_searched=[settings.unified_collection],
        )

    except Exception as e:
        logger.error(f"Error in image search: {e}")
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Advanced Filters
# ============================================================================


@router.get("/filters/by-source")
async def search_by_source(
    source_path: str = Query(..., description="Source file path"),
    collection: Optional[CollectionName] = Query(
        None, description="Collection to search"
    ),
):
    """
    Find all chunks/embeddings from a specific source file.

    Args:
        source_path: Source file path to filter by
        collection: Optional collection filter

    Returns:
        List of matching points
    """
    try:
        # Optionally filter by content type
        scroll_filter = {
            "must": [{"key": "source_path", "match": {"value": source_path}}]
        }

        # Add content_type filter if collection specified
        if collection:
            # Map collection enum to content type (for backwards compatibility)
            # Since we only have UNIFIED now, this is mostly for API compatibility
            pass

        # Search unified collection
        results, _ = qdrant_manager.client.scroll(
            collection_name=settings.unified_collection,
            scroll_filter=scroll_filter,
            limit=1000,
            with_payload=True,
            with_vectors=False,
        )

        return {
            "source_path": source_path,
            "total_results": len(results),
            "results": [
                {
                    "id": r.id,
                    "collection": settings.unified_collection,
                    "content_type": r.payload.get("content_type", "unknown"),
                    "payload": r.payload,
                }
                for r in results
            ],
        }

    except Exception as e:
        logger.error(f"Error in source filter search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/filters/by-entity")
async def search_by_entity(
    entity: str = Query(..., description="Entity to search for"),
    collection: Optional[CollectionName] = Query(
        None, description="Collection to search"
    ),
    limit: int = Query(50, ge=1, le=500),
):
    """
    Find all content containing a specific entity.

    Args:
        entity: Entity name to search for
        collection: Optional collection filter
        limit: Maximum results

    Returns:
        List of matching points
    """
    try:
        # Search for entity in extracted_entities field
        results, _ = qdrant_manager.client.scroll(
            collection_name=settings.unified_collection,
            scroll_filter={
                "must": [{"key": "extracted_entities", "match": {"any": [entity]}}]
            },
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return {
            "entity": entity,
            "total_results": len(results),
            "results": [
                {
                    "id": r.id,
                    "content_type": r.payload.get("content_type", "unknown"),
                    "payload": r.payload,
                }
                for r in results[:limit]
            ],
        }

    except Exception as e:
        logger.error(f"Error in entity search: {e}")
        raise HTTPException(status_code=500, detail=str(e))
