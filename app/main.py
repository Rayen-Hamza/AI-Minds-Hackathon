"""
Main FastAPI application for Qdrant Memory Service.
Standalone vector store for grounded memory system handling images, text, and audio.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.storage import get_qdrant_manager
from app.routes import ingest_router, search_router, admin_router

logger = logging.getLogger(__name__)


# ============================================================================
# Lifespan Management
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info("=" * 80)
    logger.info("Starting Qdrant Memory Service")
    logger.info("=" * 80)

    try:
        # Initialize Qdrant manager and check connection
        qdrant_manager = get_qdrant_manager()

        # Test connection
        if not qdrant_manager.health_check():
            logger.error("Failed to connect to Qdrant!")
            logger.error(f"Ensure Qdrant is running at {settings.qdrant_url}")
            logger.error("Run: docker-compose up -d")
        else:
            logger.info(f"✓ Connected to Qdrant at {settings.qdrant_url}")

            # Create collections if they don't exist
            try:
                qdrant_manager.create_collections()
                logger.info("✓ Collections initialized")

                # Log collection info
                collections = qdrant_manager.list_collections()
                logger.info(f"✓ Active collections: {', '.join(collections)}")

                for coll in collections:
                    count = qdrant_manager.count_points(coll)
                    logger.info(f"  - {coll}: {count} points")

            except Exception as e:
                logger.warning(f"Collections already exist or error: {e}")

        logger.info(f"✓ API server starting on {settings.api_host}:{settings.api_port}")
        logger.info("=" * 80)
        logger.info("Service ready! API docs at http://localhost:8000/docs")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Qdrant Memory Service...")
    logger.info("Goodbye! 👋")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Qdrant Memory Service",
    description=(
        "Standalone vector store service for grounded memory system. "
        "Handles text, images, and audio with semantic search, "
        "differential updates, and hybrid retrieval."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ============================================================================
# CORS Middleware
# ============================================================================
from app.routes import health, reasoning
from app.services.neo4j import close_driver, init_driver

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    # ── Startup ──────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.DEBUG if settings.app_debug else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    driver = init_driver()

    # Ensure Neo4j schema (constraints, indexes)
    from app.services.graph_schema import ensure_schema

    ensure_schema(driver)

    # Pre-warm entity resolver cache
    from app.services.entity_resolver import EntityResolver

    resolver = EntityResolver(driver)
    resolver.refresh_cache()

    logger.info("Application startup complete.")

    yield

    # ── Shutdown ─────────────────────────────────────────────────
    close_driver()
    logger.info("Application shutdown complete.")


app = FastAPI(
    title="AI-Minds-Hackathon",
    debug=settings.app_debug,
    lifespan=lifespan,
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
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
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

# Include route modules
app.include_router(admin_router)
app.include_router(ingest_router)
app.include_router(search_router)


@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Qdrant Memory Service",
        "version": "1.0.0",
        "status": "running",
        "description": "Standalone vector store for grounded memory system",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "collections": "/collections",
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
        },
        "configuration": {
            "qdrant_url": settings.qdrant_url,
            "collection": settings.unified_collection,
            "architecture": "unified collection with named vectors and metadata filtering",
            "embedding_models": {
                "text": settings.text_embedding_model,
                "image": settings.image_embedding_model,
                "text_to_image": settings.text_to_image_model,
                "speech": settings.speech_model,
            },
        },
    }


# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )
app.include_router(reasoning.router)
