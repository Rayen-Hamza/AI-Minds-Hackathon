"""
FastAPI routes for content ingestion.
Handles text, image, and audio file ingestion into Qdrant.
"""

import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import aiofiles

from ..models.models import (
    IngestTextRequest,
    IngestImageRequest,
    IngestAudioRequest,
    IngestDirectoryRequest,
    IngestResponse,
)
from app.services.storage import get_qdrant_manager, get_content_hasher
from app.services.processing import (
    get_text_processor,
    get_image_processor,
    get_audio_processor,
)
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ingest", tags=["Ingestion"])

# Get global instances
qdrant_manager = get_qdrant_manager()
content_hasher = get_content_hasher()
text_processor = get_text_processor()
image_processor = get_image_processor()
audio_processor = get_audio_processor()


# ============================================================================
# Text Ingestion
# ============================================================================


@router.post("/text", response_model=IngestResponse)
async def ingest_text(
    file: Optional[UploadFile] = File(None),
    content: Optional[str] = Form(None),
    source_path: Optional[str] = Form(None),
    file_type: str = Form("txt"),
    tags: Optional[str] = Form(None),
):
    """
    Ingest text content (from file upload or direct content).

    Args:
        file: Uploaded text file (PDF, MD, TXT, code, etc.)
        content: Direct text content (if not uploading file)
        source_path: Original file path (for content mode)
        file_type: File type identifier
        tags: Comma-separated tags

    Returns:
        IngestResponse with processing details
    """
    start_time = time.time()

    try:
        # Parse tags
        custom_tags = [t.strip() for t in tags.split(",")] if tags else []

        # Handle file upload
        if file:
            # Save uploaded file temporarily
            temp_path = Path(f"/tmp/{file.filename}")
            async with aiofiles.open(temp_path, "wb") as f:
                content_bytes = await file.read()
                await f.write(content_bytes)

            # Check file size
            if temp_path.stat().st_size > settings.max_file_size_bytes:
                temp_path.unlink()
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Max size: {settings.max_file_size_mb}MB",
                )

            # Check if content changed
            file_hash = content_hasher.hash_content(temp_path, "text")
            existing = qdrant_manager.search_by_hash(
                settings.unified_collection, file_hash
            )

            if existing:
                logger.info(f"File {file.filename} unchanged, skipping re-embedding")
                temp_path.unlink()
                processing_time = (time.time() - start_time) * 1000

                return IngestResponse(
                    success=True,
                    message="Content unchanged, skipped re-embedding",
                    points_created=0,
                    parent_doc_id=existing[0].payload.get("parent_doc_id", ""),
                    processing_time_ms=processing_time,
                    skipped_unchanged=True,
                )

            # Process file
            chunks = text_processor.process_text_file(temp_path, custom_tags)
            temp_path.unlink()

        # Handle direct content
        elif content:
            # Check if content changed
            content_hash = content_hasher.hash_text(content)
            existing = qdrant_manager.search_by_hash(
                settings.unified_collection, content_hash
            )

            if existing:
                logger.info("Content unchanged, skipping re-embedding")
                processing_time = (time.time() - start_time) * 1000

                return IngestResponse(
                    success=True,
                    message="Content unchanged, skipped re-embedding",
                    points_created=0,
                    parent_doc_id=existing[0].payload.get("parent_doc_id", ""),
                    processing_time_ms=processing_time,
                    skipped_unchanged=True,
                )

            # Process content string
            chunks = text_processor.process_text_string(
                content,
                source_path=source_path or "inline_text",
                file_type=file_type,
                custom_tags=custom_tags,
            )

        else:
            raise HTTPException(
                status_code=400, detail="Either 'file' or 'content' must be provided"
            )

        if not chunks:
            raise HTTPException(
                status_code=400, detail="No text chunks extracted from content"
            )

        # Upsert to Qdrant
        point_ids = qdrant_manager.upsert_text_chunks(chunks)

        processing_time = (time.time() - start_time) * 1000

        return IngestResponse(
            success=True,
            message=f"Successfully ingested text with {len(chunks)} chunks",
            points_created=len(point_ids),
            parent_doc_id=chunks[0].parent_doc_id,
            processing_time_ms=processing_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Image Ingestion
# ============================================================================


@router.post("/image", response_model=IngestResponse)
async def ingest_image(
    file: UploadFile = File(...),
    tags: Optional[str] = Form(None),
    enable_ocr: bool = Form(True),
    enable_caption: bool = Form(True),
):
    """
    Ingest image file with CLIP embedding and optional OCR/captioning.

    Args:
        file: Uploaded image file
        tags: Comma-separated tags
        enable_ocr: Whether to perform OCR
        enable_caption: Whether to generate caption

    Returns:
        IngestResponse with processing details
    """
    start_time = time.time()

    try:
        # Parse tags
        custom_tags = [t.strip() for t in tags.split(",")] if tags else []

        # Save uploaded file temporarily
        temp_path = Path(f"/tmp/{file.filename}")
        async with aiofiles.open(temp_path, "wb") as f:
            content_bytes = await file.read()
            await f.write(content_bytes)

        # Check file size
        if temp_path.stat().st_size > settings.max_file_size_bytes:
            temp_path.unlink()
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size: {settings.max_file_size_mb}MB",
            )

        # Check if image changed (perceptual hash)
        image_hash = content_hasher.hash_image(temp_path)
        existing = qdrant_manager.search_by_hash(
            settings.unified_collection, image_hash
        )

        if existing:
            logger.info(f"Image {file.filename} unchanged, skipping re-embedding")
            temp_path.unlink()
            processing_time = (time.time() - start_time) * 1000

            return IngestResponse(
                success=True,
                message="Image unchanged, skipped re-embedding",
                points_created=0,
                parent_doc_id=existing[0].payload.get("parent_doc_id", ""),
                processing_time_ms=processing_time,
                skipped_unchanged=True,
            )

        # Process image
        image_data = image_processor.process_image(
            temp_path, custom_tags, enable_ocr, enable_caption
        )

        # Upsert to Qdrant
        point_id = qdrant_manager.upsert_image(image_data)

        # Clean up
        temp_path.unlink()

        processing_time = (time.time() - start_time) * 1000

        return IngestResponse(
            success=True,
            message=f"Successfully ingested image",
            points_created=1,
            parent_doc_id=image_data.parent_doc_id,
            processing_time_ms=processing_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Audio Ingestion
# ============================================================================


@router.post("/audio", response_model=IngestResponse)
async def ingest_audio(file: UploadFile = File(...), tags: Optional[str] = Form(None)):
    """
    Ingest audio file with NVIDIA Canary-Qwen transcription.

    Args:
        file: Uploaded audio file
        tags: Comma-separated tags

    Returns:
        IngestResponse with processing details
    """
    start_time = time.time()

    try:
        # Parse tags
        custom_tags = [t.strip() for t in tags.split(",")] if tags else []

        # Save uploaded file temporarily
        temp_path = Path(f"/tmp/{file.filename}")
        async with aiofiles.open(temp_path, "wb") as f:
            content_bytes = await file.read()
            await f.write(content_bytes)

        # Check file size
        if temp_path.stat().st_size > settings.max_file_size_bytes:
            temp_path.unlink()
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size: {settings.max_file_size_mb}MB",
            )

        # Check if audio changed
        audio_hash = content_hasher.hash_audio(temp_path)
        existing = qdrant_manager.search_by_hash(
            settings.unified_collection, audio_hash
        )

        if existing:
            logger.info(f"Audio {file.filename} unchanged, skipping re-embedding")
            temp_path.unlink()
            processing_time = (time.time() - start_time) * 1000

            return IngestResponse(
                success=True,
                message="Audio unchanged, skipped re-embedding",
                points_created=0,
                parent_doc_id=existing[0].payload.get("parent_doc_id", ""),
                processing_time_ms=processing_time,
                skipped_unchanged=True,
            )

        # Process audio (transcription + chunking)
        chunks = audio_processor.process_audio(temp_path, custom_tags)

        if not chunks:
            temp_path.unlink()
            raise HTTPException(
                status_code=400, detail="No transcript extracted from audio"
            )

        # Upsert to Qdrant
        point_ids = qdrant_manager.upsert_audio_chunks(chunks)

        # Clean up
        temp_path.unlink()

        processing_time = (time.time() - start_time) * 1000

        return IngestResponse(
            success=True,
            message=f"Successfully ingested audio with {len(chunks)} transcript chunks",
            points_created=len(point_ids),
            parent_doc_id=chunks[0].parent_doc_id,
            processing_time_ms=processing_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Directory Ingestion
# ============================================================================


def _classify_file_type(file_path: Path) -> Optional[str]:
    """
    Classify file type based on extension.

    Returns:
        'text', 'image', 'audio', or None if unsupported
    """
    ext = file_path.suffix.lower()

    # Text files
    text_exts = {
        ".txt",
        ".md",
        ".pdf",
        ".py",
        ".js",
        ".ts",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".hpp",
        ".cs",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".html",
        ".css",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".sh",
        ".bash",
        ".zsh",
        ".sql",
        ".r",
        ".m",
        ".swift",
        ".kt",
        ".scala",
    }

    # Image files
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".svg"}

    # Audio files
    audio_exts = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus"}

    if ext in text_exts:
        return "text"
    elif ext in image_exts:
        return "image"
    elif ext in audio_exts:
        return "audio"
    else:
        return None


