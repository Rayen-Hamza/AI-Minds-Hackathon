"""
Main memory service integrating profile and event storage.
Provides the two key functions: record_event() and get_context().
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

import requests

from .models import Event, ExtractedFacts
from .profile_store import ProfileStore
from .event_store import EventStore
from .prompts import (
    EXTRACT_PROFILE_SYSTEM,
    EXTRACT_PROFILE_PROMPT,
    format_conversation_for_extraction,
    pack_context,
)
from ..config import settings

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Main memory service for profile extraction and context enrichment.
    """

    def __init__(
        self,
        profile_path: Optional[Path] = None,
        qdrant_client=None,
        embedding_model=None,
    ):
        """
        Initialize memory service.

        Args:
            profile_path: Path to profile JSON file
            qdrant_client: Optional Qdrant client
            embedding_model: Optional embedding model
        """
        self.profile_store = ProfileStore(profile_path)
        self.event_store = EventStore(qdrant_client, embedding_model)
        logger.info("Memory service initialized")

    def _extract_profile_from_conversation(
        self, user_message: str, assistant_response: str
    ) -> Dict[str, Any]:
        """
        Use LLM to extract profile information from a conversation turn.

        Args:
            user_message: User's message
            assistant_response: Assistant's response

        Returns:
            Dictionary with 'properties' and 'preferences' keys
        """
        try:
            # Format conversation
            conversation = format_conversation_for_extraction(
                user_message, assistant_response
            )

            # Build extraction prompt
            prompt = EXTRACT_PROFILE_PROMPT.format(conversation=conversation)

            # Call LLM
            response = requests.post(
                f"{settings.llm_base_url}/chat/completions",
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": EXTRACT_PROFILE_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500,
                },
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"].strip()

                # Parse JSON response
                try:
                    # Remove markdown code blocks if present
                    if content.startswith("```"):
                        content = content.split("```")[1]
                        if content.startswith("json"):
                            content = content[4:]
                    content = content.strip()

                    extracted = json.loads(content)

                    # Validate and normalize structure
                    if "properties" not in extracted:
                        extracted["properties"] = {}
                    elif not isinstance(extracted["properties"], dict):
                        logger.warning(f"Invalid properties type: {type(extracted['properties'])}, resetting to dict")
                        extracted["properties"] = {}

                    if "preferences" not in extracted:
                        extracted["preferences"] = {}
                    elif not isinstance(extracted["preferences"], dict):
                        logger.warning(f"Invalid preferences type: {type(extracted['preferences'])}, resetting to dict")
                        extracted["preferences"] = {}

                    logger.debug(f"Extracted profile data: {extracted}")
                    return extracted

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse LLM response as JSON: {e}")
                    logger.debug(f"Response content: {content}")
                    return {"properties": {}, "preferences": {}}

            else:
                logger.error(f"LLM API error: {response.status_code}")
                return {"properties": {}, "preferences": {}}

        except Exception as e:
            logger.error(f"Error extracting profile: {e}")
            return {"properties": {}, "preferences": {}}

    def record_event(
        self,
        user_message: str,
        assistant_response: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Record a conversation event and extract profile information.

        This is called AFTER the assistant responds to update memory.

        Args:
            user_message: The user's message
            assistant_response: The assistant's response
            session_id: Optional session identifier
            metadata: Optional additional metadata

        Returns:
            True if successful, False otherwise
        """
        try:
            # 1. Create and store event
            event_text = format_conversation_for_extraction(
                user_message, assistant_response
            )

            event = Event(
                text=event_text,
                session_id=session_id,
                metadata=metadata or {},
            )

            success = self.event_store.add_event(event)
            if not success:
                logger.warning("Failed to store event")

            # 2. Extract profile information
            extracted = self._extract_profile_from_conversation(
                user_message, assistant_response
            )

            # 3. Update profile if anything was extracted
            if extracted and isinstance(extracted, dict):
                props = extracted.get("properties", {})
                prefs = extracted.get("preferences", {})

                if (isinstance(props, dict) and props) or (isinstance(prefs, dict) and prefs):
                    try:
                        self.profile_store.update(extracted)
                        logger.info(
                            f"Updated profile with {len(props)} properties "
                            f"and {len(prefs)} preferences"
                        )
                    except Exception as update_err:
                        logger.error(f"Failed to update profile: {update_err}")

            return success

        except Exception as e:
            logger.error(f"Error recording event: {e}")
            return False

    def get_context(
        self,
        query: str,
        max_events: int = 5,
        session_id: Optional[str] = None,
        use_semantic_search: bool = True,
    ) -> str:
        """
        Get enriched context for a query.

        This is called BEFORE the assistant responds to inject memory into the prompt.

        Args:
            query: The user's current query
            max_events: Maximum number of relevant events to include
            session_id: Optional session filter
            use_semantic_search: If True, use semantic search; if False, use recent events

        Returns:
            Formatted context string to inject into system prompt
        """
        try:
            # 1. Load profile
            profile = self.profile_store.load()
            profile_data = {
                "properties": profile.properties,
                "preferences": profile.preferences,
            }

            # 2. Retrieve relevant events
            if use_semantic_search:
                events = self.event_store.search_relevant_events(
                    query=query, limit=max_events, session_id=session_id
                )
            else:
                events = self.event_store.get_recent_events(
                    limit=max_events, session_id=session_id
                )

            # 3. Pack context
            context = pack_context(profile_data, events, max_events)

            if context:
                logger.debug(f"Generated context with {len(events)} events")
            else:
                logger.debug("No context to add (empty profile and no events)")

            return context

        except Exception as e:
            logger.error(f"Error getting context: {e}")
            return ""

    def get_stats(self) -> Dict[str, Any]:
        """
        Get memory system statistics.

        Returns:
            Dictionary with profile and event statistics
        """
        try:
            profile = self.profile_store.load()
            event_count = self.event_store.count_events()

            return {
                "profile": {
                    "properties_count": len(profile.properties),
                    "preferences_count": len(profile.preferences),
                    "updated_at": profile.updated_at.isoformat(),
                    "properties": profile.properties,
                    "preferences": profile.preferences,
                },
                "events": {
                    "total_count": event_count,
                },
            }

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}

    def clear_all(self, session_id: Optional[str] = None) -> bool:
        """
        Clear all memory (profile and events).

        Args:
            session_id: If provided, only clear events for this session

        Returns:
            True if successful, False otherwise
        """
        try:
            if session_id:
                # Only clear events for session
                self.event_store.clear_events(session_id)
                logger.info(f"Cleared memory for session: {session_id}")
            else:
                # Clear everything
                self.profile_store.clear()
                self.event_store.clear_events()
                logger.info("Cleared all memory")

            return True

        except Exception as e:
            logger.error(f"Error clearing memory: {e}")
            return False


# ============================================================================
# Global singleton instance
# ============================================================================

_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """Get or create the global memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service


# ============================================================================
# Public API functions
# ============================================================================


def record_event(
    user_message: str,
    assistant_response: str,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Record a conversation event (convenience function).

    Args:
        user_message: The user's message
        assistant_response: The assistant's response
        session_id: Optional session identifier
        metadata: Optional additional metadata

    Returns:
        True if successful, False otherwise
    """
    service = get_memory_service()
    return service.record_event(user_message, assistant_response, session_id, metadata)


def get_context(
    query: str,
    max_events: int = 5,
    session_id: Optional[str] = None,
    use_semantic_search: bool = True,
) -> str:
    """
    Get enriched context for a query (convenience function).

    Args:
        query: The user's current query
        max_events: Maximum number of relevant events to include
        session_id: Optional session filter
        use_semantic_search: If True, use semantic search; if False, use recent events

    Returns:
        Formatted context string to inject into system prompt
    """
    service = get_memory_service()
    return service.get_context(query, max_events, session_id, use_semantic_search)
