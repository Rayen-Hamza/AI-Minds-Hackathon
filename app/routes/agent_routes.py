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

from ..agents import root_agent, qdrant_agent

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

# Store active sessions metadata
active_sessions = {}


# ============================================================================
# Request/Response Models
# ============================================================================


class AgentRequest(BaseModel):
    """Request to send a message to an agent."""

    message: str
    session_id: Optional[str] = None
    agent: Optional[str] = "orchestrator"  # "orchestrator" or "qdrant"


class AgentResponse(BaseModel):
    """Response from an agent."""

    response: str
    session_id: str
    agent: str
    success: bool
    error: Optional[str] = None


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
    Send a message to an agent and get a response.

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

        # Create user message
        user_message = Content(role="user", parts=[Part(text=request.message)])

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

        return AgentResponse(
            response=response_text,
            session_id=session_id,
            agent=agent.name,
            success=True,
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
        ]
    }
