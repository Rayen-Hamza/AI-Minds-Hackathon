# Neo4j Graph Reasoning Engine — Sub-4B LLM Architecture

## Fundamental Problem Statement

Large language models ≥ 70B parameters can brute-force multi-hop reasoning by holding vast implicit knowledge. A sub-4B model (Phi-3-mini 3.8B, Gemma-2 2B, Qwen2.5-3B, StableLM-2 1.6B) **cannot**. It has:

- Limited working memory (~2K-4K effective context window utilization)
- Weak implicit knowledge graphs
- Poor multi-hop reasoning when information spans > 2 logical steps
- Tendency to hallucinate connective reasoning

**The solution**: Offload relational reasoning to Neo4j and feed the LLM **pre-computed, structured reasoning chains** instead of raw context. The LLM becomes a **natural language formatter** over deterministic graph computations, not a reasoner.

---

## Core Design Principle: Graph-as-Brain, LLM-as-Mouth

```
Traditional RAG (big LLM):
  Query → Retrieve chunks → LLM reasons over chunks → Answer

Our Architecture (small LLM):
  Query → Decompose → Graph traversal computes answer skeleton
       → Skeleton + minimal evidence → LLM formats natural language
```

The LLM never reasons. It narrates. Neo4j reasons.

---

## Schema Design — The Ontology

### Node Labels & Properties

```cypher
// ═══════════════════════════════════════════
// CONTENT NODES — What the user has
// ═══════════════════════════════════════════

(:Document {
  id: UUID,
  title: String,
  file_path: String,            // Absolute path on user's filesystem
  content_hash: String,          // SHA-256 for dedup/change detection
  mime_type: String,             // "application/pdf", "text/markdown", etc.
  file_size_bytes: Integer,
  created_at: DateTime,
  modified_at: DateTime,
  indexed_at: DateTime,
  chunk_count: Integer,          // How many chunks this doc was split into
  language: String,              // "en", "fr", etc. (detected)
  summary: String,               // LLM-generated 1-2 sentence summary
  qdrant_collection: String,     // Which Qdrant collection holds its vectors
  quality_score: Float           // 0.0-1.0 extractability/quality metric
})

(:Chunk {
  id: UUID,
  document_id: UUID,             // FK to parent Document
  chunk_index: Integer,          // Position in document (0-based)
  content: String,               // Raw text content (≤512 tokens)
  content_hash: String,          // For differential updates
  token_count: Integer,
  start_char: Integer,           // Character offset in original document
  end_char: Integer,
  qdrant_point_id: UUID,         // Direct pointer to vector in Qdrant
  embedding_model: String,       // "bge-small-en-v1.5", etc.
  embedding_version: Integer     // For re-embedding migrations
})

(:Image {
  id: UUID,
  file_path: String,
  content_hash: String,          // Perceptual hash (pHash)
  mime_type: String,
  width: Integer,
  height: Integer,
  ocr_text: String,              // Extracted text via OCR (nullable)
  caption: String,               // Generated description
  objects_detected: [String],    // ["cat", "laptop", "coffee_cup"]
  scene_type: String,            // "indoor", "outdoor", "screenshot", etc.
  qdrant_point_id: UUID,
  created_at: DateTime,
  modified_at: DateTime
})

(:Video {
  id: UUID,
  file_path: String,
  content_hash: String,
  duration_seconds: Float,
  frame_count: Integer,
  resolution: String,            // "1920x1080"
  transcript: String,            // Full whisper transcript (nullable)
  scene_count: Integer,
  created_at: DateTime,
  modified_at: DateTime
})

(:Audio {
  id: UUID,
  file_path: String,
  content_hash: String,
  duration_seconds: Float,
  transcript: String,
  speaker_count: Integer,
  language: String,
  created_at: DateTime
})

// ═══════════════════════════════════════════
// SEMANTIC NODES — Extracted knowledge
// ═══════════════════════════════════════════

(:Person {
  id: UUID,
  canonical_name: String,        // Resolved primary name
  aliases: [String],             // ["Bob", "Robert Smith", "Bob S."]
  email: String,                 // Nullable
  role: String,                  // "colleague", "professor", "friend"
  first_seen: DateTime,
  last_seen: DateTime,
  mention_count: Integer         // Popularity/importance metric
})

(:Organization {
  id: UUID,
  name: String,
  aliases: [String],
  type: String,                  // "company", "university", "government"
  first_seen: DateTime,
  mention_count: Integer
})

(:Location {
  id: UUID,
  name: String,
  type: String,                  // "city", "building", "country"
  coordinates: Point,            // Neo4j spatial type (nullable)
  first_seen: DateTime
})

(:Topic {
  id: UUID,
  name: String,                  // Normalized lowercase
  description: String,           // Short definition
  parent_topic_id: UUID,         // Hierarchical taxonomy
  depth: Integer,                // 0 = root, 1 = category, 2+ = specific
  mention_count: Integer,
  last_active: DateTime,
  importance_score: Float        // Computed via PageRank
})

(:Concept {
  id: UUID,
  name: String,
  definition: String,
  domain: String,                // "machine_learning", "cooking", "finance"
  complexity_level: String,      // "basic", "intermediate", "advanced"
  mention_count: Integer
})

(:Event {
  id: UUID,
  name: String,
  description: String,
  occurred_at: DateTime,
  duration_hours: Float,         // Nullable
  type: String                   // "meeting", "deadline", "milestone"
})

(:Task {
  id: UUID,
  title: String,
  status: String,                // "pending", "in_progress", "done"
  priority: String,              // "low", "medium", "high", "critical"
  due_date: DateTime,
  created_at: DateTime,
  completed_at: DateTime         // Nullable
})

(:Project {
  id: UUID,
  name: String,
  description: String,
  status: String,                // "active", "paused", "completed"
  started_at: DateTime,
  tags: [String]
})

// ═══════════════════════════════════════════
// STRUCTURAL / META NODES
// ═══════════════════════════════════════════

(:Folder {
  id: UUID,
  path: String,                  // "/home/user/Documents/research"
  name: String,                  // "research"
  depth: Integer,
  file_count: Integer,
  last_scan: DateTime
})

(:Tag {
  id: UUID,
  name: String,                  // User-defined or auto-generated
  category: String,              // "user", "auto", "system"
  created_at: DateTime
})

(:QueryPattern {
  id: UUID,
  template: String,              // "find {entity} related to {topic}"
  frequency: Integer,
  last_used: DateTime,
  avg_satisfaction: Float        // 0.0-1.0 based on feedback
})

(:ReasoningChain {
  id: UUID,
  query: String,                 // Original user query
  chain_type: String,            // "path", "aggregation", "temporal", "causal"
  steps: [String],               // Ordered reasoning steps as strings
  confidence: Float,
  created_at: DateTime,
  ttl_hours: Integer             // Cache expiry
})
```

### Relationship Types — Full Catalog

```cypher
// ═══════════════════════════════════════════
// STRUCTURAL RELATIONSHIPS
// ═══════════════════════════════════════════

(:Folder)-[:CONTAINS]->(:Document|:Image|:Video|:Audio|:Folder)
  // Properties: none needed

(:Document)-[:HAS_CHUNK]->(:Chunk)
  // Properties: { order: Integer }

(:Document)-[:REFERENCES]->(:Document)
  // Properties: { reference_type: "citation"|"hyperlink"|"import", context: String }

(:Document)-[:DERIVED_FROM]->(:Document)
  // Properties: { derivation_type: "edit"|"fork"|"translation", timestamp: DateTime }

(:Document)-[:VERSION_OF]->(:Document)
  // Properties: { version: Integer, diff_hash: String }

// ═══════════════════════════════════════════
// SEMANTIC RELATIONSHIPS (the reasoning fuel)
// ═══════════════════════════════════════════

(:Chunk)-[:MENTIONS {
  confidence: Float,             // NER confidence score (0.0-1.0)
  mention_type: String,          // "direct"|"indirect"|"implied"
  context_snippet: String        // 50-char surrounding text
}]->(:Person|:Organization|:Location|:Topic|:Concept|:Event)

(:Document)-[:ABOUT {
  relevance_score: Float,        // TF-IDF or embedding similarity
  is_primary: Boolean            // Is this the main topic?
}]->(:Topic|:Concept)

(:Person)-[:AFFILIATED_WITH {
  role: String,
  since: DateTime,
  until: DateTime
}]->(:Organization)

(:Person)-[:KNOWS {
  relationship_type: String,     // "colleague", "friend", "supervisor"
  strength: Float,               // Co-occurrence based (0.0-1.0)
  first_seen: DateTime
}]->(:Person)

(:Person)-[:WORKED_ON]->(:Project)
(:Person)-[:ATTENDED]->(:Event)
(:Person)-[:EXPERT_IN {level: String}]->(:Topic|:Concept)

(:Topic)-[:SUBTOPIC_OF]->(:Topic)
  // Hierarchical taxonomy

(:Topic)-[:RELATED_TO {
  strength: Float,               // Semantic similarity
  co_occurrence_count: Integer
}]->(:Topic)

(:Concept)-[:PREREQUISITE_OF]->(:Concept)
  // Learning dependency chain

(:Concept)-[:CONTRASTS_WITH]->(:Concept)
(:Concept)-[:IMPLEMENTS]->(:Concept)

(:Event)-[:OCCURRED_AT]->(:Location)
(:Event)-[:INVOLVED {role: String}]->(:Person)
(:Event)-[:PART_OF]->(:Project)

(:Task)-[:BELONGS_TO]->(:Project)
(:Task)-[:ASSIGNED_TO]->(:Person)
(:Task)-[:BLOCKED_BY]->(:Task)
(:Task)-[:DEPENDS_ON]->(:Task)

(:Document|:Image|:Video)-[:TAGGED_WITH]->(:Tag)
(:Document|:Image|:Video)-[:BELONGS_TO]->(:Project)

// ═══════════════════════════════════════════
// TEMPORAL RELATIONSHIPS
// ═══════════════════════════════════════════

(:Document)-[:CREATED_ON {timestamp: DateTime}]->(:Event)
(:Document)-[:ACCESSED_ON {timestamp: DateTime, access_count: Integer}]->(:Event)
(:Chunk)-[:PRECEDED_BY]->(:Chunk)     // Sequential reading order
(:Event)-[:CAUSED]->(:Event)          // Causal chain

// ═══════════════════════════════════════════
// SIMILARITY RELATIONSHIPS (computed, not extracted)
// ═══════════════════════════════════════════

(:Document)-[:SIMILAR_TO {
  cosine_similarity: Float,
  method: String,                // "embedding"|"tfidf"|"graph_structure"
  computed_at: DateTime
}]->(:Document)

(:Chunk)-[:SIMILAR_TO {
  cosine_similarity: Float
}]->(:Chunk)

(:Image)-[:VISUALLY_SIMILAR_TO {
  similarity: Float,
  method: String                 // "clip"|"phash"|"dinov2"
}]->(:Image)
```

