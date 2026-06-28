# OpsWeave

English | [繁體中文](README.zh-TW.md)

An interview-ready RAG knowledge base for IT operations documents. It ingests PDF SOPs and manuals (with OCR fallback for scanned pages), chunks and embeds them into PostgreSQL + pgvector, answers operational questions with citations — either via a fixed RAG pipeline (`/chat`) or an autonomous tool-calling agent (`/agent-chat`) — and records AI runs for auditability. Multilingual embeddings (bge-m3) enable cross-lingual retrieval, and answers are normalized to Traditional Chinese.

## Language / 語言說明

The **user interface** (React frontend) is written in **Traditional Chinese**
because the target scenario is an internal enterprise tool for IT operations teams
in Taiwan or Chinese-speaking environments.

The **codebase, API paths, database schema, and technical documentation** remain in
**English** to follow common engineering conventions and make the project easier to
review internationally.

| Layer | Language | Reason |
|---|---|---|
| React UI labels / buttons / messages | 繁體中文 | Target users are zh-TW IT-ops teams |
| Code identifiers (functions / classes / variables) | English | Engineering convention |
| FastAPI route paths and request / response field names | English | Backend contract stability |
| Database column / table names | English | Schema portability |
| Primary docs (`README.md`, `docs/*.md`) | English | International reviewability |
| Mirror docs (`README.zh-TW.md`, `docs/*.zh-TW.md`) | 繁體中文 | Local-team onboarding |
| Source comments and commit messages | 繁體中文 | Team preference (see CLAUDE.md Rule 13) |

## What It Does

| Capability | Description |
|---|---|
| Document RAG | Upload PDF manuals/SOPs → chunk, embed, index in PostgreSQL full-text + pgvector; OCR fallback (Tesseract) recovers scanned / image pages |
| RAG Chat (`/chat`) | Ask operational questions → hybrid search → optional rerank → LLM answer with citations (fixed pipeline) |
| Agent Chat (`/agent-chat`) | Autonomous tool-calling agent: the LLM decides whether/what/how-many-times to retrieve and which strategy (hybrid / keyword / vector), bounded by `AGENT_MAX_STEPS` |
| Multilingual / cross-lingual | bge-m3 embeddings answer Chinese questions over English docs; answers normalized to Traditional Chinese, with translated citation snippets |
| Observability | Every AI tool call logged to PostgreSQL for auditability |
| UI | React guided workflow for uploads, Q&A, and agent run inspection |

> **Administrator login required.** The app is now gated behind a server-side session
> (HTTP-only cookie). On first run there is no administrator yet, so the login page
> **bootstraps the first administrator** (equivalently `POST /auth/bootstrap`);
> afterwards the same page is a normal session login. An operational **Dashboard**
> (`/dashboard`) and a sticky status bar sit behind this gate.
>
> **Scope (honest):** what is real today is the auth boundary, the operational
> dashboard, and the existing RAG knowledge base described above (the built-in
> Knowledge Agent). The broader vision of multiple built-in agents, channels, and
> integrations is **design-only / future work**, not implemented.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2
- **Database**: PostgreSQL 16
- **Vector DB**: PostgreSQL + pgvector
- **AI**: OpenAI-compatible (swappable to Ollama); multilingual `bge-m3` embeddings
- **Document ingestion**: pypdf + Tesseract OCR fallback (`poppler-utils`), OpenCC `s2twp` Traditional-Chinese normalization
- **Frontend**: React (Vite + TypeScript + Tailwind CSS)
- **Infra**: Docker Compose

## Quick Start (Docker Compose)

The default interview/demo path is local-first: Ollama for both the LLM
(`qwen2.5:7b-instruct`) and multilingual `bge-m3` embeddings (1024-dim) for pgvector search.

```bash
# 1. Copy the env template (defaults to Ollama for the LLM and embeddings)
cp .env.example .env

# 2. (Optional) edit .env if you want real models
#    - Set LLM_PROVIDER=openai and fill OPENAI_API_KEY for hosted OpenAI
#    - Keep LLM_PROVIDER=ollama for the bundled Docker Compose Ollama service.

# 3. Build and start the full stack (postgres + pgvector, ollama, backend, frontend)
docker compose up --build -d
# or, equivalently with the included Makefile:
make up

# 4. Pull the local LLM + embedding models into the ollama_data volume
make pull-ollama   # pulls qwen2.5:7b-instruct and bge-m3

# 5. Open the UI
#    Frontend (React):     http://localhost:8501
#    Backend docs:          http://localhost:8000/docs
#    Backend health:        http://localhost:8000/health
```

