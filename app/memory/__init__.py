"""
Memory layer for the AI assistant.
Provides profile extraction, event storage, and context enrichment.
"""

from .memory_service import record_event, get_context, MemoryService

__all__ = ["record_event", "get_context", "MemoryService"]
