# Qdrant Architecture & Embedding Models

## Overview

This document describes the **text-centric multimodal** Qdrant architecture. The system converts ALL content types (text, images, audio) to text first, then embeds with a **single model** (MiniLM 384-dim) into a **single vector space**. This enables unified cross-modal search, entity extraction across all content, and knowledge graph construction.

> **Key Architectural Decision:** Replaced the previous multi-vector approach (DINOv2 1024-dim + SigLIP 1152-dim + MiniLM 384-dim) with a single text-centric vector. This trades some image-to-image visual similarity capability for unified search, entity extraction, and graph construction across all modalities.

## Architecture: Text-Centric Single Vector

```
              ALL MODALITIES → TEXT → SINGLE EMBEDDING

Text files ──────────────────────────────────────────→ text chunks
Images ──→ BLIP caption + OCR ──→ text description ─→ text chunks
Audio  ──→ Whisper transcription ──→ transcript ────→ text chunks
PDFs   ──→ PyMuPDF extraction ──→ text content ────→ text chunks
                                                         │
                                                         ▼
                                               MiniLM embed (384-dim)
                                                         │
                                                         ▼
                                              Qdrant: text_vector
                                          (single collection, single vector)
```

### Collection Structure

```
Collection: "multimodal_embeddings"
├── Single Vector:
│   └── text_vector (384-dim, COSINE, HNSW)
│       → ALL content types in the same space
│
├── Payload Fields (keyword indexed):
│   ├── content_type: "text" | "image" | "audio"  ← filter by modality
│   ├── file_type: extension/format
│   ├── source_path: original file location
│   ├── content_hash: SHA-256 for deduplication
│   ├── parent_doc_id: document UUID
│   └── chunk_text, tags, extracted_entities, etc.
│
└── HNSW Index Configuration:
    ├── M: 16 (connections per node)
    ├── ef_construct: 200 (index quality)
    └── Distance: Cosine similarity
```

## Models

### 1. Text Embedding — THE ONLY EMBEDDING MODEL (384-dim)

**Model**: `sentence-transformers/all-MiniLM-L6-v2`

**Usage**: Embeds ALL content after text conversion:
- Text document chunks (direct)
- Image captions + OCR text (from BLIP/Tesseract)
- Audio transcripts (from Whisper)

**Characteristics**:
- Lightweight and fast (~23M parameters)
- Optimized for semantic similarity
- CPU-friendly for local deployment
- L2 normalized for cosine similarity

**Implementation**: [`app/services/embeddings/text_strategy.py`](../app/services/embeddings/text_strategy.py)

---

### 2. Image Captioning (text extraction, not embedding)

**Model**: `Salesforce/blip-image-captioning-base`

**Usage**: Generate natural language descriptions of images
- Converts images to text for the unified pipeline
- NOT an embedding model — produces text that MiniLM then embeds

**Characteristics**:
- ~247M parameters (BlipForConditionalGeneration)
- Conditional captioning with prompt "a photograph of"
- Lazy-loaded on first image ingestion
- CPU OK, GPU faster

**Implementation**: [`app/services/processing/text_extractor.py`](../app/services/processing/text_extractor.py) → `ImageTextExtractor`

---

### 3. OCR (text extraction from images)

**Tool**: Tesseract OCR (optional — disabled if not installed)

**Usage**: Extract visible text from images
- Complements BLIP captions with literal text content
- Grayscale + Otsu thresholding preprocessing

**Implementation**: [`app/services/processing/text_extractor.py`](../app/services/processing/text_extractor.py) → `ImageTextExtractor.perform_ocr()`

---

### 4. Speech-to-Text (text extraction from audio)

**Model**: `openai/whisper-base`

**Usage**: Transcribe audio files to text
- Converts speech to text for the unified pipeline
- Automatic resampling from any sample rate to 16kHz mono

**Characteristics**:
- ~74M parameters (CPU-friendly)
- Two-stage: transcribe → then embed transcript with MiniLM
- Lazy-loaded on first audio ingestion

**Implementation**: [`app/services/embeddings/audio_strategy.py`](../app/services/embeddings/audio_strategy.py)

---

### 5. Entity Extraction (for knowledge graph)

**Model**: `spaCy en_core_web_sm`

**Usage**: NER + relationship extraction from ALL text content
- Named entities: PERSON, ORG, GPE, LOC, DATE, etc.
- Relationships: Subject → Predicate → Object triples via dependency parsing
- Used for Neo4j knowledge graph construction

