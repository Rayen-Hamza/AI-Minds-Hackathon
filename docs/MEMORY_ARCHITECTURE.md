# Memory System Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Chat API Endpoint                           │
│                   /agent/chat (POST)                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
              ┌──────────────────────────┐
              │   Memory Service Layer   │
              └──────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ↓                   ↓                   ↓
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Profile Store  │  │   Event Store   │  │  LLM Extractor  │
│  (JSON File)    │  │   (Qdrant)      │  │  (Ollama)       │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Conversation Flow

### Phase 1: Context Retrieval (Before Response)

```
User Message Arrives
        │
        ↓
┌───────────────────────────────────────────┐
│  get_context(query, session_id)           │
│                                            │
│  Step 1: Load Profile                     │
│    ↓                                       │
│    profile_store.load()                   │
│    → {properties, preferences}            │
│                                            │
│  Step 2: Search Relevant Events           │
│    ↓                                       │
│    event_store.search_relevant_events()   │
│    → Embed query with SentenceTransformer │
│    → Cosine similarity search in Qdrant   │
│    → Top-k most relevant events           │
│                                            │
│  Step 3: Pack Context                     │
│    ↓                                       │
│    prompts.pack_context()                 │
│    → Format as markdown string            │
│                                            │
│  Returns: Memory context string           │
└───────────────────────────────────────────┘
        │
        ↓
Enriched Message = Memory Context + User Query
        │
        ↓
LLM Generates Response (with memory awareness)
```

### Phase 2: Event Recording (After Response)

```
Assistant Response Generated
        │
        ↓
┌────────────────────────────────────────────────┐
│  record_event(user_msg, assistant_msg, ...)   │
│                                                 │
│  Step 1: Format Conversation                   │
│    ↓                                            │
│    "User: {msg}\nAssistant: {response}"        │
│                                                 │
│  Step 2: Store Event in Qdrant                 │
│    ↓                                            │
│    event = Event(text, timestamp, session_id)  │
│    embedding = embedder.encode(text)           │
│    event_store.add_event(event)                │
│    → Upserted to Qdrant collection             │
│                                                 │
│  Step 3: Extract Profile                       │
│    ↓                                            │
│    LLM with EXTRACT_PROFILE_PROMPT             │
│    → Parse JSON: {properties, preferences}     │
│                                                 │
│  Step 4: Update Profile                        │
│    ↓                                            │
│    profile.merge(extracted_data)               │
│    profile_store.save(profile)                 │
│    → Written to data/user_profile.json         │
│                                                 │
│  Returns: Success/failure                      │
└────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │ "Hi, I'm Alex, a Python developer"
       ↓
┌─────────────────────────────────────────────┐
│          Chat API Endpoint                  │
│  1. Extract session_id (or create new)      │
│  2. Call get_context(query, session_id)     │
└──────┬──────────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────────┐
│          Memory Service                     │
│  ┌─────────────────────────────────┐        │
│  │  Load Profile                   │        │
│  │  ├─ properties: {}              │        │
│  │  └─ preferences: {}             │        │
│  └─────────────────────────────────┘        │
│  ┌─────────────────────────────────┐        │
│  │  Search Events                  │        │
│  │  ├─ Embed query                 │        │
│  │  ├─ Query Qdrant                │        │
│  │  └─ Top-5 similar events        │        │
│  └─────────────────────────────────┘        │
│  ┌─────────────────────────────────┐        │
│  │  Pack Context                   │        │
│  │  └─ Format: "# Memory\n..."     │        │
│  └─────────────────────────────────┘        │
└──────┬──────────────────────────────────────┘
       │ Context: "# Memory\n## User Profile:\n(empty)"
       ↓
┌─────────────────────────────────────────────┐
│          Inject into Prompt                 │
│  "# Memory\n...\nUser query: Hi, I'm Alex"  │
└──────┬──────────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────────┐
│          LLM (Orchestrator Agent)           │
│  Generates: "Hello Alex! Nice to meet..."   │
└──────┬──────────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────────┐
│          Return Response to User            │
└──────┬──────────────────────────────────────┘
       │
       ↓
┌─────────────────────────────────────────────┐
│          record_event()                     │
│  ┌─────────────────────────────────┐        │
│  │  Store Event                    │        │
│  │  ├─ Text: "User: Hi...Assistant"│        │
│  │  ├─ Embed text                  │        │
│  │  └─ Upsert to Qdrant            │        │
│  └─────────────────────────────────┘        │
│  ┌─────────────────────────────────┐        │
│  │  Extract Profile                │        │
│  │  ├─ LLM call with prompt        │        │
│  │  ├─ Parse JSON response         │        │
│  │  └─ {properties: {name: "Alex", │        │
│  │       role: "Python developer"}}│        │
│  └─────────────────────────────────┘        │
│  ┌─────────────────────────────────┐        │
│  │  Update Profile                 │        │
│  │  ├─ Merge extracted data        │        │
│  │  └─ Save to JSON file           │        │
│  └─────────────────────────────────┘        │
└─────────────────────────────────────────────┘
```

## Component Interaction

