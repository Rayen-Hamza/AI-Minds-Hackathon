"""
Audio embedding strategy.
Transcribes audio using OpenAI Whisper, then embeds transcript with MiniLM (384-dim).
"""

import logging
from typing import Optional
from pathlib import Path
import torch
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq
import soundfile as sf

from .base import EmbeddingStrategy
from .text_strategy import get_text_embedder

logger = logging.getLogger(__name__)


class AudioEmbeddingStrategy(EmbeddingStrategy):
    """
    Audio-to-text embedding strategy.
    1. Transcribe audio using NVIDIA Canary-Qwen 2.5B
    2. Embed transcript using MiniLM (384-dim)
    """

    def __init__(
        self,
        model_name: str = "openai/whisper-base",
        text_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        """
        Initialize audio embedding strategy.

        Args:
            model_name: Whisper model name
            text_model: Text embedding model for transcript embedding
        """
        super().__init__(model_name)
        self.text_model_name = text_model
        self._processor: Optional[AutoProcessor] = None
        self._text_embedder = None
        self._device: Optional[str] = None

    def _load_model(self) -> None:
        """Load Canary-Qwen transcription model and text embedder."""
        try:
            # Detect device
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            logger.info(f"Loading Whisper model on device: {self._device}")

            # Load Whisper processor and model
            self._processor = AutoProcessor.from_pretrained(self.model_name)
            self._model = AutoModelForSpeechSeq2Seq.from_pretrained(
                self.model_name, torch_dtype=torch_dtype, low_cpu_mem_usage=True
            ).to(self._device)

            # Load text embedder
            self._text_embedder = get_text_embedder(self.text_model_name)

            # Dimension is from text embedder (384 for MiniLM)
            self._dimension = self._text_embedder.dimension

            logger.info(
                f"Loaded {self.model_name} model. "
                f"Text embedding dimension: {self._dimension}, Device: {self._device}"
            )

        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    def transcribe(self, audio_path: str | Path) -> dict:
        """
        Transcribe audio file using Whisper.

        Args:
            audio_path: Path to audio file

        Returns:
            Transcription result dict with 'text'
        """
        try:
            # Ensure model is loaded
            _ = self.model

            audio_path = Path(audio_path)
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_path}")

            logger.info(f"Transcribing audio file: {audio_path.name}")

            # Load audio file
            audio_input, sample_rate = sf.read(str(audio_path))

            # Whisper expects 16kHz mono audio — resample if needed
            if len(audio_input.shape) > 1:
                audio_input = audio_input.mean(axis=1)  # stereo to mono

            target_sr = 16000
            if sample_rate != target_sr:
                import numpy as np
                duration = len(audio_input) / sample_rate
                num_samples = int(duration * target_sr)
                indices = np.linspace(0, len(audio_input) - 1, num_samples)
                audio_input = np.interp(indices, np.arange(len(audio_input)), audio_input)
                sample_rate = target_sr
                logger.debug(f"Resampled audio to {target_sr}Hz")

            # Process audio
            inputs = self._processor(
                audio_input, sampling_rate=sample_rate, return_tensors="pt"
            ).to(self._device)

            # Generate transcription
            with torch.no_grad():
                generated_ids = self._model.generate(**inputs)

            # Decode transcription
            transcript = self._processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0].strip()

            logger.debug(f"Transcribed {audio_path.name}: '{transcript[:100]}...'")

            return {"text": transcript}

        except Exception as e:
            logger.error(f"Error transcribing audio {audio_path}: {e}")
            raise

    def embed(self, content: str | Path) -> list[float]:
        """
        Generate embedding for audio file.
        1. Transcribe using Whisper
        2. Embed full transcript

        Args:
            content: Path to audio file

        Returns:
            384-dimensional transcript embedding vector
        """
        try:
            # Ensure model is loaded
            _ = self.model

            # Transcribe audio
            result = self.transcribe(content)
            transcript = result["text"]

            if not transcript.strip():
                logger.warning(f"Empty transcript for {content}, using zero vector")
                return [0.0] * self.dimension

            # Embed transcript
            embedding = self._text_embedder.embed(transcript)

            return embedding

        except Exception as e:
            logger.error(f"Error generating audio embedding for {content}: {e}")
            raise

    def embed_batch(self, contents: list[str | Path]) -> list[list[float]]:
        """
        Generate embeddings for multiple audio files.

        Args:
            contents: List of audio file paths

        Returns:
            List of embedding vectors
        """
        try:
            # Ensure model is loaded
            _ = self.model

            if not contents:
                return []

            logger.info(f"Generating audio embeddings for {len(contents)} files")

            # Transcribe all audio files
            transcripts = []
            for audio_path in contents:
                try:
                    result = self.transcribe(audio_path)
                    transcript = result["text"]
                    transcripts.append(transcript if transcript.strip() else " ")
                except Exception as e:
                    logger.warning(f"Failed to transcribe {audio_path}: {e}")
                    transcripts.append(" ")  # Fallback

            # Batch embed transcripts
            embeddings = self._text_embedder.embed_batch(transcripts)

            return embeddings

        except Exception as e:
            logger.error(f"Error generating batch audio embeddings: {e}")
            raise

    def transcribe_with_timestamps(self, audio_path: str | Path) -> list[dict]:
        """
        Transcribe audio with word-level timestamps.
        Note: Canary-Qwen may not provide detailed timestamps like Whisper.

        Args:
            audio_path: Path to audio file

        Returns:
            List of segment dicts with 'text', 'start', 'end'
        """
        try:
            result = self.transcribe(audio_path)
            text = result.get("text", "")

            # Since Canary-Qwen may not provide segments, return full text as single segment
            formatted_segments = [
                {
                    "text": text.strip(),
                    "start": 0.0,
                    "end": 0.0,  # Duration not available without segments
                }
            ]

            return formatted_segments

        except Exception as e:
            logger.error(f"Error getting timestamped transcript for {audio_path}: {e}")
            raise


# Global singleton instance
_audio_embedder: Optional[AudioEmbeddingStrategy] = None


def get_audio_embedder(
    model_name: str = "openai/whisper-base",
    text_model: str = "sentence-transformers/all-MiniLM-L6-v2",
) -> AudioEmbeddingStrategy:
    """
    Get or create global audio embedder instance.

    Args:
        model_name: Whisper model name
        text_model: Text embedding model name

    Returns:
        AudioEmbeddingStrategy instance
    """
    global _audio_embedder
    if _audio_embedder is None:
        _audio_embedder = AudioEmbeddingStrategy(model_name, text_model)
    return _audio_embedder
