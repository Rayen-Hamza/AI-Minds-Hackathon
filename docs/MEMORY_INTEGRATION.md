# Memory Integration Guide

## Overview

The memory layer has been successfully integrated into the chatbot to provide **profile-aware** and **history-aware** conversations.

## What Was Implemented

### 1. Memory Module Structure

Created `app/memory/` with the following components:

- **models.py** - Data models for Events and Profile
- **profile_store.py** - JSON-based profile persistence
- **event_store.py** - Qdrant-based conversation event storage
- **prompts.py** - Extraction and context packing templates
- **memory_service.py** - Main service with `record_event()` and `get_context()` functions

### 2. Integration Points

#### A. Chat Endpoint (`app/routes/agent_routes.py`)

**Before Response Generation:**
```python
# Get enriched context from memory
memory_context = get_context(
    query=request.message,
    max_events=5,
    session_id=session_id,
    use_semantic_search=True
)

# Inject into message
enriched_message = f"{memory_context}\n\nUser query: {request.message}"
```

**After Response Generation:**
```python
# Record the conversation turn
record_event(
    user_message=request.message,
    assistant_response=response_text,
    session_id=session_id,
    metadata={"agent": agent.name}
)
```

#### B. Orchestrator Agent (`app/agents/orchestrator.py`)

Updated instruction to be memory-aware:
- Explains that profile and conversation history are available
- Instructs to use information naturally
- Emphasizes respecting user preferences

### 3. Memory Management Endpoints

Added three new endpoints:

1. **GET /agent/memory/stats**
   - Returns profile statistics and event counts
   - Shows current properties and preferences

2. **GET /agent/memory/profile**
   - Returns the full user profile
   - Includes properties, preferences, and last update time

3. **DELETE /agent/memory/clear?session_id={id}**
   - Clears all memory or session-specific memory
   - Useful for testing and privacy

## How It Works

### Flow Diagram

```
User Message
     ↓
┌─────────────────────────┐
│  get_context()          │
│  - Load profile         │
│  - Search relevant      │
│    events (semantic)    │
│  - Pack into string     │
└─────────────────────────┘
     ↓
Memory Context (injected)
     ↓
┌─────────────────────────┐
│  LLM Generates Response │
│  (with memory context)  │
└─────────────────────────┘
     ↓
Assistant Response
     ↓
┌─────────────────────────┐
│  record_event()         │
│  - Store event in       │
│    Qdrant (embedded)    │
│  - Extract profile      │
│    from conversation    │
│  - Update profile JSON  │
└─────────────────────────┘
```

### Profile Extraction

Uses LLM with specialized prompt to extract:
- **Properties**: Factual attributes (name, role, location, expertise_level)
- **Preferences**: Likes, dislikes, communication style, interests

Example extraction:
```
User: "Hi, I'm Alex. I'm a Python developer and I prefer short answers."

Extracted:
{
  "properties": {
    "name": "Alex",
    "role": "Python developer"
  },
  "preferences": {
    "communication_style": "concise"
  }
}
```

### Context Packing

Formats memory into a structured prompt injection:

```markdown
---
# Memory
Unless the user has relevant queries, do not actively mention these memories.

## User Profile:
**Properties:**
  - name: Alex
  - role: Python developer

**Preferences:**
  - communication_style: concise
  - interests: machine learning, NLP

## Relevant Past Context:
- [2026-02-15 10:23] User: I'm working on AI projects...
- [2026-02-15 10:25] User: I prefer concise answers...
---

User query: What can you help me with?
```

## Data Storage

### Profile: `data/user_profile.json`
```json
{
  "properties": {
    "name": "Alex",
    "role": "Python developer",
    "expertise_level": "intermediate"
  },
  "preferences": {
    "communication_style": "concise",
    "interests": ["machine learning", "NLP"]
  },
  "updated_at": "2026-02-15T10:30:00.123456"
}
```

