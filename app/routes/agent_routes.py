"""
FastAPI routes for ADK agent interactions.
Provides endpoints to interact with the orchestrator and specialized agents.
"""

import logging
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part

from ..agents import root_agent, qdrant_agent, neo4j_agent, run_prompt_chain
from ..memory import record_event, get_context

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agents"])

# Constants for session management
APP_NAME = "multimodal_rag_app"
DEFAULT_USER_ID = "default_user"

# Initialize session service (in-memory for now)
session_service = InMemorySessionService()

# Initialize runners for each agent
orchestrator_runner = Runner(
    agent=root_agent, app_name=APP_NAME, session_service=session_service
)

qdrant_runner = Runner(
    agent=qdrant_agent, app_name=APP_NAME, session_service=session_service
)

neo4j_runner = Runner(
    agent=neo4j_agent, app_name=APP_NAME, session_service=session_service
)

# Store active sessions metadata
active_sessions = {}


# ============================================================================
# Request/Response Models
# ============================================================================


class AgentRequest(BaseModel):
    """Request to send a message to an agent."""

    message: str
    session_id: Optional[str] = None
    agent: Optional[str] = "orchestrator"  # "orchestrator", "qdrant", or "neo4j"


class AgentResponse(BaseModel):
    """Response from an agent."""

    response: str
    session_id: str
    agent: str
    success: bool
    error: Optional[str] = None
    # New fields for prompt chain metadata
    source_files: list[str] = []
    confidence: Optional[float] = None
    has_graph_reasoning: bool = False
    has_rag_context: bool = False
    entities_found: list[str] = []


class SessionInfo(BaseModel):
    """Information about an agent session."""

    session_id: str
    agent_name: str
    message_count: int


# ============================================================================
# Agent Routes
# ============================================================================


@router.post("/chat", response_model=AgentResponse)
async def chat_with_agent(request: AgentRequest):
    """
    Send a message to an agent and get a response with memory-enriched context.

    Args:
        request: Agent request with message, optional session_id, and agent type

    Returns:
        Agent response with the reply text
    """
    try:
        # Select agent and runner
        if request.agent == "qdrant":
            agent = qdrant_agent
            runner = qdrant_runner
        elif request.agent == "neo4j":
            agent = neo4j_agent
            runner = neo4j_runner
        else:
            agent = root_agent
            runner = orchestrator_runner

        # Get or create session
        session_id = request.session_id or str(uuid4())

        if session_id not in active_sessions:
            logger.info(f"Creating new session: {session_id}")
            session = await session_service.create_session(
                app_name=APP_NAME, user_id=DEFAULT_USER_ID, session_id=session_id
            )
            active_sessions[session_id] = {"agent": agent.name, "message_count": 0}

        # MEMORY ENRICHMENT: Get context before processing
        memory_context = get_context(
            query=request.message,
            max_events=5,
            session_id=session_id,
            use_semantic_search=True
        )

        # If we have memory context, prepend it to the message
        enriched_message = request.message
        if memory_context:
            logger.info(f"Enriching message with memory context (session: {session_id})")
            # Inject memory context as a system-level instruction
            enriched_message = f"{memory_context}\n\nUser query: {request.message}"

        # Create user message with enriched context
        user_message = Content(role="user", parts=[Part(text=enriched_message)])

        # Run agent and collect response
        response_text = ""

        logger.info(f"Processing message for session {session_id}: {request.message}")

        for event in runner.run(
            user_id=DEFAULT_USER_ID, session_id=session_id, new_message=user_message
        ):
            # Extract text from response
            if hasattr(event, "content") and event.content:
                if hasattr(event.content, "parts") and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            response_text += part.text

        # Update message count
        active_sessions[session_id]["message_count"] += 1

        if not response_text:
            response_text = (
                "I processed your request, but didn't generate a text response."
            )

        # MEMORY RECORDING: Record the conversation turn after response
        try:
            record_event(
                user_message=request.message,
                assistant_response=response_text,
                session_id=session_id,
                metadata={"agent": agent.name}
            )
            logger.debug(f"Recorded conversation event for session {session_id}")
        except Exception as mem_err:
            logger.warning(f"Failed to record memory event: {mem_err}")
            # Don't fail the request if memory recording fails

        # Try to extract metadata from prompt chain if available
        source_files = []
        confidence = None
        has_graph_reasoning = False
        has_rag_context = False
        entities_found = []

        # Run prompt chain to get metadata (this enriches the response)
        try:
            chain_result = run_prompt_chain(request.message)
            if chain_result.get("success"):
                source_files = chain_result.get("source_files", [])
                confidence = chain_result.get("confidence")
                has_graph_reasoning = chain_result.get("has_reasoning", False)
                has_rag_context = chain_result.get("has_rag", False)
                entities_found = chain_result.get("entities_found", [])
        except Exception as chain_error:
            logger.debug(f"Prompt chain metadata extraction failed: {chain_error}")

        return AgentResponse(
            response=response_text,
            session_id=session_id,
            agent=agent.name,
            success=True,
            source_files=source_files,
            confidence=confidence,
            has_graph_reasoning=has_graph_reasoning,
            has_rag_context=has_rag_context,
            entities_found=entities_found,
        )

    except Exception as e:
        logger.error(f"Error in chat_with_agent: {e}", exc_info=True)
        return AgentResponse(
            response="",
            session_id=request.session_id or "unknown",
            agent=request.agent,
            success=False,
            error=str(e),
        )


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions():
    """
    List all active agent sessions.

    Returns:
        List of session information
    """
    try:
        sessions = []
        for session_id, data in active_sessions.items():
            sessions.append(
                SessionInfo(
                    session_id=session_id,
                    agent_name=data["agent"],
                    message_count=data["message_count"],
                )
            )

        return sessions

    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete an agent session.

    Args:
        session_id: ID of the session to delete

    Returns:
        Success message
    """
    try:
        if session_id in active_sessions:
            del active_sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return {"success": True, "message": f"Session {session_id} deleted"}
        else:
            raise HTTPException(
                status_code=404, detail=f"Session {session_id} not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents")
async def list_agents():
    """
    List available agents.

    Returns:
        Dictionary of available agents with their descriptions
    """
    return {
        "agents": [
            {
                "name": "orchestrator",
                "agent_name": root_agent.name,
                "description": "Main orchestrator agent that coordinates tasks and delegates to specialized agents",
                "capabilities": [
                    "Task routing and delegation",
                    "System status and information",
                    "Conversation management",
                    "Multi-agent coordination",
                ],
            },
            {
                "name": "qdrant",
                "agent_name": qdrant_agent.name,
                "description": "Specialized agent for vector database operations and semantic search",
                "capabilities": [
                    "Semantic search across all content types",
                    "Vector database management",
                    "Collection information",
                    "Metadata filtering",
                ],
            },
            {
                "name": "neo4j",
                "agent_name": neo4j_agent.name,
                "description": "Specialized agent for knowledge graph queries and graph analytics",
                "capabilities": [
                    "Natural language graph queries",
                    "Entity lookup with fuzzy matching",
                    "Relationship exploration and path finding",
                    "Graph statistics and topic cluster discovery",
                ],
            },
        ]
    }


# ============================================================================
# Memory Management Routes
# ============================================================================


@router.get("/memory/stats")
async def get_memory_stats():
    """
    Get memory system statistics including profile and event counts.

    Returns:
        Dictionary with memory statistics
    """
    try:
        from ..memory import MemoryService

        service = MemoryService()
        stats = service.get_stats()

        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/profile")
async def get_user_profile():
    """
    Get the current user profile.

    Returns:
        User profile with properties and preferences
    """
    try:
        from ..memory.profile_store import ProfileStore

        store = ProfileStore()
        profile = store.load()

        return {
            "success": True,
            "profile": {
                "properties": profile.properties,
                "preferences": profile.preferences,
                "updated_at": profile.updated_at.isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memory/clear")
async def clear_memory(session_id: Optional[str] = None):
    """
    Clear memory (profile and/or events).

    Args:
        session_id: Optional - if provided, only clear events for this session

    Returns:
        Success message
    """
    try:
        from ..memory import MemoryService

        service = MemoryService()
        success = service.clear_all(session_id)

        if success:
            message = f"Memory cleared for session {session_id}" if session_id else "All memory cleared"
            return {
                "success": True,
                "message": message
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to clear memory")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing memory: {e}")
        raise HTTPException(status_code=500, detail=str(e))