```
┌────────────────────────────────────────────────────────────┐
│                    FastAPI Application                     │
│                                                             │
│  ┌──────────────────────────────────────────────────┐     │
│  │              Agent Routes                         │     │
│  │  /agent/chat                                      │     │
│  │  /agent/memory/stats                              │     │
│  │  /agent/memory/profile                            │     │
│  │  /agent/memory/clear                              │     │
│  └────────────────┬─────────────────────────────────┘     │
│                   │                                         │
└───────────────────┼─────────────────────────────────────────┘
                    │
                    ↓
┌───────────────────────────────────────────────────────────┐
│                    Memory Module                           │
│                                                             │
│  ┌─────────────────────────────────────────────────┐      │
│  │             MemoryService                        │      │
│  │  - record_event(user_msg, assistant_msg)        │      │
│  │  - get_context(query, session_id)               │      │
│  │  - get_stats()                                   │      │
│  │  - clear_all(session_id?)                        │      │
│  └──────┬──────────────────────┬───────────────────┘      │
│         │                      │                           │
│         ↓                      ↓                           │
│  ┌──────────────┐      ┌──────────────┐                   │
│  │ProfileStore  │      │ EventStore   │                   │
│  │- load()      │      │- add_event() │                   │
│  │- save()      │      │- search()    │                   │
│  │- update()    │      │- get_recent()│                   │
│  │- clear()     │      │- clear()     │                   │
│  └──────┬───────┘      └──────┬───────┘                   │
└─────────┼──────────────────────┼───────────────────────────┘
          │                      │
          ↓                      ↓
┌─────────────────┐    ┌─────────────────┐
│  File System    │    │     Qdrant      │
│                 │    │                 │
│  data/          │    │  Collection:    │
│  user_profile   │    │  conversation_  │
│  .json          │    │  events         │
│                 │    │                 │
│  {properties,   │    │  Vector: 384d   │
│   preferences,  │    │  Payload: {     │
│   updated_at}   │    │    text,        │
│                 │    │    timestamp,   │
│                 │    │    session_id,  │
│                 │    │    metadata     │
│                 │    │  }              │
└─────────────────┘    └─────────────────┘
```

## Profile Extraction Pipeline

```
Conversation Turn
        │
        ↓
┌───────────────────────────────────────────┐
│  format_conversation_for_extraction()     │
│                                            │
│  Input:                                    │
│    user_msg: "I'm Alex, a dev"            │
│    assistant_msg: "Hello Alex!"           │
│                                            │
│  Output:                                   │
│    "User: I'm Alex, a dev\n               │
│     Assistant: Hello Alex!"               │
└────────────────┬──────────────────────────┘
                 │
                 ↓
┌───────────────────────────────────────────┐
│  LLM Call (Ollama qwen2.5:3b)             │
│                                            │
│  System Prompt:                            │
│    "You are a psychologist..."            │
│                                            │
│  User Prompt:                              │
│    EXTRACT_PROFILE_PROMPT                 │
│    + conversation snippet                 │
│                                            │
│  Temperature: 0.3 (low for consistency)   │
│  Max Tokens: 500                           │
└────────────────┬──────────────────────────┘
                 │
                 ↓
┌───────────────────────────────────────────┐
│  Parse JSON Response                       │
│                                            │
│  Raw LLM output:                           │
│    ```json                                 │
│    {                                       │
│      "properties": {                       │
│        "name": "Alex",                     │
│        "role": "developer"                 │
│      },                                    │
│      "preferences": {}                     │
│    }                                       │
│    ```                                     │
│                                            │
│  Parsed:                                   │
│    {properties: {...}, preferences: {...}} │
└────────────────┬──────────────────────────┘
                 │
                 ↓
┌───────────────────────────────────────────┐
│  profile.merge(extracted_data)            │
│                                            │
│  Merge Strategy:                           │
│    - New keys → Insert                     │
│    - Existing keys → Overwrite            │
│    - List values → Extend (unique)        │
│    - Update timestamp                     │
└────────────────┬──────────────────────────┘
                 │
                 ↓
┌───────────────────────────────────────────┐
│  profile_store.save(profile)              │
│                                            │
│  Write to: data/user_profile.json         │
└───────────────────────────────────────────┘
```

## Context Enrichment Example

### Input
```
User Query: "What can you help me with?"
Session ID: "user_123"
```

### Processing
```
1. Load Profile:
   {
     "properties": {"name": "Alex", "role": "Python developer"},
     "preferences": {"communication_style": "concise"}
   }

2. Search Events (semantic):
   Query Embedding: [0.23, -0.45, 0.67, ...]

   Results:
   - Score: 0.89 | "User: I work on AI projects. Assistant: Great!"
   - Score: 0.82 | "User: I prefer short answers. Assistant: Understood."

3. Pack Context:
   ```
   ---
   # Memory
   Unless the user has relevant queries, do not actively mention these memories.

   ## User Profile:
   **Properties:**
     - name: Alex
     - role: Python developer

   **Preferences:**
     - communication_style: concise

   ## Relevant Past Context:
   - [2026-02-15 10:23] User: I work on AI projects...
   - [2026-02-15 10:25] User: I prefer short answers...
   ---
   ```
```

### Output (Enriched Message)
```
---
# Memory
Unless the user has relevant queries, do not actively mention these memories.

## User Profile:
**Properties:**
  - name: Alex
  - role: Python developer

**Preferences:**
  - communication_style: concise

## Relevant Past Context:
- [2026-02-15 10:23] User: I work on AI projects. Assistant: Great!
- [2026-02-15 10:25] User: I prefer short answers. Assistant: Understood.
---

User query: What can you help me with?
```

This enriched message is sent to the LLM, which now has full context about:
- Who the user is (Alex, Python developer)
- Their preferences (wants concise answers)
- Relevant conversation history (working on AI projects)

The LLM can now generate a personalized, context-aware response.

---

## Summary

The memory architecture provides:
1. **Profile Learning** - Automatic extraction from natural conversation
2. **Event Storage** - Semantic embeddings for intelligent retrieval
3. **Context Injection** - Transparent enrichment of prompts
4. **Persistent Memory** - JSON + Qdrant for reliable storage
5. **Session Support** - Multi-conversation awareness
6. **Privacy Controls** - Clear memory on demand

All integrated seamlessly into the existing chat flow with minimal overhead.
