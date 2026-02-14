from qdrant_client import QdrantClient

from app.config import settings


def get_qdrant_client() -> QdrantClient:
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
