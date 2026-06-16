# Product Requirements Document — OpsKnowledge Agent Lite

English | [繁體中文](PRD.zh-TW.md)

## Problem

IT/Operations teams manage large volumes of technical documentation (manuals, SOPs) and incident records (tickets, maintenance logs), but:

1. Knowledge is siloed in PDFs — hard to search and query.
2. Incident data is inconsistent across systems — different formats, missing fields.
3. There is no AI-assisted triage, classification, or insight generation.
4. No auditability for AI decisions — hard to debug or trust outputs.

## Target Users

| User | Role |
|---|---|
| IT Operations Engineer | Uploads SOPs, queries knowledge base, reviews AI analysis |
| System Integration Engineer | Uploads incident CSVs, reviews ETL output and severity scores |
| Team Lead / Manager | Reviews dashboard summaries and action items |
| (Demo) AI/Data Engineer Interviewer | Evaluates system design and code quality |

## MVP Scope

### Included

- [x] Upload PDF documents → parse → chunk → embed → store in PostgreSQL + pgvector
- [x] Semantic search / RAG Q&A over documents
- [x] Upload CSV/Excel/JSON incident records → ETL → PostgreSQL
- [x] AI classification of incident category
- [x] AI severity scoring (P1–P4)
- [x] AI insight generation and action item suggestions
- [x] Logging of every AI call to PostgreSQL (model, tokens, latency, result)
- [x] React dashboard: Upload / Chat / Dashboard / Agent Logs
- [x] Docker Compose deployment (PostgreSQL, PostgreSQL + pgvector, backend, frontend)

### Out of Scope (for this POC)

- User authentication / multi-tenant access control
- Real-time streaming of AI responses
- Production-grade vector DB (Pinecone, Weaviate, pgvector)
- Fine-tuning or custom models
- Automated alerting / PagerDuty integration
- Mobile UI

## Success Criteria

1. `/health` endpoint returns `{"status": "ok"}` with DB connected.
2. A PDF can be uploaded, chunked, and queried via semantic search.
3. A CSV of incidents can be uploaded, cleaned, and stored in PostgreSQL.
4. AI correctly classifies and scores at least 80% of sample incidents.
5. Every AI invocation is recorded with model name, tokens, and latency.
6. Demo can be walked through end-to-end in under 10 minutes.

## System Architecture & Tech Stack

OpsKnowledge Agent Lite is a containerized full-stack application. A React single-page app calls a FastAPI backend, which persists everything to PostgreSQL (with the pgvector extension for semantic search) and delegates language/embedding work to a pluggable AI provider.

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, React Router, Tailwind CSS, lucide-react, axios |
| Frontend tests | Vitest, Testing Library, jsdom |
| Backend | FastAPI, Uvicorn, SQLAlchemy, Pydantic / pydantic-settings |
| Backend tests | pytest |
| Database | PostgreSQL 16 + pgvector (`vector(384)`) |
| LLM / Embeddings | Pluggable provider: `mock` / `ollama` / `openai`; on-prem default = Ollama (`qwen2.5:7b-instruct`) for LLM + mock embeddings (dim 384) |
| Packaging / Deploy | Docker Compose (postgres, ollama, backend, frontend) |
| Observability | `agent_runs` + `tool_calls` audit logging |

- **Service ports (host → container):** frontend `8501`, backend `8000`, PostgreSQL `5432`, Ollama `11434`.
- **Backend API surface:** `health`, `projects`, `documents`, `uploads`, `chat`, `analyze`, `dashboard`.
- **AI provider model:** `EMBEDDING_PROVIDER` and `LLM_PROVIDER` independently select `mock`, `ollama`, or `openai`. The built-in default is fully offline (`mock`); the shipped `.env.example` uses Ollama for the LLM and mock embeddings for a private, on-prem-style demo.

## System Architecture Diagram

```text
┌───────────────────────────────────────────────────────────────────┐
│ Frontend — React + Vite   (:8501)                                 │
│ Event Insights | Knowledge Q&A | Dashboard | Agent Runs | Status  │
└───────────────────────────────────────────────────────────────────┘
                                 │  REST API (Axios, /api proxy)
                                 ▼
┌───────────────────────────────────────────────────────────────────┐
│ Backend — FastAPI   (:8000)                                       │
│ routers : /health /projects /documents /uploads                   │
│           /chat /analyze /dashboard                               │
│ services: document · vector_store · chat · analysis · llm         │
└───────────────────────────────────────────────────────────────────┘
                         │                                        │
                         │ SQLAlchemy                              provider: mock/Ollama/OpenAI
                         ▼                                        ▼
      ┌────────────────────────────────────┐      ┌─────────────────────────────────┐
      │ PostgreSQL 16 + pgvector  (:5432)  │      │ AI Provider (pluggable)         │
      │ 10 tables · vector(384) search     │      │ embeddings + completion         │
      │ audit: agent_runs / tool_calls     │      │ mock / Ollama(:11434) / OpenAI  │
      └────────────────────────────────────┘      └─────────────────────────────────┘
```

## User Flows

The product is organized around two guided, step-based workflows. Each step is positioned automatically from the project's `workflow-status` and the user can return to any earlier available step.

### Event Insights Workflow

```mermaid
flowchart TD
    P([Select / create project]) --> U["Upload incidents<br/>CSV / Excel / JSON"]
    U -->|"ETL: clean + normalize"| AN["AI analysis<br/>4-tool agent"]
    AN -->|"classify → score → insights → actions"| R["Analysis result<br/>(per agent run)"]
    R --> D["Dashboard / Agent runs"]
```

### Knowledge Q&A Workflow

```mermaid
flowchart TD
    P([Select / create project]) --> UP["Upload PDF documents"]
    UP -->|"chunk + embed → pgvector"| IDX["Knowledge base ready"]
    IDX --> ASK["RAG chat<br/>answers with citations"]
```