### Index Definitions (Critical for Performance)

```cypher
// ═══════════════════════════════════════════
// UNIQUE CONSTRAINTS
// ═══════════════════════════════════════════
CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT folder_path IF NOT EXISTS FOR (f:Folder) REQUIRE f.path IS UNIQUE;

// ═══════════════════════════════════════════
// LOOKUP INDEXES (B-tree for equality/range)
// ═══════════════════════════════════════════
CREATE INDEX doc_hash IF NOT EXISTS FOR (d:Document) ON (d.content_hash);
CREATE INDEX doc_path IF NOT EXISTS FOR (d:Document) ON (d.file_path);
CREATE INDEX doc_modified IF NOT EXISTS FOR (d:Document) ON (d.modified_at);
CREATE INDEX chunk_doc IF NOT EXISTS FOR (c:Chunk) ON (c.document_id);
CREATE INDEX chunk_hash IF NOT EXISTS FOR (c:Chunk) ON (c.content_hash);
CREATE INDEX chunk_qdrant IF NOT EXISTS FOR (c:Chunk) ON (c.qdrant_point_id);
CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.canonical_name);
CREATE INDEX topic_name IF NOT EXISTS FOR (t:Topic) ON (t.name);
CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name);
CREATE INDEX event_time IF NOT EXISTS FOR (e:Event) ON (e.occurred_at);
CREATE INDEX task_status IF NOT EXISTS FOR (t:Task) ON (t.status);
CREATE INDEX project_status IF NOT EXISTS FOR (p:Project) ON (p.status);

// ═══════════════════════════════════════════
// FULL-TEXT INDEXES (for keyword search fallback)
// ═══════════════════════════════════════════
CREATE FULLTEXT INDEX ft_chunk_content IF NOT EXISTS
  FOR (c:Chunk) ON EACH [c.content];

CREATE FULLTEXT INDEX ft_doc_title IF NOT EXISTS
  FOR (d:Document) ON EACH [d.title, d.summary];

CREATE FULLTEXT INDEX ft_person_name IF NOT EXISTS
  FOR (p:Person) ON EACH [p.canonical_name, p.aliases];
```

---

## Query Decomposition Engine — The Critical Bridge

### Why This Exists

A sub-4B LLM cannot reliably convert natural language to Cypher. Full text-to-Cypher requires:

- Understanding schema (burns context window)
- Generating syntactically valid Cypher (unreliable at <4B)
- Handling edge cases (NULL, OPTIONAL MATCH, aggregation)

**Our approach**: Template-based query decomposition with slot filling.

### Query Intent Classifier

We classify every user query into one of **8 reasoning types** using a lightweight classifier (not the LLM):

```python
from enum import Enum
from dataclasses import dataclass

class ReasoningType(Enum):
    # ─── Direct Lookup ───────────────────────────────
    ENTITY_LOOKUP = "entity_lookup"
    # "Who is John Smith?" → Find node, return properties

    # ─── Relationship Traversal ──────────────────────
    RELATIONSHIP = "relationship"
    # "What projects is Alice working on?" → Single-hop traversal

    # ─── Multi-Hop Path ──────────────────────────────
    MULTI_HOP = "multi_hop"
    # "How does machine learning connect to my cooking notes?"
    # → Shortest path between two concepts

    # ─── Aggregation ─────────────────────────────────
    AGGREGATION = "aggregation"
    # "How many documents mention Python?" → COUNT/SUM/AVG

    # ─── Temporal ────────────────────────────────────
    TEMPORAL = "temporal"
    # "What was I working on last Tuesday?" → Time-range filter

    # ─── Comparison ──────────────────────────────────
    COMPARISON = "comparison"
    # "Which topic appears more: ML or web dev?"
    # → Parallel aggregation + compare

    # ─── Causal Chain ────────────────────────────────
    CAUSAL = "causal"
    # "Why did I start researching transformers?"
    # → Temporal + path analysis

    # ─── Exploration ─────────────────────────────────
    EXPLORATION = "exploration"
    # "What's related to my thesis?" → Neighborhood expansion


@dataclass
class DecomposedQuery:
    reasoning_type: ReasoningType
    entities: list[str]          # Extracted entity mentions
    relationships: list[str]     # Expected relationship types
    time_range: tuple | None     # (start, end) DateTime or None
    aggregation_fn: str | None   # "count", "sum", "avg", "max", "min"
    hop_limit: int               # Max traversal depth (default 3)
    confidence: float            # Classifier confidence
```

### Lightweight Intent Classifier Implementation

**This does NOT use the LLM.** We use a tiny fine-tuned classifier or pattern matching:

```python
import re
from datetime import datetime, timedelta

class QueryDecomposer:
    """
    Rule-based + embedding classifier for query intent.
    No LLM required — runs in <5ms.
    """

    # ─── Pattern Definitions ─────────────────────────
    TEMPORAL_PATTERNS = [
        (r"last\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", "day_of_week"),
        (r"last\s+(week|month|year)", "relative_period"),
        (r"yesterday", "yesterday"),
        (r"today", "today"),
        (r"(\d{4}-\d{2}-\d{2})", "iso_date"),
        (r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}", "month_year"),
        (r"(\d+)\s+(days?|weeks?|months?|hours?)\s+ago", "relative_ago"),
        (r"between\s+(.+)\s+and\s+(.+)", "range"),
        (r"since\s+(.+)", "since"),
        (r"before\s+(.+)", "before"),
    ]

    AGGREGATION_KEYWORDS = {
        "how many": "count",
        "count": "count",
        "total": "sum",
        "average": "avg",
        "most": "max",
        "least": "min",
        "top": "max",
        "bottom": "min",
        "frequently": "count",
        "often": "count",
    }

    RELATIONSHIP_KEYWORDS = [
        "related to", "connected to", "associated with",
        "linked to", "about", "mentions", "involves",
        "works on", "worked on", "belongs to", "part of",
    ]

    MULTI_HOP_INDICATORS = [
        "how does .* connect to",
        "what's the relationship between .* and",
        "how are .* and .* related",
        "path from .* to",
        "connection between",
        "link between .* and",
    ]

    CAUSAL_INDICATORS = [
        "why did", "what caused", "what led to",
        "reason for", "because of what",
        "what triggered", "how did .* start",
    ]

    EXPLORATION_INDICATORS = [
        "what's related to", "explore", "show me everything about",
        "what do I know about", "tell me about",
        "what's connected to", "neighborhood of",
    ]

    def decompose(self, query: str) -> DecomposedQuery:
        query_lower = query.lower().strip()

        # ── Step 1: Extract temporal constraints ─────
        time_range = self._extract_time_range(query_lower)

        # ── Step 2: Detect aggregation ───────────────
        agg_fn = self._detect_aggregation(query_lower)

        # ── Step 3: Extract entities ─────────────────
        entities = self._extract_entities(query)

        # ── Step 4: Classify reasoning type ──────────
        reasoning_type, confidence = self._classify_intent(
            query_lower, time_range, agg_fn, entities
        )

        # ── Step 5: Determine hop limit ──────────────
        hop_limit = self._estimate_hop_limit(reasoning_type, query_lower)

        # ── Step 6: Identify expected relationships ──
        relationships = self._extract_relationships(query_lower)

        return DecomposedQuery(
            reasoning_type=reasoning_type,
            entities=entities,
            relationships=relationships,
            time_range=time_range,
            aggregation_fn=agg_fn,
            hop_limit=hop_limit,
            confidence=confidence,
        )

    def _classify_intent(self, query, time_range, agg_fn, entities):
        """Priority-ordered intent classification."""

        # Causal has highest priority (most specific)
        for pattern in self.CAUSAL_INDICATORS:
            if re.search(pattern, query):
                return ReasoningType.CAUSAL, 0.85

        # Multi-hop detection
        for pattern in self.MULTI_HOP_INDICATORS:
            if re.search(pattern, query):
                return ReasoningType.MULTI_HOP, 0.90

        # Temporal with no other indicators
        if time_range and not agg_fn:
            return ReasoningType.TEMPORAL, 0.88

        # Aggregation
        if agg_fn:
            if len(entities) >= 2:
                return ReasoningType.COMPARISON, 0.82
            return ReasoningType.AGGREGATION, 0.85

        # Exploration (broad, open-ended)
        for pattern in self.EXPLORATION_INDICATORS:
            if re.search(pattern, query):
                return ReasoningType.EXPLORATION, 0.80

        # Relationship traversal (1-hop)
        for kw in self.RELATIONSHIP_KEYWORDS:
            if kw in query:
                return ReasoningType.RELATIONSHIP, 0.83

        # Default: entity lookup if entities found, exploration otherwise
        if entities:
            return ReasoningType.ENTITY_LOOKUP, 0.70

        return ReasoningType.EXPLORATION, 0.50

    def _extract_entities(self, query: str) -> list[str]:
        """
        Lightweight NER using:
        1. Capitalized word sequences (proper nouns)
        2. Quoted strings
        3. Known entity cache lookup
        """
        entities = []

        # Quoted strings — highest confidence
        quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', query)
        for match in quoted:
            entities.append(match[0] or match[1])

        # Capitalized sequences (skip sentence starts)
        words = query.split()
        i = 0
        while i < len(words):
            if i > 0 and words[i][0].isupper():
                # Collect consecutive capitalized words
                entity_parts = [words[i]]
                j = i + 1
                while j < len(words) and words[j][0].isupper():
                    entity_parts.append(words[j])
                    j += 1
                entity = " ".join(entity_parts)
                # Filter out common non-entity capitals
                if entity.lower() not in {"i", "the", "a", "an", "my"}:
                    entities.append(entity)
                i = j
            else:
                i += 1

        return entities

    def _extract_time_range(self, query):
        """Parse temporal expressions into (start, end) DateTime tuples."""
        now = datetime.now()

        for pattern, ptype in self.TEMPORAL_PATTERNS:
            match = re.search(pattern, query)
            if match:
                if ptype == "yesterday":
                    start = now - timedelta(days=1)
                    return (start.replace(hour=0, minute=0),
                            start.replace(hour=23, minute=59))
                elif ptype == "today":
                    return (now.replace(hour=0, minute=0),
                            now.replace(hour=23, minute=59))
                elif ptype == "relative_period":
                    period = match.group(1)
                    if period == "week":
                        return (now - timedelta(weeks=1), now)
                    elif period == "month":
                        return (now - timedelta(days=30), now)
                    elif period == "year":
                        return (now - timedelta(days=365), now)
                elif ptype == "relative_ago":
                    amount = int(match.group(1))
                    unit = match.group(2).rstrip('s')
                    delta_map = {"day": timedelta(days=amount),
                                 "week": timedelta(weeks=amount),
                                 "month": timedelta(days=amount*30),
                                 "hour": timedelta(hours=amount)}
                    delta = delta_map.get(unit, timedelta(days=amount))
                    return (now - delta, now)
        return None

    def _detect_aggregation(self, query):
        for keyword, fn in self.AGGREGATION_KEYWORDS.items():
            if keyword in query:
                return fn
        return None

    def _estimate_hop_limit(self, reasoning_type, query):
        limits = {
            ReasoningType.ENTITY_LOOKUP: 0,
            ReasoningType.RELATIONSHIP: 1,
            ReasoningType.MULTI_HOP: 4,
            ReasoningType.AGGREGATION: 1,
            ReasoningType.TEMPORAL: 1,
            ReasoningType.COMPARISON: 1,
            ReasoningType.CAUSAL: 5,
            ReasoningType.EXPLORATION: 2,
        }
        return limits.get(reasoning_type, 2)

    def _extract_relationships(self, query):
        found = []
        for kw in self.RELATIONSHIP_KEYWORDS:
            if kw in query:
                found.append(kw)
        return found
```

