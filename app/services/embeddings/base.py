"""
Base classes for embedding strategies using the Strategy Pattern.
Allows different embedding models for different content types.
"""

from abc import ABC, abstractmethod
from typing import Any
import logging

logger = logging.getLogger(__name__)


class EmbeddingStrategy(ABC):
    """
    Abstract base class for embedding generation strategies.
    Implements the Strategy Pattern for flexible embedding model swapping.
    """

    def __init__(self, model_name: str):
        """
        Initialize embedding strategy.

        Args:
            model_name: Name/path of the embedding model
        """
        self.model_name = model_name
        self._model: Any = None
        self._dimension: int = 0
        logger.info(f"Initialized {self.__class__.__name__} with model: {model_name}")

    @abstractmethod
    def _load_model(self) -> None:
        """
        Load the embedding model.
        Called lazily on first use. Subclasses must implement this.
        """
        pass

    @abstractmethod
    def embed(self, content: Any) -> list[float]:
        """
        Generate embedding for a single piece of content.

        Args:
            content: Content to embed (type depends on strategy)

        Returns:
            Embedding vector as list of floats
        """
        pass

    @abstractmethod
    def embed_batch(self, contents: list[Any]) -> list[list[float]]:
        """
        Generate embeddings for multiple contents efficiently.

        Args:
            contents: List of contents to embed

        Returns:
            List of embedding vectors
        """
        pass

    @property
    def model(self) -> Any:
        """
        Lazy-load the model on first access.

        Returns:
            Loaded model instance
        """
        if self._model is None:
            logger.info(f"Lazy-loading model: {self.model_name}")
            self._load_model()
        return self._model

    @property
    def dimension(self) -> int:
        """
        Get embedding dimension.

        Returns:
            Dimension of embedding vectors
        """
        if self._dimension == 0:
            # Trigger model load to get dimension
            _ = self.model
        return self._dimension

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_name}, dim={self._dimension})"
