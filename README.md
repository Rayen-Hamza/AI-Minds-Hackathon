<p align="center">
  <img src="frontend/src/renderer/images/animations/Default.png" alt="Klippy" width="200"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/AI--Minds-Hackathon%202026-blueviolet?style=for-the-badge&logo=robot&logoColor=white" alt="AI Minds Hackathon"/>
</p>

<h1 align="center"> Klippy📎</h1>

<p align="center">
  <em> Paperclips Organized Your Documents Since 1867.<br/>Now They Understand Them.</em>
</p>

<p align="center">
  <strong>A text-centric multimodal RAG system with knowledge graph reasoning for sub-4B LLMs </strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FastAPI-0.109+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/Electron-Forge-47848F?style=flat-square&logo=electron&logoColor=white" alt="Electron"/>
  <img src="https://img.shields.io/badge/TypeScript-5.0+-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript"/>
  <img src="https://img.shields.io/badge/React-18+-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Qdrant-Vector%20DB-FF6B6B?style=flat-square" alt="Qdrant"/>
  <img src="https://img.shields.io/badge/Neo4j-Knowledge%20Graph-008CC1?style=flat-square&logo=neo4j&logoColor=white" alt="Neo4j"/>
  <img src="https://img.shields.io/badge/Ollama-Local%20LLM-000000?style=flat-square" alt="Ollama"/>
  <img src="https://img.shields.io/badge/Google%20ADK-Agents-4285F4?style=flat-square&logo=google&logoColor=white" alt="Google ADK"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/spaCy-NER-09A3D5?style=flat-square&logo=spacy&logoColor=white" alt="spaCy"/>
  <img src="https://img.shields.io/badge/Whisper-Speech--to--Text-74aa9c?style=flat-square&logo=openai&logoColor=white" alt="Whisper"/>
  <img src="https://img.shields.io/badge/BLIP-Image%20Captioning-FF6F00?style=flat-square&logo=salesforce&logoColor=white" alt="BLIP"/>
</p>

---

## 🎯 What is Klippy?

**Klippy** is a **local-first AI assistant** that remembers everything. It combines:

- 🔍 **Multimodal RAG** ; Search across text, images, and audio with one query
- 🧠 **Knowledge Graph Reasoning** ; Neo4j-powered ontological reasoning for complex queries
- ⚡ **Prompt Chaining** ; Google ADK agents orchestrate multi-step reasoning pipelines
- 💾 **Personal Memory** ; Your data stays local, your assistant gets smarter

> **Architecture Philosophy:** _"Graph-as-Brain, LLM-as-Mouth"_ ; All reasoning is pre-computed via deterministic graph logic. The LLM only narrates the answer. This allows sub-4B models like Qwen2.5:3b to perform like much larger models.

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🎨 Multimodal Ingestion

- 📝 **Text** ; TXT, MD, PDF, code files
- 🖼️ **Images** ; BLIP captioning + Tesseract OCR
- 🎵 **Audio** ; Whisper transcription
- 🔄 **Differential Updates** ; Skip unchanged files via content hashing

</td>
<td width="50%">

### 🔍 Unified Search

- Single vector space for ALL content (384-dim)
- One query searches text, images, and audio
- Filter by content type, source, or entity
- HNSW indexing for sub-millisecond search

</td>
</tr>
<tr>
<td width="50%">

### 🧠 Knowledge Graph Reasoning

- Entity extraction with spaCy NER
- Relationship mining (Subject → Predicate → Object)
- Multi-hop graph traversal
- Causal chain analysis
- Pre-computed reasoning chains for small LLMs

</td>
<td width="50%">

### 🤖 Agent Architecture (Google ADK)

- **Orchestrator Agent** ; Routes and coordinates
- **Qdrant Agent** ; Semantic search specialist
- **Neo4j Agent** ; Knowledge graph queries
- **Prompt Chain Agent** ; Multi-step reasoning pipeline

</td>
</tr>
<tr>
<td width="50%">

### 🖥️ Desktop App (Electron)

- Native Windows/macOS/Linux app
- Real-time chat interface
- Source file previews with images
- Confidence scores and entity badges

</td>
<td width="50%">

### ⚙️ Context-Aware Responses

- Ontological enrichment before RAG
- Smart context truncation for small LLMs
- Confidence scoring per reasoning step
- Source attribution with file paths