def _process_directory_batch(files_to_process: list[Path], custom_tags: list[str]):
    """
    Background task to process a batch of files.

    Args:
        files_to_process: List of file paths to process
        custom_tags: Tags to apply to all files
    """
    stats = {
        "total": len(files_to_process),
        "processed": 0,
        "skipped": 0,
        "errors": 0,
        "text_files": 0,
        "image_files": 0,
        "audio_files": 0,
        "unsupported": 0,
    }

    logger.info(f"Starting batch processing of {len(files_to_process)} files")

    for file_path in files_to_process:
        try:
            file_type = _classify_file_type(file_path)

            if file_type is None:
                logger.warning(f"Unsupported file type: {file_path}")
                stats["unsupported"] += 1
                continue

            # Check file size
            if file_path.stat().st_size > settings.max_file_size_bytes:
                logger.warning(f"File too large, skipping: {file_path}")
                stats["skipped"] += 1
                continue

            # Process based on type
            if file_type == "text":
                # Check if content changed
                file_hash = content_hasher.hash_content(file_path, "text")
                existing = qdrant_manager.search_by_hash(
                    settings.unified_collection, file_hash
                )

                if existing:
                    logger.debug(f"Text file unchanged, skipping: {file_path}")
                    stats["skipped"] += 1
                    continue

                # Process text file
                chunks = text_processor.process_text_file(file_path, custom_tags)
                if chunks:
                    qdrant_manager.upsert_text_chunks(chunks)
                    stats["text_files"] += 1
                    stats["processed"] += 1
                    logger.info(
                        f"Processed text file: {file_path} ({len(chunks)} chunks)"
                    )
                else:
                    stats["skipped"] += 1

            elif file_type == "image":
                # Check if image changed
                image_hash = content_hasher.hash_image(file_path)
                existing = qdrant_manager.search_by_hash(
                    settings.unified_collection, image_hash
                )

                if existing:
                    logger.debug(f"Image unchanged, skipping: {file_path}")
                    stats["skipped"] += 1
                    continue

                # Process image
                image_data = image_processor.process_image(
                    file_path, custom_tags, enable_ocr=True, enable_caption=True
                )
                qdrant_manager.upsert_image(image_data)
                stats["image_files"] += 1
                stats["processed"] += 1
                logger.info(f"Processed image: {file_path}")

            elif file_type == "audio":
                # Check if audio changed
                audio_hash = content_hasher.hash_audio(file_path)
                existing = qdrant_manager.search_by_hash(
                    settings.unified_collection, audio_hash
                )

                if existing:
                    logger.debug(f"Audio unchanged, skipping: {file_path}")
                    stats["skipped"] += 1
                    continue

                # Process audio
                chunks = audio_processor.process_audio(file_path, custom_tags)
                if chunks:
                    qdrant_manager.upsert_audio_chunks(chunks)
                    stats["audio_files"] += 1
                    stats["processed"] += 1
                    logger.info(f"Processed audio: {file_path} ({len(chunks)} chunks)")
                else:
                    stats["skipped"] += 1

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            stats["errors"] += 1

    logger.info(
        f"Batch processing complete: {stats['processed']} processed, "
        f"{stats['skipped']} skipped, {stats['errors']} errors, "
        f"{stats['unsupported']} unsupported"
    )
    logger.info(
        f"File types: {stats['text_files']} text, "
        f"{stats['image_files']} images, {stats['audio_files']} audio"
    )


