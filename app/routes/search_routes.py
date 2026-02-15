"""
FastAPI routes for search operations.
Unified text-centric search across all modalities (text, images, audio).
All content is in the same embedding space — single search covers everything.
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
# Unified Search (text-centric — all modalities in same vector space)
# ============================================================================


@router.post("", response_model=SearchResponse)
async def search_all(request: SearchRequest):
    """
    Unified search across ALL content types (text, images, audio).
    All modalities are converted to text and embedded in the same space,
    so a single search returns results from every modality.

    Args:
        request: Search request with query text

    Returns:
        SearchResponse with ranked results from all modalities
    """
    try:
        logger.info(f"Unified search for: '{request.query}'")

        # Single search across everything — no fusion needed
        results = qdrant_manager.search_unified(
            query_text=request.query,
            limit=request.limit,
            filters=request.filters,
            score_threshold=request.score_threshold,
        )

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

        # Single unified search — all modalities in the same vector space
        results = qdrant_manager.search_unified(
            query_text=request.query,
            limit=request.limit,
            filters=request.filters,
            score_threshold=request.score_threshold,
        )

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
# Filtered Search
# ============================================================================


@router.post("/by-type/{content_type}", response_model=SearchResponse)
async def search_by_content_type(content_type: str, request: SearchRequest):
    """
    Search filtered by content type (text, image, audio).
    Uses the same text_vector — just filters results.

    Args:
        content_type: Filter to 'text', 'image', or 'audio'
        request: Search request

    Returns:
        SearchResponse with results of the specified type only
    """
    try:
        valid_types = {"text", "image", "audio"}
        if content_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid content_type. Must be one of: {valid_types}",
            )

        logger.info(f"Searching {content_type} for: '{request.query}'")

        results = qdrant_manager.search_unified(
            query_text=request.query,
            content_types=[content_type],
            limit=request.limit,
            filters=request.filters,
            score_threshold=request.score_threshold,
        )

        return SearchResponse(
            results=results,
            query=request.query,
            total_results=len(results),
            collections_searched=[settings.unified_collection],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in filtered search: {e}")
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
