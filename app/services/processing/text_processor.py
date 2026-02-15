"""
Text processing pipeline for chunking, NER, and metadata extraction.
Handles plain text, markdown, code files, and PDF text.
"""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.models.models import TextChunk
from app.config import settings
from app.services.storage.content_hasher import get_content_hasher
from app.services.label_mapping import TypedEntity
from .entity_extractor import get_entity_extractor
from .pdf_processor import get_pdf_processor

logger = logging.getLogger(__name__)


class TextProcessor:
    """
    Processes text content for embedding and storage.
    Handles chunking, entity extraction, and metadata.
    """

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        """
        Initialize text processor.

        Args:
            chunk_size: Maximum chunk size in characters
            chunk_overlap: Overlap between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        # Get global instances
        self.hasher = get_content_hasher()
        self.entity_extractor = get_entity_extractor()
        self.pdf_processor = get_pdf_processor()

        logger.info(
            f"Initialized TextProcessor with chunk_size={chunk_size}, "
            f"overlap={chunk_overlap}"
        )

    def chunk_text(self, text: str) -> list[str]:
        """
        Split text into semantic chunks.

        Args:
            text: Input text

        Returns:
            List of text chunks
        """
        try:
            if not text or not text.strip():
                return []

            chunks = self.text_splitter.split_text(text)

            logger.debug(f"Split text ({len(text)} chars) into {len(chunks)} chunks")
            return chunks

        except Exception as e:
            logger.error(f"Error chunking text: {e}")
            # Fallback: return whole text as single chunk
            return [text]

    def _extract_typed_entities(self, text: str) -> tuple[list[str], list[dict]]:
        """Extract entities using spaCy, returning both flat and typed lists.

        Returns:
            ``(flat_names, typed_dicts)`` where ``typed_dicts`` contains
            ``{"text": ..., "type": ..., "confidence": ...}`` entries
            compatible with ``GraphUpdater.ingest_document``.
        """
        labeled = self.entity_extractor.extract_entities_with_labels(text)
        if not labeled:
            return [], []

        seen: set[str] = set()
        flat: list[str] = []
        typed: list[dict] = []
        for ent in labeled:
            key = ent["text"].lower()
            if key in seen:
                continue
            seen.add(key)
            flat.append(ent["text"])
            te = TypedEntity.from_spacy(ent["text"], ent["label"])
            typed.append(te.to_entity_payload_dict())

        return flat, typed

    def process_text_file(
        self, file_path: str | Path, custom_tags: Optional[list[str]] = None
    ) -> list[TextChunk]:
        """
        Process a text file into chunks with metadata.

        Args:
            file_path: Path to text file
            custom_tags: Optional custom tags to add

        Returns:
            List of TextChunk objects ready for embedding
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

            logger.info(f"Processing text file: {file_path}")

            # Detect file type and read content
            file_type = file_path.suffix.lstrip(".") or "txt"

            if file_type == "pdf":
                # Use PDF processor
                text = self.pdf_processor.extract_text(file_path)
            else:
                # Read as plain text
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

            # Compute content hash
            content_hash = self.hasher.hash_text(text)

            # Get file metadata
            stats = file_path.stat()
            file_size = stats.st_size
            creation_date = datetime.fromtimestamp(stats.st_ctime).isoformat()
            last_modified = datetime.fromtimestamp(stats.st_mtime).isoformat()

            # Generate parent document ID
            parent_doc_id = str(uuid.uuid4())

            # Chunk text
            chunks = self.chunk_text(text)

            if not chunks:
                logger.warning(f"No chunks extracted from {file_path}")
                return []

            # Process each chunk
            text_chunks = []
            for idx, chunk_text in enumerate(chunks):
                # Extract typed entities from this chunk
                entities, typed = self._extract_typed_entities(chunk_text)

                # Create TextChunk object
                text_chunk = TextChunk(
                    text=chunk_text,
                    chunk_index=idx,
                    parent_doc_id=parent_doc_id,
                    source_path=str(file_path),
                    file_type=file_type,
                    content_hash=content_hash,
                    file_size=file_size,
                    creation_date=creation_date,
                    last_modified=last_modified,
                    tags=custom_tags or [],
                    extracted_entities=entities,
                    typed_entities=typed,
                )

                text_chunks.append(text_chunk)

            logger.info(
                f"Processed {file_path.name}: {len(text_chunks)} chunks, "
                f"{len(text)} chars"
            )

            return text_chunks

        except Exception as e:
            logger.error(f"Error processing text file {file_path}: {e}")
            raise

    def process_text_string(
        self,
        text: str,
        source_path: str = "inline_text",
        file_type: str = "txt",
        custom_tags: Optional[list[str]] = None,
    ) -> list[TextChunk]:
        """
        Process a raw text string (not from file).

        Args:
            text: Input text
            source_path: Virtual source path
            file_type: File type identifier
            custom_tags: Optional custom tags

        Returns:
            List of TextChunk objects
        """
        try:
            if not text or not text.strip():
                logger.warning("Empty text string provided")
                return []

            # Compute content hash
            content_hash = self.hasher.hash_text(text)

            # Generate parent document ID
            parent_doc_id = str(uuid.uuid4())

            # Current timestamp
            now = datetime.utcnow().isoformat()

            # Chunk text
            chunks = self.chunk_text(text)

            # Process each chunk
            text_chunks = []
            for idx, chunk_text in enumerate(chunks):
                # Extract typed entities
                entities, typed = self._extract_typed_entities(chunk_text)

                text_chunk = TextChunk(
                    text=chunk_text,
                    chunk_index=idx,
                    parent_doc_id=parent_doc_id,
                    source_path=source_path,
                    file_type=file_type,
                    content_hash=content_hash,
                    file_size=len(text.encode("utf-8")),
                    creation_date=now,
                    last_modified=now,
                    tags=custom_tags or [],
                    extracted_entities=entities,
                    typed_entities=typed,
                )

                text_chunks.append(text_chunk)

            logger.info(
                f"Processed text string: {len(text_chunks)} chunks from {len(text)} chars"
            )
            return text_chunks

        except Exception as e:
            logger.error(f"Error processing text string: {e}")
            raise

    def process_batch(
        self, file_paths: list[Path], custom_tags: Optional[list[str]] = None
    ) -> list[list[TextChunk]]:
        """
        Process multiple text files in batch.

        Args:
            file_paths: List of file paths
            custom_tags: Optional custom tags for all files

        Returns:
            List of chunk lists (one per file)
        """
        try:
            logger.info(f"Processing batch of {len(file_paths)} files")

            results = []
            for file_path in file_paths:
                try:
                    chunks = self.process_text_file(file_path, custom_tags)
                    results.append(chunks)
                except Exception as e:
                    logger.error(f"Failed to process {file_path}: {e}")
                    results.append([])

            total_chunks = sum(len(chunks) for chunks in results)
            logger.info(
                f"Batch processed {len(file_paths)} files into {total_chunks} chunks"
            )

            return results

        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
            raise


# Global singleton instance
_text_processor: Optional[TextProcessor] = None


def get_text_processor(
    chunk_size: Optional[int] = None, chunk_overlap: Optional[int] = None
) -> TextProcessor:
    """
    Get or create global TextProcessor instance.

    Args:
        chunk_size: Override default chunk size
        chunk_overlap: Override default chunk overlap

    Returns:
        TextProcessor instance
    """
    global _text_processor
    if _text_processor is None:
        _text_processor = TextProcessor(
            chunk_size=chunk_size or settings.text_chunk_size,
            chunk_overlap=chunk_overlap or settings.text_chunk_overlap,
        )
    return _text_processor
