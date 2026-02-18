# Memory System Quick Start

## TL;DR

The chatbot now **remembers** users and **learns** from conversations automatically.

- ✅ **Profile-aware**: Knows who you are, what you do, what you like
- ✅ **History-aware**: Recalls past conversations semantically
- ✅ **Zero configuration**: Works out of the box
- ✅ **Privacy-friendly**: Clear memory anytime

## Quick Test (5 minutes)

### 1. Start Services

```bash
# Start Qdrant (if not already running)
docker-compose up -d qdrant

# Start API
uvicorn app.main:app --reload
```

### 2. Have a Conversation

```bash
# Message 1: Introduce yourself
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hi! I am Sarah, a machine learning engineer interested in NLP",
    "session_id": "demo_session"
  }'

# Response: "Hello Sarah! Great to meet you..."
```

### 3. Check What It Learned

```bash
# View your profile
curl http://localhost:8000/agent/memory/profile
```

**You'll see:**
```json
{
  "success": true,
  "profile": {
    "properties": {
      "name": "Sarah",
      "role": "machine learning engineer"
    },
    "preferences": {
      "interests": ["NLP"]
    },
    "updated_at": "2026-02-15T10:30:00"
  }
}
```

### 4. Express Preferences

```bash
# Message 2: Share preferences
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I prefer detailed technical explanations over high-level overviews",
    "session_id": "demo_session"
  }'
```

### 5. See Memory in Action

```bash
# Message 3: Ask a question
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me about your search capabilities",
    "session_id": "demo_session"
  }'

# The response will be:
# - Personalized (knows you're Sarah, an ML engineer)
# - Detailed (respects your preference)
# - Context-aware (references past conversation)
```

### 6. View Statistics

```bash
curl http://localhost:8000/agent/memory/stats
```

**You'll see:**
```json
{
  "success": true,
  "stats": {
    "profile": {
      "properties_count": 2,
      "preferences_count": 2,
      "updated_at": "2026-02-15T10:31:00",
      "properties": {
        "name": "Sarah",
        "role": "machine learning engineer"
      },
      "preferences": {
        "interests": ["NLP"],
        "communication_style": "detailed technical"
      }
    },
    "events": {
      "total_count": 3
    }
  }
}
```

### 7. Clear Memory (Optional)

```bash
# Clear all memory
curl -X DELETE http://localhost:8000/agent/memory/clear

# Or clear just this session
curl -X DELETE "http://localhost:8000/agent/memory/clear?session_id=demo_session"
```

## How It Works (Simple Version)

### Before Response
1. **Loads your profile** (properties + preferences)
2. **Finds relevant past conversations** (using semantic search)
3. **Injects memory into prompt** (invisibly)

### After Response
1. **Stores the conversation** (with embeddings in Qdrant)
2. **Extracts new facts** (using LLM)
3. **Updates your profile** (in JSON file)

All automatic. No extra API calls needed.

## What Gets Remembered

### Properties (Factual)
- Name
- Role/occupation
- Location
- Expertise level
- Skills
- Current projects
- etc.

### Preferences (Subjective)
- Communication style (concise, detailed, casual, formal)
- Interests and topics
- Likes and dislikes
- Preferred tools/technologies
- Working style
- etc.

### Events (Conversations)
- Full conversation turns
- Timestamps
- Session context
- Semantic embeddings for search

## API Endpoints

### Chat (With Memory)
```bash
POST /agent/chat
{
  "message": "your question",
  "session_id": "optional_session_id",
  "agent": "orchestrator"  # optional
}
```

### View Profile
```bash
GET /agent/memory/profile
```

### View Stats
```bash
GET /agent/memory/stats
```

### Clear Memory
```bash
DELETE /agent/memory/clear
DELETE /agent/memory/clear?session_id=xyz
```

## Example Scenarios

### Scenario 1: New User

```bash
# First conversation
curl -X POST http://localhost:8000/agent/chat -d '{
  "message": "Hello, I am Tom, a data scientist",
  "session_id": "tom_001"
}'
# ✓ Profile created: {name: "Tom", role: "data scientist"}

# Later...
curl -X POST http://localhost:8000/agent/chat -d '{
  "message": "What search features do you have?",
  "session_id": "tom_001"
}'
# ✓ Response references Tom's role as data scientist
```

