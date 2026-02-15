# Qdrant Memory Service

A **text-centric multimodal** vector store service for grounded memory and reasoning systems. Handles **text, images, and audio** by converting ALL content to text first, then embedding with a single model into a unified vector space. Built on Qdrant for efficient semantic search with differential updates via content hashing.

> **Architecture Philosophy:** "False multimodality" — every modality is converted to text (captions, transcripts, OCR) before embedding. This enables: (1) unified cross-modal search with a single vector, (2) entity extraction and relationship mining across all content types, and (3) knowledge graph construction via Neo4j for reasoning.

## Features

✨ **Text-Centric Multimodal Support**
- 📝 **Text** (TXT, MD, PDF, code files) → chunked and embedded directly
- 🖼️ **Images** (PNG, JPG, etc.) → BLIP captioning + Tesseract OCR → text → embedded
- 🎵 **Audio** (WAV, MP3, etc.) → Whisper transcription → text → embedded

🔍 **Unified Search**
- Single vector space for ALL content types (384-dim MiniLM)
- One query searches text, images, and audio simultaneously
- Filter by content type: `/search/by-type/{text|image|audio}`
- Filter by source file or extracted entity

⚡ **Smart Processing**
- Differential updates via content hashing (skip unchanged files)
- Automatic text chunking with configurable overlap
- NER entity extraction (spaCy) for knowledge graph construction
- Relationship extraction (subject → predicate → object triples)
- BLIP image captioning (Salesforce/blip-image-captioning-base)
- Whisper speech-to-text (openai/whisper-base)
- Tesseract OCR for text in images (optional)

🏗️ **Architecture**
- **Single embedding model** — `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
- **Single Qdrant collection** — `multimodal_embeddings` with one `text_vector`
- **Unified text extraction layer** — converts any modality to text
- Strategy Pattern for modality-specific processing
- Lazy model loading (BLIP, Whisper, spaCy load on first use)
- HNSW indexing for fast similarity search

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │              Ingestion Pipeline              │
                    └──────────────────┬──────────────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
         ┌────▼────┐            ┌──────▼──────┐          ┌──────▼──────┐
         │  Text   │            │   Image     │          │   Audio     │
         │ Files   │            │   Files     │          │   Files     │
         └────┬────┘            └──────┬──────┘          └──────┬──────┘
              │                        │                        │
              │                  ┌─────▼─────┐           ┌─────▼─────┐
              │                  │   BLIP    │           │  Whisper  │
              │                  │ Captioning│           │ Transcribe│
              │                  │  + OCR    │           │           │
              │                  └─────┬─────┘           └─────┬─────┘
              │                        │                        │
              ▼                        ▼                        ▼
         ┌─────────────────────────────────────────────────────────┐
         │                    Plain Text                           │
         └──────────────────────────┬──────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
              ┌─────▼─────┐  ┌─────▼─────┐  ┌──────▼──────┐
              │  Chunking  │  │   Entity  │  │ Relationship│
              │  (512 tok) │  │ Extraction│  │  Extraction │
              │            │  │  (spaCy)  │  │ (S→P→O)    │
              └─────┬──────┘  └─────┬─────┘  └──────┬──────┘
                    │               │               │
                    ▼               │               │
         ┌──────────────────┐      │               │
         │  MiniLM-L6-v2   │      │               │
         │  Text Embedding │      │               │
         │   (384-dim)     │      │               │
         └────────┬─────────┘      │               │
                  │               │               │
                  ▼               ▼               ▼
         ┌──────────────────────────────────────────┐
         │        Qdrant: multimodal_embeddings     │
         │  ┌────────────────────────────────────┐  │
         │  │  text_vector (384-dim, COSINE)     │  │
         │  │  payload: content_type, entities,  │  │
         │  │  caption, transcript, tags, etc.   │  │
         │  └────────────────────────────────────┘  │
         └──────────────────────────────────────────┘
                  │                         │
                  ▼                         ▼
         ┌────────────────┐       ┌─────────────────┐
         │ Unified Search │       │  Neo4j Graph     │
         │ (single query  │       │  (entities +     │
         │  all modalities│       │   relationships) │
         │  one vector)   │       │   [future]       │
         └────────────────┘       └─────────────────┘
```

## Models

| Component | Model | Size | Purpose |
|-----------|-------|------|---------|
| Text Embedding | `sentence-transformers/all-MiniLM-L6-v2` | 22M params, 384-dim | **Single embedding model** for all content |
| Image Captioning | `Salesforce/blip-image-captioning-base` | 247M params | Generate text descriptions of images |
| Speech-to-Text | `openai/whisper-base` | 74M params | Transcribe audio to text |
| Entity Extraction | `spaCy en_core_web_sm` | 12M params | NER + relationship extraction |

## Qdrant Collection Schema

**Single collection:** `multimodal_embeddings`

**Vector:** `text_vector` — 384 dimensions, COSINE distance, HNSW indexed