### Events: Qdrant Collection `conversation_events`
- **Collection Name**: `conversation_events`
- **Vector Size**: 384 (from all-MiniLM-L6-v2)
- **Distance Metric**: Cosine similarity
- **Payload**:
  - `text`: Formatted conversation turn
  - `timestamp`: ISO format timestamp
  - `session_id`: Session identifier
  - `metadata`: Additional metadata (e.g., agent name)

## API Usage Examples

### 1. Chat with Memory

**Request:**
```bash
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hi, I am Alex and I work as a Python developer",
    "session_id": "user_123",
    "agent": "orchestrator"
  }'
```

**Response:**
```json
{
  "response": "Hello Alex! Nice to meet you...",
  "session_id": "user_123",
  "agent": "orchestrator",
  "success": true
}
```

### 2. View Memory Stats

**Request:**
```bash
curl http://localhost:8000/agent/memory/stats
```

**Response:**
```json
{
  "success": true,
  "stats": {
    "profile": {
      "properties_count": 2,
      "preferences_count": 1,
      "updated_at": "2026-02-15T10:30:00",
      "properties": {
        "name": "Alex",
        "role": "Python developer"
      },
      "preferences": {
        "communication_style": "concise"
      }
    },
    "events": {
      "total_count": 5
    }
  }
}
```

### 3. View Profile

**Request:**
```bash
curl http://localhost:8000/agent/memory/profile
```

**Response:**
```json
{
  "success": true,
  "profile": {
    "properties": {
      "name": "Alex",
      "role": "Python developer"
    },
    "preferences": {
      "communication_style": "concise",
      "interests": ["machine learning", "NLP"]
    },
    "updated_at": "2026-02-15T10:30:00"
  }
}
```

### 4. Clear Memory

**Clear all memory:**
```bash
curl -X DELETE http://localhost:8000/agent/memory/clear
```

**Clear session-specific events:**
```bash
curl -X DELETE http://localhost:8000/agent/memory/clear?session_id=user_123
```

## Configuration

Memory system uses settings from `app/config.py`:

```python
# Embedding model for events
text_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
text_embedding_dim: int = 384

# Qdrant connection
qdrant_host: str = "localhost"
qdrant_port: int = 6333

# LLM for profile extraction
llm_base_url: str = "http://localhost:11434/v1"  # Ollama
llm_model: str = "qwen2.5:3b"
```

## Testing the Integration

### Start the Services

1. **Start Qdrant:**
   ```bash
   docker-compose up -d qdrant
   ```

2. **Start the API:**
   ```bash
   uvicorn app.main:app --reload
   ```

### Test Conversation Flow

```bash
# First message - introduce yourself
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hi! I am Sarah, a data scientist interested in NLP",
    "session_id": "test_001"
  }'

# Check what was extracted
curl http://localhost:8000/agent/memory/profile

# Second message - express preferences
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I prefer detailed technical explanations",
    "session_id": "test_001"
  }'

# Check updated profile
curl http://localhost:8000/agent/memory/profile

# Third message - ask a question (should use context)
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are your capabilities?",
    "session_id": "test_001"
  }'

# View stats
curl http://localhost:8000/agent/memory/stats
```

## Key Features

✅ **Automatic Profile Extraction** - Learns about users from natural conversation
✅ **Semantic Event Search** - Finds relevant past conversations using embeddings
✅ **Session Awareness** - Can filter by session for multi-user support
✅ **Persistent Storage** - Profile saved to JSON, events in Qdrant
✅ **Context Enrichment** - Automatically injects memory before responses
✅ **Privacy Controls** - Clear memory on demand

## Inspired By

This implementation is based on the **Memobase** architecture (see `.claude/memo-db-mini-blueprint/`), simplified for:
- Single-user scenarios
- Inline processing (no async queues)
- JSON profile storage (no Neo4j graph)
- Direct integration with existing Qdrant setup

## Next Steps

Potential enhancements:
- [ ] Multi-user support with user authentication
- [ ] Confidence scoring for extracted facts
- [ ] Topic/subtopic structure for better organization
- [ ] Memory consolidation (merge similar events)
- [ ] Explicit memory update API (user can add/edit facts)
- [ ] Frontend UI to view and manage memory
