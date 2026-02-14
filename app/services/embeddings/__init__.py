"""
Embedding strategies for different content types.
"""

from .base import EmbeddingStrategy
from .text_strategy import TextEmbeddingStrategy, get_text_embedder
from .image_strategy import ImageEmbeddingStrategy, get_image_embedder
from .caption_strategy import CaptionEmbeddingStrategy, get_caption_embedder
from .audio_strategy import AudioEmbeddingStrategy, get_audio_embedder

__all__ = [
    "EmbeddingStrategy",
    "TextEmbeddingStrategy",
    "ImageEmbeddingStrategy",
    "CaptionEmbeddingStrategy",
    "AudioEmbeddingStrategy",
    "get_text_embedder",
    "get_image_embedder",
    "get_caption_embedder",
    "get_audio_embedder",
]
