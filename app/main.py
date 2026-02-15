"""
Main FastAPI application — unified startup for Qdrant + Neo4j services.
"""

import logging
import warnings
from contextlib import asynccontextmanager

# Suppress Pydantic serialization warnings from LiteLLM/ADK response objects
# (local Ollama models return fewer fields than the Pydantic models expect)
warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routes import ingest_router, search_router, admin_router, agent_router, files_router
from app.routes import health, reasoning
from app.services.neo4j import close_driver, init_driver
from app.services.storage import get_qdrant_manager

logger = logging.getLogger(__name__)


# ============================================================================
# Lifespan Management
# ============================================================================


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup / shutdown lifecycle hook."""

    # ── Startup ──────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.DEBUG if settings.app_debug else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    logger.info("=" * 80)
    logger.info("Starting AI-Minds Service")
    logger.info("=" * 80)

    # 1. Initialize Qdrant
    try:
        qdrant_manager = get_qdrant_manager()
        if not qdrant_manager.health_check():
            logger.error("Failed to connect to Qdrant at %s", settings.qdrant_url)
        else:
            logger.info("Connected to Qdrant at %s", settings.qdrant_url)
            try:
                qdrant_manager.create_collections()
                collections = qdrant_manager.list_collections()
                logger.info("Active collections: %s", ", ".join(collections))
                for coll in collections:
                    count = qdrant_manager.count_points(coll)
                    logger.info("  - %s: %d points", coll, count)
            except Exception as e:
                logger.warning("Qdrant collections init: %s", e)
    except Exception as e:
        logger.warning("Qdrant initialization failed: %s", e)

    # 2. Initialize Neo4j
    try:
        driver = init_driver()

        # Ensure Neo4j schema (constraints, indexes)
        from app.services.graph_schema import ensure_schema

        ensure_schema(driver)

        # Pre-warm entity resolver cache
        from app.services.entity_resolver import EntityResolver

        resolver = EntityResolver(driver)
        resolver.refresh_cache()

        logger.info("Neo4j initialized successfully")
    except Exception as e:
        logger.warning(
            "Neo4j initialization failed: %s. "
            "Knowledge graph features will be unavailable.",
            e,
        )

    logger.info("=" * 80)
    logger.info("Service ready! API docs at http://localhost:%d/docs", settings.api_port)
    logger.info("=" * 80)

    yield

    # ── Shutdown ─────────────────────────────────────────────────
    close_driver()
    logger.info("Application shutdown complete.")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="AI-Minds-Hackathon",
    description=(
        "Hybrid vector + knowledge graph service. "
        "Handles text, images, and audio with semantic search, "
        "graph reasoning, and intelligent agents."
    ),
    version="1.0.0",
    debug=settings.app_debug,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Exception Handlers
# ============================================================================


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "detail": str(exc),
        },
    )


# ============================================================================
# Routes
# ============================================================================

app.include_router(health.router)
app.include_router(admin_router)
app.include_router(ingest_router)
app.include_router(search_router)
app.include_router(agent_router)
app.include_router(files_router)
app.include_router(reasoning.router)


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "AI-Minds Service",
        "version": "1.0.0",
        "status": "running",
        "description": "Hybrid vector + knowledge graph service",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "reasoning": {
                "query": "/reasoning/query",
                "ingest": "/reasoning/ingest",
                "stats": "/reasoning/stats",
            },
            "ingest": {
                "text": "/ingest/text",
                "image": "/ingest/image",
                "audio": "/ingest/audio",
                "directory": "/ingest/directory",
            },
            "search": {
                "all": "/search",
                "by_collection": "/search/{collection}",
                "by_image": "/search/image",
                "by_source": "/search/filters/by-source",
                "by_entity": "/search/filters/by-entity",
            },
            "agent": {
                "chat": "/agent/chat",
                "agents": "/agent/agents",
                "sessions": "/agent/sessions",
            },
        },
        "configuration": {
            "qdrant_url": settings.qdrant_url,
            "collection": settings.unified_collection,
            "neo4j_uri": settings.neo4j_uri or "not configured",
        },
    }


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )
