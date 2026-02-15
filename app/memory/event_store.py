"""
Event storage in Qdrant with semantic embeddings.
Stores conversation history for context retrieval.
"""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

from .models import Event
from ..config import settings

logger = logging.getLogger(__name__)


class EventStore:
    """Manages conversation event storage in Qdrant."""

    COLLECTION_NAME = "conversation_events"

    def __init__(
        self,
        qdrant_client: Optional[QdrantClient] = None,
        embedding_model: Optional[SentenceTransformer] = None,
    ):
        """
        Initialize event store.

        Args:
            qdrant_client: Qdrant client instance (creates new if None)
            embedding_model: Sentence transformer model (loads default if None)
        """
        # Initialize Qdrant client
        if qdrant_client is None:
            self.client = QdrantClient(
                host=settings.qdrant_host, port=settings.qdrant_port
            )
        else:
            self.client = qdrant_client

        # Initialize embedding model
        if embedding_model is None:
            logger.info(f"Loading embedding model: {settings.text_embedding_model}")
            self.embedder = SentenceTransformer(settings.text_embedding_model)
        else:
            self.embedder = embedding_model

        # Ensure collection exists
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create the events collection if it doesn't exist."""
        try:
            if not self.client.collection_exists(self.COLLECTION_NAME):
                logger.info(f"Creating collection: {self.COLLECTION_NAME}")
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=settings.text_embedding_dim, distance=Distance.COSINE
                    ),
                )
                logger.info(f"Collection {self.COLLECTION_NAME} created successfully")
        except Exception as e:
            logger.error(f"Error ensuring collection: {e}")

    def add_event(self, event: Event) -> bool:
        """
        Add an event to the store.

        Args:
            event: Event object to store

        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate embedding
            embedding = self.embedder.encode(event.text).tolist()

            # Prepare payload
            payload = {
                "text": event.text,
                "timestamp": event.timestamp.isoformat(),
                "session_id": event.session_id,
                "metadata": event.metadata,
            }

            # Upsert point
            point = PointStruct(id=event.id, vector=embedding, payload=payload)

            self.client.upsert(
                collection_name=self.COLLECTION_NAME, points=[point], wait=True
            )

            logger.debug(f"Event added: {event.id}")
            return True

        except Exception as e:
            logger.error(f"Error adding event: {e}")
            return False

    def search_relevant_events(
        self, query: str, limit: int = 5, session_id: Optional[str] = None
    ) -> List[dict]:
        """
        Search for events relevant to a query.

        Args:
            query: Query text to search for
            limit: Maximum number of results
            session_id: Optional filter by session

        Returns:
            List of relevant events with their payloads
        """
        try:
            # Generate query embedding
            query_embedding = self.embedder.encode(query).tolist()

            # Build filter if session_id provided
            query_filter = None
            if session_id:
                from qdrant_client.models import Filter, FieldCondition, MatchValue

                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="session_id", match=MatchValue(value=session_id)
                        )
                    ]
                )

            # Search using query_points (qdrant-client >= 1.12)
            response = self.client.query_points(
                collection_name=self.COLLECTION_NAME,
                query=query_embedding,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
            )

            # Extract payloads and convert timestamps back to datetime
            events = []
            for result in response.points:
                payload = result.payload.copy()
                if "timestamp" in payload:
                    payload["timestamp"] = datetime.fromisoformat(payload["timestamp"])
                payload["score"] = result.score
                events.append(payload)

            logger.debug(f"Found {len(events)} relevant events for query")
            return events

        except Exception as e:
            logger.error(f"Error searching events: {e}")
            return []

    def get_recent_events(
        self, limit: int = 10, session_id: Optional[str] = None
    ) -> List[dict]:
        """
        Get the most recent events.

        Args:
            limit: Maximum number of events to retrieve
            session_id: Optional filter by session

        Returns:
            List of recent events
        """
        try:
            # Build filter if session_id provided
            query_filter = None
            if session_id:
                from qdrant_client.models import Filter, FieldCondition, MatchValue

                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="session_id", match=MatchValue(value=session_id)
                        )
                    ]
                )

            # Scroll to get points (sorted by insertion order, which approximates time)
            scroll_result = self.client.scroll(
                collection_name=self.COLLECTION_NAME,
                scroll_filter=query_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )

            points = scroll_result[0] if scroll_result else []

            # Extract payloads and convert timestamps
            events = []
            for point in points:
                payload = point.payload.copy()
                if "timestamp" in payload:
                    payload["timestamp"] = datetime.fromisoformat(payload["timestamp"])
                events.append(payload)

            # Sort by timestamp descending
            events.sort(key=lambda x: x.get("timestamp", datetime.min), reverse=True)

            return events[:limit]

        except Exception as e:
            logger.error(f"Error getting recent events: {e}")
            return []

    def count_events(self, session_id: Optional[str] = None) -> int:
        """
        Count total events in the store.

        Args:
            session_id: Optional filter by session

        Returns:
            Number of events
        """
        try:
            result = self.client.count(collection_name=self.COLLECTION_NAME)
            return result.count
        except Exception as e:
            logger.error(f"Error counting events: {e}")
            return 0

    def clear_events(self, session_id: Optional[str] = None) -> bool:
        """
        Clear all events (or for a specific session).

        Args:
            session_id: Optional - clear only events from this session

        Returns:
            True if successful, False otherwise
        """
        try:
            if session_id:
                # Delete points matching session_id
                from qdrant_client.models import Filter, FieldCondition, MatchValue

                self.client.delete(
                    collection_name=self.COLLECTION_NAME,
                    points_selector=Filter(
                        must=[
                            FieldCondition(
                                key="session_id", match=MatchValue(value=session_id)
                            )
                        ]
                    ),
                )
                logger.info(f"Cleared events for session: {session_id}")
            else:
                # Delete entire collection and recreate
                self.client.delete_collection(self.COLLECTION_NAME)
                self._ensure_collection()
                logger.info("Cleared all events")

            return True

        except Exception as e:
            logger.error(f"Error clearing events: {e}")
            return False
