# Memory System Troubleshooting

## Common Issues and Fixes

### Issue: `'list' object has no attribute 'items'`

**Error Message:**
```
ERROR - Error recording event: 'list' object has no attribute 'items'
```

**Cause:**
LLM extraction returned malformed JSON with lists instead of dictionaries for properties/preferences.

**Fix:**
✅ **Already Fixed** - Added validation in:
- `models.py` - Type checking before calling `.items()`
- `memory_service.py` - Structure validation after JSON parsing

**Verification:**
```bash
# Check logs for:
# "Invalid properties type: <class 'list'>, resetting to dict"
# OR
# "Updated profile with X properties and Y preferences"
```

---

### Issue: Profile not updating

**Symptoms:**
- Events are stored but profile stays empty
- `curl http://localhost:8000/agent/memory/profile` returns empty

**Diagnosis Steps:**

1. **Check if extraction is running:**
   ```bash
   # Look in logs for:
   # "Extracted profile data: {...}"
   ```

2. **Check LLM connection:**
   ```bash
   curl http://localhost:11434/api/tags
   # Should show available models including qwen2.5:3b
   ```

3. **Check LLM response format:**
   ```bash
   # Look in logs for:
   # "Failed to parse LLM response as JSON"
   # "Response content: ..."
   ```

**Fixes:**

- **LLM not running:**
  ```bash
  # Start Ollama
  ollama serve

  # Pull model if needed
  ollama pull qwen2.5:3b
  ```

- **Wrong model name:**
  ```bash
  # Check .env or app/config.py
  llm_model = "qwen2.5:3b"  # Make sure this matches
  ```

- **LLM timeout:**
  ```python
  # In memory_service.py, increase timeout:
  timeout=60  # from 30
  ```

---

### Issue: Events not storing in Qdrant

**Symptoms:**
- Profile updates but event count stays 0
- `curl http://localhost:8000/agent/memory/stats` shows `"total_count": 0`

**Diagnosis:**

1. **Check Qdrant connection:**
   ```bash
   curl http://localhost:6333/collections
   ```

2. **Check if collection exists:**
   ```bash
   curl http://localhost:6333/collections/conversation_events
   ```

3. **Check logs for:**
   ```bash
   # Look for:
   # "Collection conversation_events created successfully"
   # "Event added: <uuid>"
   ```

**Fixes:**

- **Qdrant not running:**
  ```bash
  docker-compose up -d qdrant
  ```

- **Collection not created:**
  ```bash
  # Restart API to auto-create collection
  # Or manually create:
  curl -X PUT http://localhost:6333/collections/conversation_events \
    -H "Content-Type: application/json" \
    -d '{
      "vectors": {
        "size": 384,
        "distance": "Cosine"
      }
    }'
  ```

- **Embedding model not loaded:**
  ```bash
  # Check logs for:
  # "Loading embedding model: sentence-transformers/all-MiniLM-L6-v2"
  ```

---

### Issue: Context not enriching messages

**Symptoms:**
- Profile and events exist but responses don't use them
- No "memory context" visible in enriched messages

**Diagnosis:**

1. **Check if get_context is called:**
   ```bash
   # Look in logs for:
   # "Enriching message with memory context (session: ...)"
   ```

2. **Check if context is empty:**
   ```bash
   # Look in logs for:
   # "No context to add (empty profile and no events)"
   ```

3. **Test context generation manually:**
   ```python
   from app.memory import get_context
   ctx = get_context("test query", session_id="test")
   print(ctx)
   ```

**Fixes:**

- **Profile exists but context empty:**
  Check that profile has actual data:
  ```bash
  cat data/user_profile.json
  ```

- **Events exist but not retrieved:**
  Check semantic search is working:
  ```bash
  # Look in logs for:
  # "Found X relevant events for query"
  ```

- **Memory context not injected:**
  Verify agent_routes.py has the integration:
  ```python
  memory_context = get_context(...)
  if memory_context:
      enriched_message = f"{memory_context}\n\nUser query: {request.message}"
  ```

---

### Issue: Memory persists after clearing

**Symptoms:**
- Called `/agent/memory/clear` but profile still shows data
- Old events still appear in context

**Diagnosis:**

1. **Check if clear was successful:**
   ```bash
   curl -X DELETE http://localhost:8000/agent/memory/clear
   # Should return: {"success": true, "message": "All memory cleared"}
   ```

2. **Verify files:**
   ```bash
   # Check profile file
   cat data/user_profile.json
   # Should be missing or empty

   # Check Qdrant
   curl http://localhost:6333/collections/conversation_events
   # Should show points_count: 0
   ```

**Fixes:**

