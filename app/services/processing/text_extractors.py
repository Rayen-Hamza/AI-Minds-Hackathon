"""
Text extraction strategies for converting all modalities to text.
This enables unified entity extraction and graph construction.
"""

import logging
from pathlib import Path
from typing import Protocol, Optional
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
import easyocr

logger = logging.getLogger(__name__)


class TextExtractor(Protocol):
    """Protocol for text extraction from different modalities."""

    def extract(self, source: str) -> str:
        """Extract textual representation from source."""
        ...


class PlainTextExtractor:
    """Extract text from plain text files (passthrough)."""

    def extract(self, source: str) -> str:
        """Read and return text content."""
        try:
            with open(source, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading text file {source}: {e}")
            return ""


class ImageTextExtractor:
    """
    Extract text from images using:
    1. BLIP for image captioning (semantic understanding)
    2. EasyOCR for visible text extraction
    """

    def __init__(
        self,
        caption_model: str = "Salesforce/blip-image-captioning-base",
        use_gpu: bool = True,
    ):
        """
        Initialize image text extractor.

        Args:
            caption_model: HuggingFace model for captioning
            use_gpu: Use GPU if available
        """
        self._caption_processor: Optional[BlipProcessor] = None
        self._caption_model: Optional[BlipForConditionalGeneration] = None
        self._ocr_reader: Optional[easyocr.Reader] = None
        self.caption_model_name = caption_model
        self.device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
        logger.info(f"ImageTextExtractor initialized (device: {self.device})")

    @property
    def caption_processor(self) -> BlipProcessor:
        """Lazy load caption processor."""
        if self._caption_processor is None:
            logger.info(f"Loading BLIP processor: {self.caption_model_name}")
            self._caption_processor = BlipProcessor.from_pretrained(
                self.caption_model_name
            )
        return self._caption_processor

    @property
    def caption_model(self) -> BlipForConditionalGeneration:
        """Lazy load caption model."""
        if self._caption_model is None:
            logger.info(f"Loading BLIP model: {self.caption_model_name}")
            self._caption_model = BlipForConditionalGeneration.from_pretrained(
                self.caption_model_name
            ).to(self.device)
            self._caption_model.eval()
        return self._caption_model

    @property
    def ocr_reader(self) -> easyocr.Reader:
        """Lazy load OCR reader."""
        if self._ocr_reader is None:
            logger.info("Loading EasyOCR reader (English)")
            # Use GPU if available
            self._ocr_reader = easyocr.Reader(
                ["en"], gpu=self.device == "cuda", verbose=False
            )
        return self._ocr_reader

    def generate_caption(self, image_path: str) -> str:
        """
        Generate semantic caption using BLIP.

        Args:
            image_path: Path to image file

        Returns:
            Generated caption
        """
        try:
            # Load and preprocess image
            img = Image.open(image_path).convert("RGB")

            # Generate caption
            inputs = self.caption_processor(img, return_tensors="pt").to(self.device)

            with torch.no_grad():
                outputs = self.caption_model.generate(
                    **inputs, max_new_tokens=50, num_beams=3
                )

            caption = self.caption_processor.decode(
                outputs[0], skip_special_tokens=True
            )

            logger.debug(f"Generated caption for {Path(image_path).name}: {caption}")
            return caption

        except Exception as e:
            logger.error(f"Error generating caption for {image_path}: {e}")
            return f"Image file: {Path(image_path).name}"

    def extract_ocr_text(self, image_path: str) -> str:
        """
        Extract visible text using OCR.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text
        """
        try:
            # Perform OCR
            results = self.ocr_reader.readtext(str(image_path), detail=0)

            # Join all detected text
            ocr_text = " ".join(results)

            if ocr_text.strip():
                logger.debug(
                    f"Extracted OCR text from {Path(image_path).name}: {len(ocr_text)} chars"
                )
            else:
                logger.debug(f"No text detected in {Path(image_path).name}")

            return ocr_text

        except Exception as e:
            logger.error(f"Error extracting OCR from {image_path}: {e}")
            return ""

    def extract(self, source: str) -> str:
        """
        Extract comprehensive text representation from image.

        Combines:
        1. Semantic caption (BLIP)
        2. Visible text (OCR)
        3. File metadata

        Args:
            source: Path to image file

        Returns:
            Combined text representation
        """
        try:
            image_path = Path(source)

            # Generate caption
            caption = self.generate_caption(str(image_path))

            # Extract OCR text
            ocr_text = self.extract_ocr_text(str(image_path))

            # Build comprehensive text representation
            parts = [f"Image description: {caption}"]

            if ocr_text.strip():
                parts.append(f"Visible text: {ocr_text}")

            # Add filename as context
            parts.append(f"Filename: {image_path.name}")

            combined_text = ". ".join(parts)

            logger.info(
                f"Extracted text from image {image_path.name}: {len(combined_text)} chars"
            )

            return combined_text

        except Exception as e:
            logger.error(f"Error extracting text from image {source}: {e}")
            return f"Image file: {Path(source).name}"


class AudioTextExtractor:
    """
    Extract text from audio using speech-to-text.
    Reuses existing Whisper transcription.
    """

    def __init__(self):
        """Initialize audio text extractor."""
        from app.services.embeddings.audio_strategy import get_audio_embedder

        self.audio_embedder = get_audio_embedder()

    def extract(self, source: str) -> str:
        """
        Transcribe audio to text.

        Args:
            source: Path to audio file

        Returns:
            Transcribed text
        """
        try:
            # Use existing Whisper transcription
            result = self.audio_embedder.transcribe(source)
            transcript = result.get("text", "")

            if transcript.strip():
                logger.info(
                    f"Transcribed audio {Path(source).name}: {len(transcript)} chars"
                )
            else:
                logger.warning(f"Empty transcript for {source}")
                transcript = f"Audio file: {Path(source).name}"

            return transcript

        except Exception as e:
            logger.error(f"Error transcribing audio {source}: {e}")
            return f"Audio file: {Path(source).name}"


# Singleton instances
_image_extractor: Optional[ImageTextExtractor] = None
_audio_extractor: Optional[AudioTextExtractor] = None
_text_extractor: Optional[PlainTextExtractor] = None


def get_image_text_extractor() -> ImageTextExtractor:
    """Get or create global ImageTextExtractor instance."""
    global _image_extractor
    if _image_extractor is None:
        _image_extractor = ImageTextExtractor()
    return _image_extractor


def get_audio_text_extractor() -> AudioTextExtractor:
    """Get or create global AudioTextExtractor instance."""
    global _audio_extractor
    if _audio_extractor is None:
        _audio_extractor = AudioTextExtractor()
    return _audio_extractor


def get_text_extractor() -> PlainTextExtractor:
    """Get or create global PlainTextExtractor instance."""
    global _text_extractor
    if _text_extractor is None:
        _text_extractor = PlainTextExtractor()
    return _text_extractor


def get_extractor_for_content_type(content_type: str) -> TextExtractor:
    """
    Get appropriate text extractor for content type.

    Args:
        content_type: Content type ("text", "image", "audio")

    Returns:
        TextExtractor instance
    """
    extractors = {
        "text": get_text_extractor(),
        "image": get_image_text_extractor(),
        "audio": get_audio_text_extractor(),
    }

    extractor = extractors.get(content_type)
    if extractor is None:
        raise ValueError(f"Unsupported content type: {content_type}")

    return extractor
