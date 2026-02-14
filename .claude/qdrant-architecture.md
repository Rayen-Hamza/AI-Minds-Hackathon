# Qdrant Architecture & Embedding Models

## Overview

This document describes the actual implementation of the Qdrant vector database architecture and embedding models used in the Local AI Assistant project. The system uses a **unified collection architecture** with **named vectors** to support multimodal semantic search across text, images, and audio content.

## Architecture Pattern: Unified Collection with Named Vectors

Instead of using separate collections for each content type, we implemented a **unified collection architecture** that stores all content types in a single Qdrant collection using **named vectors**. This approach offers several advantages:

- **Simplified management**: Single collection to maintain and optimize
- **Flexible search**: Can search across modalities or filter to specific types
- **Efficient storage**: Shared infrastructure and indexing
- **Cross-modal queries**: Future support for multimodal fusion queries

### Collection Structure

```
Collection: "multimodal_embeddings"
├── Named Vectors:
│   ├── text_vector (384-dim)      → Text chunks & audio transcripts
│   ├── image_vector (1024-dim)     → Image-to-image similarity (DINOv2)
│   └── text_to_image_vector (1152-dim) → Text-to-image search (SigLIP)
│
├── Payload Fields (indexed):
│   ├── content_type: "text" | "image" | "audio"
│   ├── file_type: extension/format
│   ├── source_path: original file location
│   ├── content_hash: for differential updates
│   ├── parent_doc_id: document UUID
│   └── ... (metadata fields)
│
└── HNSW Index Configuration:
    ├── M: 16 (connections per node)
    ├── ef_construct: 200 (index quality)
    └── Distance: Cosine similarity
```

## Embedding Models

### 1. Text Embeddings (384-dim)

**Model**: `sentence-transformers/all-MiniLM-L6-v2`

**Usage**:
- Text document chunks
- Audio transcripts (after speech-to-text)
- General semantic text search

**Characteristics**:
- Lightweight and fast (~23M parameters)
- Optimized for semantic similarity
- CPU-friendly for local deployment
- L2 normalized for cosine similarity

**Implementation**: [`app/services/embeddings/text_strategy.py`](../app/services/embeddings/text_strategy.py)

**Key Features**:
- Batch processing support (batch_size=32)
- GPU acceleration when available
- Progress bar for large batches (>50 items)
- Empty text handling with zero vectors

---

### 2. Image Embeddings - Image Similarity (1024-dim)

**Model**: `facebook/dinov2-large`

**Usage**:
- Image-to-image similarity search
- Visual content clustering
- Duplicate image detection

**Characteristics**:
- Self-supervised Vision Transformer (~300M parameters)
- Excellent feature extraction without fine-tuning
- Robust to variations (lighting, crops, rotations)
- Uses CLS token as image representation

**Implementation**: [`app/services/embeddings/image_strategy.py`](../app/services/embeddings/image_strategy.py)

**Key Features**:
- Automatic RGB conversion
- Batch processing for multiple images
- GPU/CPU adaptive loading
- Error handling with placeholder images

---

### 3. Text-to-Image Embeddings (1152-dim)

**Model**: `google/siglip-so400m-patch14-384`

**Usage**:
- Text-to-image search (find images matching text query)
- Cross-modal retrieval
- Image captioning support (limited)

**Characteristics**:
- Sigmoid loss for better language-image alignment (~400M parameters)
- Improved over CLIP for retrieval tasks
- Separate text and vision encoders
- Normalized embeddings for similarity search

**Implementation**: [`app/services/embeddings/caption_strategy.py`](../app/services/embeddings/caption_strategy.py)

**Key Features**:
- Dual embedding methods:
  - `embed()`: Image → vector (for indexing)
  - `embed_text()`: Text → vector (for querying)
- Same embedding space for both modalities
- Batch image processing
- 384px image resolution

---

### 4. Audio Processing (Speech-to-Text → 384-dim)

**Model Pipeline**:
1. **Speech-to-Text**: `openai/whisper-base`
2. **Text Embedding**: `sentence-transformers/all-MiniLM-L6-v2`

**Usage**:
- Audio file transcription
- Semantic search over spoken content
- Podcast/lecture indexing

**Characteristics**:
- Whisper Base (~74M parameters, CPU-friendly)
- Automatic resampling to 16kHz mono
- Transcript embedding via text model
- Same vector space as text documents

**Implementation**: [`app/services/embeddings/audio_strategy.py`](../app/services/embeddings/audio_strategy.py)

**Key Features**:
- Two-stage processing (transcribe → embed)
- Audio format normalization (stereo→mono, resampling)
- Batch transcription support
- Empty transcript handling

---

## Vector Storage Schema

### Unified Collection: `multimodal_embeddings`

Each point in Qdrant stores:

