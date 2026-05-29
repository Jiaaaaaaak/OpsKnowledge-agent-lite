# OpsKnowledge Agent Lite

English | [繁體中文](README.zh-TW.md)

An enterprise-style AI + Data Engineering POC for IT operations and system integration scenarios.

## What It Does

| Capability | Description |
|---|---|
| Document RAG | Upload PDF manuals/SOPs → chunk, embed, retrieve via ChromaDB |
| Incident ETL | Upload CSV/Excel/JSON tickets → normalize, clean, store in PostgreSQL |
| AI Analysis | Classify incidents, score severity, generate insights and action items |
| Observability | Every AI tool call logged to PostgreSQL for auditability |
| Dashboard | Streamlit UI for uploads, Q&A, analysis, and agent logs |

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2
- **Database**: PostgreSQL 16
- **Vector DB**: ChromaDB
- **AI**: OpenAI-compatible (swappable to Ollama)
- **Frontend**: Streamlit
- **Infra**: Docker Compose

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — set OPENAI_API_KEY

# 2. Start all services
docker compose up --build

# 3. Verify
curl http://localhost:8000/health
# Open http://localhost:8501 in browser
```

## Mock Mode (No API Key Required)

If you have not yet set up an OpenAI or Ollama account, you can run the full backend
pipeline locally using deterministic mock providers:

| Provider | env var | Behaviour |
|---|---|---|
| `MockEmbeddingProvider` | `EMBEDDING_PROVIDER=mock` | Returns 384-dim unit vectors (MD5-seeded, no network call) |
| `MockLLMProvider` | `LLM_PROVIDER=mock` | Returns a `[mock]` prefixed answer extracted from retrieved context |

```bash
# .env — copy from .env.example and set the two provider lines:
EMBEDDING_PROVIDER=mock
LLM_PROVIDER=mock
# OPENAI_API_KEY can remain as the placeholder — it is ignored in mock mode
```

### What works in mock mode
- All unit tests — 155 tests, zero external calls
- `POST /projects/{id}/upload/documents` — PDF is parsed, chunked, stored in PostgreSQL;
  embeddings are generated locally and stored in ChromaDB (ChromaDB must be running)
- `GET /projects/{id}/search` — vector search returns results using mock vectors
- `POST /projects/{id}/chat` — returns a deterministic mock answer with citations;
  `agent_runs` and `tool_calls` rows are written to PostgreSQL

### What requires real API keys
- Production-quality answers (real LLM reasoning)
- Semantic relevance of search results (real embedding similarity)

### Run all tests (no external services required)
```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

### Quick local smoke test (requires PostgreSQL + ChromaDB running)
```bash
cp .env.example .env
# Edit .env: set EMBEDDING_PROVIDER=mock  LLM_PROVIDER=mock
#            set POSTGRES_* and CHROMA_* to your local services

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python scripts/create_tables.py

# Start the server
PYTHONPATH=. uvicorn app.main:app --reload

# In another terminal:
PROJECT_ID=$(curl -s -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Mock Test"}' | jq -r '.id')

# Verify health (both db and chroma should show "connected")
curl http://localhost:8000/health

# Upload a PDF and ask a question (mock providers, no API key)
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/upload/documents" \
  -F "file=@demo_data/documents/your_manual.pdf"

curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/chat" \
  -H "Content-Type: application/json" \
  -d '{"question": "What does this document cover?", "top_k": 3}'
# Response: { "answer": "[mock] ...", "citations": [...] }
```

## Local Development (without Docker)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Start PostgreSQL and ChromaDB separately, then:
PYTHONPATH=. uvicorn app.main:app --reload

# Run tests
PYTHONPATH=. pytest tests/ -v
```

## Database Initialisation

**Option A — Python script (recommended for local dev):**
```bash
cd backend
cp ../.env.example ../.env   # set POSTGRES_* vars
PYTHONPATH=. python scripts/create_tables.py
```

**Option B — Raw SQL (psql):**
```bash
psql -h localhost -U opsuser -d opsknowledge -f migrations/001_initial_schema.sql
```

**Option C — Docker Compose (automatic on backend start):**
```bash
docker compose up --build
```

**Verify tables were created:**
```sql
-- Connect and run:
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

## Project Structure

```
opsknowledge-agent-lite/
  backend/           FastAPI service
    app/
      core/          Config, logging
      api/           Route handlers
      models/        SQLAlchemy ORM models
      schemas/       Pydantic request/response schemas
      services/      Business logic
      tools/         AI tool definitions (LLM function calls)
      db/            DB session, migrations
      utils/         Shared helpers
    tests/
  frontend/          Streamlit UI
  docs/              Architecture, PRD, data model, API docs
  demo_data/         Sample tickets and PDFs for demos
  docker-compose.yml
```

## Upload PDF Documents

