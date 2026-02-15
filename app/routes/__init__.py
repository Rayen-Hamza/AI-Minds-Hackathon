"""API routes."""

from .ingest_routes import router as ingest_router
from .search_routes import router as search_router
from .admin_routes import router as admin_router
from .agent_routes import router as agent_router

__all__ = ["ingest_router", "search_router", "admin_router", "agent_router"]
