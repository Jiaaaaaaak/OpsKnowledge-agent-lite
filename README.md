# OpsKnowledge Agent Lite

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

## Local Development (without Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
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

**Option C — Docker Compose (automatic on first start):**
```bash
docker compose up --build
# Then run the script inside the backend container:
docker compose exec backend python scripts/create_tables.py
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

## Implementation Status

- [x] Step 1: Project scaffold, health endpoint, Docker Compose
- [x] Step 2-pre: PostgreSQL data model (10 tables, ORM models, Pydantic schemas, SQL migration)
- [ ] Step 2: PDF ingestion → RAG pipeline
- [ ] Step 3: Incident ETL (CSV/Excel/JSON → PostgreSQL)
- [ ] Step 4: AI analysis tools (classify, score, insights)
- [ ] Step 5: Observability layer (AI run logging)
- [ ] Step 6: Streamlit dashboard (complete)
- [ ] Step 7: Tests + final documentation
