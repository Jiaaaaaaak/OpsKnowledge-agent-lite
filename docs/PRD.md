# Product Requirements Document — OpsKnowledge Agent Lite

English | [繁體中文](PRD.zh-TW.md)

## Problem

IT/Operations teams manage large volumes of technical documentation (manuals, SOPs), but:

1. Knowledge is siloed in PDFs — hard to search and query.
2. No AI-assisted Q&A over documents with citation traceability.
3. No auditability for AI decisions — hard to debug or trust outputs.

## Target Users

| User | Role |
|---|---|
| IT Operations Engineer | Uploads SOPs, queries knowledge base via RAG chat |
| (Demo) AI/Data Engineer Interviewer | Evaluates system design and code quality |

## MVP Scope

### Included

- [x] Upload PDF documents → parse → chunk → embed → store in PostgreSQL + pgvector
- [x] OCR fallback for scanned / image PDFs (Tesseract, normalized to Traditional Chinese)
- [x] Hybrid search / RAG Q&A over documents with citations (`/chat`, fixed pipeline)
- [x] Autonomous tool-calling agent Q&A (`/agent-chat`): the LLM decides whether/what/how-many-times to retrieve and which strategy
- [x] Multilingual / cross-lingual retrieval (bge-m3): English docs answer Chinese questions; answers normalized to Traditional Chinese with translated citation snippets
- [x] Logging of every AI call to PostgreSQL (model, tokens, latency, result)
- [x] React guided workflow UI: Upload → Confirm → Chat → Inspect
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
2. A PDF can be uploaded, chunked, and queried via hybrid search.
3. RAG chat returns answers with citations traceable to source chunks.
4. Every AI invocation is recorded with model name, tokens, and latency.
5. Demo can be walked through end-to-end in under 10 minutes.

## System Architecture & Tech Stack

OpsKnowledge Agent Lite is a containerized full-stack application. A React single-page app calls a FastAPI backend, which persists everything to PostgreSQL. Retrieval combines PostgreSQL full-text search with pgvector dense search, then delegates language/embedding work to pluggable AI providers.

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, React Router, Tailwind CSS, lucide-react, axios |
| Frontend tests | Vitest, Testing Library, jsdom |
| Backend | FastAPI, Uvicorn, SQLAlchemy, Pydantic / pydantic-settings |
| Backend tests | pytest |
| Database | PostgreSQL 16 + pgvector (`vector(1024)`) |
| LLM / Embeddings | Pluggable provider: `mock` / `ollama` / `openai`; on-prem default = Ollama (`qwen2.5:7b-instruct`) for LLM + multilingual `bge-m3` embeddings (dim 1024) |
| Document ingestion | pypdf text extraction with Tesseract OCR fallback (`chi_tra+chi_sim+eng`) for scanned pages; OpenCC `s2twp` Traditional-Chinese normalization |
| Packaging / Deploy | Docker Compose (postgres, ollama, backend, frontend); backend image bundles `tesseract-ocr` + `poppler-utils` |
| Observability | `agent_runs` + `tool_calls` audit logging |

- **Service ports (host → container):** frontend `8501`, backend `8000`, PostgreSQL `5432`, Ollama `11434`.
- **Backend API surface:** `health`, `projects`, `documents`, `chat` (`/chat` + `/agent-chat`), `dashboard` (workflow-status, agent-runs, tool-calls).
- **AI provider model:** `EMBEDDING_PROVIDER` and `LLM_PROVIDER` independently select `mock`, `ollama`, or `openai`. The built-in code default is fully offline (`mock`); the shipped `.env.example` uses Ollama for both the LLM (`qwen2.5:7b-instruct`) and multilingual embeddings (`bge-m3`) for a private, on-prem-style demo.

## System Architecture Diagram

```text
┌───────────────────────────────────────────────────────────────────┐
│ Frontend — React + Vite   (:8501)                                 │
│ Knowledge Workflow | Agent Runs | System Status                   │
└───────────────────────────────────────────────────────────────────┘
                                 │  REST API (Axios, /api proxy)
                                 ▼
┌───────────────────────────────────────────────────────────────────┐
│ Backend — FastAPI   (:8000)                                       │
│ routers : /health /projects /documents /chat /agent-chat          │
│           /workflow-status /agent-runs /tool-calls                │
│ services: document · ocr · retrieval · vector_store · chat ·      │
│           agent · llm                                              │
└───────────────────────────────────────────────────────────────────┘
                         │                                        │
                         │ SQLAlchemy                              provider: mock/Ollama/OpenAI
                         ▼                                        ▼
      ┌────────────────────────────────────┐      ┌─────────────────────────────────┐
      │ PostgreSQL 16 + pgvector  (:5432)  │      │ AI Provider (pluggable)         │
      │ full-text + vector(1024) search     │      │ embeddings + completion         │
      │ audit: agent_runs / tool_calls     │      │ mock / Ollama(:11434) / OpenAI  │
      └────────────────────────────────────┘      └─────────────────────────────────┘
```

## User Flow

The product is organized around a single guided, step-based workflow. Each step is positioned automatically from the project's `workflow-status` and the user can return to any earlier available step.

### Knowledge Q&A Workflow

```mermaid
flowchart TD
    P([Select / create project]) --> UP["Upload PDF documents"]
    UP -->|"chunk + embed → pgvector"| IDX["Knowledge base ready"]
    IDX --> ASK["RAG chat (/chat) or<br/>autonomous agent (/agent-chat)<br/>answers with citations"]
    ASK --> OBS["Agent Runs / Tool Calls<br/>retrieval observability"]
```
