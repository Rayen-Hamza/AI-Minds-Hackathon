# Memory Layer

A simplified memory system for the AI assistant, inspired by Memobase's architecture.

## Overview

The memory layer provides **profile-aware** and **history-aware** conversation capabilities through:

1. **Profile Extraction** - Automatically extracts user properties and preferences from conversations
2. **Event Storage** - Stores conversation history with semantic embeddings in Qdrant
3. **Context Enrichment** - Injects relevant profile and history into prompts before responses

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Chat Request                          │
└─────────────────────────────────────────────────────────┘
                          ↓
                  ┌───────────────┐
                  │  get_context  │ ← Retrieve profile + relevant events
                  └───────────────┘
                          ↓
                  ┌───────────────┐
                  │  LLM Response │ ← Enriched with memory context
                  └───────────────┘
                          ↓
                  ┌───────────────┐
                  │ record_event  │ ← Store conversation + extract profile
                  └───────────────┘
```

## Components

### 1. Models (`models.py`)

- **Event** - A conversation turn to be stored
- **Profile** - User properties and preferences
- **ExtractedFacts** - Structured extraction result

### 2. Profile Store (`profile_store.py`)

- Persists user profile to `data/user_profile.json`
- Simple JSON file storage (single-user)
- Merge strategy: new keys inserted, existing keys overwritten, lists extended

### 3. Event Store (`event_store.py`)

- Stores conversation events in Qdrant collection: `conversation_events`
- Embeds text using SentenceTransformer
- Supports semantic search and recency-based retrieval

### 4. Prompts (`prompts.py`)

- **EXTRACT_PROFILE_PROMPT** - LLM prompt for extracting profile from conversations
- **pack_context()** - Formats profile + events into context string

### 5. Memory Service (`memory_service.py`)

Public API:
- `record_event(user_msg, assistant_msg, session_id)` - Store conversation after response
- `get_context(query, session_id)` - Retrieve enriched context before response

## Usage

### Integration in Chat Flow

```python
from app.memory import record_event, get_context

# BEFORE generating response
memory_context = get_context(
    query=user_message,
    max_events=5,
    session_id=session_id
)

# Inject context into prompt
enriched_prompt = f"{memory_context}\n\nUser query: {user_message}"

# Generate response with LLM
response = llm.generate(enriched_prompt)

# AFTER generating response
record_event(
    user_message=user_message,
    assistant_response=response,
    session_id=session_id
)
```

### Memory Management Endpoints

The following endpoints are available:

- `GET /agent/memory/stats` - View profile and event statistics
- `GET /agent/memory/profile` - View current user profile
- `DELETE /agent/memory/clear?session_id={id}` - Clear memory (all or by session)

## Example Context Injection

When a user asks a question, the memory system automatically injects:

```markdown
---
# Memory
Unless the user has relevant queries, do not actively mention these memories in the conversation.

## User Profile:
**Properties:**
  - name: Alex
  - role: Python developer
  - expertise_level: intermediate

**Preferences:**
  - communication_style: concise
  - interests: machine learning, NLP

## Relevant Past Context:
- [2026-02-15 10:23] User: I'm working on AI projects. Assistant: Great to meet you.
- [2026-02-15 10:25] User: I prefer concise answers. Assistant: Understood!
---

User query: What can you help me with?
```

## Profile Extraction

The system uses an LLM to extract structured information from conversations:

**Input**: Conversation snippet
**Output**: JSON with two keys:
- `properties` - Factual attributes (name, role, location, etc.)
- `preferences` - Likes, dislikes, communication style, interests

Example:
```json
{
  "properties": {
    "name": "Alex",
    "role": "Python developer"
  },
  "preferences": {
    "communication_style": "concise",
    "interests": ["machine learning", "NLP"]
  }
}
```

## Data Storage

### Profile: `data/user_profile.json`
```json
{
  "properties": { ... },
  "preferences": { ... },
  "updated_at": "2026-02-15T10:30:00"
}
```

### Events: Qdrant Collection `conversation_events`
- Vector: 384-dim embedding (SentenceTransformer)
- Payload: `{text, timestamp, session_id, metadata}`

## Configuration

Uses settings from `app/config.py`:
- `text_embedding_model` - Model for embedding events (default: all-MiniLM-L6-v2)
- `text_embedding_dim` - Embedding dimension (default: 384)
- `qdrant_host/port` - Qdrant connection
- `llm_base_url/llm_model` - LLM for profile extraction

## Inspiration

Based on Memobase architecture (see `.claude/memo-db-mini-blueprint/`), simplified for:
- Single-user scenarios
- Inline processing (no queues)
- JSON profile storage (no Neo4j)
- Direct Qdrant integration

## Testing

Run the test script:
```bash
python test_memory_integration.py
```

This tests:
1. Profile extraction from conversations
2. Event storage in Qdrant
3. Context retrieval with semantic search
4. Memory persistence across sessions