```python
{
  "id": "uuid-v4",
  "vector": {
    "text_vector": [384-dim float array],      # Optional: for text/audio
    "image_vector": [1024-dim float array],    # Optional: for images
    "text_to_image_vector": [1152-dim float array]  # Optional: for images
  },
  "payload": {
    # Core fields (all content types)
    "source_path": "/path/to/file.ext",
    "content_type": "text" | "image" | "audio",
    "file_type": "txt" | "png" | "mp3" | ...,
    "chunk_index": 0,
    "chunk_text": "actual text content / caption / transcript",
    "timestamp": "2025-02-14T10:30:00Z",
    "content_hash": "sha256-hash",
    "parent_doc_id": "parent-uuid",
    "file_size": 12345,
    "creation_date": "2025-01-15T08:00:00Z",
    "last_modified": "2025-02-10T14:30:00Z",
    "tags": ["tag1", "tag2"],
    "extracted_entities": ["Person", "Organization"],

    # Image-specific (when content_type="image")
    "image_width": 1920,
    "image_height": 1080,
    "exif_data": {...},
    "ocr_text": "text extracted from image",
    "caption": "image description",

    # Audio-specific (when content_type="audio")
    "audio_duration": 180.5,
    "sample_rate": 16000,
    "transcript": "full audio transcript"
  }
}
```

### Payload Indexes

For efficient filtering, the following fields are indexed:

- `content_type` (keyword) - **Critical** for modality-specific searches
- `file_type` (keyword)
- `content_hash` (keyword) - For differential updates
- `parent_doc_id` (keyword)
- `source_path` (keyword)

## Search Operations

### 1. Text Search (Text/Audio)

```python
# Search text and audio content
query = "machine learning algorithms"
results = qdrant_manager.search_text(
    query_text=query,
    content_types=["text", "audio"],  # Filter to text/audio
    limit=10,
    vector_name="text_vector"
)
```

**Process**:
1. Embed query with MiniLM → 384-dim vector
2. Filter by `content_type` IN ["text", "audio"]
3. Search using `text_vector` named vector
4. Return scored results

---

### 2. Text-to-Image Search

```python
# Find images matching text query
query = "sunset over mountains"
results = qdrant_manager.search_image_by_text(
    query_text=query,
    limit=10,
    vector_name="text_to_image_vector"
)
```

**Process**:
1. Embed query text with SigLIP → 1152-dim vector
2. Filter by `content_type` = "image"
3. Search using `text_to_image_vector` named vector
4. Return matching images

---

### 3. Image-to-Image Search

```python
# Find visually similar images
results = qdrant_manager.search_image_by_image(
    image_path="/path/to/query.jpg",
    limit=10,
    vector_name="image_vector"
)
```

**Process**:
1. Embed query image with DINOv2 → 1024-dim vector
2. Filter by `content_type` = "image"
3. Search using `image_vector` named vector
4. Return similar images

---

## HNSW Index Configuration

**Algorithm**: Hierarchical Navigable Small World (HNSW)

**Parameters**:
- `M = 16`: Number of bi-directional links per node
  - Higher = better recall, more memory
  - 16 is balanced for most use cases

- `ef_construct = 200`: Size of dynamic candidate list during index construction
  - Higher = better quality, slower indexing
  - 200 provides good quality/speed tradeoff

- `Distance Metric`: Cosine similarity
  - Works well with normalized embeddings
  - Range: [-1, 1], where 1 = identical

**Search Performance**:
- Sub-millisecond search for collections <100k points
- ~10-50ms for 1M+ points
- Approximate nearest neighbor (not exact)

---

## Content Processing Pipeline

### Text Documents

```
Text File → TextProcessor
  ├─> Semantic chunking (512 tokens, 50 overlap)
  ├─> Content hashing (differential updates)
  ├─> Entity extraction (optional)
  └─> TextChunk objects
        ↓
  TextEmbeddingStrategy (MiniLM)
        ↓
  Qdrant.upsert_text_chunks()
        └─> Store with "text_vector" named vector
```

### Images

```
Image File → ImageProcessor
  ├─> Load & validate image
  ├─> Extract EXIF metadata
  ├─> OCR text extraction (optional)
  ├─> Content hashing
  └─> ImageData object
        ↓
  Dual embedding:
  ├─> ImageEmbeddingStrategy (DINOv2) → "image_vector"
  └─> CaptionEmbeddingStrategy (SigLIP) → "text_to_image_vector"
        ↓
  Qdrant.upsert_image()
        └─> Store with both named vectors
```

### Audio Files

```
Audio File → AudioProcessor
  ├─> Transcribe with Whisper
  ├─> Semantic chunking of transcript
  ├─> Content hashing
  └─> AudioChunk objects
        ↓
  TextEmbeddingStrategy (MiniLM on transcript)
        ↓
  Qdrant.upsert_audio_chunks()
        └─> Store with "text_vector" named vector
```

---

## Data Models

### Core Data Structures

See [`app/models/models.py`](../app/models/models.py) for complete definitions:

- `VectorPayload`: Standard payload for all Qdrant points
- `TextChunk`: Processed text ready for embedding
- `ImageData`: Processed image with metadata
- `AudioChunk`: Processed audio transcript chunk
- `SearchResult`: Search result with score and payload

### Processing Flow

```
File → Processor → DataModel → EmbeddingStrategy → Qdrant
```

