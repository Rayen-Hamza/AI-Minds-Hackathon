"""
Text embedding strategy using sentence-transformers.
Uses all-MiniLM-L6-v2 (384-dim) for efficient text embeddings.
"""

import logging
from typing import Optional
from sentence_transformers import SentenceTransformer
import torch

from .base import EmbeddingStrategy

logger = logging.getLogger(__name__)


class TextEmbeddingStrategy(EmbeddingStrategy):
    """
    Text embedding using sentence-transformers MiniLM model.
    Generates 384-dimensional embeddings optimized for semantic similarity.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize text embedding strategy.

        Args:
            model_name: Sentence-transformers model name
        """
        super().__init__(model_name)
        self._device: Optional[str] = None

    def _load_model(self) -> None:
        """Load sentence-transformers model with GPU support if available."""
        try:
            # Detect device
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading text embedding model on device: {self._device}")

            # Load model
            self._model = SentenceTransformer(self.model_name, device=self._device)

            # Get embedding dimension
            self._dimension = self._model.get_sentence_embedding_dimension()

            logger.info(
                f"Loaded {self.model_name} successfully. "
                f"Dimension: {self._dimension}, Device: {self._device}"
            )

        except Exception as e:
            logger.error(f"Failed to load text embedding model: {e}")
            raise

    def embed(self, content: str) -> list[float]:
        """
        Generate embedding for a single text string.

        Args:
            content: Text string to embed

        Returns:
            384-dimensional embedding vector
        """
        try:
            if not content or not content.strip():
                logger.warning("Empty text provided for embedding, returning zero vector")
                return [0.0] * self.dimension

            # Generate embedding
            embedding = self.model.encode(
                content,
                convert_to_tensor=False,
                normalize_embeddings=True,  # L2 normalization for cosine similarity
                show_progress_bar=False
            )

            # Convert to list
            return embedding.tolist()

        except Exception as e:
            logger.error(f"Error generating text embedding: {e}")
            raise

    def embed_batch(self, contents: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            contents: List of text strings

        Returns:
            List of embedding vectors
        """
        try:
            if not contents:
                return []

            # Filter out empty strings
            valid_contents = [c if c.strip() else " " for c in contents]

            logger.info(f"Generating embeddings for {len(valid_contents)} text chunks")

            # Batch encode with progress bar for large batches
            embeddings = self.model.encode(
                valid_contents,
                batch_size=32,
                convert_to_tensor=False,
                normalize_embeddings=True,
                show_progress_bar=len(valid_contents) > 50
            )

            # Convert to list of lists
            return embeddings.tolist()

        except Exception as e:
            logger.error(f"Error generating batch text embeddings: {e}")
            raise

    def encode(self, text: str) -> list[float]:
        """Alias for embed() for compatibility."""
        return self.embed(text)


# Global singleton instance
_text_embedder: Optional[TextEmbeddingStrategy] = None


def get_text_embedder(model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> TextEmbeddingStrategy:
    """
    Get or create global text embedder instance.

    Args:
        model_name: Model name (uses default if not specified)

    Returns:
        TextEmbeddingStrategy instance
    """
    global _text_embedder
    if _text_embedder is None:
        _text_embedder = TextEmbeddingStrategy(model_name)
    return _text_embedder