</td>
</tr>
</table>

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         🖥️ Electron Desktop App                         │
│                     React + TypeScript + Vite                           │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ IPC / HTTP
┌────────────────────────────────▼────────────────────────────────────────┐
│                         🚀 FastAPI Backend                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │   Ingest     │  │   Search     │  │   Agent      │  │  Reasoning  │ │
│  │   Routes     │  │   Routes     │  │   Routes     │  │   Routes    │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ │
└─────────┼─────────────────┼─────────────────┼─────────────────┼────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      🤖 Google ADK Agent Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐ │
│  │ Orchestrator│◄─┤ Qdrant Agent│  │ Neo4j Agent │  │ Prompt Chain   │ │
│  │   (root)    │  │  (search)   │  │  (graph)    │  │    Agent       │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        📊 Processing Services                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐ │
│  │    Text     │  │   Image     │  │   Audio     │  │    Entity      │ │
│  │  Processor  │  │  Processor  │  │  Processor  │  │   Extractor    │ │
│  │  (chunking) │  │(BLIP + OCR) │  │  (Whisper)  │  │    (spaCy)     │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └───────┬────────┘ │
└─────────┼────────────────┼────────────────┼─────────────────┼──────────┘
          │                │                │                 │
          ▼                ▼                ▼                 │
┌─────────────────────────────────────────────────────┐       │
│          📝 Unified Text Layer                      │       │
│   All modalities → Text → MiniLM-L6-v2 → 384-dim   │       │
└──────────────────────────┬──────────────────────────┘       │
                           │                                   │
          ┌────────────────┴────────────────┐                 │
          ▼                                 ▼                 ▼
┌──────────────────┐              ┌─────────────────────────────┐
│  📦 Qdrant       │              │  🔗 Neo4j                    │
│  Vector DB       │              │  Knowledge Graph             │
│  ────────────    │              │  ─────────────               │
│  • text_vector   │              │  • Person, Topic, Event      │
│  • 384-dim HNSW  │              │  • MENTIONS, ABOUT, KNOWS    │
│  • Unified space │              │  • Cypher templates          │
└──────────────────┘              └───────────────────────────────┘
          │                                 │
          └────────────────┬────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         🦙 Ollama (Local LLM)                           │
