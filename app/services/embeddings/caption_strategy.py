"""
Text-to-image search strategy using SigLIP.
Uses google/siglip-so400m-patch14-384 (1152-dim) for text-to-image search.
"""

import logging
from typing import Optional
from pathlib import Path
from PIL import Image
from transformers import SiglipTokenizer, SiglipImageProcessor, SiglipModel
import torch

from .base import EmbeddingStrategy

logger = logging.getLogger(__name__)


class CaptionEmbeddingStrategy(EmbeddingStrategy):
    """
    Text-to-image search using SigLIP.
    Generates aligned text and image embeddings (1152-dim) for cross-modal search.
    """

    def __init__(self, model_name: str = "google/siglip-so400m-patch14-384"):
        """
        Initialize text-to-image search strategy.

        Args:
            model_name: SigLIP model name
        """
        super().__init__(model_name)
        self._tokenizer: Optional[SiglipTokenizer] = None
        self._image_processor: Optional[SiglipImageProcessor] = None
        self._device: Optional[str] = None

    def _load_model(self) -> None:
        """Load SigLIP model via transformers."""
        try:
            # Detect device
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(
                f"Loading SigLIP model '{self.model_name}' on device: {self._device}"
            )
            logger.debug(
                f"Model name type: {type(self.model_name)}, value: {repr(self.model_name)}"
            )

            # Load SigLIP tokenizer and image processor separately
            logger.debug(f"Loading tokenizer for model: {self.model_name}")
            self._tokenizer = SiglipTokenizer.from_pretrained(self.model_name)
            logger.debug("Tokenizer loaded, now loading image processor...")
            self._image_processor = SiglipImageProcessor.from_pretrained(self.model_name)
            logger.debug("Image processor loaded, now loading model...")
            self._model = SiglipModel.from_pretrained(
                self.model_name,
                trust_remote_code=False
            ).to(self._device)
            self._model.eval()

            # SigLIP SO400M outputs 1152-dim embeddings
            self._dimension = 1152

            logger.info(
                f"Loaded {self.model_name} successfully. "
                f"Dimension: {self._dimension}, Device: {self._device}"
            )

        except Exception as e:
            logger.error(f"Failed to load SigLIP model: {e}", exc_info=True)
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

            # Convert to RGB
            if img.mode != "RGB":
                img = img.convert("RGB")

            return img

        except Exception as e:
            logger.error(f"Error loading image {image_path}: {e}")
            raise

    def embed(self, content: str | Path) -> list[float]:
        """
        Generate SigLIP image embedding for text-to-image search.

        Args:
            content: Path to image file

        Returns:
            1152-dimensional image embedding vector
        """
        try:
            # Ensure model is loaded (triggers lazy loading)
            _ = self.model

            # Load image
            img = self._load_image(content)

            # Process image
            inputs = self._image_processor(images=img, return_tensors="pt").to(self._device)

            # Generate image embedding
            with torch.no_grad():
                image_features = self._model.get_image_features(**inputs)
                # Normalize for similarity search
                embedding = image_features / image_features.norm(dim=-1, keepdim=True)
                embedding = embedding.cpu().numpy()[0]

            logger.debug(f"Generated SigLIP image embedding: shape {len(embedding)}")
            return embedding.tolist()

        except Exception as e:
            logger.error(f"Error generating image embedding for {content}: {e}")
            raise

    def embed_text(self, text: str) -> list[float]:
        """
        Generate SigLIP text embedding for image search.

        Args:
            text: Query text

        Returns:
            1152-dimensional text embedding vector
        """
        try:
            # Ensure model is loaded (triggers lazy loading)
            _ = self.model

            # Process text
            inputs = self._tokenizer(text=text, return_tensors="pt", padding="max_length", truncation=True).to(self._device)

            # Generate text embedding
            with torch.no_grad():
                text_features = self._model.get_text_features(**inputs)
                # Normalize for similarity search
                embedding = text_features / text_features.norm(dim=-1, keepdim=True)
                embedding = embedding.cpu().numpy()[0]

            logger.debug(f"Generated SigLIP text embedding: shape {len(embedding)}")
            return embedding.tolist()

        except Exception as e:
            logger.error(f"Error generating text embedding for '{text}': {e}")
            raise

    def embed_batch(self, contents: list[str | Path]) -> list[list[float]]:
        """
        Generate SigLIP image embeddings for multiple images.

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
                    images.append(Image.new("RGB", (384, 384)))

            logger.info(f"Generating SigLIP embeddings for {len(images)} images")

            # Process batch
            inputs = self._image_processor(images=images, return_tensors="pt").to(
                self._device
            )

            # Generate embeddings
            with torch.no_grad():
                image_features = self._model.get_image_features(**inputs)
                # Normalize for similarity search
                embeddings = image_features / image_features.norm(dim=-1, keepdim=True)
                embeddings = embeddings.cpu().numpy()

            return embeddings.tolist()

        except Exception as e:
            logger.error(f"Error generating batch image embeddings: {e}")
            raise


# Global singleton instance
_caption_embedder: Optional[CaptionEmbeddingStrategy] = None


def get_caption_embedder(
    model_name: str = "google/siglip-so400m-patch14-384",
) -> CaptionEmbeddingStrategy:
    """
    Get or create global SigLIP embedder instance for text-to-image search.

    Args:
        model_name: SigLIP model name

    Returns:
        CaptionEmbeddingStrategy instance
    """
    global _caption_embedder
    if _caption_embedder is None:
        _caption_embedder = CaptionEmbeddingStrategy(model_name)
    return _caption_embedder
