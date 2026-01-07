# Sermon Recommender

A semantic search API that matches user emotional states to relevant sermons. Users describe how they're feeling, and the system returns sermons that address that emotional need using vector search over sermon transcripts.

## Overview

The system ingests sermon videos from YouTube channels, extracts transcripts (via captions or Whisper), generates embeddings, and stores them in a vector database. When users search, an LLM expands their emotional query into helpful sermon topics before performing semantic search.

## Features

- **Emotional Query Understanding**: LLM-powered query expansion transforms feelings into searchable sermon topics
- **Multi-Channel Support**: Sync sermons from multiple YouTube channels
- **Automatic Transcription**: YouTube captions with Whisper fallback for videos without captions
- **Semantic Search**: Vector similarity search using FastEmbed embeddings
- **Mood-Based Search**: Predefined mood categories for quick searches
- **Scheduled Sync**: GitHub Actions workflow for automated weekly updates

## Tech Stack

| Component | Technology |
|-----------|------------|
| API | FastAPI (async) |
| Frontend | SvelteKit + TypeScript + Tailwind CSS |
| Transcription | yt-dlp (YouTube captions) / Whisper large-v3 (fallback) |
| Embeddings | FastEmbed (BAAI/bge-base-en-v1.5, 768 dimensions) |
| Vector Database | Qdrant Cloud |
| Metadata Database | Turso (cloud SQLite) |
| Transcript Storage | MongoDB Atlas |
| LLM | Groq (llama-3.1-8b-instant) |

## Architecture

```
User Query
    |
    v
Query Expansion (Groq LLM)
    |
    v
Embedding Generation (FastEmbed)
    |
    v
Vector Search (Qdrant)
    |
    v
Metadata Enrichment (Turso)
    |
    v
Ranked Results with YouTube Links
```

### Data Pipeline

1. **Ingestion**: Fetch video metadata from YouTube channels
2. **Transcription**: Extract captions or transcribe with Whisper
3. **Storage**: Save transcripts to MongoDB
4. **Chunking**: Split transcripts into 500-word segments with 50-word overlap
5. **Embedding**: Generate vectors with FastEmbed
6. **Indexing**: Store vectors in Qdrant with video metadata

## Project Structure

```
sermon_recommendation/
├── app/
│   ├── main.py                      # FastAPI application
│   ├── api/routes/                  # API endpoints
│   ├── core/                        # Configuration and logging
│   ├── db/                          # Database connections and repositories
│   ├── models/                      # Pydantic schemas
│   └── services/                    # Business logic
│       ├── embeddings/              # Embedding generation and storage
│       ├── ingestion/               # Video ingestion orchestration
│       ├── search/                  # Semantic search and query expansion
│       ├── transcription/           # Whisper transcription
│       └── youtube/                 # YouTube metadata and captions
├── scripts/                         # CLI tools for ingestion and embedding
├── frontend/                        # SvelteKit frontend
├── .github/workflows/               # GitHub Actions for automation
└── tests/                           # Test suite
```

## Setup

### Prerequisites

- Python 3.12+
- uv (Python package manager)
- MongoDB Atlas account
- Turso account
- Qdrant Cloud account
- Groq API key

### Installation

```bash
# Clone the repository
git clone https://github.com/your-repo/sermon-recommendation.git
cd sermon-recommendation

# Create virtual environment and install dependencies
uv venv
uv pip install -r requirements.txt

# Initialize the database
.venv/bin/python scripts/init_db.py
```

### Environment Variables

Create a `.env` file in the project root:

```bash
# Database (Turso)
TURSO_DATABASE_URL=libsql://your-db.turso.io
TURSO_AUTH_TOKEN=your-token

# MongoDB (Transcripts)
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
MONGODB_DATABASE=sermon_recommender

# Vector Database (Qdrant)
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-api-key
QDRANT_COLLECTION_NAME=sermon_chunks

# LLM (Groq)
GROQ_API_KEY=your-groq-key
GROQ_MODEL=llama-3.1-8b-instant

# Embeddings
EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
EMBEDDING_DIMENSIONS=768

# Search
MIN_RELEVANCE_SCORE=0.35

# Ingestion
MIN_VIDEO_DURATION_MINUTES=4
```

## Usage

### Running the API

```bash
.venv/bin/uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### Ingesting a Channel

```bash
# Sync a single channel
.venv/bin/python scripts/sync_channel.py --channel "https://www.youtube.com/@pastorpoju" --max-videos 50

# Sync all channels from channels.json
.venv/bin/python scripts/sync_all_channels.py
```

### Generating Embeddings

```bash
# Embed all transcripts
.venv/bin/python scripts/embed_transcripts.py

# Embed only new transcripts
.venv/bin/python scripts/embed_new.py
```

### Running Tests

```bash
.venv/bin/pytest -xvs
.venv/bin/ruff check app/
.venv/bin/mypy app/
```

## API Endpoints

### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/search` | Search by natural language feeling |
| GET | `/api/search?query=...` | Search by query string |
| POST | `/api/search/mood` | Search by mood category |
| GET | `/api/search/mood/{mood}` | Search by predefined mood |

### Ingestion

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/channels/sync` | Start async channel sync |
| POST | `/api/channels/sync/blocking` | Sync and wait for completion |
| GET | `/api/ingestion/status` | Get ingestion statistics |
| GET | `/api/videos/{video_id}/status` | Get video ingestion status |
| GET | `/api/videos/{video_id}/transcript` | Get video transcript |
| POST | `/api/ingestion/retry` | Retry failed ingestions |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/` | API information |

## Mood Categories

The system supports predefined mood categories for quick searches:

- Anxious / Worried
- Sad
- Grieving
- Lost / Confused
- Angry / Frustrated
- Grateful / Thankful
- Hopeless
- Fearful
- Lonely
- Overwhelmed

## Multi-Channel Configuration

Add channels to `channels.json`:

```json
{
  "channels": [
    {
      "name": "Pastor Poju Oyemade",
      "url": "https://www.youtube.com/@pastorpoju",
      "active": true,
      "max_videos": 50
    },
    {
      "name": "Pastor Emmanuel Iren",
      "url": "https://www.youtube.com/@pst_iren",
      "active": true,
      "max_videos": 50
    }
  ]
}
```

## GitHub Actions

The repository includes automated workflows:

- **sync-channels.yml**: Weekly sync of all channels (Sundays at 2 AM UTC)
- **embed-new.yml**: Embed new transcripts after sync
- **migrate-mongodb.yml**: One-time migration script

### Required Secrets

Configure these secrets in your GitHub repository:

- `MONGODB_URI`
- `MONGODB_DATABASE`
- `TURSO_DATABASE_URL`
- `TURSO_AUTH_TOKEN`
- `QDRANT_URL`
- `QDRANT_API_KEY`

## Deployment

### Backend (Render)

1. Connect your GitHub repository to Render
2. Set environment variables in Render dashboard
3. Deploy with the following settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Frontend (Vercel)

1. Connect the `frontend/` directory to Vercel
2. Set the `PUBLIC_API_URL` environment variable
3. Deploy

## License

MIT License
