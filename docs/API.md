# API Reference — OpsKnowledge Agent Lite

English | [繁體中文](API.zh-TW.md)

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs`

---

## Health

### `GET /health`

Returns service status including DB and ChromaDB connectivity.

**Response 200**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "db": "connected",
  "chroma": "connected"
}
```

| Field | Values | Description |
|---|---|---|
| db | `connected` / `unavailable` | PostgreSQL reachability |
| chroma | `connected` / `unavailable` | ChromaDB reachability (`/heartbeat` probe) |

---

## Projects

### `POST /projects/`

Create a new project.

**Request Body**
```json
{
  "name": "IT Operations Demo",
  "description": "Demo project for technical manuals and incident tickets"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| name | string | ✅ | Project name |
| description | string | — | Project description (optional) |

**Response 201**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "name": "IT Operations Demo",
  "description": "Demo project for technical manuals and incident tickets",
  "created_at": "2026-05-28T10:00:00Z",
  "updated_at": "2026-05-28T10:00:00Z"
}
```

**Errors**
- `422` — name is empty or the request body is malformed

---

### `GET /projects/`

List all projects (ordered by `created_at` descending).

**Response 200**
```json
[
  {
    "id": "...",
    "name": "IT Operations Demo",
    "description": "...",
    "created_at": "...",
    "updated_at": "..."
  }
]
```

---

### `GET /projects/{project_id}`

Get the details of a single project.

**Path Parameter**

| Parameter | Type | Description |
|---|---|---|
| project_id | UUID | Project ID |

**Response 200** — same as the ProjectRead schema

**Errors**
- `404` — `{"detail": "Project not found"}`
- `422` — project_id is not a valid UUID

---

## Documents _(Step 2)_

### `POST /documents/upload`
Upload a PDF for RAG ingestion.

### `GET /documents/`
List all uploaded documents.

### `POST /documents/query`
Semantic search over documents.

---

## Documents

### `POST /projects/{project_id}/upload/documents`

Upload a PDF technical manual or SOP. Text is automatically extracted, chunked, stored in PostgreSQL, then embedded and indexed in ChromaDB for retrieval.

**Path Parameter**

| Parameter | Type | Description |
|---|---|---|
| project_id | UUID | Project ID |

**Request**
- Content-Type: `multipart/form-data`
- Field: `file` — PDF file (`.pdf`)

**Response 200**
```json
{
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "filename": "network_sop.pdf",
  "page_count": 24,
  "chunk_count": 87,
  "source_path": "data/uploads/{project_id}/documents/network_sop.pdf"
}
```

| Field | Description |
|---|---|
| document_id | UUID of the created documents row |
| page_count | Total page count of the PDF |
| chunk_count | Number of chunks stored in document_chunks |
| source_path | Path where the file is stored on the server |

**Chunking strategy**
- chunk_size: approximately 1000 characters
- overlap: 150 characters (adjacent chunks overlap to avoid breaking semantics)
- Each chunk's metadata contains `filename`, `page_number`, `chunk_size`

**Embedding & vector storage**
- After chunking, each chunk is embedded (model from `EMBEDDING_MODEL`) and upserted into ChromaDB.
- The ChromaDB id equals the `document_chunks.id` UUID, so a search hit maps 1:1 back to its PostgreSQL row.
- ChromaDB metadata: `project_id`, `document_id`, `chunk_id`, `filename`, `chunk_index`.
- Embedding runs before the DB commit — if it fails, the upload is aborted with no half-written state.

**Errors**
- `400` — not a PDF, empty file, or PDF with no extractable text (scanned image)
- `404` — `{"detail": "Project not found"}`
- `422` — project_id is not a valid UUID
- `500` — embedding unavailable (e.g. `OPENAI_API_KEY` not configured)

---

### `GET /projects/{project_id}/search`

Semantic similarity search over a project's embedded document chunks.

**Path Parameter**

| Parameter | Type | Description |
|---|---|---|
| project_id | UUID | Project ID |

**Query Parameters**

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| query | string | ✅ | — | Search text (min length 1) |
| top_k | integer | — | 5 | Number of chunks to return (1–50) |

**Example request**
```bash
curl "http://localhost:8000/projects/${PROJECT_ID}/search?query=how%20to%20restart%20the%20service&top_k=5"
```

**Response 200**
```json
{
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "query": "how to restart the service",
  "top_k": 5,
  "results": [
    {
      "chunk_id": "9b2c...",
      "content": "To restart the service, run ...",
      "metadata": {
        "project_id": "3fa85f64-...",
        "document_id": "7c1d...",
        "chunk_id": "9b2c...",
        "filename": "network_sop.pdf",
        "chunk_index": 12
      },
      "distance": 0.18,
      "score": 0.82
    }
  ]
}
```

