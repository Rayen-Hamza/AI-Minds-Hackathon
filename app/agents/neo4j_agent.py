"""
Neo4j Agent - Specialized agent for knowledge graph operations.
Handles graph queries, entity resolution, relationship traversal,
and graph analytics using the Neo4j knowledge graph.
"""

import logging
from typing import Dict, Any

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from google.adk.models import LiteLlm

from ..config import settings
from ..services.neo4j import get_driver

logger = logging.getLogger(__name__)


# ============================================================================
# Neo4j Tools
# ============================================================================


def query_knowledge_graph(query: str) -> Dict[str, Any]:
    """
    Process a natural language query against the knowledge graph.
    Uses the full reasoning pipeline: decompose → resolve entities →
    route to Cypher templates → execute → build reasoning chain.

    Args:
        query: Natural language question about entities, relationships,
               topics, documents, people, or events in the knowledge graph.

    Returns:
        Dictionary containing the reasoning chain result and LLM-ready prompt.
    """
    try:
        from ..services.graph_reasoning import GraphReasoningOrchestrator

        logger.info(f"Querying knowledge graph: '{query}'")

        driver = get_driver()
        if driver is None:
            return {"success": False, "error": "Neo4j driver is not initialized"}

        orchestrator = GraphReasoningOrchestrator(driver)
        orchestrator.warm_up()
        result_prompt = orchestrator.process_query(query)

        return {
            "success": True,
            "query": query,
            "result": result_prompt,
        }

    except Exception as e:
        logger.error(f"Error querying knowledge graph: {e}")
        return {"success": False, "error": str(e), "query": query}


def lookup_entity(
    entity_name: str, entity_type: str = None
) -> Dict[str, Any]:
    """
    Look up an entity in the knowledge graph by name.
    Supports fuzzy matching and alias resolution.

    Args:
        entity_name: Name of the entity to search for (person, topic, concept, etc.)
        entity_type: Optional entity type to prefer (Person, Topic, Concept,
                     Organization, Project, Event, Location)

    Returns:
        Dictionary with resolved entity information and match quality.
    """
    try:
        from ..services.entity_resolver import EntityResolver

        logger.info(f"Looking up entity: '{entity_name}' (type={entity_type})")

        driver = get_driver()
        if driver is None:
            return {"success": False, "error": "Neo4j driver is not initialized"}

        resolver = EntityResolver(driver)
        resolver.refresh_cache()
        entity, quality = resolver.resolve_with_quality(
            entity_name, expected_label=entity_type
        )

        if entity is None:
            return {
                "success": True,
                "found": False,
                "entity_name": entity_name,
                "match_quality": quality.value,
                "message": f"No entity found matching '{entity_name}'",
            }

        return {
            "success": True,
            "found": True,
            "entity": entity,
            "match_quality": quality.value,
        }

    except Exception as e:
        logger.error(f"Error looking up entity: {e}")
        return {"success": False, "error": str(e), "entity_name": entity_name}


def get_entity_relationships(entity_name: str) -> Dict[str, Any]:
    """
    Get all relationships (incoming and outgoing) for an entity.
    Returns the full neighborhood of the entity in the knowledge graph.

    Args:
        entity_name: Name of the entity to explore

    Returns:
        Dictionary containing all connected nodes and relationship types.
    """
    try:
        from ..services.cypher_templates import CYPHER_TEMPLATES

        logger.info(f"Getting relationships for entity: '{entity_name}'")

        driver = get_driver()
        if driver is None:
            return {"success": False, "error": "Neo4j driver is not initialized"}

        template = CYPHER_TEMPLATES.get("full_neighborhood")
        if template is None:
            return {"success": False, "error": "full_neighborhood template not found"}

        cypher = template.render({"entity_name": entity_name})

        with driver.session() as session:
            result = session.run(cypher)
            records = [dict(record) for record in result]

        return {
            "success": True,
            "entity_name": entity_name,
            "relationship_count": len(records),
            "relationships": records,
        }

    except Exception as e:
        logger.error(f"Error getting entity relationships: {e}")
        return {"success": False, "error": str(e), "entity_name": entity_name}


def find_path_between(
    entity_a: str, entity_b: str, max_hops: int = 5
) -> Dict[str, Any]:
    """
    Find the shortest path between two entities in the knowledge graph.

    Args:
        entity_a: Name of the first entity
        entity_b: Name of the second entity
        max_hops: Maximum path length to search (default: 5)

    Returns:
        Dictionary containing path nodes, relationships, and path length.
    """
    try:
        from ..services.cypher_templates import CYPHER_TEMPLATES

        logger.info(f"Finding path between '{entity_a}' and '{entity_b}'")

        driver = get_driver()
        if driver is None:
            return {"success": False, "error": "Neo4j driver is not initialized"}

        template = CYPHER_TEMPLATES.get("shortest_path_entities")
        if template is None:
            return {"success": False, "error": "shortest_path_entities template not found"}

        cypher = template.render({
            "entity_a": entity_a,
            "entity_b": entity_b,
            "max_hops": max_hops,
        })

        with driver.session() as session:
            result = session.run(cypher)
            records = [dict(record) for record in result]

        if not records:
            return {
                "success": True,
                "found": False,
                "message": f"No path found between '{entity_a}' and '{entity_b}' within {max_hops} hops",
            }

        return {
            "success": True,
            "found": True,
            "entity_a": entity_a,
            "entity_b": entity_b,
            "paths": records,
        }

    except Exception as e:
        logger.error(f"Error finding path: {e}")
        return {"success": False, "error": str(e)}


