# Architecture Flow — Graph Reasoning Engine

> **Pattern**: Graph-as-Brain, LLM-as-Mouth  
> All reasoning is pre-computed via deterministic graph logic. The LLM only narrates the answer.

---

## Table of Contents

1. [Flow 1 — Ingestion: Document → Neo4j Knowledge Graph](#flow-1--ingestion-document--neo4j-knowledge-graph)
2. [Flow 2 — Query: User Question → LLM-Ready Prompt](#flow-2--query-user-question--llm-ready-prompt)
3. [Data Models](#data-models)
4. [Startup Sequence](#startup-sequence)

---

## Flow 1 — Ingestion: Document → Neo4j Knowledge Graph

```
HTTP POST /reasoning/ingest
         │
         ▼
  ┌──────────────┐
  │ IngestRequest │  (doc_id, title, file_path, content_hash,
  │   (schema)    │   chunks[], extracted_entities[], topics[])
  └──────┬───────┘
         │
         ▼
  ┌────────────────────────────────┐
  │ EntityResolver.resolve_or_create() │──── cache lookup / Neo4j CREATE
  └────────────┬───────────────────┘
               │
               ▼
  ┌──────────────────────────┐
  │ GraphUpdater.ingest_document() │──── 4 Cypher steps
  └──────────┬───────────────┘
             │
             ▼
        Neo4j Graph
```

### Step-by-step

#### 1. HTTP Entry Point — `app/routes/reasoning.py`

**Function**: `ingest_document()` (line 63)

```python
@router.post("/ingest", response_model=IngestDocumentResponse)
async def ingest_document(body: IngestDocumentRequest):
```

- Receives a `IngestDocumentRequest` with: `doc_id`, `title`, `file_path`, `content_hash`, `chunks[]`, `extracted_entities[]`, `topics[]`
- Instantiates `EntityResolver(driver)` and `GraphUpdater(driver, resolver)`
- Calls `updater.ingest_document(...)` with all fields

#### 2. Entity Resolution — `app/services/entity_resolver.py`

**Class**: `EntityResolver`

Called internally by `GraphUpdater` during ingestion. For each entity mention in the document:

**Method**: `resolve_or_create(mention, label, properties)` → `str` (entity id)

1. **Try to resolve** via `resolve(mention)` — walks the match cascade:
   - **Exact/Alias** → `self._entity_cache.get(mention.lower())` → `MatchQuality.EXACT`
   - **Fuzzy** → `SequenceMatcher` ratio > `0.85` threshold, +0.05 same-label bonus → `MatchQuality.FUZZY`
   - **Substring** → bidirectional containment, min 3 chars → `MatchQuality.SUBSTRING`
   - **Miss** → `MatchQuality.MISS`

2. **If resolved**: return existing `entity_id`

3. **If miss**: create a new node in Neo4j:
   ```cypher
   CREATE (n:{label} $props)   -- props = {id: uuid, name: mention, mention_count: 1}
   ```
   Then cache the new entry for future lookups.

**Cache**: `_entity_cache: dict[str, dict]` — keys are lowercased names/aliases, values are `{id, name, label}`

**Cache warmup**: `refresh_cache()` queries Neo4j for all Person (with aliases), Topic, Concept, Organization, Project, Event, Location nodes.

#### 3. Graph Population — `app/services/graph_updater.py`

**Class**: `GraphUpdater.__init__(driver, entity_resolver)`

**Method**: `ingest_document(doc_id, title, file_path, content_hash, chunks, extracted_entities, topics)`

Executes 4 sequential Cypher operations inside a single session:

##### Cypher Step 1 — MERGE Document node (line 52)

```cypher
MERGE (d:Document {id: $id})
SET d.title        = $title,
    d.file_path    = $file_path,
    d.content_hash = $content_hash,
    d.indexed_at   = datetime(),
    d.chunk_count  = $chunk_count
```

##### Cypher Step 2 — MERGE Chunk nodes + HAS_CHUNK edges (line 66)

For each chunk in `chunks[]`:

```cypher
MERGE (c:Chunk {id: $chunk_id})
SET c.document_id     = $doc_id,
    c.chunk_index     = $index,
    c.content         = $content,
    c.content_hash    = $hash,
    c.qdrant_point_id = $qdrant_id
WITH c
MATCH (d:Document {id: $doc_id})
MERGE (d)-[:HAS_CHUNK {order: $index}]->(c)
```

##### Cypher Step 3 — Link entities via MENTIONS edges (line 85)

For each entity in `extracted_entities[]`:

1. Call `resolver.resolve_or_create(entity["text"], label=entity["type"])` → `entity_id`
2. Create the edge:

```cypher
MATCH (d:Document {id: $doc_id})
MATCH (e {id: $entity_id})
MERGE (d)-[r:MENTIONS]->(e)
SET r.confidence = $confidence
```

##### Cypher Step 4 — Link topics via ABOUT edges (line 100)

For each topic name in `topics[]`:

1. Call `resolver.resolve_or_create(topic_name, label="Topic")` → `topic_id`
2. Create the edge (first topic gets `is_primary = true`):

```cypher
MATCH (d:Document {id: $doc_id})
MATCH (t:Topic {id: $topic_id})
MERGE (d)-[r:ABOUT]->(t)
SET r.is_primary = $is_first
```

#### 4. Entity Extraction (Upstream) — `app/services/processing/entity_extractor.py`

**Class**: `EntityExtractor` — wraps spaCy `en_core_web_sm`

This runs **before** the ingestion API is called (in the content processing pipeline). It produces the `extracted_entities[]` list.

| Method                                 | Signature                                  | Returns                                             | Purpose                               |
| -------------------------------------- | ------------------------------------------ | --------------------------------------------------- | ------------------------------------- |
| `extract_entities()`                   | `(text, entity_types?) → list[str]`        | Flat entity names                                   | Simple extraction                     |
| `extract_entities_with_labels()`       | `(text, entity_types?) → list[dict]`       | `[{text, label, start, end}]`                       | Labeled extraction                    |
| `extract_key_entities()`               | `(text) → dict[str, list[str]]`            | `{persons, organizations, locations, dates, other}` | Categorized                           |
| `extract_relationships()`              | `(text) → list[dict]`                      | `[{subject, predicate, object}]`                    | SPO triples via verb dependency parse |
| `extract_batch()`                      | `(texts, entity_types?) → list[list[str]]` | Batch entity names                                  | Uses `nlp.pipe()`                     |
| `extract_entities_and_relationships()` | `(text) → dict`                            | `{entities, relationships}`                         | Combined                              |

**Singleton**: `get_entity_extractor(model_name)` — module-level global instance.

#### 5. Label Mapping — `app/services/label_mapping.py`

Bridges spaCy NER labels to Neo4j node labels:

| spaCy Label  | Neo4j Label  | Confidence Prior |
| ------------ | ------------ | ---------------- |
| PERSON       | Person       | 0.92             |
| ORG          | Organization | 0.80             |
| GPE          | Location     | 0.88             |
| LOC          | Location     | 0.72             |
| FAC          | Location     | 0.65             |
| EVENT        | Event        | 0.60             |
| DATE         | Event        | 0.85             |
| TIME         | Event        | 0.75             |
| WORK_OF_ART  | Concept      | 0.55             |
| LAW          | Concept      | 0.60             |
| LANGUAGE     | Concept      | 0.80             |
| PRODUCT      | Project      | 0.55             |
| NORP         | Concept      | 0.78             |
| _(unmapped)_ | Topic        | 0.50             |

**Dataclass**: `TypedEntity(text, spacy_label, neo4j_label, confidence)` — frozen, constructed via `TypedEntity.from_spacy(text, spacy_label)`.

**Method**: `to_entity_payload_dict()` → `{"text": ..., "type": ..., "confidence": ...}` — format expected by `GraphUpdater.ingest_document()`.

#### 6. Resulting Graph Structure

```
(:Document)──[:HAS_CHUNK {order}]──▶(:Chunk)
     │
     ├──[:MENTIONS {confidence}]──▶(:Person)
     ├──[:MENTIONS {confidence}]──▶(:Organization)
     ├──[:MENTIONS {confidence}]──▶(:Location)
     ├──[:MENTIONS {confidence}]──▶(:Concept)
     ├──[:MENTIONS {confidence}]──▶(:Project)
     ├──[:MENTIONS {confidence}]──▶(:Event)
     │
     └──[:ABOUT {is_primary}]──▶(:Topic)
                                    │
                                    └──[:RELATED_TO {co_occurrence_count, strength}]──▶(:Topic)
```

Additional edges created by other processes:

- `(:Person)-[:AFFILIATED_WITH]->(:Organization)`
- `(:Person)-[:EXPERT_IN]->(:Topic)`
- `(:Person)-[:WORKED_ON]->(:Project)`
- `(:Topic)-[:SUBTOPIC_OF]->(:Topic)`

#### 7. Differential Updates — `GraphUpdater.update_document()`

For re-ingestion of changed documents (line 127):

1. Update `Document.content_hash` + `modified_at`
2. Update **only changed chunks** (compare by content hash)
3. `resolve_or_create()` + MERGE for new entities
4. DELETE stale MENTIONS edges for removed entities

---

## Flow 2 — Query: User Question → LLM-Ready Prompt

```
"Who is Sarah Chen?"
         │
         ▼
  ┌──────────────────────┐
  │  QueryDecomposer     │  → DecomposedQuery
  │  .decompose()        │    {type=ENTITY_LOOKUP, entities=["Sarah Chen"],
  └──────┬───────────────┘     entity_types=["Person"], confidence=0.82}
         │
         ▼
  ┌──────────────────────┐
  │  EntityResolver      │  → resolved canonical names
  │  .resolve_with_quality() │    ("Sarah Chen", MatchQuality.EXACT)
  └──────┬───────────────┘
         │
         ▼
  ┌──────────────────────┐
  │  TemplateRouter      │  → [("entity_lookup_person", "MATCH (p:Person)...")]
  │  .route()            │
  └──────┬───────────────┘
         │
         ▼
  ┌──────────────────────┐
  │  Neo4j               │  → [{canonical_name: "Sarah Chen",
  │  session.run(cypher)  │      organizations: ["MIT CSAIL"], ...}]
  └──────┬───────────────┘
         │
         ▼
  ┌──────────────────────┐
  │  ReasoningChainBuilder│ → ReasoningChain (steps + conclusion)
  │  .build_chain()       │
  └──────┬───────────────┘
         │
         ▼
  ┌──────────────────────┐
  │  PromptBuilder       │  → final LLM prompt string
  │  .build_prompt()     │
  └──────────────────────┘
```

### Step-by-step

#### Step 1 — HTTP Entry Point — `app/routes/reasoning.py`

**Function**: `reasoning_query()` (line 27)

```python
@router.post("/query", response_model=ReasoningResponse)
async def reasoning_query(body: ReasoningRequest):
```

- Receives `ReasoningRequest` with `query: str` and optional `vector_results: list[str]`
- Instantiates `GraphReasoningOrchestrator(driver)`
- Calls `orchestrator.process_query(body.query, vector_results=body.vector_results)`
- Returns `ReasoningResponse(prompt, reasoning_type, entities, confidence)`

#### Step 2 — Orchestrator — `app/services/graph_reasoning.py`

**Class**: `GraphReasoningOrchestrator`

**Constructor** (line 46) wires together all sub-services:

```python
self.decomposer       = QueryDecomposer()
self.router           = TemplateRouter()
self.chain_builder    = ReasoningChainBuilder()
self.prompt_builder   = PromptBuilder()
self.entity_resolver  = EntityResolver(driver)
self._scorer          = ConfidenceScorer()
```

**Method**: `process_query(user_query, vector_results?) → str` (line 55)

Executes 7 sub-steps:

#### Step 3 — Query Decomposition — `app/services/query_decomposer.py`

**Class**: `QueryDecomposer`

**Method**: `decompose(query: str) → DecomposedQuery` (line 99)

Sub-steps:

1. `_extract_time_range(query)` — 10 regex patterns (yesterday, today, last week, ISO dates, relative ago, since, before, between)
2. `_detect_aggregation(query)` — keyword scan: `how many→count`, `average→avg`, `most→max`, `top→max`, etc.
3. **Entity extraction** — two-tier:
   - **Primary**: `_extract_entities_spacy(query)` → `list[TypedEntity]` — calls `EntityExtractor.extract_entities_with_labels()` then wraps in `TypedEntity.from_spacy()` for Neo4j label + confidence
   - **Fallback** (if spaCy unavailable): `_extract_entities(query)` → `list[str]` — quoted strings + capitalised sequences (skips common non-entities via `_COMMON_NON_ENTITIES` frozenset)
4. `_classify_intent(query, time_range, agg_fn, entities)` — **priority-ordered** pattern matching:

| Priority | Type            | Detection Method                                                   |
| -------- | --------------- | ------------------------------------------------------------------ |
| 1        | `CAUSAL`        | 7 regex patterns ("why did", "what caused", "what led to", etc.)   |
| 2        | `MULTI_HOP`     | 6 regex patterns ("how does X connect to", "path from X to", etc.) |
| 3        | `TEMPORAL`      | time_range parsed AND no aggregation function                      |
| 4        | `COMPARISON`    | aggregation function AND ≥2 entities                               |
| 5        | `AGGREGATION`   | aggregation function present                                       |
| 6        | `EXPLORATION`   | 7 regex patterns ("explore", "tell me about", etc.)                |
| 7        | `RELATIONSHIP`  | 11 keywords ("related to", "connected to", "works on", etc.)       |
| 8        | `ENTITY_LOOKUP` | entities found but no other intent matched                         |
| 9        | `EXPLORATION`   | true fallback — nothing matched (confidence = 0.35)                |

5. `_estimate_hop_limit(reasoning_type)` — static map: ENTITY_LOOKUP=0, RELATIONSHIP=1, MULTI_HOP=4, CAUSAL=5, EXPLORATION=2
6. `_extract_relationships(query)` — returns matching relationship keywords

**Output**: `DecomposedQuery` dataclass:

```python
DecomposedQuery(
    reasoning_type = ReasoningType.ENTITY_LOOKUP,
    entities       = ["Sarah Chen"],
    relationships  = [],
    time_range     = None,
    aggregation_fn = None,
    hop_limit      = 0,
    confidence     = 0.82,
    entity_types   = ["Person"],  # parallel list from spaCy
)
```

#### Step 4 — Entity Resolution — `app/services/entity_resolver.py`

**Method**: `resolve_with_quality(mention, expected_label?) → (dict | None, MatchQuality)`

For each entity in `decomposed.entities`:

1. Pass `expected_label = decomposed.entity_types[i]` (if available from spaCy)
2. Walk the match cascade (exact → fuzzy → substring)
3. If resolved, replace `decomposed.entities[i]` with `resolved["name"]` (canonical form)
4. Collect `MatchQuality` values for confidence scoring

**Type-aware matching**: when `expected_label` is provided:

- Fuzzy match gets +0.05 score bonus for same-label candidates
- Substring match prefers same-label candidates over untyped matches

#### Step 5 — Template Routing — `app/services/template_router.py`

**Class**: `TemplateRouter`

**Constructor** (line 14): builds a `type_index: dict[ReasoningType, list[str]]` — reverse index from reasoning type to template names.

**Method**: `route(query: DecomposedQuery) → list[tuple[str, str]]` (line 21)

1. Look up candidate templates by `query.reasoning_type` from `type_index`
2. For each candidate, call `_fill_slots(template, query)`:
   - Maps slot names to query data via `_resolve_slot()`:

     | Slot Name                                                                                      | Source                                                               |
     | ---------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
     | `entity_name`, `person_name`, `topic_name`, `search_term`, `entity_a`, `topic_a`, `event_name` | `query.entities[0]`                                                  |
     | `entity_b`, `topic_b`                                                                          | `query.entities[1]`                                                  |
     | `start_time`, `end_time`                                                                       | `query.time_range[0].isoformat()`, `query.time_range[1].isoformat()` |
     | `node_label`                                                                                   | `query.entity_types[0]` or keyword fallback or `"Topic"`             |
     | `limit`                                                                                        | default `10`                                                         |
     | `max_hops`                                                                                     | `query.hop_limit`                                                    |

3. Call `template.render(slots)` → rendered Cypher string (via `string.Template.safe_substitute()`)
4. **Fallback**: if no template matched but entities exist → use `full_neighborhood` template

**Template rendering** (`app/services/cypher_templates.py` line 25):

- `CypherTemplate.render(slots)` — checks required slots, sanitizes strings (escapes `'` and `"`), substitutes via `string.Template`

#### Step 6 — Cypher Template Library — `app/services/cypher_templates.py`

19 templates in `CYPHER_TEMPLATES` dict, grouped by `ReasoningType`:

| Category          | Template Names                                                                   | Required Slots                               |
| ----------------- | -------------------------------------------------------------------------------- | -------------------------------------------- |
| **Entity Lookup** | `entity_lookup_person`, `entity_lookup_topic`, `entity_lookup_document`          | `entity_name` / `topic_name` / `search_term` |
| **Relationship**  | `person_connections`, `documents_about_topic`                                    | `person_name` / `topic_name`                 |
| **Exploration**   | `topic_neighborhood`, `full_neighborhood`, `community_detection`                 | `topic_name` / `entity_name`                 |
| **Multi-hop**     | `shortest_path_entities`, `all_paths_between`                                    | `entity_a`, `entity_b`                       |
| **Aggregation**   | `count_by_topic`, `top_entities_by_mentions`, `content_stats`, `pagerank_topics` | `node_label` or none                         |
| **Temporal**      | `documents_in_timerange`, `activity_timeline`                                    | `start_time`, `end_time`                     |
| **Comparison**    | `compare_topics`                                                                 | `topic_a`, `topic_b`                         |
| **Causal**        | `temporal_chain`, `event_causal_chain`                                           | `entity_name` / `event_name`                 |

#### Step 7 — Cypher Execution (inside `graph_reasoning.py` line 103)

```python
with self.driver.session() as session:
    for tmpl_name, cypher in cypher_queries:
        result = session.run(cypher)
        records = [dict(record) for record in result]
        all_results.extend(records)
```

Multiple templates can fire for the same query (e.g., both `entity_lookup_person` and `entity_lookup_topic` for an entity lookup), and all results are merged.

#### Step 8 — Reasoning Chain Construction — `app/services/reasoning_chain_builder.py`

**Class**: `ReasoningChainBuilder`

**Method**: `build_chain(query, reasoning_type, cypher_results) → ReasoningChain` (line 22)

Dispatches to 9 type-specific builders:

| Builder                     | Logic                                                                                                                                                                                                                                     |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `_build_entity_chain`       | **Step 1**: lookup evidence from first result (all non-empty k/v pairs). **Step 2**: connection fields (`organizations`, `expertise`, `projects`, `related_topics`, `subtopics`, `topics`). Conclusion summarizes identity + connections. |
| `_build_relationship_chain` | Each result (max 10) → one `traverse` step. Evidence = `[f"{k}: {v}"]` for each field.                                                                                                                                                    |
| `_build_multi_hop_chain`    | Parses `path_nodes`/`path_relationships` from results. Evidence = `"source —[REL]→ target"` per hop. Conclusion = total path length.                                                                                                      |
| `_build_aggregation_chain`  | Each result → one `aggregate` step. All k/v pairs as evidence items. Conclusion = top-ranked result.                                                                                                                                      |
| `_build_temporal_chain`     | Groups documents by topics, identifies most active topic. Steps: 1 per result. Conclusion = most active topic.                                                                                                                            |
| `_build_comparison_chain`   | Requires ≥2 results. Compares numeric keys between results. Finds "winner" per metric. Conclusion = overall winner.                                                                                                                       |
| `_build_causal_chain`       | Sequential `infer` steps (one per result). Evidence = k/v pairs. Conclusion = inferred causal sequence.                                                                                                                                   |
| `_build_exploration_chain`  | Groups results by `rel_type` field. One step per relationship type. Conclusion = total unique connections.                                                                                                                                |
| `_build_generic_chain`      | Fallback — each result as one step.                                                                                                                                                                                                       |

**Output**: `ReasoningChain` dataclass with:

- `query`, `reasoning_type`, `steps[]`, `conclusion`, `evidence_summary`, `total_confidence`, `source_count`

Confidence is computed algorithmically:

```python
signals = ConfidenceSignals(
    result_count=len(cypher_results),
    expected_result_count=max(len(cypher_results), 1),
    evidence_completeness=self._measure_completeness(cypher_results),
)
chain.total_confidence = self._scorer.chain_confidence(signals)
```

#### Step 9 — Vector Enrichment Gate (line 115 of `graph_reasoning.py`)

If `pipeline_confidence < 0.45` AND `vector_results` are available:

- Append supplementary context as an extra `ReasoningStep` (operation="lookup")
- Evidence = first 3 vector search chunks
- Confidence = entity resolution confidence from signals

This is the **hybrid RAG fallback** — only activates when the graph path is weak.

#### Step 10 — Prompt Construction — `app/services/prompt_builder.py`

**Class**: `PromptBuilder`

**Method**: `build_prompt(chain, user_query) → str` (line 41)

1. Call `chain.to_llm_prompt_context()` — formats the chain as structured text:

```
QUERY: Who is Sarah Chen?
REASONING TYPE: entity_lookup
CONFIDENCE: 82%
SOURCES: 1 items analyzed

REASONING CHAIN:
  Step 1 [lookup]: Found entity matching query.
    • canonical_name: Sarah Chen
    • email: sarah.chen@mit.edu
    • role: Lead Researcher
    • organizations: ['MIT CSAIL']
    • expertise: ['transformer architectures']
    • projects: ['Project Atlas']
  Step 2 [traverse]: Connected to 3 relationships.
    • organizations: MIT CSAIL
    • expertise: transformer architectures
    • projects: Project Atlas

CONCLUSION: Sarah Chen is a Lead Researcher at MIT CSAIL...

EVIDENCE SUMMARY: ...
```

2. Truncate if > 800 words (`_truncate_context()` — preserves structural markers like CONCLUSION, REASONING CHAIN, Step, etc.)

3. Assemble final prompt:

```
{SYSTEM_PROMPT}

---
{context}
---

USER QUESTION: {user_query}

RESPONSE:
```

**System prompt** (7 rules): instructs the LLM to ONLY narrate pre-computed answers, not add information, use bullet points for lists, mention source counts, say "I'm not fully certain, but..." when confidence < 50%.

**Fallback**: `build_fallback_prompt(user_query, vector_results)` — standard RAG with `[Source N]` format, used when no Cypher template matched at all.

---

## Data Models

All models live in `app/models/reasoning.py`:

### `ReasoningType` (Enum)

```
ENTITY_LOOKUP | RELATIONSHIP | MULTI_HOP | AGGREGATION
TEMPORAL | COMPARISON | CAUSAL | EXPLORATION
```

### `DecomposedQuery` (Dataclass)

| Field            | Type                                | Description                                      |
| ---------------- | ----------------------------------- | ------------------------------------------------ |
| `reasoning_type` | `ReasoningType`                     | Classified intent                                |
| `entities`       | `list[str]`                         | Extracted entity names                           |
| `relationships`  | `list[str]`                         | Matched relationship keywords                    |
| `time_range`     | `tuple[datetime, datetime] \| None` | Parsed temporal bounds                           |
| `aggregation_fn` | `str \| None`                       | Aggregation function (count/sum/avg/max/min)     |
| `hop_limit`      | `int`                               | Max graph traversal depth                        |
| `confidence`     | `float`                             | Classification confidence                        |
| `entity_types`   | `list[str]`                         | Neo4j labels from spaCy (parallel to `entities`) |

### `ReasoningStep` (Dataclass)

| Field         | Type        | Description                                                             |
| ------------- | ----------- | ----------------------------------------------------------------------- |
| `step_number` | `int`       | Sequential step number                                                  |
| `operation`   | `str`       | One of: `"lookup"`, `"traverse"`, `"compare"`, `"aggregate"`, `"infer"` |
| `description` | `str`       | Human-readable step description                                         |
| `evidence`    | `list[str]` | Evidence items supporting this step                                     |
| `confidence`  | `float`     | Step-level confidence                                                   |

### `ReasoningChain` (Dataclass)

| Field              | Type                  | Description              |
| ------------------ | --------------------- | ------------------------ |
| `query`            | `str`                 | Original user query      |
| `reasoning_type`   | `str`                 | Classification result    |
| `steps`            | `list[ReasoningStep]` | Ordered reasoning steps  |
| `conclusion`       | `str`                 | Pre-computed answer      |
| `evidence_summary` | `str`                 | Summary of evidence      |
| `total_confidence` | `float`               | Pipeline-wide confidence |
| `source_count`     | `int`                 | Number of graph results  |

---

## Startup Sequence

Defined in `app/main.py` lifespan context manager (line 105):

```
1. init_driver()                  → Neo4j bolt connection
2. ensure_schema(driver)          → 12 constraints, 14 indexes, 3 fulltext indexes
3. EntityResolver(driver)
4. resolver.refresh_cache()       → load all entity names + aliases into memory
5. Include reasoning router       → /reasoning/query, /reasoning/ingest, /reasoning/stats
```

### Graph Schema — `app/services/graph_schema.py`

**Function**: `ensure_schema(driver)` — idempotent (all `IF NOT EXISTS`)

- **12 uniqueness constraints**: Document, Chunk, Person, Topic, Concept, Project, Event, Folder, Organization, Location, Tag, Task — all on `.id` (Folder on `.path`)
- **14 B-tree indexes**: doc hash/path/modified, chunk doc/hash/qdrant, person name, topic name, concept name, event time, task status, project status, org name, location name
- **3 fulltext indexes**: chunk content, doc title+summary, person canonical_name

---

## Confidence Scoring — `app/services/confidence.py`

All confidence values are **algorithmically derived**, never hardcoded:

### `MatchQuality` (Enum) — entity resolution strength

| Value       | Score | Meaning                               |
| ----------- | ----- | ------------------------------------- |
| `EXACT`     | 1.0   | Case-insensitive exact or alias match |
| `ALIAS`     | 0.95  | Matched via known alias               |
| `FUZZY`     | 0.75  | SequenceMatcher > 0.85                |
| `SUBSTRING` | 0.55  | Partial string containment            |
| `CREATED`   | 0.3   | No match — created new node           |
| `MISS`      | 0.0   | No match, not created                 |

### `ConfidenceScorer` methods

| Method                                  | Formula                                                                                |
| --------------------------------------- | -------------------------------------------------------------------------------------- |
| `classification_confidence(signals)`    | Based on pattern specificity (matches/checked), fallback=0.35                          |
| `entity_resolution_confidence(signals)` | Geometric mean of all `MatchQuality` scores                                            |
| `result_confidence(signals)`            | `min(result_count / expected, 1.0) × evidence_completeness`                            |
| `path_confidence(signals)`              | `max(0.95^path_length, 0.40)` — exponential decay                                      |
| `chain_confidence(signals)`             | `gate × 0.4 + result_conf × 0.6` where `gate = min(classification, entity_resolution)` |
| `step_confidence(record)`               | Fraction of non-empty fields in a result dict                                          |

---

## File Reference Index

| File                                          | Key Class/Function                                   | Role                                                    |
| --------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------- |
| `app/routes/reasoning.py`                     | `reasoning_query()`, `ingest_document()`             | HTTP API endpoints                                      |
| `app/services/graph_reasoning.py`             | `GraphReasoningOrchestrator`                         | Top-level pipeline orchestrator                         |
| `app/services/query_decomposer.py`            | `QueryDecomposer.decompose()`                        | Rule-based intent classification + entity extraction    |
| `app/services/entity_resolver.py`             | `EntityResolver`                                     | Deterministic entity resolution (exact/fuzzy/substring) |
| `app/services/template_router.py`             | `TemplateRouter.route()`                             | Maps DecomposedQuery → Cypher templates                 |
| `app/services/cypher_templates.py`            | `CYPHER_TEMPLATES`, `CypherTemplate`                 | 19 parameterised Cypher queries                         |
| `app/services/reasoning_chain_builder.py`     | `ReasoningChainBuilder.build_chain()`                | Transforms Neo4j results → structured reasoning         |
| `app/services/prompt_builder.py`              | `PromptBuilder.build_prompt()`                       | Assembles final LLM prompt (<1500 tokens)               |
| `app/services/graph_updater.py`               | `GraphUpdater.ingest_document()`                     | Document → Neo4j graph population                       |
| `app/services/graph_schema.py`                | `ensure_schema()`                                    | Schema DDL at startup                                   |
| `app/services/confidence.py`                  | `ConfidenceScorer`, `ConfidenceSignals`              | Algorithmic confidence from real signals                |
| `app/services/label_mapping.py`               | `SPACY_TO_NEO4J`, `TypedEntity`                      | spaCy label → Neo4j label mapping                       |
| `app/services/processing/entity_extractor.py` | `EntityExtractor`                                    | spaCy NER wrapper                                       |
| `app/models/reasoning.py`                     | `DecomposedQuery`, `ReasoningChain`, `ReasoningStep` | Core data models                                        |
| `app/config.py`                               | `settings`                                           | Pydantic Settings (Neo4j URI, Qdrant, spaCy model)      |
| `app/main.py`                                 | `lifespan()`                                         | FastAPI startup/shutdown lifecycle                      |
