# memo-db-mini Architecture

A dead-simple memory layer for a single-user local AI assistant.

---

## What it does (3 things)

1. **Record** — after each conversation turn, store the exchange as an embedded event in Qdrant.
2. **Extract** — inline, use the LLM to pull user properties & preferences and upsert them into a JSON profile.
3. **Enrich** — before generating a response, fetch the profile + semantically relevant events and inject them into the prompt.

That's the entire component.

---

## Single-user simplification

- No user management, no auth, no multi-tenancy.
- One implicit user. All data belongs to them.
- No pending queue or async flush — processing happens inline on every write.
- No Neo4j — profile is a flat JSON file (or in-memory dict persisted to disk). Overkill to run a graph DB for one user's properties.

---

## Data model

### Profile (JSON file on disk)

```json
{
  "properties": {
    "name": "Abid",
    "role": "Python developer",
    "location": "...",
    "expertise_level": "intermediate"
  },
  "preferences": {
    "communication_style": "concise",
    "favorite_language": "Python",
    "interests": ["AI", "local-first tools"],
    "food": "..."
  },
  "updated_at": "2026-02-15T..."
}
```

Just a dict with two top-level buckets: `properties` (who the user is) and `preferences` (what they like/want). Persisted to `~/.memo_db_mini/profile.json` on every update.

### Qdrant (Event history + semantic search)

Collection: `events`

| Field      | Type     |
|------------|----------|
| id         | uuid     |
| vector     | float[]  |
| text       | string (payload) |
| timestamp  | string (payload) |

Every conversation turn is an event. Qdrant stores both the embedding (for retrieval) and the raw text (for context injection).

---

## Flow

### On user message (write path)

```
user says something
  → embed event text → upsert vector + payload in Qdrant
  → LLM extracts properties/preferences from event text
  → merge into profile.json (new key → insert, existing → overwrite)
  → save profile.json to disk
```

All inline. No background worker. No graph DB.

### Before assistant responds (read path)

```
new query arrives
  → embed query → Qdrant top-k similar events
  → load profile.json
  → build memory context string:
      "## User Profile\n{properties + preferences}\n## Relevant Past Context\n{events}"
  → inject into system/user prompt
  → LLM generates response
```

---

## LLM / Embedding provider

Two thin interfaces:

```python
class LLMClient:
    async def complete(self, prompt: str, system: str = None) -> str: ...

class EmbeddingClient:
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

Backend options (swap without touching logic):
- Ollama local (`llama3:8b` + `nomic-embed-text`)
- Cerebras cloud (`llama3.1-8b`, embeddings TBD)

---

## Extraction prompt (simplified from Memobase)

Inspiration file: `prompts/extract_profile.py`

Core idea:
```
Given this conversation snippet, extract any user facts as JSON with two keys:
- "properties": { key: value } — factual attributes (name, role, location, etc.)
- "preferences": { key: value } — likes, dislikes, style preferences, interests

Return JSON object. If nothing extractable, return {}.
```

## Merge policy

- New key → insert.
- Existing key → overwrite value.
- For list-valued keys (e.g. `interests`) → append unique items.
- Bump `updated_at` on any change.
- No confidence scoring needed.

---

## Context packing (simplified from Memobase)

Inspiration file: `prompts/chat_context_pack.py`

Just string concatenation:
```
## User Profile
**Properties:** {key}: {value}, ...
**Preferences:** {key}: {value}, ...

## Relevant Past Context
- [{timestamp}] {event_text_snippet}
- [{timestamp}] {event_text_snippet}
...
```

Keep under ~500 tokens. Truncate oldest events first.

---

## Project layout

```
memo_db_mini/
  __init__.py
  settings.py          # Qdrant/LLM connection config + profile path
  models.py            # dataclasses (Event, Profile)
  prompts.py           # extraction + context packing templates
  llm.py               # LLMClient + EmbeddingClient
  profile_store.py     # read/write profile.json
  qdrant_store.py      # embed + upsert + search events
  memory.py            # record_event(), get_context() — the 2 public functions
```

8 files. No database besides Qdrant (which you already run).

---

## Integration with assistant

The orchestrator only calls two functions:

```python
from memo_db_mini.memory import record_event, get_context

# before generating
ctx = await get_context(query="what should I eat?")
# → returns string to inject into prompt

# after user message
await record_event(text="User: I'm a Python dev building an AI assistant. Assistant: ...")
# → embeds + stores event in Qdrant, extracts facts, updates profile.json
```

No HTTP API needed unless you want one later. Start as a Python module.

---

## Prompt inspiration files (in `prompts/`)

| File | What to study |
|------|---------------|
| `extract_profile.py` | How Memobase structures the extraction prompt, topic/subtopic schema, JSON output format |
| `merge_profile.py` | How it decides to update vs keep existing facts (we simplify to just overwrite) |
| `chat_context_pack.py` | How it formats profile + events into a compact context string |
