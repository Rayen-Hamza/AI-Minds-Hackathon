"""Neo4j-only ingestion script for sample ontological relation files.

Reads text files, extracts entities via spaCy, chunks text,
and writes to Neo4j via GraphUpdater. No Qdrant involved.
"""

import hashlib
import os
import sys
import uuid

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from neo4j import GraphDatabase

from app.services.entity_resolver import EntityResolver
from app.services.graph_updater import GraphUpdater
from app.services.label_mapping import TypedEntity
from app.services.processing.entity_extractor import EntityExtractor
from app.services.graph_schema import ensure_schema


# ── Config ───────────────────────────────────────────────────────────

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "changeme")

CHUNK_SIZE = 500  # characters per chunk
CHUNK_OVERLAP = 50

FILES = [
    "/app/tests/sample_onthological_relation1.txt",
    "/app/tests/sample_onthological_relation2.txt",
]


# ── Helpers ──────────────────────────────────────────────────────────


def chunk_text(
    text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[dict]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunk_content = text[start:end]
        chunk_id = str(uuid.uuid4())
        chunks.append(
            {
                "id": chunk_id,
                "content": chunk_content,
                "chunk_index": idx,
                "content_hash": hashlib.sha256(chunk_content.encode()).hexdigest(),
                "qdrant_point_id": chunk_id,  # placeholder, not used by Neo4j
            }
        )
        idx += 1
        start = end - overlap if end < len(text) else end
    return chunks


def extract_topics(text: str) -> list[str]:
    """Simple keyword-based topic extraction (no LLM needed)."""
    topic_keywords = {
        "AI": [
            "artificial intelligence",
            "machine learning",
            "deep learning",
            "neural network",
            "AI",
        ],
        "Technology": ["technology", "software", "hardware", "computing", "digital"],
        "Science": ["science", "research", "experiment", "hypothesis", "theory"],
        "Education": [
            "education",
            "university",
            "school",
            "learning",
            "student",
            "professor",
        ],
        "Business": ["business", "company", "corporation", "enterprise", "startup"],
        "Politics": ["politics", "government", "policy", "election", "legislation"],
        "Healthcare": [
            "health",
            "medical",
            "hospital",
            "disease",
            "treatment",
            "patient",
        ],
        "Environment": [
            "environment",
            "climate",
            "pollution",
            "sustainability",
            "conservation",
        ],
        "Finance": ["finance", "banking", "investment", "economy", "market"],
        "Culture": ["culture", "art", "music", "literature", "film"],
    }
    lower = text.lower()
    found = []
    for topic, keywords in topic_keywords.items():
        if any(kw.lower() in lower for kw in keywords):
            found.append(topic)
    return found or ["General"]


# ── Main ─────────────────────────────────────────────────────────────


def main():
    print(f"Connecting to Neo4j at {NEO4J_URI} ...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    # Verify connectivity
    driver.verify_connectivity()
    print("  Connected.")

    # Wipe existing data
    print("Wiping existing graph data ...")
    with driver.session() as session:
        result = session.run("MATCH (n) DETACH DELETE n")
        summary = result.consume()
        print(
            f"  Deleted {summary.counters.nodes_deleted} nodes, "
            f"{summary.counters.relationships_deleted} relationships."
        )

    # Ensure schema (constraints, indexes)
    print("Ensuring graph schema ...")
    ensure_schema(driver)
    print("  Schema ready.")

    # Set up resolver and updater
    resolver = EntityResolver(driver)
    updater = GraphUpdater(driver, resolver)

    # Set up spaCy entity extractor
    print("Loading spaCy model ...")
    extractor = EntityExtractor()
    _ = extractor.nlp  # force load
    print("  spaCy loaded.")

    total_entities = 0
    total_chunks = 0
    total_topics = 0

    for file_path in FILES:
        if not os.path.exists(file_path):
            print(f"  SKIP: {file_path} not found")
            continue

        print(f"\n{'=' * 60}")
        print(f"Ingesting: {file_path}")
        print(f"{'=' * 60}")

        # Read file
        with open(file_path) as f:
            text = f.read()
        print(f"  File size: {len(text)} chars")

        # Generate doc ID
        filename = os.path.basename(file_path)
        doc_id = hashlib.sha256(file_path.encode()).hexdigest()[:16]
        content_hash = hashlib.sha256(text.encode()).hexdigest()

        # Chunk text
        chunks = chunk_text(text)
        print(f"  Chunks: {len(chunks)}")
        total_chunks += len(chunks)

        # Extract entities with spaCy
        labeled = extractor.extract_entities_with_labels(text)
        print(f"  Raw spaCy entities: {len(labeled)}")

        # Convert to typed entities, filtering out None (skipped labels)
        typed_entities = []
        for ent in labeled:
            typed = TypedEntity.from_spacy(ent["text"], ent["label"])
            if typed is not None:
                typed_entities.append(typed)
        print(f"  After filtering junk labels: {len(typed_entities)}")

        # Deduplicate by (text, neo4j_label)
        seen = set()
        unique_entities = []
        for te in typed_entities:
            key = (te.text.lower().strip(), te.neo4j_label)
            if key not in seen:
                seen.add(key)
                unique_entities.append(te)
        print(f"  Unique entities: {len(unique_entities)}")
        total_entities += len(unique_entities)

        # Show entity breakdown
        from collections import Counter

        label_counts = Counter(e.neo4j_label for e in unique_entities)
        for label, count in label_counts.most_common():
            print(f"    {label}: {count}")

        # Extract topics
        topics = extract_topics(text)
        print(f"  Topics: {topics}")
        total_topics += len(topics)

        # Convert entities to payload dicts for GraphUpdater
        entity_payloads = [e.to_entity_payload_dict() for e in unique_entities]

        # Ingest into Neo4j
        updater.ingest_document(
            doc_id=doc_id,
            title=filename,
            file_path=file_path,
            content_hash=content_hash,
            chunks=chunks,
            extracted_entities=entity_payloads,
            topics=topics,
        )
        print(f"  ✓ Ingested into Neo4j")

    # Compute topic relationships and importance scores
    print(f"\nComputing topic relationships ...")
    updater.compute_topic_relationships()
    print(f"Computing importance scores ...")
    updater.compute_importance_scores()

    # Refresh resolver cache
    print(f"Refreshing entity resolver cache ...")
    resolver.refresh_cache()
    print(f"  Cache has {len(resolver._entity_cache)} entities")

    # Final stats
    print(f"\n{'=' * 60}")
    print(f"INGESTION COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Files ingested: {len(FILES)}")
    print(f"  Total chunks:   {total_chunks}")
    print(f"  Total entities: {total_entities}")
    print(f"  Total topics:   {total_topics}")

    # Quick verification query
    print(f"\nVerification queries:")
    with driver.session() as session:
        for query, desc in [
            (
                "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC",
                "Node counts",
            ),
            (
                "MATCH ()-[r]->() RETURN type(r) AS rel, count(r) AS cnt ORDER BY cnt DESC",
                "Relationship counts",
            ),
            (
                "MATCH (p:Person) RETURN p.canonical_name AS name LIMIT 10",
                "Sample persons",
            ),
            ("MATCH (t:Topic) RETURN t.name AS name LIMIT 10", "Sample topics"),
        ]:
            print(f"\n  {desc}:")
            for rec in session.run(query):
                print(f"    {dict(rec)}")

    driver.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