Stop everything (data is preserved in named volumes):
```bash
docker compose down    # or: make down
```

Wipe data and start over (destructive — drops postgres data and pulled Ollama models):
```bash
make clean              # asks for confirmation
```

### Services and ports

| Service | Host port | Container port | Image / build |
|---|---|---|---|
| frontend (React) | **8501** | 8501 | built from `frontend/Dockerfile` |
| backend (FastAPI) | **8000** | 8000 | built from `backend/Dockerfile` |
| postgres + pgvector | **5432** | 5432 | `pgvector/pgvector:pg16` |
| ollama | **11434** | 11434 | `ollama/ollama` |

### Startup ordering

`docker-compose.yml` chains the services with healthchecks so each one only starts
after its dependencies are actually ready:

```
postgres (pg_isready)  ─┐
                        ├─► backend (waits for dependencies via service_healthy)
ollama (ollama list)   ─┘             │
                                      └─► frontend (waits for backend /health)
```

Backend container runs `alembic upgrade head && uvicorn ...` on start — versioned
schema migrations are applied automatically before the API comes up (no `create_all`).
`python scripts/create_tables.py` remains as an alias that runs the same migrations.

### Useful Make targets

```bash
make up           # build + start in background
make down         # stop (keep data)
make logs         # tail all services (logs-backend / logs-frontend / ... for one)
make logs-ollama  # tail Ollama logs
make ps           # show container status
make health       # curl /health and pretty-print
make test         # run backend pytest inside the backend container
make pull-ollama  # pull the local LLM + bge-m3 embedding models into ollama_data
make psql         # open a psql shell against the postgres container
make clean        # ⚠️ stop + delete volumes (asks for confirmation)
```

### Provider modes

| Mode | env vars | API key | Notes |
|---|---|---|---|
| **ollama-local** (default) | `LLM_PROVIDER=ollama`, `EMBEDDING_PROVIDER=ollama` | None | Local Ollama answers + multilingual `bge-m3` 1024-dim embeddings for cross-lingual pgvector search |
| **mock** | `EMBEDDING_PROVIDER=mock`, `LLM_PROVIDER=mock` | None — `OPENAI_API_KEY` can stay empty | Fully deterministic offline providers; useful for tests |
| **openai** | `EMBEDDING_PROVIDER=openai`, `LLM_PROVIDER=openai` | Requires a real `OPENAI_API_KEY` | Hosted LLM + OpenAI-compatible embeddings; embeddings are requested at 1024 dimensions |