| Field | Description |
|---|---|
| chunk_id | UUID of the chunk — equals `document_chunks.id` in PostgreSQL |
| content | The chunk text stored alongside the vector |
| metadata | ChromaDB metadata (see embedding section above) |
| distance | Cosine distance from the query (lower = closer) |
| score | `1 - distance` convenience similarity score |

**Mapping back to PostgreSQL**: use `chunk_id` (or `metadata.document_id`) to look up the full row:
```sql
SELECT * FROM document_chunks WHERE id = '<chunk_id>';
```

**Errors**
- `404` — `{"detail": "Project not found"}`
- `422` — project_id is not a valid UUID, or `query` is missing/empty
- `500` — embedding unavailable (e.g. `OPENAI_API_KEY` not configured)

---

## Uploads

### `POST /projects/{project_id}/upload/tickets`

Upload an incident ticket file in CSV, Excel, or JSON format. Runs ETL and stores the result in PostgreSQL.

**Path Parameter**

| Parameter | Type | Description |
|---|---|---|
| project_id | UUID | Project ID |

**Request**
- Content-Type: `multipart/form-data`
- Field: `file` — uploaded file (`.csv`, `.xlsx`, `.json`)

**Supported column name mapping (synonyms)**

| Standard column | Accepted column names |
|---|---|
| ticket_id | ticket id, id, case_id, ticket |
| occurred_at | date, created_at, timestamp, datetime |
| system | service, system_name, service_name |
| module | component, comp, subsystem |
| issue_description | issue, description, problem, desc |
| resolution | fix, solution, resolved_by, remedy |
| status | state, ticket_status |
| priority | severity, urgency, sev |

**Required columns**: `ticket_id`, `issue_description`

**Optional column defaults**: `system`, `module`, `status`, `priority` are filled with `"unknown"` when missing

**Response 200**
```json
{
  "raw_count": 22,
  "cleaned_count": 20,
  "failed_count": 2,
  "errors": [
    {
      "row": 5,
      "raw_ticket_id": "TKT-005",
      "error": "issue_description: issue_description 為必填欄位，且不可為空"
    }
  ]
}
```

| Field | Description |
|---|---|
| raw_count | Total rows parsed (all stored in raw_records) |
| cleaned_count | Rows that passed validation and were stored in cleaned_records |
| failed_count | Rows that failed validation |
| errors | Per-row failure details, including row number and original ticket_id |

**Errors**
- `400` — unsupported file format, empty file, or parse failure
- `404` — `{"detail": "Project not found"}`
- `422` — project_id is not a valid UUID

---

## Chat (RAG Q&A)

### `POST /projects/{project_id}/chat`

Ask a question over a project's embedded documents. The endpoint retrieves the most
relevant chunks from ChromaDB, builds a grounded prompt, and calls the configured LLM.
Every request is logged to the `agent_runs` and `tool_calls` tables for auditability.

**Path Parameter**

| Parameter | Type | Description |
|---|---|---|
| project_id | UUID | Project ID |

**Request Body**
```json
{
  "question": "Docker volume data disappeared after container restart. What should I check?",
  "top_k": 5
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| question | string | ✅ | — | The natural-language question (min length 1) |
| top_k | integer | — | 5 | Number of chunks to retrieve from ChromaDB (1–50) |

**Example request**
```bash
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/chat" \
  -H "Content-Type: application/json" \
  -d '{"question": "Docker volume data disappeared after container restart. What should I check?", "top_k": 5}'
