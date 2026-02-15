"""
Image processing pipeline for metadata extraction, OCR, and captioning.
Handles EXIF data, OCR text detection, and image caption generation.
"""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
import uuid

from PIL import Image
from PIL.ExifTags import TAGS
import pytesseract
import cv2
import numpy as np

from app.models.models import ImageData
from app.services.storage.content_hasher import get_content_hasher
from app.services.embeddings.caption_strategy import get_caption_embedder
from app.services.label_mapping import TypedEntity
from app.config import settings
from .entity_extractor import get_entity_extractor

logger = logging.getLogger(__name__)


class ImageProcessor:
    """
    Processes images for embedding and storage.
    Extracts metadata, performs OCR, generates captions, and extracts entities.
    """

    def __init__(self):
        """Initialize image processor."""
        self.hasher = get_content_hasher()
        self.entity_extractor = get_entity_extractor()
        self._caption_embedder = None  # Lazy load

        logger.info("Initialized ImageProcessor")

    @property
    def caption_embedder(self):
        """Lazy-load caption embedder."""
        if self._caption_embedder is None:
            try:
                self._caption_embedder = get_caption_embedder(
                    settings.text_to_image_model
                )
            except Exception as e:
                logger.warning(f"Failed to load caption embedder: {e}")
                self._caption_embedder = None
        return self._caption_embedder

    def extract_exif(self, image_path: str | Path) -> dict:
        """
        Extract EXIF metadata from image.

        Args:
            image_path: Path to image file

        Returns:
            Dict with EXIF data
        """
        try:
            img = Image.open(image_path)

            # Get EXIF data
            exif_data = {}
            if hasattr(img, "_getexif") and img._getexif():
                exif = img._getexif()
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    exif_data[tag] = str(value)

            logger.debug(
                f"Extracted {len(exif_data)} EXIF fields from {Path(image_path).name}"
            )
            return exif_data

        except Exception as e:
            logger.warning(f"Error extracting EXIF from {image_path}: {e}")
            return {}

    def perform_ocr(self, image_path: str | Path) -> Optional[str]:
        """
        Perform OCR on image to extract text.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text or None if no text detected
        """
        try:
            # Read image with OpenCV
            img = cv2.imread(str(image_path))

            if img is None:
                logger.warning(f"Could not read image for OCR: {image_path}")
                return None

            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # Apply thresholding for better OCR results
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # Perform OCR
            text = pytesseract.image_to_string(thresh)

            if text and text.strip():
                logger.debug(
                    f"OCR extracted {len(text)} chars from {Path(image_path).name}"
                )
                return text.strip()
            else:
                logger.debug(f"No text detected in {Path(image_path).name}")
                return None

        except Exception as e:
            logger.warning(f"Error performing OCR on {image_path}: {e}")
            return None

    def generate_caption(self, image_path: str | Path) -> Optional[str]:
        """
        Generate image caption using BLIP.

        Args:
            image_path: Path to image file

        Returns:
            Generated caption or None if unavailable
        """
        try:
            if self.caption_embedder is None:
                logger.warning(
                    "Caption embedder not available, skipping caption generation"
                )
                return None

            caption = self.caption_embedder.generate_caption(image_path)
            logger.debug(f"Generated caption for {Path(image_path).name}: '{caption}'")
            return caption

        except Exception as e:
            logger.warning(f"Error generating caption for {image_path}: {e}")
            return None

    def get_image_dimensions(self, image_path: str | Path) -> tuple[int, int]:
        """
        Get image width and height.

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (width, height)
        """
        try:
            with Image.open(image_path) as img:
                return img.size
        except Exception as e:
            logger.warning(f"Error getting image dimensions: {e}")
            return (0, 0)

    def process_image(
        self,
        image_path: str | Path,
        custom_tags: Optional[list[str]] = None,
        enable_ocr: bool = True,
        enable_caption: bool = True,
    ) -> ImageData:
        """
        Process an image file with full metadata extraction.

        Args:
            image_path: Path to image file
            custom_tags: Optional custom tags
            enable_ocr: Whether to perform OCR
            enable_caption: Whether to generate caption

        Returns:
            ImageData object ready for embedding
        """
        try:
            image_path = Path(image_path)
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found: {image_path}")

            logger.info(f"Processing image: {image_path}")

            # Compute perceptual hash
            content_hash = self.hasher.hash_image(image_path)

            # Get file metadata
            stats = image_path.stat()
            file_size = stats.st_size
            creation_date = datetime.fromtimestamp(stats.st_ctime).isoformat()
            last_modified = datetime.fromtimestamp(stats.st_mtime).isoformat()

            # Generate parent document ID
            parent_doc_id = str(uuid.uuid4())

            # Get image dimensions
            width, height = self.get_image_dimensions(image_path)

            # Extract EXIF
            exif_data = self.extract_exif(image_path)

            # Perform OCR
            ocr_text = None
            if enable_ocr:
                ocr_text = self.perform_ocr(image_path)

            # Generate caption
            caption = None
            if enable_caption:
                caption = self.generate_caption(image_path)

            # Extract typed entities from caption and OCR text
            entities = []
            typed_entities = []
            for source_text in (caption, ocr_text):
                if not source_text:
                    continue
                labeled = self.entity_extractor.extract_entities_with_labels(source_text)
                for ent in labeled:
                    entities.append(ent["text"])
                    te = TypedEntity.from_spacy(ent["text"], ent["label"])
                    typed_entities.append(te.to_entity_payload_dict())

            # Remove duplicates
            entities = list(dict.fromkeys(entities))
            seen_typed: set[str] = set()
            deduped_typed: list[dict] = []
            for td in typed_entities:
                key = td["text"].lower()
                if key not in seen_typed:
                    seen_typed.add(key)
                    deduped_typed.append(td)
            typed_entities = deduped_typed

            # Create ImageData object
            image_data = ImageData(
                image_path=str(image_path),
                parent_doc_id=parent_doc_id,
                content_hash=content_hash,
                file_size=file_size,
                width=width,
                height=height,
                exif_data=exif_data,
                ocr_text=ocr_text,
                caption=caption,
                creation_date=creation_date,
                last_modified=last_modified,
                tags=custom_tags or [],
                extracted_entities=entities,
                typed_entities=typed_entities,
            )

            logger.info(
                f"Processed {image_path.name}: {width}x{height}, "
                f"caption={'✓' if caption else '✗'}, "
                f"OCR={'✓' if ocr_text else '✗'}, "
                f"{len(entities)} entities"
            )

            return image_data

        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}")
            raise

    def process_batch(
        self,
        image_paths: list[Path],
        custom_tags: Optional[list[str]] = None,
        enable_ocr: bool = True,
        enable_caption: bool = True,
    ) -> list[ImageData]:
        """
        Process multiple images in batch.

        Args:
            image_paths: List of image paths
            custom_tags: Optional custom tags for all images
            enable_ocr: Whether to perform OCR
            enable_caption: Whether to generate captions

        Returns:
            List of ImageData objects
        """
        try:
            logger.info(f"Processing batch of {len(image_paths)} images")

            results = []
            for image_path in image_paths:
                try:
                    image_data = self.process_image(
                        image_path, custom_tags, enable_ocr, enable_caption
                    )
                    results.append(image_data)
                except Exception as e:
                    logger.error(f"Failed to process {image_path}: {e}")

            logger.info(
                f"Batch processed {len(results)}/{len(image_paths)} images successfully"
            )
            return results

        except Exception as e:
            logger.error(f"Error in batch image processing: {e}")
            raise


# Global singleton instance
_image_processor: Optional[ImageProcessor] = None


def get_image_processor() -> ImageProcessor:
    """Get or create global ImageProcessor instance."""
    global _image_processor
    if _image_processor is None:
        _image_processor = ImageProcessor()
    return _image_processor
