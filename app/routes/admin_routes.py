"""
FastAPI routes for admin operations.
Handles collection management, health checks, and statistics.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from qdrant_client.http.exceptions import UnexpectedResponse

from ..models.models import (
    CollectionsResponse,
    CollectionStats,
    HealthResponse,
    DeleteResponse,
    CollectionInfo,
)
from app.services.storage import get_qdrant_manager
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Admin"])

# Get global Qdrant manager
qdrant_manager = get_qdrant_manager()


# ============================================================================
# Health Check
# ============================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Check service health and Qdrant connection.

    Returns:
        HealthResponse with connection status
    """
    try:
        # Test Qdrant connection
        is_healthy = qdrant_manager.health_check()

        if not is_healthy:
            return HealthResponse(
                status="unhealthy",
                qdrant_connected=False,
                message="Cannot connect to Qdrant",
            )

        # Get collections
        collections = qdrant_manager.list_collections()

        # Try to get Qdrant version
        try:
            # The client doesn't expose version directly, so we'll skip this
            version = None
        except:
            version = None

        return HealthResponse(
            status="healthy",
            qdrant_connected=True,
            qdrant_version=version,
            collections=collections,
            message="All systems operational",
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy", qdrant_connected=False, message=str(e)
        )


# ============================================================================
# Collection Management
# ============================================================================


@router.get("/collections", response_model=CollectionsResponse)
async def list_collections():
    """
    List all Qdrant collections with statistics.

    Returns:
        CollectionsResponse with collection stats
    """
    try:
        collection_names = qdrant_manager.list_collections()

        stats_list = []
        for name in collection_names:
            try:
                info = qdrant_manager.collection_info(name)

                # Determine vector dimension
                coll_info = qdrant_manager.client.get_collection(name)
                if hasattr(coll_info.config.params, "vectors"):
                    # Single vector config
                    vector_dim = coll_info.config.params.vectors.size
                else:
                    # Named vectors (image collection)
                    vector_dim = 0  # Multiple dimensions

                stats = CollectionStats(
                    name=name,
                    total_points=info["points_count"],
                    total_vectors=info["vectors_count"],
                    vector_dimension=vector_dim,
                )
                stats_list.append(stats)

            except Exception as e:
                logger.warning(f"Error getting stats for {name}: {e}")

        return CollectionsResponse(collections=stats_list)

    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{name}", response_model=CollectionInfo)
async def get_collection_info(name: str):
    """
    Get detailed information about a specific collection.

    Args:
        name: Collection name

    Returns:
        CollectionInfo with details
    """
    try:
        if not qdrant_manager.client.collection_exists(name):
            raise HTTPException(status_code=404, detail=f"Collection not found: {name}")

        info = qdrant_manager.client.get_collection(name)

        # Extract vector size
        if hasattr(info.config.params, "vectors"):
            vector_size = info.config.params.vectors.size
        else:
            vector_size = 0  # Named vectors

        return CollectionInfo(
            name=name,
            vectors_count=info.vectors_count or 0,
            indexed_vectors_count=info.indexed_vectors_count or 0,
            points_count=info.points_count or 0,
            segments_count=info.segments_count or 0,
            status=info.status.value,
            optimizer_status=info.optimizer_status.value,
            vector_size=vector_size,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collections/create")
async def create_all_collections():
    """
    Create all required collections with proper configuration.

    Returns:
        Success message
    """
    try:
        qdrant_manager.create_collections()

        return {
            "success": True,
            "message": "Unified collection created successfully",
            "collection": settings.unified_collection,
            "architecture": "Named vectors with metadata filtering",
        }

    except Exception as e:
        logger.error(f"Error creating collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{name}", response_model=DeleteResponse)
async def delete_collection(name: str):
    """
    Delete a collection.

    Args:
        name: Collection name to delete

    Returns:
        DeleteResponse with status
    """
    try:
        if not qdrant_manager.client.collection_exists(name):
            raise HTTPException(status_code=404, detail=f"Collection not found: {name}")

        # Get point count before deletion
        count = qdrant_manager.count_points(name)

        # Delete collection
        qdrant_manager.delete_collection(name)

        return DeleteResponse(
            success=True,
            message=f"Collection '{name}' deleted successfully",
            deleted_count=count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{name}/purge", response_model=DeleteResponse)
async def purge_collection(name: str):
    """
    Delete all points in a collection (but keep the collection).

    Args:
        name: Collection name to purge

    Returns:
        DeleteResponse with deleted count
    """
    try:
        if not qdrant_manager.client.collection_exists(name):
            raise HTTPException(status_code=404, detail=f"Collection not found: {name}")

        # Get current count
        count = qdrant_manager.count_points(name)

        # Delete collection and recreate
        qdrant_manager.delete_collection(name)
        qdrant_manager.create_collections()

        return DeleteResponse(
            success=True,
            message=f"Purged all points from '{name}'",
            deleted_count=count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error purging collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Point Management
# ============================================================================


@router.delete("/points/by-source")
async def delete_by_source(
    source_path: str = Query(..., description="Source file path to delete"),
    collection: Optional[str] = Query(None, description="Collection name (or all)"),
):
    """
    Delete all points from a specific source file.

    Args:
        source_path: Source file path
        collection: Optional collection filter

    Returns:
        Delete summary
    """
    try:
        # Delete from unified collection
        result = qdrant_manager.delete_by_source_path(
            settings.unified_collection, source_path
        )

        return DeleteResponse(
            success=True,
            message=f"Deleted points from source: {source_path}",
            deleted_count=1 if result else 0,
        )

    except Exception as e:
        logger.error(f"Error deleting by source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/points/by-parent-doc")
async def delete_by_parent_doc(
    parent_doc_id: str = Query(..., description="Parent document ID to delete"),
    collection: Optional[str] = Query(None, description="Collection name (or all)"),
):
    """
    Delete all points from a specific parent document.

    Args:
        parent_doc_id: Parent document ID
        collection: Optional collection filter

    Returns:
        Delete summary
    """
    try:
        # Delete from unified collection
        result = qdrant_manager.delete_by_parent_doc(
            settings.unified_collection, parent_doc_id
        )

        return DeleteResponse(
            success=True,
            message=f"Deleted points from parent doc: {parent_doc_id}",
            deleted_count=1 if result else 0,
        )

    except Exception as e:
        logger.error(f"Error deleting by parent doc: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Statistics
# ============================================================================


@router.get("/stats")
async def get_stats():
    """
    Get overall system statistics.

    Returns:
        System stats summary
    """
    try:
        collections = qdrant_manager.list_collections()

        stats = {"collections": {}, "total_points": 0, "total_vectors": 0}

        for coll in collections:
            try:
                info = qdrant_manager.collection_info(coll)
                stats["collections"][coll] = {
                    "points": info["points_count"],
                    "vectors": info["vectors_count"],
                    "status": info["status"],
                }
                stats["total_points"] += info["points_count"]
                stats["total_vectors"] += info["vectors_count"]
            except Exception as e:
                logger.warning(f"Error getting stats for {coll}: {e}")

        return stats

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
