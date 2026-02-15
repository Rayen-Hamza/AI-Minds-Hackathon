"""
Qdrant Agent - Specialized agent for vector database operations.
Handles semantic search, collection management, and data retrieval from Qdrant.
"""

import logging
from typing import Dict, Any
from pathlib import Path
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.models import LiteLlm

from ..services.storage import get_qdrant_manager
from ..config import settings

logger = logging.getLogger(__name__)

# Get global Qdrant manager
qdrant_manager = get_qdrant_manager()


# ============================================================================
# Qdrant Tools
# ============================================================================


def search_vectors(
    query: str, limit: int = 5, content_type: str = None, tags: str = None
) -> Dict[str, Any]:
    """
    Perform semantic search in the vector database.

    Args:
        query: The search query text
        limit: Maximum number of results to return (default: 5)
        content_type: Filter by content type (text, image, audio, or None for all)
        tags: Comma-separated tags to filter by (optional)

    Returns:
        Dictionary containing search results with content, scores, and metadata
    """
    try:
        logger.info(
            f"Searching vectors for query: '{query}' (limit={limit}, type={content_type})"
        )

        # Build filters
        filters = {}
        if content_type:
            filters["content_type"] = content_type
        if tags:
            filters["tags"] = tags

        # Perform search
        results = qdrant_manager.search(
            collection_name=settings.unified_collection,
            query_text=query,
            limit=limit,
            filters=filters if filters else None,
        )

        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append(
                {
                    "content": result.content,
                    "score": result.score,
                    "content_type": result.content_type,
                    "source_file": result.source_file,
                    "tags": result.tags,
                    "metadata": result.metadata,
                }
            )

        return {
            "success": True,
            "query": query,
            "results_count": len(formatted_results),
            "results": formatted_results,
        }

    except Exception as e:
        logger.error(f"Error searching vectors: {e}")
        return {"success": False, "error": str(e), "query": query}


def get_collection_info(collection_name: str = None) -> Dict[str, Any]:
    """
    Get information about a Qdrant collection.

    Args:
        collection_name: Name of the collection (defaults to unified collection)

    Returns:
        Dictionary containing collection information
    """
    try:
        collection = collection_name or settings.unified_collection
        logger.info(f"Getting info for collection: {collection}")

        info = qdrant_manager.client.get_collection(collection_name=collection)

        return {
            "success": True,
            "collection_name": collection,
            "points_count": info.points_count,
            "vectors_count": info.vectors_count,
            "status": info.status.value,
        }

    except Exception as e:
        logger.error(f"Error getting collection info: {e}")
        return {"success": False, "error": str(e), "collection_name": collection_name}


def list_collections() -> Dict[str, Any]:
    """
    List all available Qdrant collections.

    Returns:
        Dictionary containing list of collection names
    """
    try:
        logger.info("Listing all collections")

        collections = qdrant_manager.client.get_collections()
        collection_names = [col.name for col in collections.collections]

        return {
            "success": True,
            "collections": collection_names,
            "count": len(collection_names),
        }

    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        return {"success": False, "error": str(e)}


def search_by_filters(
    content_type: str = None, tags: str = None, source_file: str = None, limit: int = 10
) -> Dict[str, Any]:
    """
    Search vectors using only metadata filters (no semantic search).

    Args:
        content_type: Filter by content type (text, image, audio)
        tags: Comma-separated tags to filter by
        source_file: Filter by source file name
        limit: Maximum number of results to return

    Returns:
        Dictionary containing filtered results
    """
    try:
        logger.info(
            f"Searching by filters: type={content_type}, tags={tags}, file={source_file}"
        )

        # Build filters
        filters = {}
        if content_type:
            filters["content_type"] = content_type
        if tags:
            filters["tags"] = tags
        if source_file:
            filters["source_file"] = source_file

        if not filters:
            return {"success": False, "error": "At least one filter must be provided"}

        # Use a dummy query for filter-only search
        results = qdrant_manager.search(
            collection_name=settings.unified_collection,
            query_text="",
            limit=limit,
            filters=filters,
        )

        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append(
                {
                    "content": result.content,
                    "content_type": result.content_type,
                    "source_file": result.source_file,
                    "tags": result.tags,
                    "metadata": result.metadata,
                }
            )

        return {
            "success": True,
            "filters": filters,
            "results_count": len(formatted_results),
            "results": formatted_results,
        }

    except Exception as e:
        logger.error(f"Error searching by filters: {e}")
        return {"success": False, "error": str(e)}


