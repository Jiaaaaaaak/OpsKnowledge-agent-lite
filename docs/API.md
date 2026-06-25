# API Reference — OpsKnowledge Agent Lite

English | [繁體中文](API.zh-TW.md)

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs`

---

## Health

### `GET /health`

Returns service status including PostgreSQL and pgvector connectivity.

```json
{
  "status": "ok",
  "version": "0.1.0",
  "db": "connected",
  "vector": "connected"
}
```

---

## Projects

### `POST /projects/`

Create a project.

```json
{
  "name": "IT Operations Demo",
  "description": "Demo project for technical manuals"
}
```

### `GET /projects/`

List projects, newest first.

### `GET /projects/{project_id}`

Get one project by UUID.

---

## Documents

### `POST /projects/{project_id}/upload/documents`

Upload a PDF technical manual or SOP. The backend extracts text, chunks it, stores
metadata in PostgreSQL, creates embeddings, and stores vectors in pgvector. The
`document_chunks.search_vector` generated column also indexes chunk text for the
keyword branch of hybrid search.

Multimodal ingestion: pages with too little extractable text (scanned / image PDFs)
are rendered and OCR'd with Tesseract (`chi_tra+chi_sim+eng`, normalized to Traditional
Chinese), controlled by the `OCR_*` settings. OCR degrades gracefully when
`tesseract`/`poppler` are absent. `ocr_page_count` reports how many pages were recovered
via OCR.

Request:
- `multipart/form-data`
- field `file`
- `.pdf` only

Response:

```json
{
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "filename": "network_sop.pdf",
  "page_count": 24,
  "chunk_count": 87,
  "source_path": "data/uploads/{project_id}/documents/network_sop.pdf",
  "ocr_page_count": 0
}
```

### `GET /projects/{project_id}/documents`

List uploaded documents for a project.

### `GET /projects/{project_id}/search`

Hybrid search over indexed chunks. The backend runs:

1. pgvector dense retrieval
2. PostgreSQL full-text retrieval via `websearch_to_tsquery('english', query)`
3. Reciprocal-rank fusion by `chunk_id`

Query parameters:

| Parameter | Required | Default | Description |
|---|---:|---:|---|
| `query` | yes | — | Search text |
| `top_k` | no | 5 | Number of chunks to return, 1-50 |

Example:

```bash
curl "http://localhost:8000/projects/${PROJECT_ID}/search?query=restart%20postgres&top_k=5"
```

Response:

```json
{
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "query": "restart postgres",
  "top_k": 5,
  "results": [
    {
      "chunk_id": "9b2c...",
      "content": "To restart PostgreSQL, run ...",
      "metadata": {
        "project_id": "3fa85f64-...",
        "document_id": "7c1d...",
        "chunk_id": "9b2c...",
        "filename": "postgres_sop.pdf",
        "chunk_index": 12
      },
      "fusion_score": 0.0325,
      "sources": ["vector", "keyword"],
      "scores": {
        "vector": 0.82,
        "keyword": 0.41
      }
    }
  ]
}
```

---

## Chat

### `POST /projects/{project_id}/chat`

Answer a question using RAG over the project's indexed documents.

Request:

```json
{
  "question": "How do I restart PostgreSQL safely?",
  "top_k": 5
}
```

Response:

```json
{
  "answer": "Use the documented restart procedure...",
  "citations": [
    {
      "document_id": "7c1d...",
      "chunk_id": "9b2c...",
      "filename": "postgres_sop.pdf",
      "chunk_index": 12,
      "snippet": "To restart PostgreSQL...",
      "source_language": "en",
      "snippet_translated": null
    }
  ]
}
```

Citation fields:
- `source_language` — detected language of the source chunk (`"zh"` / `"en"`).
- `snippet_translated` — the snippet translated into the question's language, set only
  when the chunk language differs from the question; `null` otherwise. (Enables
  cross-lingual answers, e.g. English docs with Chinese questions.)

Answers are normalized to Traditional Chinese (Taiwan) when the model emits Simplified
Chinese; the LLM is also instructed to answer in the question's language.

Retrieval behavior:
- Chat uses the same hybrid search service as `/search` (fixed pipeline: hybrid
  retrieval → optional rerank → answer; `task_type="rag_chat"`).
- If `RERANKER_ENABLED=true`, fused candidates are reranked by the configured cross-encoder.
- Each request writes one `agent_runs` row.
- Each request writes one `tool_calls` row with `tool_name="hybrid_search"`.
- If reranking runs, a second `tool_calls` row is written with `tool_name="rerank"`.
- If any cross-lingual snippet is translated, a `tool_calls` row with
  `tool_name="translate"` is written.

### `POST /projects/{project_id}/agent-chat`

Autonomous agent Q&A over the project's documents. Unlike `/chat`'s fixed pipeline, the
LLM itself decides whether to retrieve, what to query, how many times, and which
retrieval strategy to use, via a single `search_documents(query, strategy)` tool, then
answers. `strategy` is one of `hybrid` (default, general), `keyword` (exact terms such as
error codes, command names, config keys, IDs), or `vector` (conceptual / semantic). The
loop is bounded by `AGENT_MAX_STEPS` as a safety cap.

Request and response shapes are identical to `/chat` (`ChatRequest` → `ChatResponse`,
including the `source_language` / `snippet_translated` citation fields).

Observability:
- Each request writes one `agent_runs` row with `task_type="agent_chat"`; its
  `output_json` includes `search_count` and `stop_reason` (`"completed"` or `"max_steps"`).
- Each agent search writes a `tool_calls` row with `tool_name="search_documents"`
  (`input_json` includes `query` and `strategy`).
- If any cross-lingual snippet is translated, a `tool_calls` row with
  `tool_name="translate"` is written.

---

## Workflow Status

### `GET /projects/{project_id}/workflow-status`

Return knowledge workflow readiness for a project.

```json
{
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "knowledge": {
    "document_count": 2,
    "total_pages": 31,
    "total_chunks": 92,
    "can_chat": true
  }
}
```

---

## Observability

### `GET /projects/{project_id}/agent-runs`

List recent agent runs for a project, newest first.

Query parameters:

| Parameter | Default | Description |
|---|---:|---|
| `limit` | 50 | Maximum rows, 1-200 |
| `offset` | 0 | Pagination offset |

### `GET /agent-runs/{agent_run_id}/tool-calls`

List tool calls for one agent run in execution order.

---

## Error Conventions

- `400` — invalid upload, empty file, or PDF without extractable text
- `404` — project or agent run not found
- `422` — invalid UUID, missing required fields, or invalid query parameters
- `500` — embedding, retrieval, or LLM provider unavailable
