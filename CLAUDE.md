# CLAUDE.md

## Project Overview
Sermon recommender API that matches user emotional states to relevant sermons. Users input how they're feeling; the system returns sermons that address that emotional need using semantic search over sermon transcripts.

## Tech Stack
- **API**: FastAPI
- **Transcription**: YouTube captions via yt-dlp (Whisper as fallback for videos without captions)
- **Embeddings**: Qdrant vector database + sentence-transformers
- **Metadata**: SQLite
- **LLM**: Groq
- **Data Source**: YouTube (Pastor Poju Oyemade)

## Project Structure
```
sermon-recommender/
├── app/
│   ├── api/          # FastAPI routes
│   ├── core/         # Config, settings, logging
│   ├── services/     # Business logic (ingestion, transcription, search, embeddings, youtube)
│   ├── models/       # Pydantic schemas
│   └── db/           # Database models, connections, repositories
├── scripts/          # Ingestion and maintenance scripts
├── data/             # Local data storage (transcripts, etc.)
├── logs/             # Application logs
└── tests/            # Pytest tests
```

## Development Commands
- Install dependencies: `pip install -r requirements.txt --break-system-packages`
- Run tests: `.venv/bin/pytest -xvs`
- Type checking: `.venv/bin/mypy app/`
- Linting: `.venv/bin/ruff check app/`
- Start server: `.venv/bin/uvicorn app.main:app --reload`
- Initialize database: `.venv/bin/python scripts/init_db.py`

## Code Conventions
- Use Pydantic v2 for all schemas
- Async everywhere—FastAPI routes, database calls, external APIs
- Use `httpx` for HTTP clients, not `requests`
- Use `structlog` for logging, not `print()`
- Environment variables via `pydantic-settings`

## Mood Categories
- Anxious / Worried
- Sad / Grieving
- Lost / Confused
- Angry / Frustrated
- Grateful / Thankful
- Needing hope
- Needing strength

## Verification Requirements
After any code changes:
1. Run `.venv/bin/pytest -xvs` to verify tests pass
2. Run `.venv/bin/mypy app/` for type checking
3. Run `.venv/bin/ruff check app/` for linting
4. For API changes, test the endpoint with curl

## Common Mistakes to Avoid
- Don't hardcode YouTube API keys or any credentials
- Don't use synchronous HTTP calls in async functions
- Don't store audio files in git—use data/ directory (gitignored)
- Always handle Qdrant connection errors gracefully
- Use batch operations for embedding insertions
