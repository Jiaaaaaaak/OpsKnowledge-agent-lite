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
        SVC_DOC[Document Service\n(+ OCR fallback)]
        SVC_CHAT[Chat Service\n(/chat)]
        SVC_AGENT[Agent Service\n(/agent-chat)]
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
    API --> SVC_AGENT
    API --> SVC_LOG

    SVC_DOC --> PGVECTOR
    SVC_DOC --> LLM
    SVC_CHAT --> LLM
    SVC_CHAT --> PGVECTOR
    SVC_AGENT --> LLM
    SVC_AGENT --> PGVECTOR
    SVC_LOG --> PGVECTOR
```

## Component Responsibilities

| Component | Responsibility |
|---|---|
| `api/` | Route definitions, request validation, response serialization |
| `services/document_service.py` | PDF parsing, chunking, then embedding + PostgreSQL + pgvector storage (via injected `VectorStoreService`); OCR fallback for scanned / image pages |
| `services/ocr_service.py` | Tesseract OCR for pages with too little extractable text; lazy-imports `pytesseract`/`pdf2image` and degrades gracefully when absent |
| `services/embedding_service.py` | `EmbeddingProvider` interface + `OpenAIEmbeddingProvider`; swap-in point for local embeddings |
| `services/vector_store.py` | `VectorStoreService` wrapping PostgreSQL + pgvector: upsert chunk vectors, project-scoped similarity search |
| `services/retrieval/` | Modular hybrid retrieval: pgvector dense recall, PostgreSQL full-text recall, reciprocal-rank fusion |
| `services/reranker_service.py` | Optional second-stage cross-encoder reranker for fused retrieval candidates |
| `services/llm_service.py` | `LLMProvider` interface + `OpenAICompatibleLLMProvider`; `build_rag_prompt` and `format_citations` pure functions |
| `services/chat_service.py` | RAG chat (`/chat`): retrieve → prompt → LLM → citations (fixed pipeline) |
| `services/agent_service.py` | Autonomous agent chat (`/agent-chat`): LLM decides whether/what/how-many-times to retrieve and which strategy via a `search_documents` tool, bounded by `AGENT_MAX_STEPS` |
| `services/retrieval/service.py` | `HybridRetrievalService.search(..., strategy)` with strategy ∈ `hybrid` (default) / `keyword` / `vector` |
| `models/agent.py` | `agent_runs` and `tool_calls` persistence models used by chat and observability routes |
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
  ├─ _extract_pages_with_ocr()  pypdf.PdfReader → [(page_num, text), ...]
  │    ├─ Pages with < OCR_MIN_CHARS extractable text → render + Tesseract OCR
  │    │    (chi_tra+chi_sim+eng, normalized to Traditional Chinese); skipped if
  │    │    OCR_ENABLED=false or tesseract/poppler absent
  │    └─ No text after OCR → 400 Bad Request
  │
  ├─ _save_file()  write to data/uploads/{project_id}/documents/{filename}
  │
  ├─ documents INSERT (filename, document_type="pdf", source_path,
  │    metadata.{page_count, ocr_page_count})
  │
  ├─ Per-page _chunk_text()  sliding window (chunk_size=1000, overlap=150)
  │    └─ Each chunk (explicit uuid) → document_chunks INSERT
  │         metadata: { filename, page_number, chunk_size }
  │
  ├─ VectorStoreService.add_chunks()  embed all chunks → PostgreSQL + pgvector upsert
  │    ├─ id = document_chunks.id  (same UUID in PG and PostgreSQL + pgvector)
  │    ├─ metadata: { project_id, document_id, chunk_id, filename, chunk_index }
  │    ├─ Chunk rows are flushed before embeddings are written (content + embedding atomic)
  │    └─ Runs BEFORE db.commit() — embedding failure aborts the upload (no half-written state)
  │
  └─ Return DocumentIngestionResult
       { document_id, filename, page_count, chunk_count, source_path, ocr_page_count }

GET /projects/{id}/search?query=...&top_k=5
  └─ HybridRetrievalService.search(project_id, query, top_k)
       ├─ VectorRetriever → embed query → pgvector cosine search
       ├─ KeywordRetriever → PostgreSQL websearch_to_tsquery full-text search
       └─ ReciprocalRankFusion → de-duplicate by chunk_id and return top-k chunks
       each hit: { chunk_id, content, metadata, fusion_score, sources, scores }
       chunk_id maps 1:1 back to the document_chunks row in PostgreSQL
```

