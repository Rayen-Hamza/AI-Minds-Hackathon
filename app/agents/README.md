# ADK Agents for Multimodal RAG System

This directory contains Google ADK (Agent Development Kit) agents for the multimodal RAG system.

## Agents

### 1. Orchestrator Agent (`orchestrator.py`)
The main coordinator agent that:
- Routes user requests to appropriate specialized agents
- Manages conversation flow
- Provides system information and status
- Coordinates multi-agent tasks

**Tools:**
- `get_system_status()` - Get overall system status
- `get_capabilities()` - List system capabilities
- `analyze_request()` - Analyze and route user requests
- `AgentTool(qdrant_agent)` - Delegate to Qdrant agent

### 2. Qdrant Agent (`qdrant_agent.py`)
Specialized agent for vector database operations:
- Semantic search across all content types (text, images, audio)
- Collection management
- Vector database statistics
- Filter-based retrieval

**Tools:**
- `search_vectors()` - Perform semantic search
- `get_collection_info()` - Get collection details
- `list_collections()` - List all collections
- `search_by_filters()` - Filter-based search
- `get_vector_stats()` - Database statistics

## Setup

### 1. Install Dependencies

The agents require Google ADK which is already in `pyproject.toml`:

```bash
uv sync
```

### 2. Set API Key

Create or update `.env` file with your Google API key:

```bash
# Google Gemini API Key (required)
GOOGLE_API_KEY=your_api_key_here

# Use API key directly (not Vertex AI)
GOOGLE_GENAI_USE_VERTEXAI=False
```

Get your API key from: https://aistudio.google.com/app/apikey

### 3. Configure Model (Optional)

The agents use `gemini-2.0-flash-exp` by default. You can change this in the agent files:

```python
root_agent = Agent(
    model="gemini-2.0-flash-exp",  # Change this
    ...
)
```

Supported models:
- `gemini-2.0-flash-exp` (default, fast and capable)
- `gemini-2.5-flash` (latest stable)
- `gemini-pro` (production-ready)

## Usage

### Option 1: Test Script (Interactive)

Run the interactive test script:

```bash
python -m app.test_agents
```

This starts an interactive chat where you can talk to the orchestrator agent.

### Option 2: Test Script (Example Queries)

Run pre-defined example queries:

```bash
python -m app.test_agents example
```

### Option 3: FastAPI Endpoints

The agents are exposed via FastAPI at `/agent/*` endpoints:

```bash
# Start the server
uvicorn app.main:app --reload

# Chat with orchestrator
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What are the system capabilities?",
    "agent": "orchestrator"
  }'

# Chat with Qdrant agent directly
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Search for vector databases",
    "agent": "qdrant"
  }'

# List available agents
curl http://localhost:8000/agent/agents

# List active sessions
curl http://localhost:8000/agent/sessions
```

### Option 4: ADK Web UI

Use the built-in ADK web interface for development:

```bash
# Navigate to the app directory
cd app

# Run ADK web UI
adk web
```

Then open http://localhost:8000 and select the agent from the dropdown.

## Example Queries

Try these queries with the orchestrator:

1. **System Information:**
   - "What are the system capabilities?"
   - "What is the system status?"
   - "What can you do?"

2. **Search Operations:**
   - "Search for information about vector databases"
   - "Find audio files"
   - "Show me images about cats"
   - "Search for text containing 'machine learning'"

3. **Database Information:**
   - "Show me statistics about the vector database"
   - "List all collections"
   - "How many vectors are stored?"

4. **Complex Queries:**
   - "Search for audio files tagged with 'speech' and tell me about them"
   - "What types of content do you have in the database?"
   - "Find the most relevant documents about AI"

## Agent Architecture

```
┌─────────────────────────────────────┐
│      Orchestrator Agent             │
│  (Main Coordinator & Router)        │
│                                     │
│  - Conversation Management          │
│  - Task Routing                     │
│  - System Information               │
│  - Multi-agent Coordination         │
└─────────────┬───────────────────────┘
              │
              │ Delegates to
              │
              ▼
┌─────────────────────────────────────┐
│       Qdrant Agent                  │
│  (Vector DB Specialist)             │
│                                     │
│  - Semantic Search                  │
│  - Collection Management            │
│  - Database Statistics              │
│  - Filter Operations                │
└─────────────┬───────────────────────┘
              │
              │ Uses
              │
              ▼
┌─────────────────────────────────────┐
│     Qdrant Manager                  │
│  (Vector Database Layer)            │
│                                     │
│  - Embeddings                       │
│  - CRUD Operations                  │
│  - Search & Filtering               │
└─────────────────────────────────────┘
```

## Session Management

The agents maintain conversation context through sessions:

- Each conversation gets a unique `session_id`
- Messages and events are stored in session history
- Agents can reference previous messages
- Sessions persist across multiple requests

Example with session:

```python
# First message - creates session
response1 = requests.post(
    "http://localhost:8000/agent/chat",
    json={"message": "What is the system status?"}
)
session_id = response1.json()["session_id"]

# Follow-up message - uses same session
response2 = requests.post(
    "http://localhost:8000/agent/chat",
    json={
        "message": "Can you search for 'AI' now?",
        "session_id": session_id
    }
)
```

## Advanced Features

### Custom Tools

Add new tools to agents by defining functions:

```python
def my_custom_tool(arg: str) -> dict:
    """Tool description for the LLM."""
    # Your implementation
    return {"result": "..."}

# Add to agent
my_agent = Agent(
    name="my_agent",
    model="gemini-2.0-flash-exp",
    tools=[
        FunctionTool(func=my_custom_tool),
        # ... other tools
    ]
)
```

### Agent Callbacks

Add callbacks for logging, monitoring, or validation:

```python
async def before_model_callback(context):
    """Called before LLM invocation."""
    logger.info(f"Calling model with: {context.message}")
    # Modify or validate request
    return context

root_agent = Agent(
    name="root",
    model="gemini-2.0-flash-exp",
    before_model_callback=before_model_callback,
    ...
)
```

### Multi-Model Support

Use different LLMs via LiteLLM:

```python
from google.adk.models.lite_llm import LiteLlm

# Use GPT-4
gpt_model = LiteLlm(model="openai/gpt-4")

# Use Claude
claude_model = LiteLlm(model="anthropic/claude-sonnet-4")

agent = Agent(
    name="multi_model_agent",
    model=gpt_model,
    ...
)
```

## Troubleshooting

### API Key Issues

If you see authentication errors:
1. Verify your API key is set: `echo $GOOGLE_API_KEY`
2. Check the key is valid at https://aistudio.google.com/app/apikey
3. Ensure `GOOGLE_GENAI_USE_VERTEXAI=False` is set

### Import Errors

If agents fail to import:
```bash
# Reinstall dependencies
uv sync

# Verify google-adk is installed
uv pip list | grep google-adk
```

### Connection Errors

If Qdrant connection fails:
```bash
# Start Qdrant
docker-compose up -d

# Verify it's running
curl http://localhost:6333/health
```

## Documentation

- **Google ADK Docs:** https://google.github.io/adk-docs/
- **Gemini API:** https://ai.google.dev/gemini-api/docs
- **ADK GitHub:** https://github.com/google/adk

## Next Steps

1. **Add More Agents:** Create specialized agents for specific tasks
2. **Enhance Tools:** Add more capabilities to existing agents
3. **Implement Memory:** Add long-term memory across sessions
4. **Add Evaluation:** Set up agent evaluation and testing
5. **Deploy:** Deploy agents to production with proper scaling