```bash
# Upload a PDF technical manual or SOP
PROJECT_ID=$(curl -s -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name":"IT Operations Demo"}' | jq -r '.id')

curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/upload/documents" \
  -F "file=@demo_data/documents/your_manual.pdf"

# Expected response
# {
#   "document_id": "...",
#   "filename": "your_manual.pdf",
#   "page_count": 24,
#   "chunk_count": 87,
#   "source_path": "data/uploads/.../your_manual.pdf"
# }
```

> **Note:** Place public domain manuals (e.g., open-source SOP PDFs, RFC documents)
> in `demo_data/documents/` for demo purposes. Files in this directory are excluded
> from git tracking. Uploaded files are stored under `backend/data/uploads/`.

> **Embedding:** On upload, each chunk is embedded and indexed in ChromaDB. This
> requires a valid `OPENAI_API_KEY` in `.env`; without it the upload fails with a
> clear error (no half-written state).

## Chat (RAG Q&A)

```bash
# Ask a question over the uploaded documents
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Docker volume data disappeared after container restart. What should I check?",
    "top_k": 5
  }'

# Expected response
# {
#   "answer": "Check the following:\n- Run `docker inspect <container>` and look at the Mounts field.\n- Confirm the volume type is not `tmpfs`.\n- Verify volumes are declared under the `volumes:` key in docker-compose.yml.",
#   "citations": [
#     {
#       "document_id": "7c1d...",
#       "chunk_id": "9b2c...",
#       "filename": "docker_operations.pdf",
#       "chunk_index": 3,
#       "snippet": "Docker volumes persist data outside container lifecycle..."
#     }
#   ]
# }
```

> **Hallucination control:** The model is instructed to answer _only_ from retrieved
> context. If the context is insufficient it responds with a fixed phrase rather than
> fabricating an answer. Every request writes one `agent_runs` row and one
> `tool_calls` row (retrieval step) to PostgreSQL for auditability.

## Search Documents

```bash
# Semantic search over a project's embedded chunks
curl "http://localhost:8000/projects/${PROJECT_ID}/search?query=how%20to%20restart%20the%20service&top_k=5"

# Expected response
# {
#   "project_id": "...",
#   "query": "how to restart the service",
#   "top_k": 5,
#   "results": [
#     {
#       "chunk_id": "9b2c...",          # == document_chunks.id in PostgreSQL
#       "content": "To restart the service, run ...",
#       "metadata": { "project_id": "...", "document_id": "...",
#                     "chunk_id": "9b2c...", "filename": "network_sop.pdf",
#                     "chunk_index": 12 },
#       "distance": 0.18,
#       "score": 0.82
#     }
#   ]
# }
```

> Each `chunk_id` returned by search equals the `document_chunks.id` UUID in
> PostgreSQL, so you can join search hits back to the full row:
> `SELECT * FROM document_chunks WHERE id = '<chunk_id>';`

## Upload Incident Tickets

```bash
# 1. Create a project and capture the project_id
PROJECT_ID=$(curl -s -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name":"IT Operations Demo"}' | jq -r '.id')

# 2. Upload a CSV (.xlsx and .json are also supported)
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/upload/tickets" \
  -F "file=@demo_data/tickets/sample_incidents.csv"

# Expected response
# {
#   "raw_count": 22,
#   "cleaned_count": 22,
#   "failed_count": 0,
#   "errors": []
# }
```

## Verify Records in PostgreSQL

```sql
-- Inspect raw_records (original data)
SELECT id, source_file, raw_json->>'ticket_id' AS ticket_id, created_at
FROM raw_records
WHERE project_id = '<your-project-id>'
ORDER BY created_at
LIMIT 5;

-- Inspect cleaned_records (ETL output)
SELECT ticket_id, occurred_at, system, module, status, priority
FROM cleaned_records
WHERE project_id = '<your-project-id>'
ORDER BY occurred_at
LIMIT 10;

-- Count distribution by priority
SELECT priority, COUNT(*) FROM cleaned_records
WHERE project_id = '<your-project-id>'
GROUP BY priority;
```

## Implementation Status

- [x] Step 1: Project scaffold, health endpoint, Docker Compose
- [x] Step 2-pre: PostgreSQL data model (10 tables, ORM models, Pydantic schemas, SQL migration)
- [x] Step 2: PDF ingestion → RAG pipeline (`POST /projects/{id}/upload/documents`)
- [x] Step 2b: Embedding + ChromaDB vector storage & search (`GET /projects/{id}/search`)
- [x] Step 3: Incident ETL (`POST /projects/{id}/upload/tickets` — CSV/Excel/JSON → PostgreSQL)
- [x] Prompt 7: RAG chat API (`POST /projects/{id}/chat` — retrieval → LLM → answer + citations)
- [x] Prompt 7: Observability — every chat request writes `agent_runs` + `tool_calls` rows
- [ ] Step 4: AI analysis tools (classify incidents, score severity, generate insights)
- [ ] Step 6: Streamlit dashboard (complete)
- [ ] Step 8+: Local model provider (Ollama), agent tools
