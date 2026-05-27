# API Reference — OpsKnowledge Agent Lite

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

新建專案。

**Request Body**
```json
{
  "name": "IT Operations Demo",
  "description": "Demo project for technical manuals and incident tickets"
}
```

| 欄位 | 型別 | 必填 | 說明 |
|---|---|---|---|
| name | string | ✅ | 專案名稱 |
| description | string | — | 專案描述（可選） |

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
- `422` — name 為空或 request body 格式錯誤

---

### `GET /projects/`

列出所有專案（依 `created_at` 降冪排列）。

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

取得單一專案詳情。

**Path Parameter**

| 參數 | 型別 | 說明 |
|---|---|---|
| project_id | UUID | 專案 ID |

**Response 200** — 同 ProjectRead 結構

**Errors**
- `404` — `{"detail": "Project not found"}`
- `422` — project_id 不是合法 UUID

---

## Documents _(Step 2)_

### `POST /documents/upload`
Upload a PDF for RAG ingestion.

### `GET /documents/`
List all uploaded documents.

### `POST /documents/query`
Semantic search over documents.

---

## Incidents _(Step 3)_

### `POST /incidents/upload`
Upload CSV/Excel/JSON incident records for ETL.

### `GET /incidents/`
List all normalized incidents.

### `GET /incidents/{id}`
Get a single incident.

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
