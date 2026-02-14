"""
Content hashing utilities for differential updates.
Computes hashes to detect content changes and avoid redundant embedding generation.
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional
from PIL import Image
import imagehash

logger = logging.getLogger(__name__)


class ContentHasher:
    """
    Handles content hashing for text, images, and audio files.
    Uses different hashing strategies based on content type.
    """

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize text for consistent hashing.

        Args:
            text: Raw text content

        Returns:
            Normalized text (stripped whitespace, lowercase)
        """
        # Remove excessive whitespace and normalize
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        normalized = " ".join(lines)
        return normalized.lower()

    def hash_text(self, text: str) -> str:
        """
        Generate SHA-256 hash of normalized text content.

        Args:
            text: Text content to hash

        Returns:
            Hexadecimal hash string
        """
        try:
            normalized = self.normalize_text(text)
            hash_obj = hashlib.sha256(normalized.encode('utf-8'))
            text_hash = hash_obj.hexdigest()
            logger.debug(f"Generated text hash: {text_hash[:16]}...")
            return text_hash
        except Exception as e:
            logger.error(f"Error hashing text: {e}")
            # Fallback to hash of raw text
            return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def hash_image(self, image_path: str | Path) -> str:
        """
        Generate perceptual hash (pHash) for image content.
        Uses imagehash library for robust duplicate detection.

        Args:
            image_path: Path to image file

        Returns:
            Perceptual hash string
        """
        try:
            image_path = Path(image_path)
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")

            # Open image and compute perceptual hash
            with Image.open(image_path) as img:
                # Convert to RGB if needed (handles RGBA, grayscale, etc.)
                if img.mode not in ('RGB', 'L'):
                    img = img.convert('RGB')

                # Compute pHash (8x8 = 64-bit hash by default)
                phash = imagehash.phash(img, hash_size=8)
                hash_str = str(phash)

                logger.debug(f"Generated image pHash for {image_path.name}: {hash_str}")
                return hash_str

        except Exception as e:
            logger.error(f"Error hashing image {image_path}: {e}")
            # Fallback to file-based hash
            return self.hash_file(image_path)

    def hash_audio(self, audio_path: str | Path) -> str:
        """
        Generate SHA-256 hash of audio file bytes.

        Args:
            audio_path: Path to audio file

        Returns:
            Hexadecimal hash string
        """
        try:
            audio_path = Path(audio_path)
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            hash_str = self.hash_file(audio_path)
            logger.debug(f"Generated audio hash for {audio_path.name}: {hash_str[:16]}...")
            return hash_str

        except Exception as e:
            logger.error(f"Error hashing audio {audio_path}: {e}")
            raise

    def hash_file(self, file_path: str | Path) -> str:
        """
        Generate SHA-256 hash of file contents.
        Generic method for any file type.

        Args:
            file_path: Path to file

        Returns:
            Hexadecimal hash string
        """
        file_path = Path(file_path)
        hash_obj = hashlib.sha256()

        # Read file in chunks to handle large files efficiently
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_obj.update(chunk)

        return hash_obj.hexdigest()

    def hash_content(self, content: str | Path, content_type: str) -> str:
        """
        Smart hash dispatcher based on content type.

        Args:
            content: Either text string or file path
            content_type: "text", "image", or "audio"

        Returns:
            Content hash string
        """
        content_type = content_type.lower()

        if content_type == "text":
            if isinstance(content, (str, Path)) and Path(content).exists():
                # It's a file path, read and hash
                with open(content, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                return self.hash_text(text)
            else:
                # It's raw text content
                return self.hash_text(str(content))

        elif content_type == "image":
            return self.hash_image(content)

        elif content_type == "audio":
            return self.hash_audio(content)

        else:
            raise ValueError(f"Unknown content type: {content_type}")

    async def has_changed_in_collection(
        self,
        content_hash: str,
        qdrant_manager,
        collection: str
    ) -> bool:
        """
        Check if content hash already exists in Qdrant collection.

        Args:
            content_hash: Hash to check
            qdrant_manager: QdrantManager instance
            collection: Collection name to search

        Returns:
            True if content has changed (hash not found), False if unchanged (hash exists)
        """
        try:
            # Search for existing points with this hash
            results = await qdrant_manager.search_by_hash(collection, content_hash)

            if results:
                logger.info(f"Content hash {content_hash[:16]}... found in {collection}, skipping re-embedding")
                return False  # Hash exists, content unchanged
            else:
                logger.info(f"Content hash {content_hash[:16]}... not found, will embed")
                return True  # Hash not found, content is new or changed

        except Exception as e:
            logger.warning(f"Error checking hash in collection: {e}, assuming content changed")
            return True  # On error, assume changed to be safe

    def compare_image_hashes(self, hash1: str, hash2: str, threshold: int = 5) -> bool:
        """
        Compare two perceptual image hashes for similarity.

        Args:
            hash1: First image hash
            hash2: Second image hash
            threshold: Hamming distance threshold (lower = more similar)

        Returns:
            True if images are similar enough to be considered duplicates
        """
        try:
            # Convert hex strings back to imagehash objects
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)

            # Calculate Hamming distance
            distance = h1 - h2

            is_similar = distance <= threshold
            logger.debug(f"Image hash distance: {distance}, similar: {is_similar}")
            return is_similar

        except Exception as e:
            logger.error(f"Error comparing image hashes: {e}")
            return hash1 == hash2  # Fallback to exact match


# Global singleton instance
_hasher_instance: Optional[ContentHasher] = None


def get_content_hasher() -> ContentHasher:
    """Get or create global ContentHasher instance."""
    global _hasher_instance
    if _hasher_instance is None:
        _hasher_instance = ContentHasher()
    return _hasher_instance
