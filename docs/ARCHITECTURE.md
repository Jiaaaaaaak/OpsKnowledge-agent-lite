# Architecture — OpsKnowledge Agent Lite

English | [繁體中文](ARCHITECTURE.zh-TW.md)

## Overview

```mermaid
graph TD
    subgraph Frontend["Frontend (React :8501)"]
        UI_Workflow[Knowledge Workflow]
        UI_Logs[Agent Runs Page]
        UI_Status[System Status]
    end

    subgraph Backend["Backend (FastAPI :8000)"]
        API[REST API Layer]
        SVC_DOC[Document Service]
        SVC_CHAT[Chat Service]
        SVC_LOG[Observability Service]
        LLM[LLMProvider\n(OpenAI / Ollama)]
    end

    subgraph Storage["Storage"]
        PGVECTOR[(PostgreSQL + pgvector\n:5432)]
    end

    UI_Workflow --> API
    UI_Logs --> API
    UI_Status --> API

    API --> SVC_DOC
    API --> SVC_CHAT
    API --> SVC_LOG

    SVC_DOC --> PGVECTOR
    SVC_DOC --> LLM
    SVC_CHAT --> LLM
    SVC_CHAT --> PGVECTOR
    SVC_LOG --> PGVECTOR
```

## Component Responsibilities

| Component | Responsibility |
|---|---|
| `api/` | Route definitions, request validation, response serialization |
| `services/document_service.py` | PDF parsing, chunking, then embedding + PostgreSQL + pgvector storage (via injected `VectorStoreService`) |
| `services/embedding_service.py` | `EmbeddingProvider` interface + `OpenAIEmbeddingProvider`; swap-in point for local embeddings |
| `services/vector_store.py` | `VectorStoreService` wrapping PostgreSQL + pgvector: upsert chunk vectors, project-scoped similarity search |
| `services/llm_service.py` | `LLMProvider` interface + `OpenAICompatibleLLMProvider`; `build_rag_prompt` and `format_citations` pure functions |
| `services/chat_service.py` | RAG chat: retrieve → prompt → LLM → citations |
| `services/log_service.py` | Records every AI run to `agent_runs` / `tool_calls` tables |
| `tools/` | Individual AI tool definitions (structured function call specs) |
| `db/session.py` | SQLAlchemy engine, session factory, `get_db` dependency |
| `core/config.py` | All configuration via environment variables (Pydantic Settings) |
| `LLMProvider` | Abstraction over OpenAI SDK — supports OpenAI or Ollama base URL |

## Data Flow

### Document RAG

```
POST /projects/{id}/upload/documents
  │
  ├─ Extension validation (.pdf only)
  │
  ├─ _extract_pages()  pypdf.PdfReader → [(page_num, text), ...]
  │    └─ Non-text PDF (scanned image) → 400 Bad Request
  │
  ├─ _save_file()  write to data/uploads/{project_id}/documents/{filename}
  │
  ├─ documents INSERT (filename, document_type="pdf", source_path, metadata.page_count)
  │
  ├─ Per-page _chunk_text()  sliding window (chunk_size=1000, overlap=150)
  │    └─ Each chunk (explicit uuid) → document_chunks INSERT
  │         metadata: { filename, page_number, chunk_size }
  │
  ├─ VectorStoreService.add_chunks()  embed all chunks → PostgreSQL + pgvector upsert
  │    ├─ id = document_chunks.id  (same UUID in PG and PostgreSQL + pgvector)
  │    ├─ metadata: { project_id, document_id, chunk_id, filename, chunk_index }
  │    └─ Runs BEFORE db.commit() — embedding failure aborts the upload (no half-written state)
  │
  └─ Return DocumentIngestionResult
       { document_id, filename, page_count, chunk_count, source_path }

GET /projects/{id}/search?query=...&top_k=5
  └─ embed query → PostgreSQL + pgvector query (where project_id == {id}) → top-k chunks
       each hit: { chunk_id, content, metadata, distance, score }
       chunk_id maps 1:1 back to the document_chunks row in PostgreSQL
```

### RAG Chat

```
POST /projects/{id}/chat  { question, top_k }
  │
  ├─ Project 404 guard
  │
  ├─ VectorStoreService.search(project_id, question, top_k)
  │    └─ embed question → PostgreSQL + pgvector query (where project_id == {id}) → top-k hits
  │         each hit: { chunk_id, content, metadata, distance, score }
  │
  ├─ build_rag_prompt(hits)
  │    └─ numbered context blocks + hallucination-guard rules
  │
  ├─ OpenAICompatibleLLMProvider.complete(system_prompt, question)
  │    └─ temperature=0.1, model from LLM_MODEL env var
  │
  ├─ format_citations(hits)
  │    └─ { document_id, chunk_id, filename, chunk_index, snippet(≤200 chars) }
  │
  ├─ AgentRun INSERT  (task_type="rag_chat", status, latency_ms, input_json, output_json)
  │    └─ ToolCall INSERT  (tool_name="vector_search", latency_ms, hit_count, chunk_ids)
  │
  └─ Return ChatResponse  { answer, citations[] }
       citations map back to PostgreSQL via chunk_id == document_chunks.id
```

## Port Map

| Service | Port |
|---|---|
| FastAPI backend | 8000 |
| React frontend (Vite + TypeScript + Tailwind) | 8501 |
| PostgreSQL + pgvector | 5432 |

## LLMProvider Design

The LLM backend is hidden behind a one-method abstraction so it can be swapped
without touching the RAG/chat flow. `get_llm_provider()` selects the concrete
implementation from the `LLM_PROVIDER` env var.

```python
class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_message: str) -> tuple[str, dict]:
        """Returns (answer_text, usage_metadata)."""

class OpenAICompatibleLLMProvider(LLMProvider):
    # Hosted API via the OpenAI SDK (OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL).
    def complete(self, system_prompt, user_message): ...

class OllamaLLMProvider(LLMProvider):
    # Local / on-premise model. Calls the native Ollama HTTP API (/api/chat)
    # directly via httpx — no OpenAI SDK, no API key, no data leaving the host.
    # Configured by OLLAMA_BASE_URL / OLLAMA_MODEL. Raises a clear RuntimeError
    # if the Ollama server is unreachable.
    def complete(self, system_prompt, user_message): ...

class MockLLMProvider(LLMProvider):
    # Deterministic, offline; for CI / local dev (no network call).
    def complete(self, system_prompt, user_message): ...
```

| `LLM_PROVIDER` | Implementation | Backend | Use case |
|---|---|---|---|
| `openai` | `OpenAICompatibleLLMProvider` | OpenAI-compatible API (SDK) | Fast POC / hosted demo |
| `ollama` | `OllamaLLMProvider` | Local Ollama server (native HTTP) | Private / on-premise deployment |
| `mock` | `MockLLMProvider` | None (deterministic) | CI / offline local dev |

**Switching providers requires only an `.env` change** (`LLM_PROVIDER`, plus the
relevant `OPENAI_*` or `OLLAMA_*` values). Adding a new provider requires only
implementing `complete()` and registering it in `get_llm_provider()`.

> **Hosted vs local scope:** The `openai` path is used for a fast, low-setup POC.
> The `ollama` path is prepared for private / on-premise scenarios where the LLM
> must run inside the customer's network. Note the abstraction currently covers
> the **LLM** only — embeddings are still chosen via `EMBEDDING_PROVIDER`
> (`openai` / `mock`), so a fully local stack would also need a local embedding
> provider (a future `EmbeddingProvider` implementation, the same pattern as here).