- **File permissions:**
  ```bash
  # Ensure API can write to data directory
  chmod 755 data/
  ls -la data/user_profile.json
  ```

- **Cached in memory:**
  ```bash
  # Restart API to clear in-memory cache
  # Kill and restart uvicorn
  ```

- **Multiple instances:**
  ```bash
  # Check if multiple API instances are running
  ps aux | grep uvicorn
  # Kill old instances
  ```

---

### Issue: Extraction quality is poor

**Symptoms:**
- Profile contains wrong information
- Important details not extracted
- Extraction too aggressive (extracting random things)

**Fixes:**

1. **Adjust extraction temperature:**
   ```python
   # In memory_service.py, line ~82
   "temperature": 0.1,  # Lower = more consistent (was 0.3)
   ```

2. **Use better model:**
   ```bash
   # In .env or config.py
   llm_model = "qwen2.5:7b"  # Larger model
   # or
   llm_model = "llama3:8b"
   ```

3. **Customize extraction prompt:**
   Edit `app/memory/prompts.py`:
   ```python
   EXTRACT_PROFILE_PROMPT = """
   [Your custom instructions...]
   Be more conservative/aggressive about extraction.
   Only extract if you are 100% confident.
   """
   ```

4. **Add confidence threshold:**
   Modify extraction logic to only update if confident.

---

### Issue: Out of memory / Performance issues

**Symptoms:**
- API becomes slow over time
- High memory usage
- Qdrant collection growing too large

**Diagnosis:**

```bash
# Check event count
curl http://localhost:8000/agent/memory/stats

# Check Qdrant storage
curl http://localhost:6333/collections/conversation_events
# Look at points_count
```

**Fixes:**

1. **Clear old events periodically:**
   ```bash
   # Clear events older than X days
   curl -X DELETE http://localhost:8000/agent/memory/clear
   ```

2. **Implement event expiration:**
   Add to `event_store.py`:
   ```python
   def clear_old_events(self, days_old=30):
       cutoff = datetime.now() - timedelta(days=days_old)
       # Delete events older than cutoff
   ```

3. **Reduce max_events in context:**
   ```python
   # In agent_routes.py
   memory_context = get_context(
       query=request.message,
       max_events=3,  # Reduced from 5
       ...
   )
   ```

4. **Use session-specific cleanup:**
   ```bash
   # Clear inactive sessions
   curl -X DELETE "http://localhost:8000/agent/memory/clear?session_id=old_session"
   ```

---

## Debugging Commands

### View full system state

```bash
# 1. Check API health
curl http://localhost:8000/health

# 2. Check memory stats
curl http://localhost:8000/agent/memory/stats | jq

# 3. Check profile
curl http://localhost:8000/agent/memory/profile | jq

# 4. Check Qdrant collections
curl http://localhost:6333/collections | jq

# 5. Check event collection
curl http://localhost:6333/collections/conversation_events | jq

# 6. Check Qdrant points (first 10)
curl -X POST http://localhost:6333/collections/conversation_events/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "with_payload": true, "with_vector": false}' | jq
```

### Enable debug logging

Edit `app/config.py`:
```python
log_level: str = "DEBUG"  # from "INFO"
```

Restart API and check logs for detailed info.

### Test memory components individually

```python
# Test profile store
from app.memory.profile_store import ProfileStore
store = ProfileStore()
profile = store.load()
print(profile)

# Test event store
from app.memory.event_store import EventStore
events = EventStore()
print(events.count_events())

# Test extraction
from app.memory.memory_service import MemoryService
service = MemoryService()
result = service._extract_profile_from_conversation(
    "Hi, I'm Alex",
    "Hello Alex!"
)
print(result)
```

---

## Quick Fixes Summary

| Issue | Quick Fix |
|-------|-----------|
| Profile not updating | Restart LLM (Ollama) |
| Events not storing | Restart Qdrant |
| Context not enriching | Check logs for "Enriching message" |
| Extraction errors | Check LLM is running |
| Memory persists | Manually delete `data/user_profile.json` |
| Slow performance | Clear old events |
| Wrong information | Lower extraction temperature |

---

## Getting Help

If issues persist:

1. **Check logs carefully** - Most issues show clear error messages
2. **Verify all services running** - Qdrant, Ollama, API
3. **Test components individually** - Use Python REPL to test each part
4. **Check file permissions** - Ensure API can read/write `data/`
5. **Review configuration** - Verify `.env` and `config.py` settings

**Still stuck?**
- Check `app/memory/README.md` for architecture details
- Review `docs/MEMORY_INTEGRATION.md` for integration specifics
- Look at test script: `test_memory_integration.py`
