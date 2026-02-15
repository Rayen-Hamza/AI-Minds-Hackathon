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

### 2. Start Ollama

The agents use **Qwen2.5:3b** via Ollama for local inference:

```bash
# Start Ollama (if not already running)
ollama serve

# Pull the model (first time only)
ollama pull qwen2.5:3b
```

### 3. Configure Environment

Create or update `.env` file:

```bash
# LLM Configuration (Ollama)
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:3b
LLM_BASE_URL=http://localhost:11434/v1
```

### 4. Configure Model (Optional)

The agents use `qwen2.5:3b` via LiteLLM by default. You can change this in the agent files:

```python
from google.adk.models.lite_llm import LiteLlm

root_agent = Agent(
    model=LiteLlm(model="ollama/qwen2.5:3b"),
    ...
)
```

Supported local models:

- `qwen2.5:3b` (default, excellent multilingual + tool calling)
- `qwen2.5:7b` (larger, more capable)
- `llama3.2:3b` (alternative small model)

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
from google.adk.models.lite_llm import LiteLlm

def my_custom_tool(arg: str) -> dict:
    """Tool description for the LLM."""
    # Your implementation
    return {"result": "..."}

# Add to agent
my_agent = Agent(
    name="my_agent",
    model=LiteLlm(model="ollama/qwen2.5:3b"),
    tools=[
        FunctionTool(func=my_custom_tool),
        # ... other tools
    ]
)
```

### Agent Callbacks

Add callbacks for logging, monitoring, or validation:

```python
from google.adk.models.lite_llm import LiteLlm

async def before_model_callback(context):
    """Called before LLM invocation."""
    logger.info(f"Calling model with: {context.message}")
    # Modify or validate request
    return context

root_agent = Agent(
    name="root",
    model=LiteLlm(model="ollama/qwen2.5:3b"),
    before_model_callback=before_model_callback,
    ...
)
```

### Multi-Model Support

Use different LLMs via LiteLLM:

```python
from google.adk.models.lite_llm import LiteLlm

# Use Qwen via Ollama (default)
qwen_model = LiteLlm(model="ollama/qwen2.5:3b")

# Use Llama via Ollama
llama_model = LiteLlm(model="ollama/llama3.2:3b")

# Use cloud models (if API keys configured)
# gpt_model = LiteLlm(model="openai/gpt-4")

agent = Agent(
    name="multi_model_agent",
    model=qwen_model,
    ...
)
```

## Troubleshooting

### Ollama Connection Issues

If you see LLM connection errors:

1. Verify Ollama is running: `curl http://localhost:11434/api/tags`
2. Check the model is pulled: `ollama list`
3. Ensure `LLM_BASE_URL=http://localhost:11434/v1` is set in `.env`

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
- **Ollama:** https://ollama.ai/
- **LiteLLM:** https://docs.litellm.ai/
- **Qwen2.5:** https://huggingface.co/Qwen/Qwen2.5-3B-Instruct

## Next Steps

1. **Add More Agents:** Create specialized agents for specific tasks
2. **Enhance Tools:** Add more capabilities to existing agents
3. **Implement Memory:** Add long-term memory across sessions
4. **Add Evaluation:** Set up agent evaluation and testing
5. **Deploy:** Deploy agents to production with proper scaling