@router.post("/directory", response_model=dict)
async def ingest_directory(
    request: IngestDirectoryRequest, background_tasks: BackgroundTasks
):
    """
    Ingest all supported files from a directory.

    Args:
        request: Directory ingestion request
        background_tasks: FastAPI background tasks

    Returns:
        Summary of ingestion operation
    """
    try:
        directory = Path(request.directory_path)
        if not directory.exists() or not directory.is_dir():
            raise HTTPException(
                status_code=400, detail=f"Directory not found: {directory}"
            )

        # Collect files based on patterns
        files_to_process = []

        for pattern in request.file_patterns:
            if request.recursive:
                files_to_process.extend(directory.rglob(pattern))
            else:
                files_to_process.extend(directory.glob(pattern))

        # Filter out excluded patterns
        if request.exclude_patterns:
            filtered_files = []
            for f in files_to_process:
                excluded = False
                for exclude_pattern in request.exclude_patterns:
                    if f.match(exclude_pattern):
                        excluded = True
                        break
                if not excluded:
                    filtered_files.append(f)
            files_to_process = filtered_files

        # Filter to only regular files
        files_to_process = [f for f in files_to_process if f.is_file()]

        logger.info(f"Found {len(files_to_process)} files to process in {directory}")

        if not files_to_process:
            return {
                "success": True,
                "message": "No files found matching the patterns",
                "files_found": 0,
            }

        # Parse tags
        custom_tags = (
            [t.strip() for t in request.tags.split(",")] if request.tags else []
        )

        # Start background processing
        background_tasks.add_task(
            _process_directory_batch, files_to_process, custom_tags
        )

        return {
            "success": True,
            "message": f"Processing {len(files_to_process)} files in background",
            "files_found": len(files_to_process),
            "status": "processing",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in directory ingestion: {e}")
        raise HTTPException(status_code=500, detail=str(e))
