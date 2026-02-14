"""
Image embedding strategy using DINOv2.
Uses facebook/dinov2-large (1024-dim) for image similarity and clustering.
"""

import logging
from typing import Optional
from pathlib import Path
from PIL import Image
from transformers import AutoImageProcessor, AutoModel
import torch

from .base import EmbeddingStrategy

logger = logging.getLogger(__name__)


class ImageEmbeddingStrategy(EmbeddingStrategy):
    """
    Image embedding using DINOv2 ViT-L model.
    Generates 1024-dimensional embeddings for image similarity search and clustering.
    """

    def __init__(self, model_name: str = "facebook/dinov2-large"):
        """
        Initialize image embedding strategy.

        Args:
            model_name: DINOv2 model name
        """
        super().__init__(model_name)
        self._device: Optional[str] = None
        self._processor: Optional[AutoImageProcessor] = None

    def _load_model(self) -> None:
        """Load DINOv2 model via transformers."""
        try:
            # Detect device
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Loading DINOv2 image model on device: {self._device}")

            # Load DINOv2 processor and model
            self._processor = AutoImageProcessor.from_pretrained(self.model_name)
            self._model = AutoModel.from_pretrained(self.model_name).to(self._device)
            self._model.eval()

            # DINOv2 ViT-L outputs 1024-dim embeddings
            self._dimension = 1024

            logger.info(
                f"Loaded {self.model_name} successfully. "
                f"Dimension: {self._dimension}, Device: {self._device}"
            )

        except Exception as e:
            logger.error(f"Failed to load DINOv2 image model: {e}")
            raise

    def _load_image(self, image_path: str | Path) -> Image.Image:
        """
        Load and preprocess image.

        Args:
            image_path: Path to image file

        Returns:
            PIL Image object
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        try:
            img = Image.open(image_path)

            # Convert to RGB if needed
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            return img

        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            raise

    def embed(self, content: str | Path) -> list[float]:
        """
        Generate DINOv2 embedding for a single image.

        Args:
            content: Path to image file

        Returns:
            1024-dimensional embedding vector
        """
        try:
            # Ensure model is loaded (triggers lazy loading)
            _ = self.model

            # Load image
            img = self._load_image(content)

            # Process image
            inputs = self._processor(images=img, return_tensors="pt").to(self._device)

            # Generate embedding
            with torch.no_grad():
                outputs = self._model(**inputs)
                # Use CLS token embedding
                embedding = outputs.last_hidden_state[:, 0].cpu().numpy()[0]

            logger.debug(f"Generated DINOv2 embedding: shape {len(embedding)}")
            return embedding.tolist()

        except Exception as e:
            logger.error(f"Error generating image embedding for {content}: {e}")
            raise

    def embed_batch(self, contents: list[str | Path]) -> list[list[float]]:
        """
        Generate DINOv2 embeddings for multiple images.

        Args:
            contents: List of image file paths

        Returns:
            List of embedding vectors
        """
        try:
            if not contents:
                return []

            # Ensure model is loaded (triggers lazy loading)
            _ = self.model

            # Load all images
            images = []
            for img_path in contents:
                try:
                    img = self._load_image(img_path)
                    images.append(img)
                except Exception as e:
                    logger.warning(f"Skipping image {img_path}: {e}")
                    # Add a blank image as placeholder
                    images.append(Image.new("RGB", (224, 224)))

            logger.info(f"Generating DINOv2 embeddings for {len(images)} images")

            # Process batch
            inputs = self._processor(images=images, return_tensors="pt").to(
                self._device
            )

            # Generate embeddings
            with torch.no_grad():
                outputs = self._model(**inputs)
                # Use CLS token embeddings
                embeddings = outputs.last_hidden_state[:, 0].cpu().numpy()

            return embeddings.tolist()

        except Exception as e:
            logger.error(f"Error generating batch image embeddings: {e}")
            raise


# Global singleton instance
_image_embedder: Optional[ImageEmbeddingStrategy] = None


def get_image_embedder(
    model_name: str = "facebook/dinov2-large",
) -> ImageEmbeddingStrategy:
    """
    Get or create global image embedder instance.

    Args:
        model_name: DINOv2 model name

    Returns:
        ImageEmbeddingStrategy instance
    """
    global _image_embedder
    if _image_embedder is None:
        _image_embedder = ImageEmbeddingStrategy(model_name)
    return _image_embedder
