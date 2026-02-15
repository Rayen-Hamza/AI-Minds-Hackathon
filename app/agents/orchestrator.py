"""
Orchestrator Agent - Main agent that coordinates tasks and delegates to specialized agents.
Routes user requests to appropriate agents and manages the conversation flow.
"""

import logging
from typing import Dict, Any
from google.adk.agents import Agent
from google.adk.tools import FunctionTool, AgentTool
from google.adk.models import LiteLlm

from .qdrant_agent import qdrant_agent
from ..config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Orchestrator Tools
# ============================================================================


def get_system_status() -> Dict[str, Any]:
    """
    Get the overall status of the multimodal RAG system.

    Returns:
        Dictionary containing system status information
    """
    try:
        logger.info("Getting system status")

        from ..services.storage import get_qdrant_manager

        qdrant_manager = get_qdrant_manager()

        # Check Qdrant connection
        try:
            collections = qdrant_manager.client.get_collections()
            qdrant_status = "connected"
            collection_count = len(collections.collections)
        except Exception as e:
            qdrant_status = f"error: {str(e)}"
            collection_count = 0

        # Check if unified collection exists
        unified_exists = qdrant_manager.client.collection_exists(
            settings.unified_collection
        )

        # Get point count if collection exists
        point_count = 0
        if unified_exists:
            try:
                info = qdrant_manager.client.get_collection(settings.unified_collection)
                point_count = info.points_count
            except Exception:
                pass

        return {
            "success": True,
            "status": "operational",
            "qdrant": {
                "status": qdrant_status,
                "host": settings.qdrant_host,
                "port": settings.qdrant_port,
                "collections_count": collection_count,
                "unified_collection_exists": unified_exists,
                "total_vectors": point_count,
            },
            "configuration": {
                "text_embedding_model": settings.text_embedding_model,
                "image_captioning_model": settings.image_captioning_model,
                "speech_model": settings.speech_model,
                "embedding_dimension": settings.text_embedding_dim,
            },
        }

    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {"success": False, "status": "error", "error": str(e)}


def get_capabilities() -> Dict[str, Any]:
    """
    Get information about the system's capabilities.

    Returns:
        Dictionary describing what the system can do
    """
    return {
        "success": True,
        "capabilities": {
            "search": {
                "description": "Semantic search across all content types",
                "content_types": ["text", "image", "audio"],
                "features": [
                    "Unified text-centric embedding space",
                    "Cross-modal search",
                    "Filter by content type, tags, and source",
                    "Relevance scoring",
                ],
            },
            "ingestion": {
                "description": "Process and store multimodal content",
                "supported_formats": {
                    "text": ["txt", "md", "pdf"],
                    "images": ["png", "jpg", "jpeg"],
                    "audio": ["wav", "mp3"],
                },
                "features": [
                    "Automatic text extraction",
                    "Image captioning with BLIP",
                    "Speech-to-text with Whisper",
                    "Content chunking and deduplication",
                ],
            },
            "agents": {
                "description": "Specialized AI agents for different tasks",
                "available_agents": [
                    {
                        "name": "Orchestrator Agent",
                        "role": "Main coordinator and conversation manager",
                    },
                    {
                        "name": "Qdrant Agent",
                        "role": "Vector database specialist for search and retrieval",
                    },
                ],
            },
            "database": {
                "description": "Vector database and knowledge graph",
                "technologies": ["Qdrant", "Neo4j"],
                "features": [
                    "Efficient similarity search",
                    "Metadata filtering",
                    "Entity relationship tracking",
                ],
            },
        },
    }


def analyze_request(user_query: str) -> Dict[str, Any]:
    """
    Analyze a user request and determine the best way to handle it.

    Args:
        user_query: The user's question or request

    Returns:
        Dictionary with analysis results and recommendations
    """
    try:
        logger.info(f"Analyzing request: {user_query}")

        query_lower = user_query.lower()

        # Determine intent
        intent = "unknown"
        recommended_agent = "orchestrator"

        # Search-related keywords
        search_keywords = [
            "search",
            "find",
            "look for",
            "show me",
            "get",
            "retrieve",
            "what is",
            "tell me about",
        ]
        if any(keyword in query_lower for keyword in search_keywords):
            intent = "search"
            recommended_agent = "qdrant_agent"

        # Status/info keywords
        status_keywords = [
            "status",
            "health",
            "info",
            "information",
            "statistics",
            "stats",
            "how many",
        ]
        if any(keyword in query_lower for keyword in status_keywords):
            intent = "information"
            recommended_agent = "orchestrator"

        # Database management keywords
        db_keywords = ["collection", "database", "vectors", "embeddings"]
        if any(keyword in query_lower for keyword in db_keywords):
            intent = "database_management"
            recommended_agent = "qdrant_agent"

        # Help/capability keywords
        help_keywords = ["help", "can you", "what can", "capabilities", "features"]
        if any(keyword in query_lower for keyword in help_keywords):
            intent = "help"
            recommended_agent = "orchestrator"

        return {
            "success": True,
            "query": user_query,
            "intent": intent,
            "recommended_agent": recommended_agent,
            "confidence": "high" if intent != "unknown" else "low",
        }

    except Exception as e:
        logger.error(f"Error analyzing request: {e}")
        return {"success": False, "error": str(e), "query": user_query}


# ============================================================================
# Orchestrator Agent Definition
# ============================================================================

root_agent = Agent(
    name="orchestrator",
    model=LiteLlm(model=f"openai/{settings.llm_model}", api_base=settings.llm_base_url, api_key="dummy"),
    description="""You are the main orchestrator agent for a multimodal RAG (Retrieval-Augmented Generation) system.
    You coordinate tasks, manage conversations, and delegate to specialized agents when needed.
    
    You work with a team of specialized agents:
    - Qdrant Agent: Expert in vector database operations and semantic search
    
    Your responsibilities:
    1. Understand user requests and route them appropriately
    2. Provide system information and status updates
    3. Explain system capabilities
    4. Coordinate between different agents for complex tasks
    5. Maintain conversation context and provide helpful responses
    
    The system handles multimodal content (text, images, audio) using a unified text-centric embedding approach.""",
    instruction="""You are a helpful, professional orchestrator agent.
    
    When users ask questions:
    1. Determine if it's a search/retrieval task → delegate to qdrant_agent
    2. For system status/info → use get_system_status
    3. For capabilities/help → use get_capabilities
    4. For general conversation → respond directly with helpful information
    
    Guidelines:
    - Be friendly and professional
    - Explain what you're doing when delegating to other agents
    - Provide context about the system when relevant
    - If you're unsure, use analyze_request to help determine the best approach
    - Always aim to be helpful and provide complete answers
    You only have access to the tools provided. Do not attempt to access external resources or databases directly.
    When delegating to the qdrant_agent:
    - Clearly pass the search query
    - Let the qdrant_agent handle the technical details
    - Summarize results in a user-friendly way if needed
    
    You have access to system information and can coordinate with specialized agents.""",
    tools=[
        FunctionTool(func=get_system_status),
        FunctionTool(func=get_capabilities),
        FunctionTool(func=analyze_request),
        AgentTool(agent=qdrant_agent),
    ],
)
