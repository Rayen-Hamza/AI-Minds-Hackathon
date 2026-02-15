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
from .neo4j_agent import neo4j_agent
from .prompt_chain import chain_agent, run_prompt_chain
from ..config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# Orchestrator Tools
# ============================================================================


def answer_with_reasoning(user_query: str) -> Dict[str, Any]:
    """
    Answer a question using the full prompt chaining pipeline.
    
    This tool:
    1. Enriches the query with ontological reasoning from Neo4j
    2. Searches Qdrant for relevant RAG context
    3. Builds a context-limited prompt for the small LLM
    4. Returns the final answer
    
    Use this for complex questions that benefit from knowledge graph reasoning
    combined with semantic search.
    
    Args:
        user_query: The user's question
        
    Returns:
        Dictionary with the reasoned answer and metadata
    """
    try:
        logger.info(f"Running prompt chain for: {user_query[:50]}...")
        
        # Execute the full prompt chaining pipeline
        result = run_prompt_chain(user_query)
        
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error", "Unknown error in prompt chain"),
                "query": user_query,
            }
        
        return {
            "success": True,
            "query": user_query,
            "prompt": result.get("final_prompt", ""),
            "token_estimate": result.get("token_estimate", 0),
            "has_graph_reasoning": result.get("has_reasoning", False),
            "has_rag_context": result.get("has_rag", False),
            "confidence": result.get("confidence", 0.0),
            "entities_found": result.get("entities_found", []),
            "rag_results_count": result.get("rag_results_count", 0),
            "source_files": result.get("source_files", []),
        }
        
    except Exception as e:
        logger.error(f"Error in answer_with_reasoning: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": user_query,
            "source_files": [],
        }


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
                    {
                        "name": "Neo4j Agent",
                        "role": "Knowledge graph specialist for entity resolution, relationship traversal, and graph analytics",
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

        # Ingestion keywords — delegate to neo4j_agent
        ingest_keywords = [
            "ingest",
            "injest",
            "import",
            "add to graph",
            "add document",
            "load file",
            "load document",
            "index file",
            "index document",
            "store in graph",
            "populate graph",
        ]
        if any(keyword in query_lower for keyword in ingest_keywords):
            intent = "ingestion"
            recommended_agent = "neo4j_agent"

        # Knowledge graph keywords
        graph_keywords = [
            "graph",
            "entity",
            "relationship",
            "connected",
            "path between",
            "knowledge graph",
            "neo4j",
            "topic cluster",
            "who knows",
            "related to",
            "linked to",
        ]
        if any(keyword in query_lower for keyword in graph_keywords):
            intent = "graph_query"
            recommended_agent = "neo4j_agent"

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
    model=LiteLlm(
        model=f"openai/{settings.llm_model}",
        api_base=settings.llm_base_url,
        api_key="dummy",
    ),
    description="Orchestrator agent with memory-enhanced conversation capabilities. Routes to specialized agents and maintains user context.",
    instruction="""You are a memory-aware orchestrator agent. You have access to user profile information and past conversation history.

Memory Context:
- User profile and preferences are automatically injected at the start of conversations
- Past relevant conversations are provided for context
- Use this information naturally without explicitly mentioning "I remember" unless directly relevant
- Respect user preferences (e.g., communication style, interests)

Routing Strategy:
- Search/find content → delegate to qdrant_agent
- Entity, person, event, graph questions → delegate to neo4j_agent
- System status → use get_system_status
- Help/capabilities/capabilities → use get_capabilities

Be conversational, helpful, and leverage memory context to provide personalized responses.
- Request analysis → use analyze_request

Always prefer answer_with_reasoning for natural language questions.""",
    tools=[
        FunctionTool(func=answer_with_reasoning),
        FunctionTool(func=get_system_status),
        FunctionTool(func=get_capabilities),
        FunctionTool(func=analyze_request),
        AgentTool(agent=qdrant_agent),
        AgentTool(agent=neo4j_agent),
        AgentTool(agent=chain_agent),
    ],
)
