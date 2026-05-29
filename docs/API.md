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
  "chroma": "configured"
}
```

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

## Incidents _(to be implemented)_

### `GET /incidents/`
List imported incident records.

### `GET /incidents/{id}`
Get a single incident record.

---

## Analysis _(Step 4)_

### `POST /analysis/run`
Trigger AI classification + scoring on a batch of incidents.

### `GET /analysis/results`
List AI analysis results.

---

## Agent Logs _(Step 5)_

### `GET /logs/`
List AI run log entries (with pagination).

### `GET /logs/{id}`
Get a single run log entry.