### Scenario 2: Preference Learning

```bash
curl -X POST http://localhost:8000/agent/chat -d '{
  "message": "I hate long explanations, keep it brief",
  "session_id": "alice_001"
}'
# ✓ Preference saved: {communication_style: "concise"}

# Future responses will be shorter automatically
```

### Scenario 3: Context Recall

```bash
# Week 1
curl -X POST http://localhost:8000/agent/chat -d '{
  "message": "I am working on a chatbot project using Python",
  "session_id": "bob_001"
}'

# Week 2
curl -X POST http://localhost:8000/agent/chat -d '{
  "message": "How should I handle user authentication?",
  "session_id": "bob_001"
}'
# ✓ Response considers the chatbot context from Week 1
```

## Privacy & Control

### Clear Individual Session
```bash
curl -X DELETE "http://localhost:8000/agent/memory/clear?session_id=my_session"
```
- Deletes only events from that session
- Keeps profile intact

### Clear Everything
```bash
curl -X DELETE http://localhost:8000/agent/memory/clear
```
- Deletes profile JSON
- Deletes all events from Qdrant
- Fresh start

### View Before Clear
```bash
# Always check first
curl http://localhost:8000/agent/memory/profile
curl http://localhost:8000/agent/memory/stats
```

## Files & Storage

### Profile Location
```
data/user_profile.json
```

### Events Location
```
Qdrant collection: conversation_events
Vector dimension: 384
Distance: Cosine similarity
```

### Backup Profile
```bash
# Save a copy
cp data/user_profile.json data/user_profile_backup.json

# Restore
cp data/user_profile_backup.json data/user_profile.json
```

## Configuration

Edit `app/config.py` or `.env`:

```python
# Embedding model for events
text_embedding_model = "sentence-transformers/all-MiniLM-L6-v2"

# LLM for profile extraction
llm_model = "qwen2.5:3b"
llm_base_url = "http://localhost:11434/v1"

# Qdrant connection
qdrant_host = "localhost"
qdrant_port = 6333
```

## Troubleshooting

### Memory not working?

1. **Check Qdrant is running:**
   ```bash
   curl http://localhost:6333/collections
   ```

2. **Check LLM is running:**
   ```bash
   curl http://localhost:11434/api/tags  # Ollama
   ```

3. **Check logs:**
   ```bash
   # In API logs, look for:
   # "Enriching message with memory context"
   # "Recorded conversation event"
   ```

4. **Verify collection exists:**
   ```bash
   curl http://localhost:6333/collections/conversation_events
   ```

### Profile not updating?

- Check if LLM extraction is working (view logs)
- Ensure conversation contains extractable information
- Profile extraction uses temperature=0.3 for consistency

### Events not storing?

- Check Qdrant connection
- Verify embedding model is loaded
- Check disk space for Qdrant storage

## Best Practices

### 1. Use Meaningful Session IDs
```bash
# Good
session_id: "user_alice_2026_02"
session_id: "project_chatbot_dev"

# Avoid
session_id: "abc123"
session_id: "test"
```

### 2. Let Users Know
Tell users their preferences are being learned for a better experience.

### 3. Provide Clear Controls
Make it easy to view and clear memory.

### 4. Monitor Storage
Events accumulate over time. Consider periodic cleanup for old sessions.

### 5. Test Profile Extraction
Check `data/user_profile.json` periodically to ensure quality extraction.

## What's Next?

The memory system is live and working! Every chat interaction now:
1. ✅ Retrieves relevant context
2. ✅ Generates personalized responses
3. ✅ Learns from the conversation
4. ✅ Updates the profile

No additional work needed. Just chat naturally and watch it learn!

---

**Questions?** Check:
- `app/memory/README.md` - Module documentation
- `docs/MEMORY_INTEGRATION.md` - Integration details
- `docs/MEMORY_ARCHITECTURE.md` - System diagrams
- `MEMORY_SYSTEM_SUMMARY.md` - Complete overview