> **Local-first for interviews.** The main demo path uses `ollama` for both answers
> and multilingual `bge-m3` embeddings. The `openai` provider remains available when
> hosted model quality is needed, and `mock` gives fully deterministic offline runs.
> Switching is an `.env` change; no application code changes. See
> [Local model provider (Ollama)](#local-model-provider-ollama) below.

### Switching from local Ollama mode to OpenAI

The system ships in **Ollama LLM + Ollama (bge-m3) embedding mode** by default. To
connect a real OpenAI-compatible API:

1. In the project-root `.env` (the same file `cp .env.example .env` creates), set the
   provider and key (the model / base URL already have defaults). Config is anchored to
   this root `.env`, so it is read no matter which directory you launch from:
   ```bash
   LLM_PROVIDER=openai
   EMBEDDING_PROVIDER=openai
   EMBEDDING_DIMENSIONS=1024
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
   (the module lives under `backend/`, so run it from there; it still reads the
   root `.env`.) This prints the current provider names, sends one short LLM request
   and one short embedding request, and reports `PASS` / `FAIL`. It **never prints the API key**
   (only a masked summary), and exits non-zero on failure so it can be used in CI.
   If the key is missing or invalid it returns a clear error.

> `EMBEDDING_DIMENSIONS=1024` is important because the pgvector column is
> `vector(1024)`. Switching back to local demo mode is:
> `LLM_PROVIDER=ollama`, `EMBEDDING_PROVIDER=ollama` (or `EMBEDDING_PROVIDER=mock`
> for deterministic offline vectors).

### Hostnames: Docker vs local

The app connects to PostgreSQL with pgvector via the `POSTGRES_*` settings.
(there is no `DATABASE_URL` — see `backend/app/core/config.py`).

- **Docker Compose** overrides `POSTGRES_HOST` to `postgres`. pgvector is a
  PostgreSQL extension inside that service, not a separate hostname.
- **Docker Compose** overrides `OLLAMA_BASE_URL` to `http://ollama:11434` for
  container networking.
- **Local (no Docker)** uses the `.env.example` defaults of `localhost`.

## Mock Mode (No API Key Required)

If you need fully deterministic tests without running a local model request, switch
both providers to mock:

| Provider | env var | Behaviour |
|---|---|---|
| `MockEmbeddingProvider` | `EMBEDDING_PROVIDER=mock` | Returns 1024-dim unit vectors (MD5-seeded, no network call) |
| `MockLLMProvider` | `LLM_PROVIDER=mock` | Returns a `[mock]` prefixed answer extracted from retrieved context |

```bash
EMBEDDING_PROVIDER=mock
LLM_PROVIDER=mock
# OPENAI_API_KEY is left empty — it is ignored in mock mode
```

### What works in mock mode
- Backend unit tests, zero external calls
- `POST /projects/{id}/upload/documents` — PDF is parsed, chunked, stored in PostgreSQL;
  embeddings are generated locally and stored in PostgreSQL + pgvector (PostgreSQL + pgvector must be running)
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

### Quick local smoke test (requires PostgreSQL + pgvector running)
```bash
cp .env.example .env
# Edit .env: set EMBEDDING_PROVIDER=mock  LLM_PROVIDER=mock
#            set POSTGRES_* to your local PostgreSQL + pgvector service

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

# Verify health (both db and vector should show "connected")
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
# 1. Point the app at Ollama (.env)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
# Docker Compose uses the bundled ollama service inside the backend container.
DOCKER_OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
# Embeddings are independent — the default uses Ollama bge-m3 (multilingual, cross-lingual);
# you can also keep EMBEDDING_PROVIDER=mock (deterministic offline) or =openai
EMBEDDING_PROVIDER=ollama
OLLAMA_EMBEDDING_MODEL=bge-m3

# 2. Start compose, then pull the LLM + embedding models into the ollama_data volume
docker compose up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b-instruct
docker compose exec ollama ollama pull bge-m3
```

That is the only change required — no application code changes. If the Ollama server
is unreachable, `/chat` fails with a clear error (e.g. *"無法連線到 Ollama … 請確認
Ollama 服務已啟動"*) rather than hanging or returning a fabricated answer.

> **Scope:** This provider covers the **LLM**. Embeddings are selected independently by
> `EMBEDDING_PROVIDER` (`ollama` / `openai` / `mock`); the default `ollama` path uses the
> local multilingual `bge-m3` model, giving a fully local, on-prem-style stack with no
> data leaving the host. Use `EMBEDDING_PROVIDER=mock` when you want deterministic,
> dependency-light vector search (e.g. CI).

## Local Development (without Docker)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Start PostgreSQL and PostgreSQL + pgvector separately, then:
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
psql -h localhost -U opsuser -d opsweave -f backend/migrations/001_initial_schema.sql
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
opsweave/
  backend/           FastAPI service
    app/
      core/          Config, logging
      api/           Route handlers
      models/        SQLAlchemy ORM models
      schemas/       Pydantic request/response schemas
      services/      Business logic
      db/            DB session, migrations
      utils/         Shared helpers
    tests/
  frontend/          React UI (Vite + TypeScript + Tailwind CSS)
  docs/              Architecture, PRD, data model, API docs
  demo_data/         Sample PDFs for demos
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
#   "source_path": "data/uploads/.../your_manual.pdf",
#   "ocr_page_count": 0
# }
```

> **OCR fallback:** Pages with too little extractable text (scanned / image PDFs) are
> rendered and OCR'd with Tesseract (`chi_tra+chi_sim+eng`, normalized to Traditional
> Chinese); `ocr_page_count` reports how many pages were recovered this way. Controlled
> by `OCR_ENABLED` / `OCR_DPI` / `OCR_LANGUAGES` / `OCR_MIN_CHARS`. It degrades gracefully
> when `tesseract` / `poppler` are absent (the Docker backend image bundles both).

> **Note:** Place public domain manuals (e.g., open-source SOP PDFs, RFC documents)
> in `demo_data/documents/` for demo purposes. Files in this directory are excluded
> from git tracking. Uploaded files are stored under `backend/data/uploads/`.

> **Embedding:** On upload, each chunk is embedded and indexed in PostgreSQL + pgvector.
> In the default Ollama mode (multilingual `bge-m3`) and in mock mode no API key is needed.
> In openai mode this requires a valid `OPENAI_API_KEY` in `.env`; without it the upload
> fails with a clear error (no half-written state).

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
> fabricating an answer. Every request writes one `agent_runs` row (`task_type="rag_chat"`)
> and one `tool_calls` row (`tool_name="hybrid_search"`) to PostgreSQL for auditability.

> **Cross-lingual citations:** Each citation also carries `source_language` (`"zh"`/`"en"`)
> and `snippet_translated` — the snippet translated into the question's language when the
> chunk language differs (otherwise `null`). A `translate` tool call is logged when any
> snippet is translated.

## Agent Chat (Autonomous Tool-Calling)

```bash
# Same request/response shape as /chat; the LLM drives retrieval itself.
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/agent-chat" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which command resets the cache and what error code 4xx means?",
    "top_k": 5
  }'
```

Unlike `/chat`'s fixed pipeline, `/agent-chat` lets the LLM decide — via a single
`search_documents(query, strategy)` tool — whether to retrieve, what to query, how many
times, and which strategy (`hybrid` default / `keyword` for exact terms / `vector` for
semantic), then answers. The loop is bounded by `AGENT_MAX_STEPS`. It writes one
`agent_runs` row (`task_type="agent_chat"`, with `search_count` / `stop_reason`) plus one
`tool_calls` row per search (`tool_name="search_documents"`, input `query`/`strategy`).

## Search Documents

```bash
# Hybrid search over a project's indexed chunks
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
#       "fusion_score": 0.0325,
#       "sources": ["vector", "keyword"],
#       "scores": { "vector": 0.82, "keyword": 0.41 }
#     }
#   ]
# }
```

> Each `chunk_id` returned by search equals the `document_chunks.id` UUID in
> PostgreSQL, so you can join search hits back to the full row:
> `SELECT * FROM document_chunks WHERE id = '<chunk_id>';`

## Frontend (React)

The React UI is the recommended way to drive the full demo. It mirrors the
backend API surface and is what an interviewer or stakeholder will actually see.

**Stack:** Vite + React 18 + TypeScript + Tailwind CSS + React Router v7

### Pages

| Page | Route | Purpose |
|---|---|---|
| Login | `/login` | Administrator session login; on first run it bootstraps the first administrator |
| Dashboard | `/dashboard` | Operational overview: system pulse plus knowledge / agent / activity groups |
| Project Setup | `/projects` | Create or select the active project (kept in React context) |
| Knowledge Workflow | `/knowledge/workflow` | Guided flow: upload PDF → confirm chunks → RAG chat with citations |
| Agent Runs | `/agent-runs` | Browse `agent_runs`; drill into `tool_calls` (input / output / errors / latency per tool) |

### Run with Docker (preferred for demo)
```bash
docker compose up --build
# UI:      http://localhost:8501
# Backend: http://localhost:8000
```
`BACKEND_URL=http://backend:8000` is injected by `docker-compose.yml`, so the
React container reaches the backend over the compose network.

### Run locally (no Docker)
```bash
# Start the backend first (see Local Development above), then:
cd frontend
npm install
BACKEND_URL=http://localhost:8000 npm run dev
# UI: http://localhost:5173  (dev server)
# or: npm run preview        (production preview on :8501)
```

## Demo Flow (end-to-end, local Ollama mode)

```bash
# 1. Create a project
PROJECT_ID=$(curl -s -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name":"IT Operations Demo"}' | jq -r '.id')

# 2. Upload a SOP PDF (RAG corpus)
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/upload/documents" \
  -F "file=@demo_data/documents/your_manual.pdf"

# 3. Confirm document count, pages, and chunks
curl "http://localhost:8000/projects/${PROJECT_ID}/workflow-status"

# 4. Ask a grounded question over the SOP corpus
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/chat" \
  -H "Content-Type: application/json" \
  -d '{"question":"How do I respond to a Docker volume outage?","top_k":5}'

# 5. Inspect agent runs and tool calls for retrieval observability
curl "http://localhost:8000/projects/${PROJECT_ID}/agent-runs"
```

## Observability & Debugging

Every agent invocation writes one row to `agent_runs` plus one row per tool call to
`tool_calls`. They are the primary debugging surface — there is no other log to
correlate against.

```sql
-- Last 10 RAG chat agent runs for a project
SELECT id, task_type, model_name, status, latency_ms, created_at
FROM agent_runs
WHERE project_id = '<your-project-id>'
ORDER BY created_at DESC
LIMIT 10;

-- All tool calls for one RAG chat run (in order)
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
- **`agent_runs.status = "error"`** → orchestrator-level failure (LLM provider
  unreachable, DB error, etc.). `agent_runs.error_message` carries the exception.
- **High latency** → `tool_calls.latency_ms` per tool isolates the slow step.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `make up` fails with `.env 不存在` | First-time setup not done | `cp .env.example .env` then retry |
| `bind: address already in use` on port 5432 / 8000 / 8501 | Local Postgres / another dev server is holding the port | Stop the conflicting process, or change the **host** side of the port mapping in `docker-compose.yml` (e.g. `"5433:5432"`) |
| `backend` container restarts in a loop | Schema migration failed (postgres not actually ready, or volume from older schema lingers) | `make logs-backend` to see the traceback; if schema changed, `make clean` wipes volumes (destructive) |
| Frontend shows `無法連線到後端 (http://backend:8000)` | Backend container is down or not yet healthy | `make ps` to check status; `make logs-backend` for the cause |
| Chat returns `OPENAI_API_KEY` errors | `.env` set `LLM_PROVIDER=openai` but key is empty | Either fill `OPENAI_API_KEY` in `.env`, or switch to `LLM_PROVIDER=mock` |
| Ollama mode can't reach the server from container | The `ollama` service is not healthy, the model has not been pulled, or `DOCKER_OLLAMA_BASE_URL` points to the wrong endpoint | `docker compose ps ollama`; then run `docker compose exec ollama ollama pull qwen2.5:7b-instruct`, or set `DOCKER_OLLAMA_BASE_URL` for an external endpoint |
| Ollama request times out | Local model is loading or CPU inference is slower than the request timeout | Keep the app running and retry after model warm-up, or increase `OLLAMA_TIMEOUT_SECONDS` in `.env`; use a smaller model for demos if needed |
| Tests fail with `ModuleNotFoundError` when running `make test-local` | Local `.venv` missing or stale | `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` |
| Postgres / pgvector data unexpectedly empty after restart | Someone ran `docker compose down -v` or `make clean` | Volumes were dropped on purpose — re-ingest. Use `make down` (without `-v`) to preserve data |
| Windows / WSL2 path issues with bind mounts | Volume mounts use Linux paths | Run all commands from inside WSL2, not from PowerShell |

## Implementation Status

- [x] Project scaffold, health endpoint, Docker Compose
- [x] PostgreSQL data model (ORM models, Pydantic schemas, SQL migration)
- [x] PDF ingestion → RAG pipeline (`POST /projects/{id}/upload/documents`), with Tesseract OCR fallback for scanned pages
- [x] Embedding + PostgreSQL + pgvector vector storage & search (`GET /projects/{id}/search`)
- [x] RAG chat API (`POST /projects/{id}/chat` — retrieval → optional rerank → LLM → answer + citations)
- [x] Autonomous tool-calling agent (`POST /projects/{id}/agent-chat` — LLM-driven retrieval, strategy selection)
- [x] Multilingual / cross-lingual retrieval (`bge-m3`) + Traditional-Chinese normalization + translated citation snippets
- [x] Observability — every chat / agent request writes `agent_runs` + `tool_calls` rows
- [x] React guided workflow UI (Vite + TypeScript + Tailwind CSS)
- [x] Local model provider (Ollama) — native HTTP LLM + multilingual embedding provider for private / on-premise deployment
- [ ] Additional agent tools