### RAG Chat

```
POST /projects/{id}/chat  { question, top_k }
  │
  ├─ Project 404 guard
  │
  ├─ HybridRetrievalService.search(project_id, question, candidate_k)
  │    └─ vector recall + full-text recall + reciprocal-rank fusion
  │         each hit: { chunk_id, content, metadata, fusion_score, sources, scores }
  │
  ├─ Optional reranker
  │    └─ if RERANKER_ENABLED=true, rerank fused candidates and keep top_k
  │
  ├─ build_rag_prompt(hits)
  │    └─ numbered context blocks + hallucination-guard rules
  │
  ├─ LLMProvider.complete(system_prompt, question)
  │    ├─ temperature=0.1, model from LLM_MODEL env var
  │    └─ answer normalized to Traditional Chinese (OpenCC s2twp)
  │
  ├─ format_citations(hits)
  │    ├─ { document_id, chunk_id, filename, chunk_index, snippet(≤200 chars),
  │    │    source_language, snippet_translated }
  │    └─ Cross-lingual snippets (chunk language ≠ question language) translated
  │         into the question's language; same-language → snippet_translated=null
  │
  ├─ AgentRun INSERT  (task_type="rag_chat", status, latency_ms, input_json, output_json)
  │    ├─ ToolCall INSERT  (tool_name="hybrid_search", vector/keyword/fused counts, chunk_ids)
  │    ├─ Optional ToolCall INSERT  (tool_name="rerank", status, returned)
  │    └─ Optional ToolCall INSERT  (tool_name="translate", translated/failed counts)
  │
  └─ Return ChatResponse  { answer, citations[] }
       citations map back to PostgreSQL via chunk_id == document_chunks.id
```

### Agent Chat

```
POST /projects/{id}/agent-chat  { question, top_k }
  │
  ├─ Project 404 guard
  │
  ├─ Agent loop (≤ AGENT_MAX_STEPS): LLMProvider.complete_with_tools(messages, [search_documents])
  │    ├─ LLM decides: answer directly, or call search_documents(query, strategy)
  │    │    strategy ∈ hybrid (default) / keyword (exact terms) / vector (semantic)
  │    ├─ Each call → HybridRetrievalService.search(..., strategy); hits fed back to LLM
  │    └─ Loop ends when the LLM answers (stop_reason="completed") or the cap is hit
  │         (stop_reason="max_steps", forced final answer from results gathered so far)
  │
  ├─ Answer normalized to Traditional Chinese; citations de-duplicated across searches
  │    then cross-lingual snippets translated (same as /chat)
  │
  ├─ AgentRun INSERT  (task_type="agent_chat"; output_json includes search_count, stop_reason)
  │    ├─ ToolCall INSERT per search  (tool_name="search_documents", input {query, strategy})
  │    └─ Optional ToolCall INSERT  (tool_name="translate")
  │
  └─ Return ChatResponse  { answer, citations[] }   (same shape as /chat)
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

For `/agent-chat`, providers also implement `complete_with_tools(messages, tools)`
(tool-calling), used by the agent loop. `MockLLMProvider` returns deterministic
tool-calls so the agent flow runs in CI without a real model. LLM-emitted Simplified
Chinese (answers and `zh` translations) is normalized to Traditional Chinese (Taiwan)
via OpenCC `s2twp`.

> **Hosted vs local scope:** The `openai` path is used for a fast, low-setup POC.
> The `ollama` path is prepared for private / on-premise scenarios where the LLM
> must run inside the customer's network. Note the abstraction currently covers
> the **LLM** only — embeddings are still chosen via `EMBEDDING_PROVIDER`
> (`openai` / `mock`), so a fully local stack would also need a local embedding
> provider (a future `EmbeddingProvider` implementation, the same pattern as here).