│                        Qwen2.5:3b / Llama3.2                            │
│              "Narrates" pre-computed reasoning chains                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Category       | Technologies                                                                                                                                                                                                                                                                                                                                                                                                             | Purpose                         |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------- |
| **Backend**    | ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) ![Python](https://img.shields.io/badge/Python%203.12-3776AB?style=flat-square&logo=python&logoColor=white) ![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=flat-square&logo=pydantic&logoColor=white)                                                                                              | REST API, validation, async I/O |
| **Frontend**   | ![Electron](https://img.shields.io/badge/Electron-47848F?style=flat-square&logo=electron&logoColor=white) ![React](https://img.shields.io/badge/React-61DAFB?style=flat-square&logo=react&logoColor=black) ![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white) ![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white) | Desktop app, chat UI            |
| **Vector DB**  | ![Qdrant](https://img.shields.io/badge/Qdrant-FF6B6B?style=flat-square)                                                                                                                                                                                                                                                                                                                                                  | Semantic search, HNSW indexing  |
| **Graph DB**   | ![Neo4j](https://img.shields.io/badge/Neo4j-008CC1?style=flat-square&logo=neo4j&logoColor=white)                                                                                                                                                                                                                                                                                                                         | Knowledge graph, Cypher queries |
| **LLM**        | ![Ollama](https://img.shields.io/badge/Ollama-000000?style=flat-square) ![Qwen](https://img.shields.io/badge/Qwen2.5:3b-purple?style=flat-square)                                                                                                                                                                                                                                                                        | Local inference                 |
| **Agents**     | ![Google ADK](https://img.shields.io/badge/Google%20ADK-4285F4?style=flat-square&logo=google&logoColor=white) ![LiteLLM](https://img.shields.io/badge/LiteLLM-orange?style=flat-square)                                                                                                                                                                                                                                  | Agent orchestration             |
| **Embeddings** | ![MiniLM](https://img.shields.io/badge/MiniLM--L6--v2-FFD21E?style=flat-square&logo=huggingface&logoColor=black)                                                                                                                                                                                                                                                                                                         | Text embeddings (384-dim)       |
| **Vision**     | ![BLIP](https://img.shields.io/badge/BLIP-FF6F00?style=flat-square&logo=salesforce&logoColor=white) ![Tesseract](https://img.shields.io/badge/Tesseract-OCR-blue?style=flat-square)                                                                                                                                                                                                                                      | Image captioning, OCR           |
| **Speech**     | ![Whisper](https://img.shields.io/badge/Whisper-74aa9c?style=flat-square&logo=openai&logoColor=white)                                                                                                                                                                                                                                                                                                                    | Speech-to-text                  |
| **NLP**        | ![spaCy](https://img.shields.io/badge/spaCy-09A3D5?style=flat-square&logo=spacy&logoColor=white)                                                                                                                                                                                                                                                                                                                         | NER, relationship extraction    |
| **DevOps**     | ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white) ![uv](https://img.shields.io/badge/uv-purple?style=flat-square)                                                                                                                                                                                                                                                      | Containers, fast packaging      |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- **Docker Desktop** (for Qdrant & Neo4j)
- **Ollama** (for local LLM)
- **Node.js 18+** (for frontend)
- **uv** package manager (recommended)

### 1️⃣ Clone & Install

```bash
git clone https://github.com/Rayen-Hamza/AI-Minds-Hackathon.git
cd AI-Minds-Hackathon

# Install Python dependencies
uv sync

# Download spaCy model
uv run python -m spacy download en_core_web_sm
```

### 2️⃣ Start Databases

```bash
docker compose up -d
```

This starts:

- **Qdrant** on `localhost:6333` (Vector DB)
- **Neo4j** on `localhost:7474` (Graph DB, password: `changeme`)

### 3️⃣ Start Ollama

```bash
# In a separate terminal (or it may already be running)
ollama serve

# Pull the model (first time only)
ollama pull qwen2.5:3b
```

### 4️⃣ Start the API

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

📚 API docs: http://localhost:8000/docs

### 5️⃣ Start the Desktop App (Optional)

```bash
cd frontend
npm install
npm start
```

---

## 📡 API Reference

### Ingestion

| Endpoint            | Method | Description                  |
| ------------------- | ------ | ---------------------------- |
| `/ingest/text`      | POST   | Upload text/PDF/markdown     |
| `/ingest/image`     | POST   | Upload image → caption + OCR |
| `/ingest/audio`     | POST   | Upload audio → transcribe    |
| `/ingest/directory` | POST   | Batch ingest from path       |

### Search

| Endpoint                    | Method | Description                         |
| --------------------------- | ------ | ----------------------------------- |
| `/search`                   | POST   | **Unified search** ; all modalities |
| `/search/by-type/{type}`    | POST   | Filter by `text`/`image`/`audio`    |
| `/search/filters/by-entity` | GET    | Find content by entity              |

### Agents (Google ADK)

| Endpoint          | Method | Description                  |
| ----------------- | ------ | ---------------------------- |
| `/agent/chat`     | POST   | Chat with orchestrator agent |
| `/agent/sessions` | GET    | List active sessions         |
| `/agent/agents`   | GET    | List available agents        |

### Reasoning

| Endpoint            | Method | Description                  |
| ------------------- | ------ | ---------------------------- |
| `/reasoning/query`  | POST   | Graph reasoning → LLM prompt |
| `/reasoning/ingest` | POST   | Ingest document to graph     |

---

## 🧪 Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app

# Run specific test
uv run pytest tests/test_embeddings.py -v
```

---

## 📁 Project Structure

```
AI-Minds-Hackathon/
├── app/                          # FastAPI backend
│   ├── agents/                   # Google ADK agents
│   │   ├── orchestrator.py       # Root agent (router)
│   │   ├── qdrant_agent.py       # Vector search specialist
│   │   ├── neo4j_agent.py        # Knowledge graph specialist
│   │   └── prompt_chain.py       # Prompt chaining pipeline
│   ├── models/                   # Pydantic models
│   ├── routes/                   # API endpoints
│   ├── services/                 # Business logic
│   │   ├── embeddings/           # Embedding strategies
│   │   ├── processing/           # Text/Image/Audio processors
│   │   └── storage/              # Qdrant manager
│   └── config.py                 # Settings
├── frontend/                     # Electron desktop app
│   └── src/
│       ├── main/                 # Electron main process
│       └── renderer/             # React UI
├── tests/                        # pytest tests
├── docker-compose.yml            # Qdrant + Neo4j
└── pyproject.toml                # Python dependencies
```

---

## 🔧 Configuration

Create a `.env` file:

```env
# Qdrant
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme

# Ollama (Local LLM)
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:3b
LLM_BASE_URL=http://localhost:11434/v1

# Processing
TEXT_CHUNK_SIZE=512
TEXT_CHUNK_OVERLAP=50
LOG_LEVEL=INFO
```

---

## 🏆 Hackathon Team

<table>
<tr>
<td align="center">
  <strong>AI Minds 2026</strong><br/>
  Built with ❤️ and ☕
</td>
</tr>
</table>

---

## 📜 License

MIT License ; see [LICENSE](LICENSE) for details.

---

<p align="center">
  <img src="https://img.shields.io/badge/Made%20for-AI%20Minds%20Hackathon%202026-blueviolet?style=for-the-badge"/>
</p>

<p align="center">
  <sub>⭐ Star this repo if you find it useful!</sub>
</p>
