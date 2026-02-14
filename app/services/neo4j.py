"""Neo4j driver singleton — create once, reuse everywhere."""

from __future__ import annotations

import logging

from neo4j import Driver, GraphDatabase

from app.config import settings

logger = logging.getLogger(__name__)

_driver: Driver | None = None


def init_driver() -> Driver:
    """Create the global Neo4j driver (called at startup)."""
    global _driver  # noqa: PLW0603
    _driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
    _driver.verify_connectivity()
    logger.info("Neo4j driver connected to %s", settings.neo4j_uri)
    return _driver


def get_driver() -> Driver | None:
    """Return the current Neo4j driver (or ``None`` before init)."""
    return _driver


def close_driver() -> None:
    """Close the global Neo4j driver (called at shutdown)."""
    global _driver  # noqa: PLW0603
    if _driver is not None:
        _driver.close()
        logger.info("Neo4j driver closed.")
        _driver = None
