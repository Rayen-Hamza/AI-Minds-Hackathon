# Qdrant Memory Service

A standalone vector store service for grounded memory systems that handles **images, text, and audio**. Built on Qdrant for efficient semantic search with differential updates via content hashing.

## Features

✨ **Multi-Modal Support**
- 📝 Text (TXT, MD, PDF, code files)
- 🖼️ Images (PNG, JPG, etc.) with CLIP + caption embeddings
- 🎵 Audio (MP3, WAV, etc.) with Whisper transcription

🔍 **Advanced Search**
- Semantic search across all content types
- Image similarity search (CLIP)
- Text-based image search (via captions)
- Cross-modal retrieval

⚡ **Smart Processing**
- Differential updates (content hashing)
- Automatic chunking with semantic splitting
- NER entity extraction
- OCR for images
- BLIP image captioning

🏗️ **Architecture**
- Strategy Pattern for embedding generation
- Lazy model loading for efficiency
- Batch operations
- HNSW indexing for fast similarity search

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Docker & Docker Compose
- ~4GB RAM for models

### 2. Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
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
# Development mode
python -m src.main

# Or with uvicorn directly
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## API Endpoints

### Ingestion
- `POST /ingest/text` - Upload text/PDF/markdown
- `POST /ingest/image` - Upload image with OCR/caption
- `POST /ingest/audio` - Upload audio with transcription
- `POST /ingest/directory` - Batch ingest from directory

### Search
- `POST /search` - Search all collections
- `POST /search/{collection}` - Search specific collection
- `POST /search/image` - Image similarity search
- `GET /search/filters/by-source` - Filter by source file
- `GET /search/filters/by-entity` - Filter by entity

### Admin
- `GET /health` - Health check
- `GET /collections` - List collections with stats
- `POST /collections/create` - Initialize collections

See full documentation at http://localhost:8000/docs

## Configuration

Edit `.env` to customize models and settings.

## License

MIT License

---

**Built with ❤️ for AI Minds Hackathon**