---

## Cypher Template Engine — Pre-Built Query Library

### Why Templates, Not Generation

| Approach                  | Accuracy at <4B | Latency   | Maintenance          |
| ------------------------- | --------------- | --------- | -------------------- |
| LLM generates Cypher      | ~30-40% valid   | 500ms+    | None                 |
| Fine-tuned text-to-Cypher | ~60-70% valid   | 200ms     | Training data needed |
| **Template + slot fill**  | **~95% valid**  | **<10ms** | Template library     |

### Template Registry

```python
from string import Template
from typing import Any

class CypherTemplate:
    def __init__(self, template: str, required_slots: list[str],
                 reasoning_type: ReasoningType):
        self.template = template
        self.required_slots = required_slots
        self.reasoning_type = reasoning_type

    def render(self, slots: dict[str, Any]) -> str:
        """Fill template slots and return valid Cypher."""
        # Validate all required slots present
        missing = [s for s in self.required_slots if s not in slots]
        if missing:
            raise ValueError(f"Missing slots: {missing}")

        # Sanitize inputs (prevent injection)
        sanitized = {}
        for key, value in slots.items():
            if isinstance(value, str):
                sanitized[key] = value.replace("'", "\\'").replace('"', '\\"')
            else:
                sanitized[key] = value

        return Template(self.template).safe_substitute(sanitized)


# ═══════════════════════════════════════════════════════════
# TEMPLATE LIBRARY — Organized by ReasoningType
# ═══════════════════════════════════════════════════════════

CYPHER_TEMPLATES = {

    # ─── ENTITY LOOKUP ───────────────────────────────────
    "entity_lookup_person": CypherTemplate(
        template="""
        MATCH (p:Person)
        WHERE p.canonical_name =~ '(?i).*$entity_name.*'
           OR ANY(alias IN p.aliases WHERE alias =~ '(?i).*$entity_name.*')
        OPTIONAL MATCH (p)-[:AFFILIATED_WITH]->(org:Organization)
        OPTIONAL MATCH (p)-[:EXPERT_IN]->(topic:Topic)
        OPTIONAL MATCH (p)-[:WORKED_ON]->(proj:Project)
        RETURN p {
            .canonical_name, .email, .role, .mention_count,
            organizations: collect(DISTINCT org.name),
            expertise: collect(DISTINCT topic.name),
            projects: collect(DISTINCT proj.name)
        } AS person
        LIMIT 5
        """,
        required_slots=["entity_name"],
        reasoning_type=ReasoningType.ENTITY_LOOKUP
    ),

    "entity_lookup_topic": CypherTemplate(
        template="""
        MATCH (t:Topic)
        WHERE t.name =~ '(?i).*$topic_name.*'
        OPTIONAL MATCH (t)<-[:ABOUT]-(d:Document)
        OPTIONAL MATCH (t)-[:RELATED_TO]-(related:Topic)
        OPTIONAL MATCH (t)-[:SUBTOPIC_OF]->(parent:Topic)
        OPTIONAL MATCH (child:Topic)-[:SUBTOPIC_OF]->(t)
        RETURN t {
            .name, .description, .mention_count, .importance_score,
            document_count: count(DISTINCT d),
            related_topics: collect(DISTINCT related.name)[0..10],
            parent_topic: parent.name,
            subtopics: collect(DISTINCT child.name)[0..10]
        } AS topic
        LIMIT 5
        """,
        required_slots=["topic_name"],
        reasoning_type=ReasoningType.ENTITY_LOOKUP
    ),

    "entity_lookup_document": CypherTemplate(
        template="""
        MATCH (d:Document)
        WHERE d.title =~ '(?i).*$search_term.*'
           OR d.summary =~ '(?i).*$search_term.*'
        OPTIONAL MATCH (d)-[:ABOUT]->(t:Topic)
        OPTIONAL MATCH (d)-[:BELONGS_TO]->(p:Project)
        OPTIONAL MATCH (d)<-[:CONTAINS]-(f:Folder)
        RETURN d {
            .title, .file_path, .created_at, .modified_at, .summary,
            topics: collect(DISTINCT t.name),
            project: p.name,
            folder: f.path
        } AS document
        ORDER BY d.modified_at DESC
        LIMIT 10
        """,
        required_slots=["search_term"],
        reasoning_type=ReasoningType.ENTITY_LOOKUP
    ),

    # ─── RELATIONSHIP TRAVERSAL ──────────────────────────
    "person_connections": CypherTemplate(
        template="""
        MATCH (p:Person)
        WHERE p.canonical_name =~ '(?i).*$person_name.*'
        OPTIONAL MATCH (p)-[r:KNOWS]->(other:Person)
        OPTIONAL MATCH (p)-[:WORKED_ON]->(proj:Project)
        OPTIONAL MATCH (p)-[:AFFILIATED_WITH]->(org:Organization)
        OPTIONAL MATCH (p)-[:ATTENDED]->(evt:Event)
        RETURN p.canonical_name AS person,
               collect(DISTINCT {
                   name: other.canonical_name,
                   relationship: r.relationship_type,
                   strength: r.strength
               }) AS connections,
               collect(DISTINCT proj.name) AS projects,
               collect(DISTINCT org.name) AS organizations,
               collect(DISTINCT {name: evt.name, date: evt.occurred_at}) AS events
        """,
        required_slots=["person_name"],
        reasoning_type=ReasoningType.RELATIONSHIP
    ),

    "documents_about_topic": CypherTemplate(
        template="""
        MATCH (t:Topic)
        WHERE t.name =~ '(?i).*$topic_name.*'
        MATCH (d:Document)-[r:ABOUT]->(t)
        OPTIONAL MATCH (d)<-[:CONTAINS]-(f:Folder)
        RETURN d {
            .title, .file_path, .summary, .modified_at,
            relevance: r.relevance_score,
            folder: f.path
        } AS document
        ORDER BY r.relevance_score DESC
        LIMIT $limit
        """,
        required_slots=["topic_name"],
        reasoning_type=ReasoningType.RELATIONSHIP
    ),

    "topic_neighborhood": CypherTemplate(
        template="""
        MATCH (t:Topic)
        WHERE t.name =~ '(?i).*$topic_name.*'
        CALL {
            WITH t
            MATCH (t)-[r:RELATED_TO]-(other:Topic)
            RETURN other.name AS name, r.strength AS weight,
                   'related_to' AS rel_type
            UNION
            WITH t
            MATCH (t)<-[:SUBTOPIC_OF]-(child:Topic)
            RETURN child.name AS name, 1.0 AS weight,
                   'subtopic' AS rel_type
            UNION
            WITH t
            MATCH (t)-[:SUBTOPIC_OF]->(parent:Topic)
            RETURN parent.name AS name, 1.0 AS weight,
                   'parent' AS rel_type
        }
        RETURN name, weight, rel_type
        ORDER BY weight DESC
        LIMIT 20
        """,
        required_slots=["topic_name"],
        reasoning_type=ReasoningType.EXPLORATION
    ),

    # ─── MULTI-HOP PATH FINDING ─────────────────────────
    "shortest_path_entities": CypherTemplate(
        template="""
        MATCH (source)
        WHERE (source:Topic OR source:Concept OR source:Person OR source:Project)
          AND (source.name =~ '(?i).*$entity_a.*'
               OR source.canonical_name =~ '(?i).*$entity_a.*')
        MATCH (target)
        WHERE (target:Topic OR target:Concept OR target:Person OR target:Project)
          AND (target.name =~ '(?i).*$entity_b.*'
               OR target.canonical_name =~ '(?i).*$entity_b.*')
        MATCH path = shortestPath((source)-[*..${max_hops}]-(target))
        RETURN [node IN nodes(path) |
            CASE
                WHEN node:Person THEN {type: 'Person', name: node.canonical_name}
                WHEN node:Topic THEN {type: 'Topic', name: node.name}
                WHEN node:Concept THEN {type: 'Concept', name: node.name}
                WHEN node:Document THEN {type: 'Document', name: node.title}
                WHEN node:Project THEN {type: 'Project', name: node.name}
                WHEN node:Organization THEN {type: 'Organization', name: node.name}
                ELSE {type: labels(node)[0], name: coalesce(node.name, node.title, node.canonical_name, 'unknown')}
            END
        ] AS path_nodes,
        [rel IN relationships(path) | type(rel)] AS path_relationships,
        length(path) AS path_length
        ORDER BY path_length ASC
        LIMIT 5
        """,
        required_slots=["entity_a", "entity_b"],
        reasoning_type=ReasoningType.MULTI_HOP
    ),

    "all_paths_between": CypherTemplate(
        template="""
        MATCH (source)
        WHERE (source.name =~ '(?i).*$entity_a.*'
               OR source.canonical_name =~ '(?i).*$entity_a.*')
        MATCH (target)
        WHERE (target.name =~ '(?i).*$entity_b.*'
               OR target.canonical_name =~ '(?i).*$entity_b.*')
        MATCH path = allShortestPaths((source)-[*..${max_hops}]-(target))
        WITH path, length(path) AS len
        ORDER BY len ASC
        LIMIT 10
        RETURN [node IN nodes(path) |
            coalesce(node.canonical_name, node.name, node.title)
        ] AS node_names,
        [rel IN relationships(path) | type(rel)] AS relationships,
        len AS hops
        """,
        required_slots=["entity_a", "entity_b"],
        reasoning_type=ReasoningType.MULTI_HOP
    ),

    # ─── AGGREGATION ─────────────────────────────────────
    "count_by_topic": CypherTemplate(
        template="""
        MATCH (t:Topic)<-[:ABOUT]-(d:Document)
        WHERE t.name =~ '(?i).*$topic_name.*'
        RETURN t.name AS topic, count(d) AS document_count,
               collect(d.title)[0..5] AS sample_documents
        ORDER BY document_count DESC
        """,
        required_slots=["topic_name"],
        reasoning_type=ReasoningType.AGGREGATION
    ),

    "top_entities_by_mentions": CypherTemplate(
        template="""
        MATCH (n:$node_label)
        WHERE n.mention_count IS NOT NULL
        RETURN n.name AS entity,
               n.mention_count AS mentions,
               labels(n)[0] AS type
        ORDER BY n.mention_count DESC
        LIMIT $limit
        """,
        required_slots=["node_label"],
        reasoning_type=ReasoningType.AGGREGATION
    ),

    "content_stats": CypherTemplate(
        template="""
        CALL {
            MATCH (d:Document) RETURN 'Documents' AS type, count(d) AS cnt
            UNION ALL
            MATCH (i:Image) RETURN 'Images' AS type, count(i) AS cnt
            UNION ALL
            MATCH (v:Video) RETURN 'Videos' AS type, count(v) AS cnt
            UNION ALL
            MATCH (a:Audio) RETURN 'Audio' AS type, count(a) AS cnt
            UNION ALL
            MATCH (t:Topic) RETURN 'Topics' AS type, count(t) AS cnt
            UNION ALL
            MATCH (p:Person) RETURN 'People' AS type, count(p) AS cnt
            UNION ALL
            MATCH (c:Concept) RETURN 'Concepts' AS type, count(c) AS cnt
        }
        RETURN type, cnt
        ORDER BY cnt DESC
        """,
        required_slots=[],
        reasoning_type=ReasoningType.AGGREGATION
    ),

    # ─── TEMPORAL ────────────────────────────────────────
    "documents_in_timerange": CypherTemplate(
        template="""
        MATCH (d:Document)
        WHERE d.modified_at >= datetime('$start_time')
          AND d.modified_at <= datetime('$end_time')
        OPTIONAL MATCH (d)-[:ABOUT]->(t:Topic)
        OPTIONAL MATCH (d)-[:BELONGS_TO]->(p:Project)
        RETURN d {
            .title, .file_path, .modified_at, .summary,
            topics: collect(DISTINCT t.name),
            project: p.name
        } AS document
        ORDER BY d.modified_at DESC
        LIMIT 20
        """,
        required_slots=["start_time", "end_time"],
        reasoning_type=ReasoningType.TEMPORAL
    ),

    "activity_timeline": CypherTemplate(
        template="""
        MATCH (d:Document)
        WHERE d.modified_at >= datetime('$start_time')
          AND d.modified_at <= datetime('$end_time')
        WITH d.modified_at.year AS year,
             d.modified_at.month AS month,
             d.modified_at.day AS day,
             count(d) AS activity_count,
             collect(d.title)[0..3] AS sample_docs
        RETURN year, month, day, activity_count, sample_docs
        ORDER BY year, month, day
        """,
        required_slots=["start_time", "end_time"],
        reasoning_type=ReasoningType.TEMPORAL
    ),

    # ─── COMPARISON ──────────────────────────────────────
    "compare_topics": CypherTemplate(
        template="""
        UNWIND [$topic_a, $topic_b] AS topic_name
        MATCH (t:Topic)
        WHERE t.name =~ '(?i).*' + topic_name + '.*'
        OPTIONAL MATCH (t)<-[:ABOUT]-(d:Document)
        OPTIONAL MATCH (t)-[:RELATED_TO]-(related:Topic)
        RETURN t.name AS topic,
               t.mention_count AS mentions,
               t.importance_score AS importance,
               count(DISTINCT d) AS document_count,
               collect(DISTINCT related.name)[0..5] AS related_topics
        """,
        required_slots=["topic_a", "topic_b"],
        reasoning_type=ReasoningType.COMPARISON
    ),

    # ─── CAUSAL CHAIN ────────────────────────────────────
    "temporal_chain": CypherTemplate(
        template="""
        MATCH (t:Topic)
        WHERE t.name =~ '(?i).*$topic_name.*'
        MATCH (d:Document)-[:ABOUT]->(t)
        WITH d ORDER BY d.created_at ASC
        WITH collect(d {.title, .created_at, .summary})[0..15] AS timeline
        RETURN timeline
        """,
        required_slots=["topic_name"],
        reasoning_type=ReasoningType.CAUSAL
    ),

    "event_causal_chain": CypherTemplate(
        template="""
        MATCH (e:Event)
        WHERE e.name =~ '(?i).*$event_name.*'
        MATCH chain = (e)-[:CAUSED*0..5]->(effect:Event)
        RETURN [node IN nodes(chain) | node {.name, .occurred_at, .description}]
               AS causal_chain,
               length(chain) AS chain_length
        ORDER BY chain_length ASC
        """,
        required_slots=["event_name"],
        reasoning_type=ReasoningType.CAUSAL
    ),

    # ─── EXPLORATION ─────────────────────────────────────
    "full_neighborhood": CypherTemplate(
        template="""
        MATCH (center)
        WHERE center.name =~ '(?i).*$entity_name.*'
           OR center.canonical_name =~ '(?i).*$entity_name.*'
           OR center.title =~ '(?i).*$entity_name.*'
        WITH center LIMIT 1
        CALL {
            WITH center
            MATCH (center)-[r]->(outgoing)
            RETURN type(r) AS rel_type,
                   'outgoing' AS direction,
                   labels(outgoing)[0] AS node_type,
                   coalesce(outgoing.name, outgoing.title,
                            outgoing.canonical_name) AS node_name,
                   properties(r) AS rel_props
            UNION
            WITH center
            MATCH (center)<-[r]-(incoming)
            RETURN type(r) AS rel_type,
                   'incoming' AS direction,
                   labels(incoming)[0] AS node_type,
                   coalesce(incoming.name, incoming.title,
                            incoming.canonical_name) AS node_name,
                   properties(r) AS rel_props
        }
        RETURN rel_type, direction, node_type, node_name, rel_props
        ORDER BY rel_type, direction
        LIMIT 50
        """,
        required_slots=["entity_name"],
        reasoning_type=ReasoningType.EXPLORATION
    ),

    # ─── GRAPH ALGORITHMS ────────────────────────────────
    "pagerank_topics": CypherTemplate(
        template="""
        MATCH (t:Topic)-[r:RELATED_TO]-(other:Topic)
        WITH t, count(r) AS degree,
             sum(r.strength) AS total_strength
        RETURN t.name AS topic,
               degree,
               total_strength,
               t.mention_count AS mentions,
               total_strength / degree AS avg_connection_strength
        ORDER BY degree * coalesce(t.mention_count, 1) DESC
        LIMIT $limit
        """,
        required_slots=[],
        reasoning_type=ReasoningType.AGGREGATION
    ),

    "community_detection": CypherTemplate(
        template="""
        // Find clusters of tightly connected topics
        MATCH (t:Topic)-[:RELATED_TO]-(neighbor:Topic)
        WITH t, collect(DISTINCT neighbor) AS neighbors
        WHERE size(neighbors) >= 3
        RETURN t.name AS hub_topic,
               [n IN neighbors | n.name] AS cluster_members,
               size(neighbors) AS cluster_size
        ORDER BY cluster_size DESC
        LIMIT 10
        """,
        required_slots=[],
        reasoning_type=ReasoningType.EXPLORATION
    ),
}
```