Each modality has specialized processors and data models that conform to a unified payload schema.

---

## Differential Updates

The system supports **differential updates** to avoid re-processing unchanged content:

1. **Content Hashing**: SHA-256 hash of file content
2. **Hash Lookup**: Check if hash exists in Qdrant
3. **Skip or Update**:
   - If hash exists → Skip processing
   - If new/changed → Process and upsert
4. **Cleanup**: Delete old entries for modified files

**Benefits**:
- Faster re-ingestion of directories
- Reduced embedding computation
- Storage efficiency

---

## Configuration

All settings are managed via [`app/config.py`](../app/config.py) and can be overridden with environment variables:

```bash
# Qdrant Connection
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Embedding Models
TEXT_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
IMAGE_EMBEDDING_MODEL=facebook/dinov2-large
TEXT_TO_IMAGE_MODEL=google/siglip-so400m-patch14-384
SPEECH_MODEL=openai/whisper-base

# Processing
TEXT_CHUNK_SIZE=512
TEXT_CHUNK_OVERLAP=50
MAX_FILE_SIZE_MB=100

# Collection
UNIFIED_COLLECTION=multimodal_embeddings

# HNSW Configuration
HNSW_M=16
HNSW_EF_CONSTRUCT=200
```

---

## Performance Characteristics

### Model Sizes

| Model | Parameters | Embedding Dim | Device | Speed |
|-------|-----------|---------------|--------|-------|
| MiniLM-L6-v2 | 23M | 384 | CPU/GPU | Fast |
| DINOv2-Large | 300M | 1024 | GPU recommended | Medium |
| SigLIP-SO400M | 400M | 1152 | GPU recommended | Medium |
| Whisper-Base | 74M | N/A (ASR) | CPU/GPU | Medium |

### Throughput (GPU - NVIDIA RTX 3090)

- **Text**: ~500-1000 chunks/sec
- **Images**: ~10-50 images/sec (dual embedding)
- **Audio**: ~10-30x real-time (transcription bottleneck)

### Storage

- **Text**: ~1.5KB per chunk (vector + payload)
- **Image**: ~10KB per image (2 vectors + metadata)
- **Audio**: ~1.5KB per transcript chunk

---

## API Examples

### Ingestion

```bash
# Ingest text file
curl -X POST "http://localhost:8000/api/ingest/text" \
  -H "Content-Type: application/json" \
  -d '{"content": "Machine learning is...", "tags": ["AI", "ML"]}'

# Ingest image (multipart form)
curl -X POST "http://localhost:8000/api/ingest/image" \
  -F "file=@photo.jpg" \
  -F "tags=vacation,beach"

# Ingest directory
curl -X POST "http://localhost:8000/api/ingest/directory" \
  -H "Content-Type: application/json" \
  -d '{"directory_path": "/path/to/docs", "recursive": true}'
```

### Search

```bash
# Text search
curl -X POST "http://localhost:8000/api/search/text" \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning algorithms", "limit": 10}'

# Text-to-image search
curl -X POST "http://localhost:8000/api/search/image-by-text" \
  -H "Content-Type: application/json" \
  -d '{"query": "sunset over ocean", "limit": 5}'

# Image-to-image search
curl -X POST "http://localhost:8000/api/search/image-by-image" \
  -F "file=@query_image.jpg" \
  -F "limit=10"
```

---

## Implementation Files

- **Qdrant Manager**: [`app/services/storage/qdrant_manager.py`](../app/services/storage/qdrant_manager.py)
- **Embedding Strategies**: [`app/services/embeddings/`](../app/services/embeddings/)
  - `text_strategy.py`: MiniLM text embeddings
  - `image_strategy.py`: DINOv2 image embeddings
  - `caption_strategy.py`: SigLIP text-to-image embeddings
  - `audio_strategy.py`: Whisper + MiniLM audio processing
- **Data Models**: [`app/models/models.py`](../app/models/models.py)
- **Configuration**: [`app/config.py`](../app/config.py)

---

## Future Enhancements

1. **Neo4j Integration**: Link vector points to knowledge graph nodes
2. **Multimodal Fusion**: Combined text+image query embeddings
3. **Sparse Embeddings**: Add BM25 for hybrid retrieval
4. **Quantization**: 8-bit vector storage for 4x compression
5. **Reranking**: Two-stage retrieval with cross-encoder reranking
6. **Video Support**: Frame sampling + temporal segmentation
7. **PDF Advanced**: Layout-aware chunking with figure extraction

---

## Summary

The implemented architecture uses a **unified Qdrant collection** with **named vectors** to support multimodal semantic search. Key design decisions:

✅ **Single collection** for all content types (simplified management)
✅ **Named vectors** for modality-specific embeddings
✅ **Lightweight models** optimized for local CPU/GPU deployment
✅ **Dual image embeddings** for similarity + text-to-image search
✅ **Differential updates** to minimize re-processing
✅ **Indexed payloads** for efficient filtering

This architecture balances **performance**, **scalability**, and **flexibility** for a local AI assistant.