**Payload fields (indexed):**
- `content_type` — `"text"` | `"image"` | `"audio"` (keyword index)
- `source_path` — original file path (keyword index)
- `content_hash` — SHA-256 for deduplication (keyword index)
- `parent_doc_id` — groups chunks from same file (keyword index)
- `file_type` — file extension (keyword index)
- `chunk_text` — the actual text content
- `chunk_index` — position within parent document
- `extracted_entities` — NER entities (for entity-based filtering)
- `tags` — user-defined tags
- **Image-specific:** `caption`, `ocr_text`, `image_width`, `image_height`, `exif_data`
- **Audio-specific:** `transcript`, `audio_duration`, `sample_rate`

## Quick Start

### 1. Prerequisites

- Python 3.12+
- Docker & Docker Compose (for Qdrant)
- `uv` package manager (recommended) or `pip`
- ~2GB RAM for models (loaded lazily on first use)

### 2. Installation

```bash
# Clone and install with uv
uv sync

# Or with pip
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Install Tesseract for OCR (optional)
# Ubuntu: sudo apt-get install tesseract-ocr
# macOS: brew install tesseract
```

### 3. Start Qdrant

```bash
docker-compose up -d
```

Verify Qdrant is running:
```bash
curl http://localhost:6333/collections
```

### 4. Run the Service

```bash
# Development mode with uv
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs at: http://localhost:8000/docs

## API Endpoints

### Ingestion
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ingest/text` | POST | Upload text/PDF/markdown (form or file) |
| `/ingest/image` | POST | Upload image → BLIP caption + OCR → embed |
| `/ingest/audio` | POST | Upload audio → Whisper transcribe → embed |
| `/ingest/directory` | POST | Batch ingest from directory (auto-detect types) |

### Search
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/search` | POST | **Unified search** — one query, all modalities |
| `/search/{collection}` | POST | Search (backwards compat) |
| `/search/by-type/{content_type}` | POST | Filter by `text`, `image`, or `audio` |
| `/search/filters/by-source` | GET | Find all content from a source file |
| `/search/filters/by-entity` | GET | Find all content mentioning an entity |

### Admin
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/collections` | GET | List collections with stats |
| `/collections/create` | POST | Initialize collections |

## Usage Examples

### Ingest text
```bash
curl -X POST http://localhost:8000/ingest/text \
  -F "content=Vector databases store high-dimensional embeddings for similarity search." \
  -F "source_path=notes.txt" \
  -F "tags=ml,databases"
```

### Ingest images from directory
```bash
curl -X POST http://localhost:8000/ingest/directory \
  -H "Content-Type: application/json" \
  -d '{"directory_path": "/path/to/images", "file_patterns": ["*.png", "*.jpg"]}'
```

### Ingest audio
```bash
curl -X POST http://localhost:8000/ingest/directory \
  -H "Content-Type: application/json" \
  -d '{"directory_path": "/path/to/audio", "file_patterns": ["*.wav", "*.mp3"]}'
```

### Unified search (returns text, images, AND audio)
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "cat sitting", "limit": 5}'
```

### Search only images
```bash
curl -X POST http://localhost:8000/search/by-type/image \
  -H "Content-Type: application/json" \
  -d '{"query": "red car", "limit": 5}'
```

## Configuration

All settings via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_HOST` | `localhost` | Qdrant host |
| `QDRANT_PORT` | `6333` | Qdrant port |
| `TEXT_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Text embedding model |
| `IMAGE_CAPTIONING_MODEL` | `Salesforce/blip-image-captioning-base` | BLIP model |
| `SPEECH_MODEL` | `openai/whisper-base` | Whisper model |
| `TEXT_CHUNK_SIZE` | `512` | Chunk size in tokens |
| `TEXT_CHUNK_OVERLAP` | `50` | Chunk overlap |
| `TEXT_EMBEDDING_DIM` | `384` | Embedding dimension |
| `HNSW_M` | `16` | HNSW M parameter |
| `HNSW_EF_CONSTRUCT` | `200` | HNSW ef_construct |

## Project Structure

```
app/
├── main.py                          # FastAPI app + startup
├── config.py                        # Pydantic settings
├── models/
│   └── models.py                    # Data models (TextChunk, ImageData, etc.)
├── routes/
│   ├── health.py                    # Health + admin routes
│   ├── ingest_routes.py             # Ingestion endpoints
│   └── search_routes.py             # Unified search endpoints
└── services/
    ├── embeddings/
    │   ├── base.py                  # Base embedding strategy
    │   ├── text_strategy.py         # MiniLM text embeddings
    │   ├── audio_strategy.py        # Whisper transcription + embedding
    │   ├── image_strategy.py        # (legacy, unused)
    │   └── caption_strategy.py      # (legacy, unused)
    ├── processing/
    │   ├── text_extractor.py        # ★ Unified text extraction layer
    │   ├── text_processor.py        # Text chunking
    │   ├── image_processor.py       # Image metadata + BLIP + OCR
    │   ├── audio_processor.py       # Audio processing + Whisper
    │   ├── entity_extractor.py      # spaCy NER + relationship extraction
    │   └── pdf_processor.py         # PDF text extraction
    └── storage/
        ├── qdrant_manager.py        # ★ All Qdrant operations (single vector)
        └── content_hasher.py        # SHA-256 content hashing
```

## License

MIT License

---

**Built with ❤️ for AI Minds Hackathon**