---

## Template Router — Connecting Decomposition to Cypher

```python
class TemplateRouter:
    """
    Maps a DecomposedQuery to the best Cypher template(s) and fills slots.
    """

    def __init__(self, templates: dict[str, CypherTemplate]):
        self.templates = templates
        # Build index by reasoning type for fast lookup
        self.type_index: dict[ReasoningType, list[str]] = {}
        for name, tmpl in templates.items():
            self.type_index.setdefault(tmpl.reasoning_type, []).append(name)

    def route(self, query: DecomposedQuery) -> list[tuple[str, str]]:
        """
        Returns list of (template_name, rendered_cypher) pairs.
        May return multiple queries for complex reasoning types.
        """
        candidates = self.type_index.get(query.reasoning_type, [])
        results = []

        for tmpl_name in candidates:
            tmpl = self.templates[tmpl_name]
            slots = self._fill_slots(tmpl, query)
            if slots is not None:
                try:
                    cypher = tmpl.render(slots)
                    results.append((tmpl_name, cypher))
                except ValueError:
                    continue

        # If no templates match, fall back to exploration
        if not results and query.entities:
            fallback = self.templates.get("full_neighborhood")
            if fallback:
                slots = {"entity_name": query.entities[0]}
                results.append(("full_neighborhood", fallback.render(slots)))

        return results

    def _fill_slots(self, template: CypherTemplate,
                    query: DecomposedQuery) -> dict | None:
        """
        Attempt to fill template slots from decomposed query data.
        Returns None if required slots cannot be filled.
        """
        slots = {}

        for slot in template.required_slots:
            value = self._resolve_slot(slot, query)
            if value is None:
                return None
            slots[slot] = value

        # Fill optional slots with defaults
        if "limit" not in slots:
            slots["limit"] = 10
        if "max_hops" not in slots:
            slots["max_hops"] = query.hop_limit

        return slots

    def _resolve_slot(self, slot_name: str,
                      query: DecomposedQuery) -> str | None:
        """Map slot names to query data."""

        # Direct entity mapping
        entity_slots = {
            "entity_name": 0,    # First entity
            "person_name": 0,
            "topic_name": 0,
            "search_term": 0,
            "event_name": 0,
            "entity_a": 0,       # First entity for comparison/path
            "topic_a": 0,
        }
        second_entity_slots = {
            "entity_b": 1,       # Second entity
            "topic_b": 1,
        }

        if slot_name in entity_slots:
            idx = entity_slots[slot_name]
            return query.entities[idx] if len(query.entities) > idx else None

        if slot_name in second_entity_slots:
            idx = second_entity_slots[slot_name]
            return query.entities[idx] if len(query.entities) > idx else None

        # Temporal slots
        if slot_name == "start_time" and query.time_range:
            return query.time_range[0].isoformat()
        if slot_name == "end_time" and query.time_range:
            return query.time_range[1].isoformat()

        # Node label mapping (for aggregation)
        if slot_name == "node_label":
            label_map = {
                "person": "Person", "people": "Person",
                "topic": "Topic", "topics": "Topic",
                "document": "Document", "documents": "Document",
                "project": "Project", "projects": "Project",
            }
            for entity in query.entities:
                mapped = label_map.get(entity.lower())
                if mapped:
                    return mapped
            return "Topic"  # Default

        return None
```

