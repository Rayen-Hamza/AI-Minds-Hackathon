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
    # BLIP for image captioning (text-centric approach)
    image_captioning_model: str = "Salesforce/blip-image-captioning-base"
    # OpenAI Whisper Base for speech-to-text (~74M params, CPU-friendly)
    speech_model: str = "openai/whisper-base"

    # Processing Configuration
    text_chunk_size: int = 512
    text_chunk_overlap: int = 50
    max_file_size_mb: int = 100

    # Collection Names (unified collection with single text vector)
    unified_collection: str = "multimodal_embeddings"

    # Embedding Dimensions (text-centric: single dimension for all)
    text_embedding_dim: int = 384  # MiniLM-L6-v2

    # HNSW Index Configuration
    hnsw_m: int = 16
    hnsw_ef_construct: int = 200

    # Logging
    log_level: str = "INFO"

    # LLM Configuration (Local or API)
    llm_provider: str = "ollama"  # "ollama", "openai", or "gemini"
    llm_model: str = "qwen2.5:3b"  # Model name for Ollama
    llm_base_url: str = "http://localhost:11434/v1"  # Ollama OpenAI-compatible endpoint
    llm_api_key: Optional[str] = None  # Not needed for Ollama

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