def get_graph_stats() -> Dict[str, Any]:
    """
    Get statistics about the knowledge graph: node counts by type,
    relationship counts, and overall graph health.

    Returns:
        Dictionary containing graph statistics.
    """
    try:
        from ..services.cypher_templates import CYPHER_TEMPLATES

        logger.info("Getting knowledge graph statistics")

        driver = get_driver()
        if driver is None:
            return {"success": False, "error": "Neo4j driver is not initialized"}

        template = CYPHER_TEMPLATES.get("content_stats")
        if template is None:
            return {"success": False, "error": "content_stats template not found"}

        cypher = template.render({})

        with driver.session() as session:
            # Node counts by type
            result = session.run(cypher)
            node_counts = {record["type"]: record["cnt"] for record in result}

            # Total relationship count
            rel_result = session.run(
                "MATCH ()-[r]->() RETURN count(r) AS total_relationships"
            )
            rel_count = rel_result.single()
            total_relationships = rel_count["total_relationships"] if rel_count else 0

        return {
            "success": True,
            "node_counts": node_counts,
            "total_relationships": total_relationships,
            "neo4j_uri": settings.neo4j_uri,
        }

    except Exception as e:
        logger.error(f"Error getting graph stats: {e}")
        return {"success": False, "error": str(e)}


def get_documents_by_topic(topic_name: str, limit: int = 10) -> Dict[str, Any]:
    """
    Find documents related to a specific topic in the knowledge graph.

    Args:
        topic_name: Name of the topic to search for
        limit: Maximum number of documents to return (default: 10)

    Returns:
        Dictionary containing matching documents with metadata.
    """
    try:
        from ..services.cypher_templates import CYPHER_TEMPLATES

        logger.info(f"Getting documents for topic: '{topic_name}'")

        driver = get_driver()
        if driver is None:
            return {"success": False, "error": "Neo4j driver is not initialized"}

        template = CYPHER_TEMPLATES.get("documents_about_topic")
        if template is None:
            return {"success": False, "error": "documents_about_topic template not found"}

        cypher = template.render({"topic_name": topic_name, "limit": limit})

        with driver.session() as session:
            result = session.run(cypher)
            records = [dict(record) for record in result]

        return {
            "success": True,
            "topic": topic_name,
            "document_count": len(records),
            "documents": records,
        }

    except Exception as e:
        logger.error(f"Error getting documents by topic: {e}")
        return {"success": False, "error": str(e), "topic": topic_name}


def get_topic_clusters() -> Dict[str, Any]:
    """
    Discover topic clusters in the knowledge graph using co-occurrence analysis.
    Returns groups of topics that are strongly connected.

    Returns:
        Dictionary containing topic clusters with hub topics and members.
    """
    try:
        from ..services.cypher_templates import CYPHER_TEMPLATES

        logger.info("Detecting topic clusters")

        driver = get_driver()
        if driver is None:
            return {"success": False, "error": "Neo4j driver is not initialized"}

        template = CYPHER_TEMPLATES.get("community_detection")
        if template is None:
            return {"success": False, "error": "community_detection template not found"}

        cypher = template.render({})

        with driver.session() as session:
            result = session.run(cypher)
            records = [dict(record) for record in result]

        return {
            "success": True,
            "cluster_count": len(records),
            "clusters": records,
        }

    except Exception as e:
        logger.error(f"Error detecting topic clusters: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# Neo4j Agent Definition
# ============================================================================

neo4j_agent = Agent(
    name="neo4j_agent",
    model=LiteLlm(
        model=f"openai/{settings.llm_model}",
        api_base=settings.llm_base_url,
        api_key="dummy",
    ),
    description="""You are a Neo4j knowledge graph specialist.
    You help users query, explore, and analyze the knowledge graph containing
    entities (people, topics, concepts, organizations, projects, events, locations),
    documents, and their relationships.

    Key capabilities:
    - Natural language queries against the knowledge graph
    - Entity lookup with fuzzy matching and alias resolution
    - Relationship exploration and graph traversal
    - Path finding between entities
    - Topic-based document retrieval
    - Graph statistics and analytics
    - Topic cluster discovery

    When users ask about entities, relationships, connections, or want to explore
    the knowledge graph, use the appropriate tools to find answers.""",
    instruction="""You are an expert in knowledge graphs, entity resolution, and graph analytics.

    When handling queries:
    1. For natural language questions about the knowledge graph, use query_knowledge_graph
       which runs the full reasoning pipeline (decomposition → entity resolution →
       Cypher execution → reasoning chain)
    2. For specific entity lookups, use lookup_entity with optional type hints
    3. For exploring an entity's connections, use get_entity_relationships
    4. For finding how two entities are connected, use find_path_between
    5. For finding documents about a topic, use get_documents_by_topic
    6. For graph overview and statistics, use get_graph_stats
    7. For discovering topic clusters, use get_topic_clusters

    Guidelines:
    - Present graph results in a clear, structured format
    - Explain entity relationships and paths in plain language
    - When an entity is not found, suggest possible alternatives
    - Use match quality information to communicate confidence
    - For complex questions, prefer query_knowledge_graph as it handles the full pipeline

    You only have access to the tools provided. Do not attempt to access
    external resources or databases directly.""",
    tools=[
        FunctionTool(func=query_knowledge_graph),
        FunctionTool(func=lookup_entity),
        FunctionTool(func=get_entity_relationships),
        FunctionTool(func=find_path_between),
        FunctionTool(func=get_graph_stats),
        FunctionTool(func=get_documents_by_topic),
        FunctionTool(func=get_topic_clusters),
    ],
)
