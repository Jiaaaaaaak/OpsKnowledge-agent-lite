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

## Uploads

### `POST /projects/{project_id}/upload/tickets`

上傳 CSV、Excel 或 JSON 格式的 incident ticket 檔案，執行 ETL 並儲存至 PostgreSQL。

**Path Parameter**

| 參數 | 型別 | 說明 |
|---|---|---|
| project_id | UUID | 專案 ID |

**Request**
- Content-Type: `multipart/form-data`
- Field: `file` — 上傳的檔案（`.csv`、`.xlsx`、`.json`）

**支援欄位名稱對應（同義詞）**

| 標準欄位 | 接受的欄位名稱 |
|---|---|
| ticket_id | ticket id, id, case_id, ticket |
| occurred_at | date, created_at, timestamp, datetime |
| system | service, system_name, service_name |
| module | component, comp, subsystem |
| issue_description | issue, description, problem, desc |
| resolution | fix, solution, resolved_by, remedy |
| status | state, ticket_status |
| priority | severity, urgency, sev |

**必填欄位**：`ticket_id`、`issue_description`

**選填欄位預設值**：`system`、`module`、`status`、`priority` 缺值時填入 `"unknown"`

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

| 欄位 | 說明 |
|---|---|
| raw_count | 解析出的總列數（全數存入 raw_records） |
| cleaned_count | 成功驗證並存入 cleaned_records 的列數 |
| failed_count | 驗證失敗的列數 |
| errors | 各筆失敗的詳細錯誤，含列號與原始 ticket_id |

**Errors**
- `400` — 不支援的檔案格式、檔案為空、解析失敗
- `404` — `{"detail": "Project not found"}`
- `422` — project_id 不是合法 UUID

---

## Incidents _(待實作)_

### `GET /incidents/`
列出已匯入的 incident 記錄。

### `GET /incidents/{id}`
取得單筆 incident 記錄。

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
