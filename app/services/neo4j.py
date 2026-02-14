from neo4j import GraphDatabase

from app.config import settings


def get_neo4j_driver():
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )
