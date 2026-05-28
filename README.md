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

## Upload PDF Documents

```bash
# 上傳 PDF 技術手冊或 SOP
PROJECT_ID=$(curl -s -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name":"IT Operations Demo"}' | jq -r '.id')

curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/upload/documents" \
  -F "file=@demo_data/documents/your_manual.pdf"

# 預期回應
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

## Upload Incident Tickets

```bash
# 1. 建立專案，取得 project_id
PROJECT_ID=$(curl -s -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name":"IT Operations Demo"}' | jq -r '.id')

# 2. 上傳 CSV（也支援 .xlsx、.json）
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/upload/tickets" \
  -F "file=@demo_data/tickets/sample_incidents.csv"

# 預期回應
# {
#   "raw_count": 22,
#   "cleaned_count": 22,
#   "failed_count": 0,
#   "errors": []
# }
```

## Verify Records in PostgreSQL

```sql
-- 確認 raw_records 原始資料
SELECT id, source_file, raw_json->>'ticket_id' AS ticket_id, created_at
FROM raw_records
WHERE project_id = '<your-project-id>'
ORDER BY created_at
LIMIT 5;

-- 確認 cleaned_records 清洗結果
SELECT ticket_id, occurred_at, system, module, status, priority
FROM cleaned_records
WHERE project_id = '<your-project-id>'
ORDER BY occurred_at
LIMIT 10;

-- 統計各 priority 分佈
SELECT priority, COUNT(*) FROM cleaned_records
WHERE project_id = '<your-project-id>'
GROUP BY priority;
```

## Implementation Status

- [x] Step 1: Project scaffold, health endpoint, Docker Compose
- [x] Step 2-pre: PostgreSQL data model (10 tables, ORM models, Pydantic schemas, SQL migration)
- [ ] Step 2: PDF ingestion → RAG pipeline
- [x] Step 3: Incident ETL (`POST /projects/{id}/upload/tickets` — CSV/Excel/JSON → PostgreSQL)
- [ ] Step 4: AI analysis tools (classify, score, insights)
- [ ] Step 5: Observability layer (AI run logging)
- [ ] Step 6: Streamlit dashboard (complete)
- [ ] Step 7: Tests + final documentation