---

## Reasoning Chain Builder — The Answer Skeleton

This is where graph results get transformed into **structured reasoning that the small LLM can narrate**.

```python
from dataclasses import dataclass, field

@dataclass
class ReasoningStep:
    """A single atomic reasoning step."""
    step_number: int
    operation: str          # "lookup", "traverse", "compare", "aggregate", "infer"
    description: str        # Human-readable description of what was found
    evidence: list[str]     # Supporting data points
    confidence: float       # 0.0-1.0

@dataclass
class ReasoningChain:
    """Complete reasoning chain ready for LLM narration."""
    query: str
    reasoning_type: str
    steps: list[ReasoningStep] = field(default_factory=list)
    conclusion: str = ""
    evidence_summary: str = ""
    total_confidence: float = 0.0
    source_count: int = 0

    def to_llm_prompt_context(self) -> str:
        """
        Format the chain as structured context for the small LLM.
        This is the KEY format — it must be dense, unambiguous,
        and require ZERO reasoning from the LLM.
        """
        lines = []
        lines.append(f"QUERY: {self.query}")
        lines.append(f"REASONING TYPE: {self.reasoning_type}")
        lines.append(f"CONFIDENCE: {self.total_confidence:.0%}")
        lines.append(f"SOURCES: {self.source_count} items analyzed")
        lines.append("")
        lines.append("REASONING CHAIN:")

        for step in self.steps:
            lines.append(f"  Step {step.step_number} [{step.operation}]: {step.description}")
            for evidence in step.evidence:
                lines.append(f"    • {evidence}")

        lines.append("")
        lines.append(f"CONCLUSION: {self.conclusion}")
        lines.append("")
        lines.append(f"EVIDENCE SUMMARY: {self.evidence_summary}")

        return "\n".join(lines)


class ReasoningChainBuilder:
    """
    Transforms raw Neo4j query results into structured reasoning chains.
    This is where the 'intelligence' lives — deterministic graph logic,
    NOT LLM inference.
    """

    def build_chain(self, query: str, reasoning_type: ReasoningType,
                    cypher_results: list[dict]) -> ReasoningChain:
        """Dispatch to type-specific chain builder."""

        builders = {
            ReasoningType.ENTITY_LOOKUP: self._build_entity_chain,
            ReasoningType.RELATIONSHIP: self._build_relationship_chain,
            ReasoningType.MULTI_HOP: self._build_multi_hop_chain,
            ReasoningType.AGGREGATION: self._build_aggregation_chain,
            ReasoningType.TEMPORAL: self._build_temporal_chain,
            ReasoningType.COMPARISON: self._build_comparison_chain,
            ReasoningType.CAUSAL: self._build_causal_chain,
            ReasoningType.EXPLORATION: self._build_exploration_chain,
        }

        builder = builders.get(reasoning_type, self._build_generic_chain)
        chain = builder(query, cypher_results)
        chain.total_confidence = self._compute_chain_confidence(chain)
        return chain

    def _build_entity_chain(self, query: str,
                            results: list[dict]) -> ReasoningChain:
        chain = ReasoningChain(query=query, reasoning_type="entity_lookup")

        if not results:
            chain.steps.append(ReasoningStep(
                step_number=1,
                operation="lookup",
                description="No matching entity found in knowledge graph.",
                evidence=[],
                confidence=0.0
            ))
            chain.conclusion = "Entity not found in your personal knowledge base."
            return chain

        entity = results[0]
        chain.source_count = 1

        # Step 1: Identity
        chain.steps.append(ReasoningStep(
            step_number=1,
            operation="lookup",
            description=f"Found entity matching query.",
            evidence=[f"{k}: {v}" for k, v in entity.items()
                      if v and v != [] and v != ""],
            confidence=0.9
        ))

        # Step 2: Connections (if present)
        connection_fields = ["organizations", "expertise", "projects",
                           "related_topics", "subtopics", "topics"]
        connections = {k: v for k, v in entity.items()
                      if k in connection_fields and v}

        if connections:
            chain.steps.append(ReasoningStep(
                step_number=2,
                operation="traverse",
                description="Retrieved connected entities.",
                evidence=[f"{k}: {', '.join(v) if isinstance(v, list) else v}"
                         for k, v in connections.items()],
                confidence=0.85
            ))

        # Conclusion
        chain.conclusion = self._summarize_entity(entity)
        chain.evidence_summary = f"Based on {len(chain.steps)} graph lookups."
        return chain

    def _build_multi_hop_chain(self, query: str,
                                results: list[dict]) -> ReasoningChain:
        chain = ReasoningChain(query=query, reasoning_type="multi_hop")

        if not results:
            chain.steps.append(ReasoningStep(
                step_number=1,
                operation="traverse",
                description="No path found between the specified entities.",
                evidence=["Entities may not be connected within the knowledge graph."],
                confidence=0.0
            ))
            chain.conclusion = "No connection found."
            return chain

        for i, path_result in enumerate(results):
            path_nodes = path_result.get("path_nodes", [])
            path_rels = path_result.get("path_relationships", [])
            path_length = path_result.get("path_length", 0)

            # Build step-by-step traversal narrative
            step_desc_parts = []
            for j in range(len(path_nodes) - 1):
                source = path_nodes[j]
                target = path_nodes[j + 1]
                rel = path_rels[j] if j < len(path_rels) else "CONNECTED_TO"
                step_desc_parts.append(
                    f"{source.get('name', '?')} ({source.get('type', '?')}) "
                    f"—[{rel}]→ "
                    f"{target.get('name', '?')} ({target.get('type', '?')})"
                )

            chain.steps.append(ReasoningStep(
                step_number=i + 1,
                operation="traverse",
                description=f"Path {i+1} ({path_length} hops):",
                evidence=step_desc_parts,
                confidence=max(0.5, 1.0 - (path_length * 0.15))
            ))

        # Conclusion: narrate the shortest path
        best_path = results[0]
        nodes = best_path.get("path_nodes", [])
        if len(nodes) >= 2:
            chain.conclusion = (
                f"Connection found: {nodes[0].get('name')} connects to "
                f"{nodes[-1].get('name')} through {len(nodes)-2} intermediate "
                f"node(s) via {best_path.get('path_length')} relationship(s)."
            )

        chain.source_count = len(results)
        chain.evidence_summary = (
            f"Found {len(results)} path(s) between entities. "
            f"Shortest path: {results[0].get('path_length', '?')} hops."
        )
        return chain

    def _build_temporal_chain(self, query: str,
                              results: list[dict]) -> ReasoningChain:
        chain = ReasoningChain(query=query, reasoning_type="temporal")

        if not results:
            chain.conclusion = "No activity found in the specified time period."
            return chain

        chain.source_count = len(results)

        # Group by meaningful clusters (project, topic)
        topic_groups: dict[str, list] = {}
        for doc in results:
            doc_data = doc.get("document", doc)
            topics = doc_data.get("topics", ["uncategorized"])
            for topic in topics:
                topic_groups.setdefault(topic, []).append(doc_data)

        step_num = 1
        for topic, docs in sorted(topic_groups.items(),
                                    key=lambda x: len(x[1]), reverse=True):
            chain.steps.append(ReasoningStep(
                step_number=step_num,
                operation="aggregate",
                description=f"Topic '{topic}': {len(docs)} document(s)",
                evidence=[
                    f"'{d.get('title', '?')}' (modified: {d.get('modified_at', '?')})"
                    for d in docs[:5]
                ],
                confidence=0.9
            ))
            step_num += 1

        chain.conclusion = (
            f"During this period, you worked on {len(topic_groups)} topic area(s) "
            f"across {len(results)} document(s). "
            f"Most active topic: '{max(topic_groups, key=lambda k: len(topic_groups[k]))}'"
        )
        chain.evidence_summary = (
            f"Analyzed {len(results)} documents from the specified time range."
        )
        return chain

    def _build_comparison_chain(self, query: str,
                                 results: list[dict]) -> ReasoningChain:
        chain = ReasoningChain(query=query, reasoning_type="comparison")

        if len(results) < 2:
            chain.conclusion = "Not enough data for comparison."
            return chain

        chain.source_count = len(results)

        # Build comparison table
        for i, item in enumerate(results):
            chain.steps.append(ReasoningStep(
                step_number=i + 1,
                operation="aggregate",
                description=f"Entity: {item.get('topic', item.get('entity', '?'))}",
                evidence=[f"{k}: {v}" for k, v in item.items() if v],
                confidence=0.9
            ))

        # Determine winner for each metric
        comparisons = []
        numeric_keys = [k for k in results[0].keys()
                       if isinstance(results[0].get(k), (int, float))]
        for key in numeric_keys:
            values = [(r.get("topic", r.get("entity", "?")), r.get(key, 0))
                     for r in results]
            winner = max(values, key=lambda x: x[1] if x[1] else 0)
            comparisons.append(f"{key}: {winner[0]} leads ({winner[1]})")

        chain.conclusion = "Comparison: " + "; ".join(comparisons)
        return chain

    def _build_relationship_chain(self, query, results):
        chain = ReasoningChain(query=query, reasoning_type="relationship")
        if not results:
            chain.conclusion = "No relationships found."
            return chain
        chain.source_count = len(results)
        for i, r in enumerate(results[:10]):
            chain.steps.append(ReasoningStep(
                step_number=i+1, operation="traverse",
                description="Found connection.",
                evidence=[f"{k}: {v}" for k, v in r.items() if v and v != []],
                confidence=0.85
            ))
        chain.conclusion = f"Found {len(results)} connected items."
        return chain

    def _build_aggregation_chain(self, query, results):
        chain = ReasoningChain(query=query, reasoning_type="aggregation")
        chain.source_count = len(results)
        for i, r in enumerate(results):
            chain.steps.append(ReasoningStep(
                step_number=i+1, operation="aggregate",
                description="Aggregated data point.",
                evidence=[f"{k}: {v}" for k, v in r.items()],
                confidence=0.9
            ))
        chain.conclusion = f"Aggregated {len(results)} results."
        return chain

    def _build_causal_chain(self, query, results):
        chain = ReasoningChain(query=query, reasoning_type="causal")
        chain.source_count = len(results)
        for i, r in enumerate(results):
            chain.steps.append(ReasoningStep(
                step_number=i+1, operation="infer",
                description="Temporal/causal data point.",
                evidence=[f"{k}: {v}" for k, v in r.items() if v],
                confidence=0.7
            ))
        chain.conclusion = f"Traced causal chain across {len(results)} events/documents."
        return chain

    def _build_exploration_chain(self, query, results):
        chain = ReasoningChain(query=query, reasoning_type="exploration")
        chain.source_count = len(results)
        # Group by relationship type
        by_rel: dict[str, list] = {}
        for r in results:
            rel = r.get("rel_type", "unknown")
            by_rel.setdefault(rel, []).append(r)
        step_num = 1
        for rel_type, items in by_rel.items():
            chain.steps.append(ReasoningStep(
                step_number=step_num, operation="traverse",
                description=f"Relationship '{rel_type}': {len(items)} connections",
                evidence=[
                    f"{item.get('direction', '?')} → {item.get('node_name', '?')} ({item.get('node_type', '?')})"
                    for item in items[:5]
                ],
                confidence=0.85
            ))
            step_num += 1
        chain.conclusion = f"Found {len(results)} connections across {len(by_rel)} relationship types."
        return chain

    def _build_generic_chain(self, query, results):
        chain = ReasoningChain(query=query, reasoning_type="generic")
        chain.source_count = len(results)
        for i, r in enumerate(results[:10]):
            chain.steps.append(ReasoningStep(
                step_number=i+1, operation="lookup",
                description="Result.",
                evidence=[f"{k}: {v}" for k, v in r.items() if v],
                confidence=0.7
            ))
        chain.conclusion = f"Found {len(results)} results."
        return chain

    def _summarize_entity(self, entity: dict) -> str:
        parts = []
        for k, v in entity.items():
            if v and v != []:
                if isinstance(v, list):
                    parts.append(f"{k}: {', '.join(str(x) for x in v)}")
                else:
                    parts.append(f"{k}: {v}")
        return "; ".join(parts[:6])

    def _compute_chain_confidence(self, chain: ReasoningChain) -> float:
        if not chain.steps:
            return 0.0
        confidences = [s.confidence for s in chain.steps]
        # Overall confidence = geometric mean (penalizes weak links)
        product = 1.0
        for c in confidences:
            product *= c
        return product ** (1.0 / len(confidences))
```

