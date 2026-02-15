"""
Unified text extraction layer for the text-centric multimodal pipeline.
Converts all modalities (images, audio, PDFs, text) into textual representations
that can be embedded with a single text model and used for entity extraction.
"""

import logging
from pathlib import Path
from typing import Optional, Protocol

from PIL import Image

from .content_sanitizer import sanitize_ingested_text

logger = logging.getLogger(__name__)


# ============================================================================
# Protocol for text extractors
# ============================================================================


class TextExtractorProtocol(Protocol):
    """Interface for modality-specific text extractors."""

    def extract(self, source_path: str | Path) -> str:
        """Extract textual representation from source content."""
        ...


# ============================================================================
# Image Text Extractor
# ============================================================================


class ImageTextExtractor:
    """
    Extracts textual representation from images.
    Combines OCR (visible text) + generated caption (visual description).
    """

    def __init__(self):
        self._ocr_available = False
        self._caption_model = None
        self._caption_processor = None
        self._device = None
        self._check_ocr()

    def _check_ocr(self):
        """Check if Tesseract OCR is available."""
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            self._ocr_available = True
            logger.info("Tesseract OCR is available")
        except Exception:
            self._ocr_available = False
            logger.warning("Tesseract OCR not available — OCR disabled")

    def _load_caption_model(self):
        """Lazy-load BLIP captioning model."""
        if self._caption_model is not None:
            return

        try:
            import torch
            from transformers import BlipProcessor, BlipForConditionalGeneration

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            model_name = "Salesforce/blip-image-captioning-base"

            logger.info(f"Loading BLIP captioning model on {self._device}...")
            self._caption_processor = BlipProcessor.from_pretrained(model_name)
            self._caption_model = BlipForConditionalGeneration.from_pretrained(
                model_name
            ).to(self._device)
            self._caption_model.eval()
            logger.info("BLIP captioning model loaded successfully")

        except Exception as e:
            logger.warning(f"Failed to load BLIP captioning model: {e}")
            self._caption_model = None

    def generate_caption(self, image_path: str | Path) -> str:
        """
        Generate a natural language caption for an image using BLIP.

        Args:
            image_path: Path to image file

        Returns:
            Caption string describing the image
        """
        try:
            import torch

            self._load_caption_model()
            if self._caption_model is None:
                return f"Image: {Path(image_path).name}"

            img = Image.open(image_path).convert("RGB")

            # Conditional captioning with prompt
            inputs = self._caption_processor(
                images=img,
                text="a photograph of",
                return_tensors="pt",
            ).to(self._device)

            with torch.no_grad():
                output_ids = self._caption_model.generate(
                    **inputs, max_new_tokens=50, num_beams=3
                )

            caption = self._caption_processor.decode(
                output_ids[0], skip_special_tokens=True
            ).strip()

            logger.debug(f"Caption for {Path(image_path).name}: '{caption}'")
            return caption

        except Exception as e:
            logger.warning(f"Captioning failed for {image_path}: {e}")
            return f"Image: {Path(image_path).name}"

    def perform_ocr(self, image_path: str | Path) -> Optional[str]:
        """
        Extract visible text from image using Tesseract OCR.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text string, or None
        """
        if not self._ocr_available:
            return None

        try:
            import cv2
            import pytesseract

            img = cv2.imread(str(image_path))
            if img is None:
                return None

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            text = pytesseract.image_to_string(thresh).strip()

            if text:
                # Sanitize OCR output — adversarial images can contain
                # text designed to inject into downstream LLM prompts.
                text = sanitize_ingested_text(text, source="ocr")
                logger.debug(
                    f"OCR extracted {len(text)} chars from {Path(image_path).name}"
                )
                return text
            return None

        except Exception as e:
            logger.warning(f"OCR failed for {image_path}: {e}")
            return None

    def extract(self, source_path: str | Path) -> str:
        """
        Extract full textual representation from an image.
        Combines caption + OCR text.

        Args:
            source_path: Path to image file

        Returns:
            Combined text representation of the image
        """
        parts = []

        # Generate visual description
        caption = self.generate_caption(source_path)
        if caption:
            parts.append(caption)

        # Extract visible text
        ocr_text = self.perform_ocr(source_path)
        if ocr_text:
            parts.append(f"Text in image: {ocr_text}")

        if not parts:
            return f"Image: {Path(source_path).name}"

        return ". ".join(parts)


# ============================================================================
# Audio Text Extractor
# ============================================================================


class AudioTextExtractor:
    """
    Extracts textual representation from audio files via Whisper transcription.
    Reuses the existing AudioEmbeddingStrategy for transcription.
    """

    def __init__(self):
        self._audio_embedder = None

    def _get_embedder(self):
        """Lazy-load audio embedder for transcription."""
        if self._audio_embedder is None:
            from app.services.embeddings.audio_strategy import get_audio_embedder

            self._audio_embedder = get_audio_embedder()
        return self._audio_embedder

    def extract(self, source_path: str | Path) -> str:
        """
        Extract text from audio via Whisper transcription.

        Args:
            source_path: Path to audio file

        Returns:
            Transcript text
        """
        try:
            embedder = self._get_embedder()
            result = embedder.transcribe(source_path)
            transcript = result.get("text", "").strip()

            if not transcript:
                logger.warning(f"Empty transcript for {source_path}")
                return f"Audio: {Path(source_path).name}"

            # Sanitize transcript — audio may contain spoken injection
            # payloads that Whisper faithfully transcribes.
            transcript = sanitize_ingested_text(transcript, source="audio_transcript")

            logger.info(
                f"Transcribed {Path(source_path).name}: {len(transcript)} chars"
            )
            return transcript

        except Exception as e:
            logger.error(f"Audio transcription failed for {source_path}: {e}")
            return f"Audio: {Path(source_path).name}"