def get_vector_stats() -> Dict[str, Any]:
    """
    Get statistics about vectors in the database.

    Returns:
        Dictionary containing vector database statistics
    """
    try:
        logger.info("Getting vector database statistics")

        collection_name = settings.unified_collection

        if not qdrant_manager.client.collection_exists(collection_name):
            return {
                "success": False,
                "error": f"Collection {collection_name} does not exist",
            }

        info = qdrant_manager.client.get_collection(collection_name=collection_name)

        return {
            "success": True,
            "collection": collection_name,
            "total_vectors": info.points_count,
            "status": info.status.value,
            "vector_dimension": settings.text_embedding_dim,
            "distance_metric": "COSINE",
        }

    except Exception as e:
        logger.error(f"Error getting vector stats: {e}")
        return {"success": False, "error": str(e)}


def ingest_directory(
    directory_path: str,
    file_patterns: str = "*.txt,*.md,*.pdf,*.png,*.jpg,*.jpeg,*.wav,*.mp3",
    recursive: bool = False,
    tags: str = None,
) -> Dict[str, Any]:
    """
    Ingest all supported files from a directory into the vector database.
    Uses the existing ingestion pipeline for processing text, images, and audio.

    Args:
        directory_path: Path to the directory to ingest
        file_patterns: Comma-separated file patterns (e.g., "*.txt,*.pdf,*.png")
        recursive: Whether to search subdirectories recursively
        tags: Comma-separated tags to apply to all ingested files

    Returns:
        Dictionary containing ingestion status and statistics
    """
    try:
        from ..services.processing import (
            get_text_processor,
            get_image_processor,
            get_audio_processor,
        )
        from ..services.storage import get_content_hasher

        logger.info(f"Ingesting directory: {directory_path} (recursive={recursive})")

        directory = Path(directory_path)
        if not directory.exists() or not directory.is_dir():
            return {"success": False, "error": f"Directory not found: {directory_path}"}

        patterns = [p.strip() for p in file_patterns.split(",")]

        files_to_process = []
        for pattern in patterns:
            if recursive:
                files_to_process.extend(directory.rglob(pattern))
            else:
                files_to_process.extend(directory.glob(pattern))

        files_to_process = [f for f in files_to_process if f.is_file()]

        if not files_to_process:
            return {
                "success": True,
                "message": "No files found matching the patterns",
                "files_found": 0,
                "processed": 0,
            }

        custom_tags = [t.strip() for t in tags.split(",")] if tags else []

        text_processor = get_text_processor()
        image_processor = get_image_processor()
        audio_processor = get_audio_processor()
        content_hasher = get_content_hasher()

        stats = {
            "processed": 0,
            "skipped": 0,
            "errors": 0,
            "text_files": 0,
            "image_files": 0,
            "audio_files": 0,
        }

        for file_path in files_to_process:
            try:
                suffix = file_path.suffix.lower()

                if suffix in [
                    ".txt",
                    ".md",
                    ".pdf",
                    ".py",
                    ".js",
                    ".java",
                    ".cpp",
                    ".h",
                ]:
                    file_type = "text"
                elif suffix in [".png", ".jpg", ".jpeg", ".gif", ".bmp"]:
                    file_type = "image"
                elif suffix in [".wav", ".mp3", ".m4a", ".ogg"]:
                    file_type = "audio"
                else:
                    stats["skipped"] += 1
                    continue

                if file_type == "text":
                    file_hash = content_hasher.hash_content(file_path, "text")
                    if qdrant_manager.search_by_hash(
                        settings.unified_collection, file_hash
                    ):
                        stats["skipped"] += 1
                        continue

                    chunks = text_processor.process_text_file(file_path, custom_tags)
                    if chunks:
                        qdrant_manager.upsert_text_chunks(chunks)
                        stats["text_files"] += 1
                        stats["processed"] += 1

                elif file_type == "image":
                    image_hash = content_hasher.hash_image(file_path)
                    if qdrant_manager.search_by_hash(
                        settings.unified_collection, image_hash
                    ):
                        stats["skipped"] += 1
                        continue

                    image_data = image_processor.process_image(file_path, custom_tags)
                    if image_data:
                        qdrant_manager.upsert_image(image_data)
                        stats["image_files"] += 1
                        stats["processed"] += 1

                elif file_type == "audio":
                    audio_hash = content_hasher.hash_audio(file_path)
                    if qdrant_manager.search_by_hash(
                        settings.unified_collection, audio_hash
                    ):
                        stats["skipped"] += 1
                        continue

                    chunks = audio_processor.process_audio(file_path, custom_tags)
                    if chunks:
                        qdrant_manager.upsert_audio_chunks(chunks)
                        stats["audio_files"] += 1
                        stats["processed"] += 1

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                stats["errors"] += 1

        return {
            "success": True,
            "directory": str(directory),
            "files_found": len(files_to_process),
            "processed": stats["processed"],
            "skipped": stats["skipped"],
            "errors": stats["errors"],
            "text_files": stats["text_files"],
            "image_files": stats["image_files"],
            "audio_files": stats["audio_files"],
        }

    except Exception as e:
        logger.error(f"Error ingesting directory: {e}")
        return {"success": False, "error": str(e), "directory": directory_path}