---

## LLM Prompt Engineering — Making Sub-4B Work

### The Golden Rule

> **Never ask the LLM to reason. Ask it to narrate.**

### Prompt Template Architecture

```python
class PromptBuilder:
    """
    Build minimal, structured prompts for sub-4B LLMs.

    Key constraints for small models:
    - Max prompt length: ~1500 tokens (leave room for generation)
    - No ambiguity — every instruction is explicit
    - No implicit reasoning — all logic is pre-computed
    - Structured output format — model just fills slots
    - Zero-shot is better than few-shot (saves tokens)
    """

    SYSTEM_PROMPT = """You are a personal knowledge assistant. You NARRATE pre-computed answers.

RULES:
1. ONLY use information from the REASONING CHAIN below. Do NOT add information.
2. Convert the structured data into natural, conversational language.
3. If confidence is below 50%, say "I'm not fully certain, but..."
4. Always mention the number of sources when relevant.
5. Keep responses concise (2-5 sentences for simple queries, up to a paragraph for complex ones).
6. When listing items, use bullet points.
7. Do NOT hallucinate details not present in the evidence."""

    def build_prompt(self, chain: ReasoningChain,
                     user_query: str) -> str:
        """
        Build the final prompt. Total target: <1500 tokens.
        """
        context = chain.to_llm_prompt_context()

        # Truncate context if too long (preserve structure)
        if len(context.split()) > 800:
            context = self._truncate_context(context, max_words=800)

        prompt = f"""{self.SYSTEM_PROMPT}

---
{context}
---

USER QUESTION: {user_query}

RESPONSE:"""

        return prompt

    def build_fallback_prompt(self, user_query: str,
                              vector_results: list[str]) -> str:
        """
        Fallback when graph reasoning doesn't apply.
        Uses vector search results as context (standard RAG).
        """
        context_block = "\n\n".join(
            f"[Source {i+1}]: {chunk}"
            for i, chunk in enumerate(vector_results[:5])
        )

        return f"""{self.SYSTEM_PROMPT}

RETRIEVED CONTEXT:
{context_block}

USER QUESTION: {user_query}

Respond based ONLY on the context above. If the context doesn't contain the answer, say so.

RESPONSE:"""

    def _truncate_context(self, context: str, max_words: int) -> str:
        """
        Smart truncation: preserve structure, trim evidence.
        """
        lines = context.split("\n")
        result = []
        word_count = 0

        for line in lines:
            line_words = len(line.split())
            if word_count + line_words > max_words:
                # Keep structural lines (steps, conclusions)
                if any(marker in line for marker in
                       ["Step", "CONCLUSION", "REASONING", "QUERY", "CONFIDENCE"]):
                    result.append(line)
                    word_count += line_words
                else:
                    continue
            else:
                result.append(line)
                word_count += line_words

        return "\n".join(result)
```