**Characteristics**:
- ~12M parameters
- Dependency parsing for S→P→O triple extraction
- Noun phrase expansion for richer entities

**Implementation**: [`app/services/processing/entity_extractor.py`](../app/services/processing/entity_extractor.py)

---

### REMOVED Models (no longer used)

- ~~`facebook/dinov2-large`~~ (1024-dim image embeddings) — replaced by BLIP caption → MiniLM
- ~~`google/siglip-so400m-patch14-384`~~ (1152-dim text-to-image) — replaced by BLIP caption → MiniLM
- Legacy files still exist in `app/services/embeddings/` but are not imported

---

## Vector Storage Schema

### Unified Collection: `multimodal_embeddings`

Each point in Qdrant stores:

```python
{
  "id": "uuid-v4",
  "vector": {
    "text_vector": [384-dim float array]  # SINGLE vector for ALL content
  },
  "payload": {
    # Core fields (all content types)
    "source_path": "/path/to/file.ext",
    "content_type": "text" | "image" | "audio",
    "file_type": "txt" | "png" | "wav" | ...,
    "chunk_index": 0,
    "chunk_text": "actual text / caption+OCR / transcript",
    "content_hash": "sha256-hash",
    "parent_doc_id": "parent-uuid",
    "file_size": 12345,
    "creation_date": "2025-01-15T08:00:00Z",
    "last_modified": "2025-02-10T14:30:00Z",
    "tags": ["tag1", "tag2"],
    "extracted_entities": ["Entity1", "Entity2"],

    # Image-specific (when content_type="image")
    "image_width": 384,
    "image_height": 384,
    "exif_data": {...},
    "ocr_text": "text extracted from image",
    "caption": "a photograph of a red car on a road",

    # Audio-specific (when content_type="audio")
    "audio_duration": 33.62,
    "sample_rate": 16000,
    "transcript": "full audio transcript"
  }
}
```

### Payload Indexes

For efficient filtering, the following fields are keyword-indexed:

- `content_type` — **Critical** for filtering by modality (text/image/audio)
- `file_type` — filter by file extension
- `content_hash` — for differential update lookups
- `parent_doc_id` — group chunks from same file
- `source_path` — find all content from a file

## Search Operations

### 1. Unified Search (ALL modalities)

```python
# Single query searches text, images, AND audio
results = qdrant_manager.search_unified(
    query_text="cat sitting on a couch",
    limit=10,
)
```

**Process**:
1. Embed query with MiniLM → 384-dim vector
2. Search `text_vector` across ALL points
3. Return ranked results (may include text, image, and audio hits)

**API**: `POST /search` with `{"query": "...", "limit": 10}`

---

### 2. Filtered Search (by content type)

```python
# Search only images
results = qdrant_manager.search_unified(
    query_text="sunset over mountains",
    content_types=["image"],
    limit=10,
)

# Search only audio transcripts
results = qdrant_manager.search_unified(
    query_text="speech about technology",
    content_types=["audio"],
    limit=10,
)
```

**Process**:
1. Embed query with MiniLM → 384-dim vector
2. Filter by `content_type` field (MatchValue or MatchAny)
3. Search `text_vector` with filter applied
4. Return results of specified type only

**API**: `POST /search/by-type/{content_type}` with `{"query": "...", "limit": 10}`

---

### 3. Filter by Source or Entity

```python
# Find all content from a specific file
results = qdrant_manager.client.scroll(
    collection_name="multimodal_embeddings",
    scroll_filter={"must": [{"key": "source_path", "match": {"value": "/path/to/file"}}]},
)

# Find all content mentioning an entity
results = qdrant_manager.client.scroll(
    collection_name="multimodal_embeddings",
    scroll_filter={"must": [{"key": "extracted_entities", "match": {"any": ["entity"]}}]},
)
```

**API**: `GET /search/filters/by-source?source_path=...` and `GET /search/filters/by-entity?entity=...`

---

## HNSW Index Configuration

**Algorithm**: Hierarchical Navigable Small World (HNSW)

**Parameters**:
- `M = 16`: Number of bi-directional links per node
- `ef_construct = 200`: Size of dynamic candidate list during construction
- `Distance Metric`: Cosine similarity (works with normalized MiniLM embeddings)

