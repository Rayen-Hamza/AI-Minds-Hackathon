"""
Configuration management using Pydantic Settings.
All settings are loaded from environment variables or .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import logging


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Qdrant Configuration
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # FastAPI Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Embedding Models
    text_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # DINOv2 ViT-L for image similarity/clustering (~300M params)
    image_embedding_model: str = "facebook/dinov2-large"
    # SigLIP for text-to-image search (~400M params)
    text_to_image_model: str = "google/siglip-so400m-patch14-384"
    # NVIDIA Canary-Qwen 2.5B for speech-to-text
    speech_model: str = "nvidia/canary-qwen-2.5b"

    # Processing Configuration
    text_chunk_size: int = 512
    text_chunk_overlap: int = 50
    max_file_size_mb: int = 100

    # Collection Names (unified collection with named vectors)
    unified_collection: str = "multimodal_embeddings"

    # Embedding Dimensions
    text_embedding_dim: int = 384  # MiniLM-L6-v2
    image_embedding_dim: int = 1024  # DINOv2 ViT-L
    text_to_image_dim: int = 1152  # SigLIP SO400M

    # HNSW Index Configuration
    hnsw_m: int = 16
    hnsw_ef_construct: int = 200

    # Logging
    log_level: str = "INFO"

    # Neo4j (for future integration)
    neo4j_uri: Optional[str] = None
    neo4j_user: Optional[str] = None
    neo4j_password: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    def setup_logging(self) -> None:
        """Configure logging based on settings."""
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    @property
    def qdrant_url(self) -> str:
        """Get full Qdrant URL."""
        return f"http://{self.qdrant_host}:{self.qdrant_port}"

    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024


# Global settings instance
settings = Settings()
settings.setup_logging()
