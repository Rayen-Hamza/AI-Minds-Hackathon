"""
File serving routes for images, audio, and other media files.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/serve")
async def serve_file(path: str):
    """
    Serve a file from the local filesystem.

    Args:
        path: Absolute file path to serve

    Returns:
        FileResponse with the requested file
    """
    try:
        logger.info(f"File serve request received: {path}")

        # Handle both absolute and relative paths
        file_path = Path(path)

        # If path starts with /mnt/data/home/adem/Desktop/AI-Minds-Hackathon, convert to /app
        # This handles the case where paths were ingested on host but served from container
        path_str = str(file_path)
        if path_str.startswith("/mnt/data/home/adem/Desktop/AI-Minds-Hackathon"):
            # Replace with container path
            relative_part = path_str.replace("/mnt/data/home/adem/Desktop/AI-Minds-Hackathon", "").lstrip("/")
            file_path = Path("/app") / relative_part
            logger.info(f"Converted host path to container path: {file_path}")
        elif not file_path.is_absolute():
            # Try relative to current working directory
            file_path = Path.cwd() / path
            logger.info(f"Converted to absolute path: {file_path}")

        logger.info(f"Checking if file exists: {file_path}")
        logger.info(f"File exists: {file_path.exists()}, Is file: {file_path.is_file() if file_path.exists() else 'N/A'}")

        # Security check: ensure file exists and is a file
        if not file_path.exists():
            logger.warning(f"File not found: {file_path} (original: {path})")
            raise HTTPException(status_code=404, detail=f"File not found: {path}")

        if not file_path.is_file():
            logger.warning(f"Path is not a file: {file_path}")
            raise HTTPException(status_code=400, detail="Path is not a file")

        # Determine media type based on extension
        extension = file_path.suffix.lower()
        media_type_map = {
            # Images
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
            # Audio
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.ogg': 'audio/ogg',
            '.m4a': 'audio/mp4',
            '.flac': 'audio/flac',
        }

        media_type = media_type_map.get(extension, 'application/octet-stream')

        logger.info(f"Serving file: {path} (type: {media_type})")

        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=file_path.name
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving file {path}: {e}")
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")