**Search Performance**:
- Sub-millisecond for collections <100k points
- ~10-50ms for 1M+ points
- Approximate nearest neighbor

---

## Content Processing Pipeline

### Text Documents

```
Text File → TextProcessor
  ├─> Semantic chunking (512 tokens, 50 overlap)
  ├─> Content hashing (SHA-256)
  ├─> Entity extraction (spaCy NER)
  └─> TextChunk objects
        ↓
  TextEmbeddingStrategy (MiniLM) → 384-dim
        ↓
  Qdrant.upsert_text_chunks() → text_vector
```

### Images

```
Image File → ImageProcessor
  ├─> BLIP captioning → "a photograph of a red car..."
  ├─> Tesseract OCR (optional) → visible text
  ├─> Extract EXIF metadata
  ├─> Content hashing
  ├─> Entity extraction from caption+OCR text
  └─> ImageData object (chunk_text = caption + OCR)
        ↓
  TextEmbeddingStrategy (MiniLM on caption+OCR) → 384-dim
        ↓
  Qdrant.upsert_image() → text_vector (same space as text!)
```

### Audio Files

```
Audio File → AudioProcessor
  ├─> Whisper transcription → full transcript text
  ├─> Resampling if needed (e.g. 8kHz → 16kHz)
  ├─> Semantic chunking of transcript
  ├─> Content hashing
  ├─> Entity extraction from transcript
  └─> AudioChunk objects
        ↓
  TextEmbeddingStrategy (MiniLM on transcript) → 384-dim
        ↓
  Qdrant.upsert_audio_chunks() → text_vector (same space!)
```

---

## Unified Text Extraction Layer

The `UnifiedTextExtractor` in [`app/services/processing/text_extractor.py`](../app/services/processing/text_extractor.py) is the core of the text-centric architecture:

```
UnifiedTextExtractor
├── classify(file_path)         → "text" | "image" | "audio" | "pdf"
├── extract(file_path)          → dispatches to correct extractor
│   ├── ImageTextExtractor      → BLIP caption + Tesseract OCR → text
│   ├── AudioTextExtractor      → Whisper transcription → text
│   ├── PDFTextExtractor        → PyMuPDF extraction → text
│   └── PlainTextExtractor      → direct file read → text
└── extract_from_text(text)     → pass-through for direct content
```

**File type classification**:
- Text: `.txt`, `.md`, `.py`, `.js`, `.ts`, `.java`, `.json`, `.yaml`, etc.
- Images: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.tiff`
- Audio: `.mp3`, `.wav`, `.m4a`, `.flac`, `.ogg`, `.aac`, `.wma`, `.opus`
- PDF: `.pdf`

---

## Data Models

### Core Data Structures

See [`app/models/models.py`](../app/models/models.py):

- `VectorPayload`: Standard payload for all Qdrant points
- `TextChunk`: Processed text ready for embedding
- `ImageData`: Processed image with metadata, caption, OCR
- `AudioChunk`: Processed audio transcript chunk
- `SearchResult`: Search result with score and payload

### Processing Flow

```
File → UnifiedTextExtractor → text → Processor → DataModel → MiniLM → Qdrant
```

---

## Differential Updates

1. **Content Hashing**: SHA-256 hash of file content
2. **Hash Lookup**: `qdrant_manager.search_by_hash()` checks if hash exists
3. **Skip or Update**:
   - If hash exists → Skip processing (file unchanged)
   - If new/changed → Process and upsert
4. **Cleanup**: Delete old entries for modified files

---

## Configuration

All settings via [`app/config.py`](../app/config.py) or environment variables:

```bash
# Qdrant Connection
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Models
TEXT_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
IMAGE_CAPTIONING_MODEL=Salesforce/blip-image-captioning-base
SPEECH_MODEL=openai/whisper-base

# Processing
TEXT_CHUNK_SIZE=512
TEXT_CHUNK_OVERLAP=50
MAX_FILE_SIZE_MB=100

# Single vector dimension
TEXT_EMBEDDING_DIM=384

# Collection
UNIFIED_COLLECTION=multimodal_embeddings