### Example: End-to-End Query Flow

**User asks**: _"How does machine learning connect to my cooking notes?"_

**Step 1 — Decomposition** (< 5ms, no LLM):

```
DecomposedQuery(
    reasoning_type=MULTI_HOP,
    entities=["machine learning", "cooking"],
    relationships=[],
    time_range=None,
    aggregation_fn=None,
    hop_limit=4,
    confidence=0.90
)
```

**Step 2 — Template Selection & Cypher** (< 10ms):

```cypher
MATCH (source)
WHERE (source:Topic OR source:Concept)
  AND source.name =~ '(?i).*machine learning.*'
MATCH (target)
WHERE (target:Topic OR source:Concept)
  AND target.name =~ '(?i).*cooking.*'
MATCH path = shortestPath((source)-[*..4]-(target))
RETURN [...] -- path details
```

**Step 3 — Neo4j Execution** (< 50ms):

```json
[
  {
    "path_nodes": [
      { "type": "Topic", "name": "machine learning" },
      { "type": "Document", "name": "Recipe Classification Project" },
      { "type": "Topic", "name": "image recognition" },
      { "type": "Document", "name": "Food Photography Tips" },
      { "type": "Topic", "name": "cooking" }
    ],
    "path_relationships": ["ABOUT", "ABOUT", "ABOUT", "ABOUT"],
    "path_length": 4
  }
]
```

**Step 4 — Chain Building** (< 2ms):

```
REASONING CHAIN:
  Step 1 [traverse]: Path 1 (4 hops):
    • machine learning (Topic) —[ABOUT]→ Recipe Classification Project (Document)
    • Recipe Classification Project (Document) —[ABOUT]→ image recognition (Topic)
    • image recognition (Topic) —[ABOUT]→ Food Photography Tips (Document)
    • Food Photography Tips (Document) —[ABOUT]→ cooking (Topic)

CONCLUSION: Connection found: machine learning connects to cooking
through 3 intermediate node(s) via 4 relationship(s).
```

**Step 5 — LLM Narration** (~200ms for 3B model):

> "Machine learning connects to your cooking notes through an interesting path! You have a 'Recipe Classification Project' that bridges ML and image recognition, and your 'Food Photography Tips' document links image recognition back to cooking. Essentially, your work on classifying recipe images is the bridge between these two domains — spanning 4 relationships across your knowledge base."

**Total latency**: ~270ms. The LLM did zero reasoning.

---

## Graph Maintenance & Entity Resolution

### Entity Resolution Pipeline

Critical for a small LLM system — the model can't resolve "Bob", "Robert Smith", and "Dr. R. Smith" on its own.

```python
from difflib import SequenceMatcher

class EntityResolver:
    """
    Deterministic entity resolution — no LLM required.
    Resolves mentions to canonical graph nodes.
    """

    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver
        self._entity_cache: dict[str, dict] = {}
        self._refresh_cache()

    def _refresh_cache(self):
        """Load all entity names + aliases into memory for fast matching."""
        with self.driver.session() as session:
            # Load persons
            result = session.run("""
                MATCH (p:Person)
                RETURN p.id AS id, p.canonical_name AS name,
                       p.aliases AS aliases, 'Person' AS label
            """)
            for record in result:
                key = record["name"].lower()
                self._entity_cache[key] = {
                    "id": record["id"],
                    "name": record["name"],
                    "label": record["label"]
                }
                for alias in (record["aliases"] or []):
                    self._entity_cache[alias.lower()] = {
                        "id": record["id"],
                        "name": record["name"],
                        "label": record["label"]
                    }

            # Load topics, concepts, organizations, etc.
            for label in ["Topic", "Concept", "Organization", "Project"]:
                result = session.run(f"""
                    MATCH (n:{label})
                    RETURN n.id AS id, n.name AS name, '{label}' AS label
                """)
                for record in result:
                    self._entity_cache[record["name"].lower()] = {
                        "id": record["id"],
                        "name": record["name"],
                        "label": record["label"]
                    }

    def resolve(self, mention: str) -> dict | None:
        """
        Resolve a text mention to a graph entity.

        Resolution priority:
        1. Exact match (case-insensitive)
        2. Alias match
        3. Fuzzy match (>0.85 similarity)
        4. Substring match
        5. None (new entity)
        """
        mention_lower = mention.lower().strip()

        # 1. Exact match
        if mention_lower in self._entity_cache:
            return self._entity_cache[mention_lower]

        # 2. Already covered by alias loading above

        # 3. Fuzzy match
        best_match = None
        best_score = 0.0
        for cached_name, entity in self._entity_cache.items():
            score = SequenceMatcher(None, mention_lower, cached_name).ratio()
            if score > best_score and score > 0.85:
                best_score = score
                best_match = entity

        if best_match:
            # Cache this alias for future lookups
            self._entity_cache[mention_lower] = best_match
            return best_match

        # 4. Substring match (both directions)
        for cached_name, entity in self._entity_cache.items():
            if mention_lower in cached_name or cached_name in mention_lower:
                if len(mention_lower) >= 3:  # Avoid tiny substring matches
                    return entity

        return None

    def resolve_or_create(self, mention: str, label: str = "Topic",
                          properties: dict = None) -> str:
        """Resolve to existing entity or create new one. Returns entity ID."""
        existing = self.resolve(mention)
        if existing:
            return existing["id"]

        # Create new entity
        import uuid
        new_id = str(uuid.uuid4())
        props = properties or {}
        props["id"] = new_id
        props["name"] = mention
        props["mention_count"] = 1

        with self.driver.session() as session:
            session.run(
                f"CREATE (n:{label} $props)",
                props=props
            )

        # Update cache
        self._entity_cache[mention.lower()] = {
            "id": new_id, "name": mention, "label": label
        }

        return new_id
```

### Incremental Graph Updates

```python
class GraphUpdater:
    """
    Handles differential graph updates when documents change.
    Maintains consistency between Qdrant vectors and Neo4j graph.
    """

    def __init__(self, neo4j_driver, entity_resolver: EntityResolver):
        self.driver = neo4j_driver
        self.resolver = entity_resolver

    def ingest_document(self, doc_id: str, title: str, file_path: str,
                        content_hash: str, chunks: list[dict],
                        extracted_entities: list[dict],
                        topics: list[str]):
        """
        Full document ingestion into the graph.

        Args:
            chunks: [{"id": UUID, "content": str, "qdrant_point_id": UUID, ...}]
            extracted_entities: [{"text": str, "type": "Person"|"Org"|..., "confidence": float}]
            topics: ["machine learning", "python"] — auto-detected topics
        """
        with self.driver.session() as session:
            # ── Step 1: Upsert Document node ─────────
            session.run("""
                MERGE (d:Document {id: $id})
                SET d.title = $title,
                    d.file_path = $file_path,
                    d.content_hash = $content_hash,
                    d.indexed_at = datetime(),
                    d.chunk_count = $chunk_count
            """, id=doc_id, title=title, file_path=file_path,
                content_hash=content_hash, chunk_count=len(chunks))

            # ── Step 2: Create/update Chunk nodes ────
            for chunk in chunks:
                session.run("""
                    MERGE (c:Chunk {id: $chunk_id})
                    SET c.document_id = $doc_id,
                        c.chunk_index = $index,
                        c.content = $content,
                        c.content_hash = $hash,
                        c.qdrant_point_id = $qdrant_id
                    MERGE (d:Document {id: $doc_id})
                    MERGE (d)-[:HAS_CHUNK {order: $index}]->(c)
                """, chunk_id=chunk["id"], doc_id=doc_id,
                    index=chunk["chunk_index"], content=chunk["content"],
                    hash=chunk.get("content_hash", ""),
                    qdrant_id=chunk["qdrant_point_id"])

            # ── Step 3: Link extracted entities ──────
            for entity in extracted_entities:
                entity_id = self.resolver.resolve_or_create(
                    entity["text"], label=entity["type"]
                )
                session.run("""
                    MATCH (d:Document {id: $doc_id})
                    MATCH (e {id: $entity_id})
                    MERGE (d)-[r:MENTIONS]->(e)
                    SET r.confidence = $confidence
                """, doc_id=doc_id, entity_id=entity_id,
                    confidence=entity["confidence"])

            # ── Step 4: Link topics ──────────────────
            for topic_name in topics:
                topic_id = self.resolver.resolve_or_create(
                    topic_name, label="Topic"
                )
                session.run("""
                    MATCH (d:Document {id: $doc_id})
                    MATCH (t:Topic {id: $topic_id})
                    MERGE (d)-[r:ABOUT]->(t)
                    SET r.is_primary = CASE WHEN $is_first THEN true ELSE false END
                """, doc_id=doc_id, topic_id=topic_id,
                    is_first=(topic_name == topics[0]))

    def update_document(self, doc_id: str, new_content_hash: str,
                        changed_chunks: list[dict],
                        new_entities: list[dict],
                        removed_entity_ids: list[str]):
        """
        Differential update — only process what changed.

        This is the KEY performance optimization:
        - Don't re-process unchanged chunks
        - Don't re-extract unchanged entities
        - Only update graph edges that changed
        """
        with self.driver.session() as session:
            # Update document hash
            session.run("""
                MATCH (d:Document {id: $id})
                SET d.content_hash = $hash,
                    d.modified_at = datetime()
            """, id=doc_id, hash=new_content_hash)

            # Update only changed chunks
            for chunk in changed_chunks:
                session.run("""
                    MATCH (c:Chunk {id: $chunk_id})
                    SET c.content = $content,
                        c.content_hash = $hash,
                        c.qdrant_point_id = $qdrant_id
                """, chunk_id=chunk["id"], content=chunk["content"],
                    hash=chunk["content_hash"],
                    qdrant_id=chunk["qdrant_point_id"])

            # Add new entities
            for entity in new_entities:
                entity_id = self.resolver.resolve_or_create(
                    entity["text"], label=entity["type"]
                )
                session.run("""
                    MATCH (d:Document {id: $doc_id})
                    MATCH (e {id: $entity_id})
                    MERGE (d)-[r:MENTIONS]->(e)
                    SET r.confidence = $confidence
                """, doc_id=doc_id, entity_id=entity_id,
                    confidence=entity["confidence"])

            # Remove stale entity links
            for entity_id in removed_entity_ids:
                session.run("""
                    MATCH (d:Document {id: $doc_id})-[r:MENTIONS]->(e {id: $entity_id})
                    DELETE r
                """, doc_id=doc_id, entity_id=entity_id)

    def compute_topic_relationships(self):
        """
        Batch job: compute RELATED_TO edges between topics
        based on co-occurrence in documents.

        Run periodically (every N new documents or on schedule).
        """
        with self.driver.session() as session:
            session.run("""
                MATCH (t1:Topic)<-[:ABOUT]-(d:Document)-[:ABOUT]->(t2:Topic)
                WHERE id(t1) < id(t2)
                WITH t1, t2, count(d) AS co_occurrence,
                     collect(d.title)[0..3] AS shared_docs
                WHERE co_occurrence >= 2
                MERGE (t1)-[r:RELATED_TO]-(t2)
                SET r.co_occurrence_count = co_occurrence,
                    r.strength = 1.0 - (1.0 / (1 + co_occurrence)),
                    r.computed_at = datetime()
            """)

    def compute_importance_scores(self):
        """
        Batch job: PageRank-approximation for topic importance.
        Uses degree centrality as a lightweight proxy.
        """
        with self.driver.session() as session:
            session.run("""
                MATCH (t:Topic)
                OPTIONAL MATCH (t)<-[:ABOUT]-(d:Document)
                OPTIONAL MATCH (t)-[:RELATED_TO]-(other:Topic)
                WITH t, count(DISTINCT d) AS doc_count,
                     count(DISTINCT other) AS topic_connections
                SET t.importance_score =
                    (doc_count * 0.6 + topic_connections * 0.4) /
                    (doc_count + topic_connections + 1.0)
            """)
```

