# API 參考文件 — OpsKnowledge Agent Lite

[English](API.md) | 繁體中文

Base URL：`http://localhost:8000`

互動式文件：`http://localhost:8000/docs`

---

## Health

### `GET /health`

回傳服務狀態，包含資料庫與 ChromaDB 的連線狀況。

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

**錯誤**
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

**錯誤**
- `404` — `{"detail": "Project not found"}`
- `422` — project_id 不是合法 UUID

---

## Documents _(Step 2)_

### `POST /documents/upload`
上傳 PDF 進行 RAG 匯入。

### `GET /documents/`
列出所有已上傳的文件。

### `POST /documents/query`
對文件進行語意搜尋。

---

## Documents

### `POST /projects/{project_id}/upload/documents`

上傳 PDF 技術手冊或 SOP 文件，自動抽取文字、分塊、儲存至 PostgreSQL，接著嵌入並索引至 ChromaDB 供檢索。

**Path Parameter**

| 參數 | 型別 | 說明 |
|---|---|---|
| project_id | UUID | 專案 ID |

**Request**
- Content-Type：`multipart/form-data`
- Field：`file` — PDF 檔案（`.pdf`）

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

| 欄位 | 說明 |
|---|---|
| document_id | 建立的 documents 資料列 UUID |
| page_count | PDF 總頁數 |
| chunk_count | 儲存至 document_chunks 的分塊數量 |
| source_path | 檔案在伺服器上的儲存路徑 |

**分塊策略**
- chunk_size：約 1000 字元
- overlap：150 字元（相鄰分塊重疊，避免語意截斷）
- 每個 chunk metadata 包含 `filename`、`page_number`、`chunk_size`

**嵌入與向量儲存**
- 分塊後，每個 chunk 會被嵌入（模型取自 `EMBEDDING_MODEL`）並 upsert 至 ChromaDB。
- ChromaDB 的 id 等同 `document_chunks.id` UUID，因此搜尋結果可 1:1 對回 PostgreSQL 資料列。
- ChromaDB metadata：`project_id`、`document_id`、`chunk_id`、`filename`、`chunk_index`。
- 嵌入在 DB commit 前執行 — 若失敗則中止上傳，不留下半套資料。

**錯誤**
- `400` — 非 PDF 格式、檔案為空、PDF 無可抽取文字（掃描圖檔）
- `404` — `{"detail": "Project not found"}`
- `422` — project_id 不是合法 UUID
- `500` — 無法嵌入（例如未設定 `OPENAI_API_KEY`）

---

### `GET /projects/{project_id}/search`

對專案內已嵌入的文件分塊做語意相似度搜尋。

**Path Parameter**

| 參數 | 型別 | 說明 |
|---|---|---|
| project_id | UUID | 專案 ID |

**Query Parameters**

| 參數 | 型別 | 必填 | 預設 | 說明 |
|---|---|---|---|---|
| query | string | ✅ | — | 搜尋字串（長度至少 1） |
| top_k | integer | — | 5 | 回傳的最相似 chunk 數（1–50） |

**範例請求**
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

| 欄位 | 說明 |
|---|---|
| chunk_id | chunk 的 UUID — 等同 PostgreSQL 的 `document_chunks.id` |
| content | 與向量一同儲存的 chunk 文字 |
| metadata | ChromaDB metadata（見上方嵌入說明） |
| distance | 與 query 的 cosine 距離（越小越接近） |
| score | `1 - distance` 的相似度分數，方便排序顯示 |

**對回 PostgreSQL**：用 `chunk_id`（或 `metadata.document_id`）查回完整資料列：
```sql
SELECT * FROM document_chunks WHERE id = '<chunk_id>';
```

**錯誤**
- `404` — `{"detail": "Project not found"}`
- `422` — project_id 不是合法 UUID，或 `query` 缺漏／為空
- `500` — 無法嵌入（例如未設定 `OPENAI_API_KEY`）

---

## Uploads

### `POST /projects/{project_id}/upload/tickets`

上傳 CSV、Excel 或 JSON 格式的 incident ticket 檔案，執行 ETL 並儲存至 PostgreSQL。

**Path Parameter**

| 參數 | 型別 | 說明 |
|---|---|---|
| project_id | UUID | 專案 ID |

**Request**
- Content-Type：`multipart/form-data`
- Field：`file` — 上傳的檔案（`.csv`、`.xlsx`、`.json`）

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

**錯誤**
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
對一批 incident 觸發 AI 分類與評分。

### `GET /analysis/results`
列出 AI 分析結果。

---

## Agent Logs _(Step 5)_

### `GET /logs/`
列出 AI 執行日誌（含分頁）。

### `GET /logs/{id}`
取得單筆執行日誌。