# HNSW
HNSW_M=16
HNSW_EF_CONSTRUCT=200
```

---

## Performance Characteristics

### Model Sizes

| Model | Parameters | Output | Device | Purpose |
|-------|-----------|--------|--------|---------|
| MiniLM-L6-v2 | 23M | 384-dim vector | CPU/GPU | **Single embedding model** |
| BLIP Base | 247M | text caption | CPU/GPU | Image → text |
| Whisper Base | 74M | text transcript | CPU/GPU | Audio → text |
| spaCy sm | 12M | entities/triples | CPU | NER + relations |

### Storage

- **Text**: ~1.5KB per chunk (384-dim vector + payload)
- **Image**: ~1.5KB per image (384-dim vector + metadata + caption)
- **Audio**: ~1.5KB per transcript chunk (384-dim vector + transcript)

---

## API Endpoints

### Ingestion

```bash
# Ingest text
curl -X POST http://localhost:8000/ingest/text \
  -F "content=Vector databases store embeddings..." \
  -F "tags=ml,databases"

# Ingest images from directory
curl -X POST http://localhost:8000/ingest/directory \
  -H "Content-Type: application/json" \
  -d '{"directory_path": "/path/to/images", "file_patterns": ["*.png", "*.jpg"]}'

# Ingest audio from directory
curl -X POST http://localhost:8000/ingest/directory \
  -H "Content-Type: application/json" \
  -d '{"directory_path": "/path/to/audio", "file_patterns": ["*.wav", "*.mp3"]}'
```

### Search

```bash
# Unified search (returns ALL content types)
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "cat sitting", "limit": 5}'

# Search only images
curl -X POST http://localhost:8000/search/by-type/image \
  -H "Content-Type: application/json" \
  -d '{"query": "red car", "limit": 5}'

# Search only audio
curl -X POST http://localhost:8000/search/by-type/audio \
  -H "Content-Type: application/json" \
  -d '{"query": "speech about technology", "limit": 5}'
```

---

## Implementation Files

- **Qdrant Manager**: [`app/services/storage/qdrant_manager.py`](../app/services/storage/qdrant_manager.py) — single `text_vector`, `search_unified()`
- **Text Extraction Layer**: [`app/services/processing/text_extractor.py`](../app/services/processing/text_extractor.py) — ★ core of text-centric arch
- **Text Embedding**: [`app/services/embeddings/text_strategy.py`](../app/services/embeddings/text_strategy.py) — MiniLM (only embedding model)
- **Audio Transcription**: [`app/services/embeddings/audio_strategy.py`](../app/services/embeddings/audio_strategy.py) — Whisper
- **Entity Extraction**: [`app/services/processing/entity_extractor.py`](../app/services/processing/entity_extractor.py) — spaCy NER + relationships
- **Image Processing**: [`app/services/processing/image_processor.py`](../app/services/processing/image_processor.py) — delegates to ImageTextExtractor
- **Search Routes**: [`app/routes/search_routes.py`](../app/routes/search_routes.py) — unified + filtered endpoints
- **Ingest Routes**: [`app/routes/ingest_routes.py`](../app/routes/ingest_routes.py) — text, image, audio, directory
- **Configuration**: [`app/config.py`](../app/config.py)
- **Legacy (unused)**: `image_strategy.py` (DINOv2), `caption_strategy.py` (SigLIP)

---

## Future Enhancements

1. **Neo4j Integration**: Link entities/relationships to knowledge graph for reasoning
2. **Sparse Embeddings**: Add BM25 for hybrid retrieval
3. **Quantization**: 8-bit vector storage for 4x compression
4. **Reranking**: Two-stage retrieval with cross-encoder reranking
5. **Video Support**: Frame sampling → BLIP captioning → text → embed
6. **PDF Advanced**: Layout-aware chunking with figure extraction
7. **Better Captioning**: Replace BLIP-base with BLIP-2 or LLaVA for richer descriptions

---

## Summary

The architecture uses a **text-centric single-vector** approach:

✅ **Single collection** `multimodal_embeddings` for all content types
✅ **Single vector** `text_vector` (384-dim MiniLM) for all modalities
✅ **All content → text first** (BLIP captions, Whisper transcripts, OCR)
✅ **One query searches everything** — text, images, and audio simultaneously
✅ **Entity extraction** works on all content (enables knowledge graph)
✅ **Content-type filtering** via indexed `content_type` payload field
✅ **Differential updates** via SHA-256 content hashing
✅ **Lazy model loading** — BLIP/Whisper/spaCy load on first use, not startup
✅ **Low memory footprint** — ~23M MiniLM always loaded; 247M BLIP + 74M Whisper only when needed
