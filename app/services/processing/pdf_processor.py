"""
PDF processing using PyMuPDF (fitz) for text extraction.
Handles PDF parsing with layout awareness and metadata extraction.
"""

import logging
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PDFProcessor:
    """
    Extract text and metadata from PDF files using PyMuPDF.
    Preserves layout information and handles multi-page documents.
    """

    def __init__(self):
        logger.info("Initialized PDFProcessor")

    def extract_text(
        self,
        pdf_path: str | Path,
        preserve_layout: bool = True
    ) -> str:
        """
        Extract all text from a PDF file.

        Args:
            pdf_path: Path to PDF file
            preserve_layout: Preserve layout with whitespace (vs. simple text extraction)

        Returns:
            Extracted text content
        """
        try:
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF not found: {pdf_path}")

            logger.info(f"Extracting text from PDF: {pdf_path.name}")

            # Open PDF
            doc = fitz.open(pdf_path)

            # Extract text from all pages
            text_parts = []
            for page_num in range(len(doc)):
                page = doc[page_num]

                if preserve_layout:
                    # Extract text preserving layout
                    text = page.get_text("text")
                else:
                    # Simple text extraction
                    text = page.get_text()

                if text.strip():
                    text_parts.append(text)

            doc.close()

            # Join all pages
            full_text = "\n\n".join(text_parts)

            logger.info(
                f"Extracted {len(full_text)} chars from "
                f"{len(text_parts)} pages in {pdf_path.name}"
            )

            return full_text

        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
            raise

    def extract_text_by_page(
        self,
        pdf_path: str | Path
    ) -> list[dict]:
        """
        Extract text page by page with metadata.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of dicts with 'page_num', 'text', 'char_count'
        """
        try:
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF not found: {pdf_path}")

            doc = fitz.open(pdf_path)

            pages = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")

                pages.append({
                    "page_num": page_num + 1,
                    "text": text,
                    "char_count": len(text)
                })

            doc.close()

            logger.info(f"Extracted text from {len(pages)} pages in {pdf_path.name}")
            return pages

        except Exception as e:
            logger.error(f"Error extracting pages from PDF {pdf_path}: {e}")
            raise

    def extract_metadata(self, pdf_path: str | Path) -> dict:
        """
        Extract PDF metadata.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict with metadata fields
        """
        try:
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF not found: {pdf_path}")

            doc = fitz.open(pdf_path)

            metadata = {
                "title": doc.metadata.get("title", ""),
                "author": doc.metadata.get("author", ""),
                "subject": doc.metadata.get("subject", ""),
                "keywords": doc.metadata.get("keywords", ""),
                "creator": doc.metadata.get("creator", ""),
                "producer": doc.metadata.get("producer", ""),
                "creation_date": doc.metadata.get("creationDate", ""),
                "mod_date": doc.metadata.get("modDate", ""),
                "page_count": len(doc),
                "format": doc.metadata.get("format", ""),
            }

            doc.close()

            logger.debug(f"Extracted metadata from {pdf_path.name}: {metadata.get('title', 'Untitled')}")
            return metadata

        except Exception as e:
            logger.error(f"Error extracting PDF metadata from {pdf_path}: {e}")
            return {}

    def extract_images(self, pdf_path: str | Path, output_dir: Optional[Path] = None) -> list[dict]:
        """
        Extract images from PDF (optional feature).

        Args:
            pdf_path: Path to PDF file
            output_dir: Directory to save extracted images (if None, returns image data only)

        Returns:
            List of dicts with image info
        """
        try:
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF not found: {pdf_path}")

            if output_dir:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

            doc = fitz.open(pdf_path)

            images = []
            image_count = 0

            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images()

                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)

                    image_info = {
                        "page_num": page_num + 1,
                        "image_index": img_index,
                        "width": base_image["width"],
                        "height": base_image["height"],
                        "colorspace": base_image["colorspace"],
                        "ext": base_image["ext"],
                    }

                    if output_dir:
                        # Save image to file
                        image_filename = f"page{page_num + 1}_img{img_index}.{base_image['ext']}"
                        image_path = output_dir / image_filename

                        with open(image_path, "wb") as img_file:
                            img_file.write(base_image["image"])

                        image_info["saved_path"] = str(image_path)

                    images.append(image_info)
                    image_count += 1

            doc.close()

            logger.info(f"Extracted {image_count} images from {pdf_path.name}")
            return images

        except Exception as e:
            logger.error(f"Error extracting images from PDF {pdf_path}: {e}")
            return []

    def is_text_based(self, pdf_path: str | Path, sample_pages: int = 3) -> bool:
        """
        Check if PDF is text-based (vs. image-based/scanned).

        Args:
            pdf_path: Path to PDF file
            sample_pages: Number of pages to sample

        Returns:
            True if text-based, False if likely scanned/image-based
        """
        try:
            pdf_path = Path(pdf_path)
            doc = fitz.open(pdf_path)

            # Sample first few pages
            pages_to_check = min(sample_pages, len(doc))
            total_text_len = 0

            for page_num in range(pages_to_check):
                page = doc[page_num]
                text = page.get_text()
                total_text_len += len(text.strip())

            doc.close()

            # If we have substantial text, it's text-based
            avg_text_per_page = total_text_len / pages_to_check
            is_text_based = avg_text_per_page > 100  # Threshold: 100 chars/page

            logger.debug(
                f"PDF {pdf_path.name} is {'text-based' if is_text_based else 'image-based'} "
                f"(avg {avg_text_per_page:.0f} chars/page)"
            )

            return is_text_based

        except Exception as e:
            logger.error(f"Error checking PDF type: {e}")
            return False


# Global singleton instance
_pdf_processor: Optional[PDFProcessor] = None


def get_pdf_processor() -> PDFProcessor:
    """Get or create global PDFProcessor instance."""
    global _pdf_processor
    if _pdf_processor is None:
        _pdf_processor = PDFProcessor()
    return _pdf_processor