# ============================================================================
# PDF Text Extractor
# ============================================================================


class PDFTextExtractor:
    """Extracts text from PDF files using PyMuPDF."""

    def extract(self, source_path: str | Path) -> str:
        """
        Extract text content from a PDF file.

        Args:
            source_path: Path to PDF file

        Returns:
            Extracted text content
        """
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(source_path))
            text_parts = []

            for page in doc:
                text = page.get_text().strip()
                if text:
                    text_parts.append(text)

            doc.close()

            full_text = "\n\n".join(text_parts)
            if not full_text.strip():
                return f"PDF: {Path(source_path).name}"

            # Sanitize — PDFs can contain invisible text layers
            # (white-on-white, zero-size fonts) with injection payloads.
            full_text = sanitize_ingested_text(full_text, source="pdf")

            logger.info(
                f"Extracted {len(full_text)} chars from PDF {Path(source_path).name}"
            )
            return full_text

        except Exception as e:
            logger.error(f"PDF text extraction failed for {source_path}: {e}")
            return f"PDF: {Path(source_path).name}"


# ============================================================================
# Plain Text Extractor
# ============================================================================


class PlainTextExtractor:
    """Reads plain text files directly."""

    def extract(self, source_path: str | Path) -> str:
        """
        Read text from a file.

        Args:
            source_path: Path to text file

        Returns:
            File contents as string
        """
        try:
            text = Path(source_path).read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                return f"File: {Path(source_path).name}"
            # Sanitize plain text — files may contain embedded injection payloads.
            return sanitize_ingested_text(text, source="text_file")

        except Exception as e:
            logger.error(f"Text file read failed for {source_path}: {e}")
            return f"File: {Path(source_path).name}"


# ============================================================================
# Unified Text Extractor (dispatcher)
# ============================================================================

# File extension → content type mapping
_TEXT_EXTS = {
    ".txt",
    ".md",
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
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"}
_AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".opus"}
_PDF_EXTS = {".pdf"}


class UnifiedTextExtractor:
    """
    Dispatches to the correct modality-specific text extractor
    based on file extension. All outputs are plain text, ready for
    embedding with a single text model and entity extraction.
    """

    def __init__(self):
        self._image_extractor = None
        self._audio_extractor = None
        self._pdf_extractor = PDFTextExtractor()
        self._text_extractor = PlainTextExtractor()

    @property
    def image_extractor(self) -> ImageTextExtractor:
        """Lazy-load image extractor (loads BLIP on first use)."""
        if self._image_extractor is None:
            self._image_extractor = ImageTextExtractor()
        return self._image_extractor

    @property
    def audio_extractor(self) -> AudioTextExtractor:
        """Lazy-load audio extractor (loads Whisper on first use)."""
        if self._audio_extractor is None:
            self._audio_extractor = AudioTextExtractor()
        return self._audio_extractor

    def classify(self, file_path: str | Path) -> Optional[str]:
        """
        Classify file type by extension.

        Returns:
            'text', 'image', 'audio', 'pdf', or None if unsupported
        """
        ext = Path(file_path).suffix.lower()
        if ext in _PDF_EXTS:
            return "pdf"
        if ext in _TEXT_EXTS:
            return "text"
        if ext in _IMAGE_EXTS:
            return "image"
        if ext in _AUDIO_EXTS:
            return "audio"
        return None

    def extract(self, file_path: str | Path) -> Optional[str]:
        """
        Extract textual representation from any supported file.

        Args:
            file_path: Path to the file

        Returns:
            Extracted text, or None if unsupported
        """
        file_type = self.classify(file_path)
        if file_type is None:
            logger.warning(f"Unsupported file type: {file_path}")
            return None

        if file_type == "image":
            return self.image_extractor.extract(file_path)
        elif file_type == "audio":
            return self.audio_extractor.extract(file_path)
        elif file_type == "pdf":
            return self._pdf_extractor.extract(file_path)
        else:
            return self._text_extractor.extract(file_path)

    def extract_from_text(self, text: str) -> str:
        """
        Pass-through for direct text content (not from a file).

        Args:
            text: Raw text string

        Returns:
            The same text (no transformation needed)
        """
        return text


# ============================================================================
# Global singleton
# ============================================================================

_unified_extractor: Optional[UnifiedTextExtractor] = None


def get_unified_text_extractor() -> UnifiedTextExtractor:
    """Get or create global UnifiedTextExtractor instance."""
    global _unified_extractor
    if _unified_extractor is None:
        _unified_extractor = UnifiedTextExtractor()
    return _unified_extractor
