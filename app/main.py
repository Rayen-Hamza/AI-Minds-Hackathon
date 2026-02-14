import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
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

app.include_router(health.router)
app.include_router(reasoning.router)