# ============================================================================
# Qdrant Agent Definition
# ============================================================================

from ..config import settings as qdrant_settings

qdrant_agent = Agent(
    name="qdrant_agent",
    model=LiteLlm(model=f"openai/{qdrant_settings.llm_model}", api_base=qdrant_settings.llm_base_url, api_key="dummy"),
    description="""You are a Qdrant vector database specialist. 
    You help users search for information, ingest content, manage collections, and retrieve data from the vector database.
    You have access to semantic search capabilities, directory ingestion, and can filter by content type, tags, and source files.
    
    Key capabilities:
    - Semantic search across text, images, and audio content
    - Directory ingestion with automatic file type detection
    - Filter-based retrieval by metadata
    - Collection management and statistics
    - Vector database information
    
    When users ask to search or find information, use the search_vectors tool.
    When users ask to ingest, embed, or index files/directories, use the ingest_directory tool.
    When users ask about database statistics or collection info, use the appropriate tools.
    Always provide clear, helpful responses based on the results.""",
    instruction="""You are an expert in vector databases, semantic search, and content ingestion.
    
    When handling search requests:
    1. Use search_vectors for semantic queries
    2. Use search_by_filters when users specify exact filters
    3. Interpret results and present them in a user-friendly format
    4. Explain relevance scores when appropriate
    5. Suggest refinements if results aren't satisfactory
    
    When handling ingestion requests:
    1. Use ingest_directory to process files from a directory
    2. Explain what file types are supported (text, images, audio)
    3. Report statistics about what was processed
    4. Inform users about skipped or failed files
    5. Suggest appropriate tags when relevant
    
    When handling information requests:
    - Use get_collection_info for collection details
    - Use list_collections to show available collections
    - Use get_vector_stats for database statistics
    
    Always be helpful, explain what you're doing, and provide actionable feedback.""",
    tools=[
        FunctionTool(func=search_vectors),
        FunctionTool(func=get_collection_info),
        FunctionTool(func=list_collections),
        FunctionTool(func=search_by_filters),
        FunctionTool(func=get_vector_stats),
        FunctionTool(func=ingest_directory),
    ],
)