---

## Orchestrator — The Complete Pipeline

```python
from neo4j import GraphDatabase

class GraphReasoningOrchestrator:
    """
    Top-level orchestrator. Receives user query, returns LLM-ready prompt.

    This is the main entry point for the reasoning system.
    Total latency budget: <300ms (excluding LLM inference).
    """

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(
            neo4j_uri, auth=(neo4j_user, neo4j_password)
        )
        self.decomposer = QueryDecomposer()
        self.router = TemplateRouter(CYPHER_TEMPLATES)
        self.chain_builder = ReasoningChainBuilder()
        self.prompt_builder = PromptBuilder()
        self.entity_resolver = EntityResolver(self.driver)

    def process_query(self, user_query: str,
                      vector_results: list[str] = None) -> str:
        """
        Main pipeline:
        1. Decompose query (rule-based, <5ms)
        2. Resolve entities against graph (<10ms)
        3. Route to Cypher templates (<5ms)
        4. Execute Cypher against Neo4j (<50ms)
        5. Build reasoning chain (<5ms)
        6. Construct LLM prompt (<1ms)

        Returns: formatted prompt string ready for LLM inference
        """

        # ── Step 1: Decompose ────────────────────────
        decomposed = self.decomposer.decompose(user_query)

        # ── Step 2: Entity resolution ────────────────
        resolved_entities = []
        for entity in decomposed.entities:
            resolved = self.entity_resolver.resolve(entity)
            if resolved:
                resolved_entities.append(resolved["name"])
            else:
                resolved_entities.append(entity)  # Keep original
        decomposed.entities = resolved_entities

        # ── Step 3: Route to templates ───────────────
        cypher_queries = self.router.route(decomposed)

        if not cypher_queries:
            # No graph query applicable — fall back to vector RAG
            if vector_results:
                return self.prompt_builder.build_fallback_prompt(
                    user_query, vector_results
                )
            return self.prompt_builder.build_fallback_prompt(
                user_query, ["No relevant context found."]
            )

        # ── Step 4: Execute Cypher ───────────────────
        all_results = []
        with self.driver.session() as session:
            for tmpl_name, cypher in cypher_queries:
                try:
                    result = session.run(cypher)
                    records = [dict(record) for record in result]
                    all_results.extend(records)
                except Exception as e:
                    # Log error, continue with other queries
                    print(f"Cypher error in {tmpl_name}: {e}")
                    continue

        # ── Step 5: Build reasoning chain ────────────
        chain = self.chain_builder.build_chain(
            user_query, decomposed.reasoning_type, all_results
        )

        # ── Step 6: Enrich with vector results ───────
        if vector_results and chain.total_confidence < 0.7:
            # Low graph confidence — supplement with vector context
            chain.steps.append(ReasoningStep(
                step_number=len(chain.steps) + 1,
                operation="lookup",
                description="Supplementary context from document search:",
                evidence=vector_results[:3],
                confidence=0.6
            ))

        # ── Step 7: Build LLM prompt ─────────────────
        prompt = self.prompt_builder.build_prompt(chain, user_query)

        return prompt

    def close(self):
        self.driver.close()
```

---

## Performance Characteristics

### Latency Breakdown (Measured Targets)

| Component           | Target Latency | Method                           |
| ------------------- | -------------- | -------------------------------- |
| Query Decomposition | < 5ms          | Rule-based, regex                |
| Entity Resolution   | < 10ms         | In-memory cache + fuzzy match    |
| Template Routing    | < 5ms          | Dict lookup + slot fill          |
| Cypher Execution    | < 50ms         | Indexed queries, LIMIT clauses   |
| Chain Building      | < 5ms          | Pure Python data transform       |
| Prompt Construction | < 1ms          | String concatenation             |
| **Total (pre-LLM)** | **< 76ms**     |                                  |
| LLM Inference (3B)  | ~200-500ms     | Depends on hardware (GPU vs CPU) |
| **End-to-End**      | **< 580ms**    |                                  |

### Memory Footprint

| Component                    | Memory                              |
| ---------------------------- | ----------------------------------- |
| Entity Resolution Cache      | ~10-50MB (scales with entity count) |
| Cypher Template Registry     | < 1MB                               |
| Neo4j Driver Connection Pool | ~5MB                                |
| QueryDecomposer (patterns)   | < 1MB                               |
| **Total Reasoning Engine**   | **~20-60MB**                        |

### Scaling Characteristics

| Metric               | 1K docs | 10K docs | 100K docs |
| -------------------- | ------- | -------- | --------- |
| Graph Nodes          | ~5K     | ~50K     | ~500K     |
| Graph Edges          | ~15K    | ~200K    | ~2M       |
| Entity Cache Size    | ~2MB    | ~20MB    | ~200MB    |
| Cypher Query Latency | <20ms   | <50ms    | <200ms    |
| Cache Refresh Time   | <1s     | <5s      | <30s      |

---

## Failure Modes & Mitigations

### 1. Entity Not Found in Graph

**Trigger**: User mentions entity not yet indexed.
**Mitigation**: Fall back to Qdrant vector search → standard RAG pipeline.
The prompt builder seamlessly switches to `build_fallback_prompt()`.

### 2. No Path Between Entities

**Trigger**: `shortestPath` returns empty.
**Mitigation**: Return "no direct connection found" + trigger exploration query
to show each entity's neighborhood separately. The user gets two context clusters
instead of a bridge.

### 3. Ambiguous Entity Resolution

**Trigger**: "Smith" matches 5 people.
**Mitigation**: Return top-3 candidates ranked by `mention_count`.
Include disambiguation context in the reasoning chain:
`"Multiple matches found for 'Smith': John Smith (45 mentions), Jane Smith (12 mentions)..."`

### 4. Cypher Template Mismatch

**Trigger**: Query doesn't map to any template.
**Mitigation**: Fall to `full_neighborhood` exploration template for any extracted entity.
If zero entities extracted, fall to vector-only RAG.

### 5. Graph Stale / Out of Sync

**Trigger**: File was modified but graph not updated yet.
**Mitigation**: Check `content_hash` match between filesystem and graph node.
If mismatch detected, trigger async re-ingestion and serve from Qdrant meanwhile.

### 6. LLM Narration Hallucination

**Trigger**: Small LLM adds information not in the reasoning chain.
**Mitigation**: Post-generation validation — compare named entities in response
against entities in the reasoning chain. Flag responses with >20% novel entities.
Response includes confidence score from the chain for user calibration.

---

## Summary: Why This Works at Sub-4B

| Challenge              | Big LLM Solution          | Our Sub-4B Solution               |
| ---------------------- | ------------------------- | --------------------------------- |
| Multi-hop reasoning    | Implicit chain-of-thought | Pre-computed graph paths          |
| Entity resolution      | In-context learning       | Deterministic fuzzy matching      |
| Query understanding    | Free-form NLU             | Template-based decomposition      |
| Knowledge recall       | Parametric memory         | Explicit graph + vector retrieval |
| Complex aggregation    | In-context counting       | Cypher GROUP BY / COUNT           |
| Temporal reasoning     | Date parsing in context   | Rule-based temporal extraction    |
| Relationship discovery | Emergent from attention   | Explicit graph traversal          |
| Response factuality    | RLHF alignment            | Pre-computed evidence chains      |

**The small LLM only does ONE thing**: convert a structured, pre-digested reasoning chain into natural language. That's a task even a 1.6B model handles well — it's essentially controlled text generation with a template, not open-ended reasoning.

Intelligence lives in the architecture. The LLM is just the voice.
