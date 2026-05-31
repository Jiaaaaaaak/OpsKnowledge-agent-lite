# OpsKnowledge Agent Lite

English | [繁體中文](README.zh-TW.md)

An enterprise-style AI + Data Engineering POC for IT operations and system integration scenarios.

## Language / 語言說明

The **user interface** (Streamlit frontend) is written in **Traditional Chinese**
because the target scenario is an internal enterprise tool for IT operations teams
in Taiwan or Chinese-speaking environments.

The **codebase, API paths, database schema, and technical documentation** remain in
**English** to follow common engineering conventions and make the project easier to
review internationally.

| Layer | Language | Reason |
|---|---|---|
| Streamlit UI labels / buttons / messages | 繁體中文 | Target users are zh-TW IT-ops teams |
| Code identifiers (functions / classes / variables) | English | Engineering convention |
| FastAPI route paths and request / response field names | English | Backend contract stability |
| Database column / table names | English | Schema portability |
| Primary docs (`README.md`, `docs/*.md`) | English | International reviewability |
| Mirror docs (`README.zh-TW.md`, `docs/*.zh-TW.md`) | 繁體中文 | Local-team onboarding |
| Source comments and commit messages | 繁體中文 | Team preference (see CLAUDE.md Rule 13) |

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

## Quick Start (Docker Compose)

Four steps, no manual setup beyond the `.env`:

```bash
# 1. Copy the env template (defaults to mock mode — no API key needed)
cp .env.example .env

# 2. (Optional) edit .env if you want real models
#    - Set LLM_PROVIDER=openai and fill OPENAI_API_KEY for hosted OpenAI
#    - Set LLM_PROVIDER=ollama for a host-side Ollama. Docker Compose overrides
#      OLLAMA_BASE_URL with DOCKER_OLLAMA_BASE_URL (default: http://host.docker.internal:11434).

# 3. Build and start the full stack (postgres, chromadb, backend, frontend)
docker compose up --build
# or, equivalently with the included Makefile:
make up

# 4. Open the UI
#    Frontend (Streamlit): http://localhost:8501
#    Backend docs:          http://localhost:8000/docs
#    Backend health:        http://localhost:8000/health
```

Stop everything (data is preserved in named volumes):
```bash
docker compose down    # or: make down
```

Wipe data and start over (destructive — drops postgres + chroma volumes):
```bash
make clean              # asks for confirmation
```

### Services and ports

| Service | Host port | Container port | Image / build |
|---|---|---|---|
| frontend (Streamlit) | **8501** | 8501 | built from `frontend/Dockerfile` |
| backend (FastAPI) | **8000** | 8000 | built from `backend/Dockerfile` |
| postgres | **5432** | 5432 | `postgres:16-alpine` |
| chromadb | **8001** | 8000 | `chromadb/chroma:0.5.23` (host 8001 to avoid clashing with backend) |

### Startup ordering

`docker-compose.yml` chains the services with healthchecks so each one only starts
after its dependencies are actually ready:

```
postgres (pg_isready)  ─┐
                        ├─► backend (waits for both via service_healthy)
chromadb (/heartbeat)  ─┘             │
                                      └─► frontend (waits for backend /health)
```

Backend container runs `python scripts/create_tables.py && uvicorn ...` on start —
schema is applied automatically before the API comes up.

### Useful Make targets

```bash
make up           # build + start in background
make down         # stop (keep data)
make logs         # tail all services (logs-backend / logs-frontend / ... for one)
make ps           # show container status
make health       # curl /health and pretty-print
make test         # run backend pytest inside the backend container
make psql         # open a psql shell against the postgres container
make clean        # ⚠️ stop + delete volumes (asks for confirmation)
```

### Provider modes

| Mode | env vars | API key | Notes |
|---|---|---|---|
| **mock** (default) | `EMBEDDING_PROVIDER=mock`, `LLM_PROVIDER=mock` | None — `OPENAI_API_KEY` can stay empty | Deterministic local providers; runs the full pipeline offline |
| **openai** | `EMBEDDING_PROVIDER=openai`, `LLM_PROVIDER=openai` | Requires a real `OPENAI_API_KEY` | Calls the OpenAI-compatible API for real embeddings and answers |
| **ollama** (LLM) | `LLM_PROVIDER=ollama` (+ `EMBEDDING_PROVIDER=openai` or `mock`) | None for the LLM | Calls a local Ollama server for answers — for private / on-premise deployment |