```

**Response 200**
```json
{
  "answer": "Docker volumes can lose data if not configured with a named volume or bind mount. Check the following:\n- Run `docker inspect <container>` and look at the `Mounts` field.\n- Confirm that the volume type is `volume` or `bind`, not `tmpfs`.\n- Verify the volume is declared in `docker-compose.yml` under the `volumes:` key.",
  "citations": [
    {
      "document_id": "7c1d...",
      "chunk_id": "9b2c...",
      "filename": "docker_operations.pdf",
      "chunk_index": 3,
      "snippet": "Docker volumes persist data outside container lifecycle. Use named volumes..."
    }
  ]
}
```

| Field | Description |
|---|---|
| answer | LLM-generated answer grounded strictly in the retrieved context |
| citations[].document_id | UUID of the source document in PostgreSQL |
| citations[].chunk_id | UUID of the source chunk — equals `document_chunks.id` in PostgreSQL |
| citations[].filename | Original PDF filename |
| citations[].chunk_index | Zero-based chunk position within the document |
| citations[].snippet | First 200 characters of the chunk (truncated with `...` if longer) |

**Hallucination reduction**
The system prompt instructs the model to:
1. Answer _only_ from the provided context.
2. If the context is insufficient, respond verbatim: _"The document does not contain enough information to answer this question."_
3. Never invent commands, file paths, or procedures not present in the context.

**Observability** — every request writes:
- One `agent_runs` row (`task_type="rag_chat"`, `model_name`, `latency_ms`, `status`, `input_json`, `output_json`)
- One `tool_calls` row for the retrieval step (`tool_name="vector_search"`, `latency_ms`, `hit_count`)

**Errors**
- `404` — `{"detail": "Project not found"}`
- `422` — project_id is not a valid UUID, `question` is missing/empty, or `top_k` is out of range
- `500` — embedding or LLM provider unavailable (e.g. `OPENAI_API_KEY` not configured)

---

## Incidents _(to be implemented)_

### `GET /incidents/`
List imported incident records.

### `GET /incidents/{id}`
Get a single incident record.

---

## Incident Analysis Agent

### `POST /projects/{project_id}/analyze/incidents`

Run the multi-tool incident analysis agent over a project's cleaned records. The agent
chains four tools and persists results into `incident_analysis`, `insights`, and
`action_items`. One row is written to `agent_runs` plus four rows to `tool_calls`
(one per tool) for full auditability.

The endpoint is idempotent for already-analyzed records: it processes only
`cleaned_records` that do not yet have a row in `incident_analysis`, so it can be
re-run safely after ingesting more tickets without deleting prior analysis.

**Path Parameter**

| Parameter | Type | Description |
|---|---|---|
| project_id | UUID | Project ID |

**Request Body**: none.

**Pipeline**

| Step | Tool | Input | Output |
|---|---|---|---|
| 1 | `classify_incidents` | each cleaned record | category ∈ {network_issue, storage_issue, deployment_issue, permission_issue, security_issue, performance_issue, data_quality_issue, unknown} |
| 2 | `analyze_severity` | each cleaned record | severity_score (1-5), sentiment_score (-1..1), confidence (0..1), reason; `needs_review=true` when `confidence < 0.65` |
| 3 | `generate_insights` | aggregated category counts + high-severity samples | project-level insights (title, summary, evidence, recommendation) |
| 4 | `create_action_items` | insights | action items (title, description, priority, owner_role, `status="open"`) |

Every tool calls the configured LLM via `LLMProvider.complete()` requesting structured
JSON. The output is validated with Pydantic; on validation failure the tool logs the
error, the corresponding `tool_calls` row records `error_message`, and the overall
agent run is marked `status="partial"` rather than silently dropping the failure.

**Example request**
```bash
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/analyze/incidents"
```

**Response 200**
```json
{
  "agent_run_id": "9c8f3b1a-0f4c-4f1d-9b65-1c0c3a86a512",
  "status": "success",
  "summary": {
    "records_analyzed": 20,
    "needs_review": 3,
    "insights_created": 5,
    "action_items_created": 4
  }
}
```

| Field | Description |
|---|---|
| agent_run_id | UUID of the `agent_runs` row written for this invocation |
| status | `success`, `partial` (one or more tool validations failed), or `error` (orchestrator-level failure) |
| summary.records_analyzed | Number of `incident_analysis` rows created |
| summary.needs_review | Records with `confidence < 0.65` |
| summary.insights_created | Number of `insights` rows created |
| summary.action_items_created | Number of `action_items` rows created (all `status="open"`) |

**Observability** — every request writes:
- One `agent_runs` row (`task_type="analyze_incidents"`, `model_name`, `latency_ms`, `status`, `input_json` includes record count, `output_json` includes the summary and list of tools run)
- Four `tool_calls` rows, one per tool: `tool_name`, per-tool `input_json` / `output_json`, `latency_ms`, and `error_message` when JSON validation fails

Use these tables to trace any analysis after the fact — see the [debugging section in README](../README.md#observability--debugging).

**Errors**
- `400` — `{"detail": "No cleaned records to analyze..."}` (upload tickets first or all records already analyzed)
- `404` — `{"detail": "Project not found"}`
- `422` — project_id is not a valid UUID
- `500` — LLM provider unavailable or orchestrator-level failure (also written to `agent_runs` with `status="error"`)

---

## Dashboard

### `GET /projects/{project_id}/dashboard`

Aggregated project-level summary. Pure PostgreSQL aggregation — **no LLM call**, fast
and deterministic. Designed to drive the React frontend dashboard in a single round-trip.

**Path Parameter**

| Parameter | Type | Description |
|---|---|---|
| project_id | UUID | Project ID |

**Query Parameters**

| Parameter | Type | Default | Range | Description |
|---|---|---|---|---|
| insights_limit | integer | 5 | 1–50 | Max insights returned in `top_insights` |
| action_items_limit | integer | 10 | 1–100 | Max open action items returned |
| agent_runs_limit | integer | 5 | 1–50 | Max recent agent runs returned |

**Example request**
```bash
curl "http://localhost:8000/projects/${PROJECT_ID}/dashboard"
```

**Response 200**
```json
{
  "project_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "ticket_count": 100,
  "category_distribution": [
    {"category": "network_issue", "count": 20},
    {"category": "storage_issue", "count": 15}
  ],
  "severity_distribution": [
    {"severity": 1, "count": 5},
    {"severity": 3, "count": 30},
    {"severity": 5, "count": 3}
  ],
  "needs_review_count": 4,
  "top_insights": [
    {
      "id": "…",
      "title": "Top category: network_issue",
      "summary": "20 incident(s) classified as network_issue.",
      "recommendation": "Investigate the root cause of network_issue incidents..."
    }
  ],
  "open_action_items": [
    {
      "id": "…",
      "title": "Action: High severity patterns",
      "description": "Prioritise post-mortems...",
      "priority": "high",
      "owner_role": "ops_lead",
      "status": "open"
    }
  ],
  "recent_agent_runs": [
    {
      "id": "…",
      "task_type": "analyze_incidents",
      "model_name": "mock",
      "status": "success",
      "latency_ms": 142,
      "created_at": "2026-05-30T10:00:00Z"
    }
  ]
}
```

| Field | Source | Description |
|---|---|---|
| ticket_count | `cleaned_records` | Total imported tickets for the project |
| category_distribution | `incident_analysis` GROUP BY category | Sorted desc by count, then alpha |
| severity_distribution | `incident_analysis` GROUP BY severity_score (cast to int) | Sorted asc by severity |
| needs_review_count | `incident_analysis` WHERE needs_review = true | Low-confidence tickets requiring human review |
| top_insights | `insights` ORDER BY created_at DESC | Most recent insights, capped by `insights_limit` |
| open_action_items | `action_items` WHERE status='open' | Open follow-ups, capped by `action_items_limit` |
| recent_agent_runs | `agent_runs` ORDER BY created_at DESC | Latest agent runs (chat + analysis), capped by `agent_runs_limit` |

**Errors**
- `404` — `{"detail": "Project not found"}`
- `422` — project_id is not a valid UUID, or a query parameter is out of range

---

## Observability

### `GET /projects/{project_id}/agent-runs`

List agent runs for a project (newest first). Use this to power an "Agent Logs" page
in the UI or for ad-hoc auditing.

**Query Parameters**

| Parameter | Type | Default | Range | Description |
|---|---|---|---|---|
| limit | integer | 50 | 1–200 | Page size |
| offset | integer | 0 | ≥ 0 | Page offset |

**Response 200** — list of `AgentRunRead`:
```json
[
  {
    "id": "…",
    "project_id": "…",
    "task_type": "analyze_incidents",
    "model_name": "mock",
    "input_json": {"project_id": "…", "record_count": 20},
    "output_json": {"records_analyzed": 20, "tools_run": ["classify_incidents", "..."]},
    "status": "success",
    "latency_ms": 142,
    "error_message": null,
    "created_at": "2026-05-30T10:00:00Z",
    "updated_at": "2026-05-30T10:00:00Z"
  }
]
```

**Errors**
- `404` — `{"detail": "Project not found"}`
- `422` — invalid UUID or out-of-range pagination

---

### `GET /agent-runs/{agent_run_id}/tool-calls`

List tool calls for a single agent run, **in execution order** (ASC by `created_at`).
Pairs naturally with `/agent-runs` for a drill-down view.

**Response 200** — list of `ToolCallRead`:
```json
[
  {
    "id": "…",
    "agent_run_id": "…",
    "tool_name": "classify_incidents",
    "input_json": {"project_id": "…", "record_count": 20},
    "output_json": {"classified": 20, "failed": 0, "categories": {"network_issue": 8, "...": 4}},
    "error_message": null,
    "latency_ms": 38,
    "created_at": "2026-05-30T10:00:00Z"
  }
]
```

**Errors**
- `404` — `{"detail": "Agent run not found"}`
- `422` — invalid UUID
