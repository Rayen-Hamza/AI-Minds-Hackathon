"""
Audio processing pipeline using NVIDIA Canary-Qwen for transcription.
Handles audio transcription, chunking, and entity extraction.
"""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
import uuid

import soundfile as sf

from app.models.models import AudioChunk
from app.config import settings
from app.services.storage.content_hasher import get_content_hasher
from app.services.embeddings.audio_strategy import get_audio_embedder
from .entity_extractor import get_entity_extractor
from .text_processor import get_text_processor

logger = logging.getLogger(__name__)


class AudioProcessor:
    """
    Processes audio files for embedding and storage.
    Transcribes audio using NVIDIA Canary-Qwen, chunks transcript, and extracts entities.
    """

    def __init__(self):
        """Initialize audio processor."""
        self.hasher = get_content_hasher()
        self.entity_extractor = get_entity_extractor()
        self.text_processor = get_text_processor()
        self._audio_embedder = None  # Lazy load

        logger.info("Initialized AudioProcessor")

    @property
    def audio_embedder(self):
        """Lazy-load audio embedder."""
        if self._audio_embedder is None:
            try:
                self._audio_embedder = get_audio_embedder()
            except Exception as e:
                logger.warning(f"Failed to load audio embedder: {e}")
                self._audio_embedder = None
        return self._audio_embedder

    def get_audio_metadata(self, audio_path: str | Path) -> dict:
        """
        Extract audio metadata using soundfile.

        Args:
            audio_path: Path to audio file

        Returns:
            Dict with audio metadata
        """
        try:
            audio_path = Path(audio_path)
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            # Get audio info
            info = sf.info(str(audio_path))

            metadata = {
                "duration": info.duration,  # in seconds
                "sample_rate": info.samplerate,
                "channels": info.channels,
                "format": info.format,
                "subtype": info.subtype,
            }

            logger.debug(
                f"Audio metadata for {audio_path.name}: "
                f"{metadata['duration']:.2f}s, {metadata['sample_rate']}Hz"
            )

            return metadata

        except Exception as e:
            logger.warning(f"Error extracting audio metadata from {audio_path}: {e}")
            return {}

    def transcribe_audio(self, audio_path: str | Path) -> dict:
        """
        Transcribe audio file using NVIDIA Canary-Qwen.

        Args:
            audio_path: Path to audio file

        Returns:
            Dict with 'text' (full transcript)
        """
        try:
            if self.audio_embedder is None:
                raise RuntimeError(
                    "Audio embedder not available. Cannot transcribe audio."
                )

            audio_path = Path(audio_path)
            logger.info(f"Transcribing audio file: {audio_path.name}")

            # Transcribe with Canary-Qwen
            result = self.audio_embedder.transcribe(audio_path)

            transcript = result["text"]

            logger.info(f"Transcribed {audio_path.name}: {len(transcript)} chars")

            return {"text": transcript}

        except Exception as e:
            logger.error(f"Error transcribing audio {audio_path}: {e}")
            raise

    def process_audio(
        self, audio_path: str | Path, custom_tags: Optional[list[str]] = None
    ) -> list[AudioChunk]:
        """
        Process an audio file into chunks with metadata.

        Args:
            audio_path: Path to audio file
            custom_tags: Optional custom tags

        Returns:
            List of AudioChunk objects ready for embedding
        """
        try:
            audio_path = Path(audio_path)
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            logger.info(f"Processing audio file: {audio_path}")

            # Compute content hash
            content_hash = self.hasher.hash_audio(audio_path)

            # Get file metadata
            stats = audio_path.stat()
            file_size = stats.st_size
            creation_date = datetime.fromtimestamp(stats.st_ctime).isoformat()
            last_modified = datetime.fromtimestamp(stats.st_mtime).isoformat()

            # Get audio metadata
            audio_metadata = self.get_audio_metadata(audio_path)
            duration = audio_metadata.get("duration")
            sample_rate = audio_metadata.get("sample_rate")

            # Generate parent document ID
            parent_doc_id = str(uuid.uuid4())

            # Transcribe audio
            transcription = self.transcribe_audio(audio_path)
            full_transcript = transcription["text"]

            if not full_transcript.strip():
                logger.warning(f"Empty transcript for {audio_path}, no chunks created")
                return []

            # Chunk the transcript using text chunker
            transcript_chunks = self.text_processor.chunk_text(full_transcript)

            # Process each chunk
            audio_chunks = []
            file_type = audio_path.suffix.lstrip(".") or "audio"

            for idx, chunk_text in enumerate(transcript_chunks):
                # Extract entities from this chunk
                entities = self.entity_extractor.extract_entities(chunk_text)

                # Create AudioChunk object
                audio_chunk = AudioChunk(
                    text=chunk_text,
                    chunk_index=idx,
                    parent_doc_id=parent_doc_id,
                    source_path=str(audio_path),
                    file_type=file_type,
                    content_hash=content_hash,
                    file_size=file_size,
                    audio_duration=duration,
                    sample_rate=sample_rate,
                    full_transcript=full_transcript,
                    creation_date=creation_date,
                    last_modified=last_modified,
                    tags=custom_tags or [],
                    extracted_entities=entities,
                )

                audio_chunks.append(audio_chunk)

            logger.info(
                f"Processed {audio_path.name}: {len(audio_chunks)} chunks "
                f"from {duration:.2f}s audio, {len(full_transcript)} chars transcript"
            )

            return audio_chunks

        except Exception as e:
            logger.error(f"Error processing audio {audio_path}: {e}")
            raise

    def process_batch(
        self, audio_paths: list[Path], custom_tags: Optional[list[str]] = None
    ) -> list[list[AudioChunk]]:
        """
        Process multiple audio files in batch.

        Args:
            audio_paths: List of audio file paths
            custom_tags: Optional custom tags for all files

        Returns:
            List of chunk lists (one per file)
        """
        try:
            logger.info(f"Processing batch of {len(audio_paths)} audio files")

            results = []
            for audio_path in audio_paths:
                try:
                    chunks = self.process_audio(audio_path, custom_tags)
                    results.append(chunks)
                except Exception as e:
                    logger.error(f"Failed to process {audio_path}: {e}")
                    results.append([])

            total_chunks = sum(len(chunks) for chunks in results)
            logger.info(
                f"Batch processed {len(audio_paths)} files into {total_chunks} chunks"
            )

            return results

        except Exception as e:
            logger.error(f"Error in batch audio processing: {e}")
            raise


# Global singleton instance
_audio_processor: Optional[AudioProcessor] = None


def get_audio_processor() -> AudioProcessor:
    """Get or create global AudioProcessor instance."""
    global _audio_processor
    if _audio_processor is None:
        _audio_processor = AudioProcessor()
    return _audio_processor