> **Hosted API vs local model.** The `openai` provider is used for a **fast POC** —
> minimal setup, strong out-of-the-box quality. The `ollama` provider is prepared for
> **private / on-premise deployment**, where the LLM must run inside the customer's
> network and no data may leave the host. Switching is a one-line `.env` change
> (`LLM_PROVIDER`); no application code changes. See
> [Local model provider (Ollama)](#local-model-provider-ollama) below.

### Switching from mock mode to OpenAI

The system ships in **mock mode** by default. To connect a real OpenAI-compatible API:

1. In `backend/.env`, set the provider and key (the model / base URL already have defaults):
   ```bash
   LLM_PROVIDER=openai
   EMBEDDING_PROVIDER=openai
   OPENAI_API_KEY=sk-...your-real-key...
   # optional overrides:
   # OPENAI_BASE_URL=https://api.openai.com/v1
   # LLM_MODEL=gpt-4o-mini
   # EMBEDDING_MODEL=text-embedding-3-small
   ```
2. Verify the providers actually work **before** running the app:
   ```bash
   cd backend
   python -m app.utils.verify_providers
   ```
   This prints the current provider names, sends one short LLM request and one short
   embedding request, and reports `PASS` / `FAIL`. It **never prints the API key**
   (only a masked summary), and exits non-zero on failure so it can be used in CI.
   If the key is missing or invalid it returns a clear error.

> Switching back to mock mode is the reverse one-line change
> (`LLM_PROVIDER=mock`, `EMBEDDING_PROVIDER=mock`); no application code is involved.

### Hostnames: Docker vs local

The app connects to PostgreSQL and ChromaDB via `POSTGRES_HOST` / `CHROMA_HOST`
(there is no `DATABASE_URL` — see `backend/app/core/config.py`).

- **Docker Compose** overrides these to the service names `postgres` and `chromadb`
  (set in `docker-compose.yml`), so you do not edit `.env` for container networking.
- **Local (no Docker)** uses the `.env.example` defaults of `localhost`.

## Mock Mode (No API Key Required)

If you have not yet set up an OpenAI or Ollama account, you can run the full backend
pipeline locally using deterministic mock providers:

| Provider | env var | Behaviour |
|---|---|---|
| `MockEmbeddingProvider` | `EMBEDDING_PROVIDER=mock` | Returns 384-dim unit vectors (MD5-seeded, no network call) |
| `MockLLMProvider` | `LLM_PROVIDER=mock` | Returns a `[mock]` prefixed answer extracted from retrieved context |

```bash
# .env — these are the defaults from .env.example, no edit needed:
EMBEDDING_PROVIDER=mock
LLM_PROVIDER=mock
# OPENAI_API_KEY is left empty — it is ignored in mock mode
```

### What works in mock mode
- Backend unit tests, zero external calls
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

## Local Model Provider (Ollama)

For private / on-premise scenarios the LLM can run entirely on local hardware via
[Ollama](https://ollama.com), with no OpenAI account and no data leaving the host.
`OllamaLLMProvider` calls the native Ollama HTTP API (`/api/chat`) directly.

```bash
# 1. Install and start Ollama, then pull the model
ollama serve                       # starts the local server on :11434
ollama pull qwen2.5:7b-instruct

# 2. Point the app at Ollama (.env)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
# Docker Compose uses this inside the backend container.
DOCKER_OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
# Embeddings are independent — keep EMBEDDING_PROVIDER=mock (offline) or =openai
EMBEDDING_PROVIDER=mock
```

That is the only change required — no application code changes. If the Ollama server
is unreachable, `/chat` fails with a clear error (e.g. *"無法連線到 Ollama … 請確認
Ollama 服務已啟動"*) rather than hanging or returning a fabricated answer.

> **Scope:** This provider covers the **LLM** only. Embeddings are still selected by
> `EMBEDDING_PROVIDER` (`openai` / `mock`). A fully local stack would also need a local
> embedding provider — the `EmbeddingProvider` interface supports adding one the same way.
> Ollama is **not required for the normal demo**: the default mock mode runs the full
> pipeline with no external dependencies.

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
psql -h localhost -U opsuser -d opsknowledge -f backend/migrations/001_initial_schema.sql
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

> **Embedding:** On upload, each chunk is embedded and indexed in ChromaDB. In mock
> mode (the default) no API key is needed. In openai mode this requires a valid
> `OPENAI_API_KEY` in `.env`; without it the upload fails with a clear error (no
> half-written state).

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

## Incident Analysis Agent

After ingesting tickets, run the multi-tool incident analysis agent. It chains four
LLM-driven tools and writes results into PostgreSQL with full audit trail.

```bash
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/analyze/incidents"

# Expected response
# {
#   "agent_run_id": "9c8f3b1a-0f4c-4f1d-9b65-1c0c3a86a512",
#   "status": "success",
#   "summary": {
#     "records_analyzed": 20,
#     "needs_review": 3,
#     "insights_created": 5,
#     "action_items_created": 4
#   }
# }
```

**The four tools (run in sequence)**

| # | Tool | Persists to |
|---|---|---|
| 1 | `classify_incidents` — categorize each ticket | (combined into `incident_analysis`) |
| 2 | `analyze_severity` — severity 1-5, sentiment, confidence, `needs_review` flag | `incident_analysis` |
| 3 | `generate_insights` — project-level patterns and recommendations | `insights` |
| 4 | `create_action_items` — actionable follow-ups derived from insights | `action_items` (all `status="open"`) |

Every tool requests structured JSON from the LLM and validates the output with
Pydantic; validation failures are recorded rather than silently dropped. The endpoint
is idempotent — re-running it skips records already in `incident_analysis`. Full API
reference: [docs/API.md](docs/API.md#incident-analysis-agent).

## Frontend (Streamlit)

The Streamlit UI is the recommended way to drive the full demo. It mirrors the
backend API surface and is what an interviewer or stakeholder will actually see.

### Pages

| Page | Purpose |
|---|---|
| Project Setup | Create or select the active project (kept in session state) |
| Upload | Upload PDFs (RAG corpus) and incident tickets (ETL → cleaned_records) |
| Knowledge Chat | RAG Q&A — answer + citations (filename, chunk index, snippet) |
| Incident Analysis | One-click "Run Incident Analysis" — fires the 4-tool agent and shows the summary |
| Dashboard | ticket count, category / severity distribution charts, top insights, open action items, recent agent runs |
| Agent Logs | Browse `agent_runs`; select a row to drill into its `tool_calls` (input / output / errors / latency per tool) |

### Run with Docker (preferred for demo)
```bash
docker compose up --build
# UI:      http://localhost:8501
# Backend: http://localhost:8000
```
`BACKEND_URL=http://backend:8000` is injected by `docker-compose.yml`, so the
Streamlit container reaches the backend over the compose network.

### Run locally (no Docker)
```bash
# Start the backend first (see Local Development above), then:
cd frontend
pip install -r requirements.txt
BACKEND_URL=http://localhost:8000 streamlit run streamlit_app.py
# UI: http://localhost:8501
```

`BACKEND_URL` defaults to `http://localhost:8000` if unset. All HTTP errors are
caught and surfaced via `st.error()` — the UI never shows a Python traceback.

## Demo Flow (end-to-end, mock mode)

```bash
# 1. Create a project
PROJECT_ID=$(curl -s -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name":"IT Operations Demo"}' | jq -r '.id')

# 2. Upload a SOP PDF (RAG corpus)
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/upload/documents" \
  -F "file=@demo_data/documents/your_manual.pdf"

# 3. Upload incident tickets (CSV / Excel / JSON)
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/upload/tickets" \
  -F "file=@demo_data/tickets/sample_incidents.csv"

# 4. Run the incident analysis agent
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/analyze/incidents"

# 5. Ask a grounded question over the SOP corpus
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/chat" \
  -H "Content-Type: application/json" \
  -d '{"question":"How do I respond to a Docker volume outage?","top_k":5}'
```

## Observability & Debugging

Every agent invocation writes one row to `agent_runs` plus one row per tool call to
`tool_calls`. They are the primary debugging surface — there is no other log to
correlate against.

```sql
-- Last 10 agent runs (chat + analysis) for a project
SELECT id, task_type, model_name, status, latency_ms, created_at
FROM agent_runs
WHERE project_id = '<your-project-id>'
ORDER BY created_at DESC
LIMIT 10;

-- All tool calls for one analysis run (in order)
SELECT tool_name, latency_ms, error_message, output_json
FROM tool_calls
WHERE agent_run_id = '<agent_run_id from the response>'
ORDER BY created_at;

-- Find runs where any tool failed validation
SELECT ar.id, ar.task_type, ar.status, tc.tool_name, tc.error_message
FROM agent_runs ar
JOIN tool_calls tc ON tc.agent_run_id = ar.id
WHERE tc.error_message IS NOT NULL
ORDER BY ar.created_at DESC;
```

How to use this trail when something looks wrong:
- **`agent_runs.status = "partial"`** → at least one tool's LLM output failed Pydantic
  validation. Look at `tool_calls.error_message` for the failing tool to see the parse
  error, then `tool_calls.input_json` to see what was sent. The orchestrator does not
  retry — partial runs persist whatever the other tools produced.
- **`agent_runs.status = "error"`** → orchestrator-level failure (LLM provider
  unreachable, DB error, etc.). `agent_runs.error_message` carries the exception.
- **Unexpected category / severity** → `tool_calls.output_json` for `classify_incidents`
  and `analyze_severity` summarizes counts; join with `incident_analysis` by record
  to drill in.
- **High latency** → `tool_calls.latency_ms` per tool isolates the slow step (typically
  one of the per-record tools when running against a real LLM).

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `make up` fails with `.env 不存在` | First-time setup not done | `cp .env.example .env` then retry |
| `bind: address already in use` on port 5432 / 8000 / 8001 / 8501 | Local Postgres / another dev server is holding the port | Stop the conflicting process, or change the **host** side of the port mapping in `docker-compose.yml` (e.g. `"5433:5432"`) |
| `backend` container restarts in a loop | Schema migration failed (postgres not actually ready, or volume from older schema lingers) | `make logs-backend` to see the traceback; if schema changed, `make clean` wipes volumes (destructive) |
| `chromadb` healthcheck never goes healthy | First boot can take 10-20s; on slow disks longer | Wait; if still red after 60s: `make logs-chromadb`. Persistent failure is usually a corrupted volume — `make clean` resets it |
| Frontend shows `無法連線到後端 (http://backend:8000)` | Backend container is down or not yet healthy | `make ps` to check status; `make logs-backend` for the cause |
| Chat / analysis returns `OPENAI_API_KEY` errors | `.env` set `LLM_PROVIDER=openai` but key is empty | Either fill `OPENAI_API_KEY` in `.env`, or switch to `LLM_PROVIDER=mock` |
| Ollama mode can't reach the server from container | Ollama is not running on the host, or you need a different container URL | Start `ollama serve` on the host, or set `DOCKER_OLLAMA_BASE_URL` for a different endpoint |
| Tests fail with `ModuleNotFoundError` when running `make test-local` | Local `.venv` missing or stale | `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` |
| Postgres / Chroma data unexpectedly empty after restart | Someone ran `docker compose down -v` or `make clean` | Volumes were dropped on purpose — re-ingest. Use `make down` (without `-v`) to preserve data |
| Windows / WSL2 path issues with bind mounts | Volume mounts use Linux paths | Run all commands from inside WSL2, not from PowerShell |

## Implementation Status

- [x] Step 1: Project scaffold, health endpoint, Docker Compose
- [x] Step 2-pre: PostgreSQL data model (10 tables, ORM models, Pydantic schemas, SQL migration)
- [x] Step 2: PDF ingestion → RAG pipeline (`POST /projects/{id}/upload/documents`)
- [x] Step 2b: Embedding + ChromaDB vector storage & search (`GET /projects/{id}/search`)
- [x] Step 3: Incident ETL (`POST /projects/{id}/upload/tickets` — CSV/Excel/JSON → PostgreSQL)
- [x] Prompt 7: RAG chat API (`POST /projects/{id}/chat` — retrieval → LLM → answer + citations)
- [x] Prompt 7: Observability — every chat request writes `agent_runs` + `tool_calls` rows
- [x] Step 4: Incident analysis agent (`POST /projects/{id}/analyze/incidents` — 4 tools, structured JSON, Pydantic validation, full agent_runs/tool_calls trail)
- [ ] Step 6: Streamlit dashboard (complete)
- [x] Local model provider (Ollama) — native HTTP LLM provider for private / on-premise deployment
- [ ] Step 8+: Local embedding provider, additional agent tools
