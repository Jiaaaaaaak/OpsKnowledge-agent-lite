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
  "chroma": "connected"
}
```

| 欄位 | 可能值 | 說明 |
|---|---|---|
| db | `connected` / `unavailable` | PostgreSQL 連線狀態 |
| chroma | `connected` / `unavailable` | ChromaDB 連線狀態（`/heartbeat` 探測） |

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

## Chat（RAG 問答）

### `POST /projects/{project_id}/chat`

對專案內已嵌入的文件提問。端點從 ChromaDB 取回最相關的 chunk，組裝有根據的 prompt，並呼叫設定的 LLM。
每次請求皆記錄至 `agent_runs` 與 `tool_calls` 資料表，確保可稽核性。

**Path Parameter**

| 參數 | 型別 | 說明 |
|---|---|---|
| project_id | UUID | 專案 ID |

**Request Body**
```json
{
  "question": "Docker volume data disappeared after container restart. What should I check?",
  "top_k": 5
}
```

| 欄位 | 型別 | 必填 | 預設值 | 說明 |
|---|---|---|---|---|
| question | string | ✅ | — | 自然語言問題（最少 1 個字元） |
| top_k | integer | — | 5 | 從 ChromaDB 取回的 chunk 數量（1–50） |

**範例請求**
```bash
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/chat" \
  -H "Content-Type: application/json" \
  -d '{"question": "Docker volume data disappeared after container restart. What should I check?", "top_k": 5}'
```

**Response 200**
```json
{
  "answer": "Docker volumes 可能因未設定具名 volume 或 bind mount 而遺失資料。請確認：\n- 執行 `docker inspect <container>` 並查看 `Mounts` 欄位。\n- 確認 volume 類型不是 `tmpfs`。\n- 確認 `docker-compose.yml` 的 `volumes:` 已正確宣告。",
  "citations": [
    {
      "document_id": "7c1d...",
      "chunk_id": "9b2c...",
      "filename": "docker_operations.pdf",
      "chunk_index": 3,
      "snippet": "Docker volumes persist data outside container lifecycle..."
    }
  ]
}
```

| 欄位 | 說明 |
|---|---|
| answer | 嚴格根據已取回 context 生成的 LLM 答案 |
| citations[].document_id | 來源文件在 PostgreSQL 的 UUID |
| citations[].chunk_id | 來源 chunk 的 UUID — 等同 PostgreSQL `document_chunks.id` |
| citations[].filename | 原始 PDF 檔名 |
| citations[].chunk_index | 文件內 chunk 的零起始索引 |
| citations[].snippet | chunk 前 200 個字元（超過則截斷並加 `...`） |

**幻覺抑制**  
System prompt 指示模型：
1. 只根據提供的 context 回答。
2. 若 context 不足，固定回應：「The document does not contain enough information to answer this question.」
3. 絕不捏造 context 中未出現的指令、路徑或操作步驟。

**可觀測性** — 每次請求寫入：
- 一筆 `agent_runs`（`task_type="rag_chat"`、`model_name`、`latency_ms`、`status`、`input_json`、`output_json`）
- 一筆 `tool_calls`（`tool_name="vector_search"`、`latency_ms`、`hit_count`）

**錯誤**
- `404` — `{"detail": "Project not found"}`
- `422` — project_id 不是合法 UUID、`question` 缺漏／為空、或 `top_k` 超出範圍
- `500` — 嵌入或 LLM provider 無法使用（例如未設定 `OPENAI_API_KEY`）

---

## Incidents _(待實作)_

### `GET /incidents/`
列出已匯入的 incident 記錄。

### `GET /incidents/{id}`
取得單筆 incident 記錄。

---

## 事件分析 Agent

### `POST /projects/{project_id}/analyze/incidents`

對某個 project 的 cleaned records 跑多工具事件分析 agent。Agent 串接 4 個工具，
結果寫入 `incident_analysis`、`insights`、`action_items`。同時會寫 1 筆 `agent_runs`
與 4 筆 `tool_calls`（每個工具一筆），提供完整稽核能力。

此端點對已分析過的紀錄是 idempotent 的：只處理還沒有 `incident_analysis` row
的 `cleaned_records`，所以匯入更多 ticket 之後可以安全重跑，不會刪掉先前分析。

**Path 參數**

| 參數 | 型別 | 說明 |
|---|---|---|
| project_id | UUID | Project ID |

**Request Body**：無。

**流程**

| 步驟 | 工具 | 輸入 | 輸出 |
|---|---|---|---|
| 1 | `classify_incidents` | 每筆 cleaned record | category ∈ {network_issue, storage_issue, deployment_issue, permission_issue, security_issue, performance_issue, data_quality_issue, unknown} |
| 2 | `analyze_severity` | 每筆 cleaned record | severity_score (1-5)、sentiment_score (-1..1)、confidence (0..1)、reason；`confidence < 0.65` 時 `needs_review=true` |
| 3 | `generate_insights` | 彙總後的類別計數 + 高嚴重度樣本 | 專案層級 insights（title、summary、evidence、recommendation） |
| 4 | `create_action_items` | insights | action items（title、description、priority、owner_role、`status="open"`） |

每個工具透過 `LLMProvider.complete()` 向 LLM 索取結構化 JSON，
輸出以 Pydantic 驗證；驗證失敗時，工具會 log error，對應的 `tool_calls` row 會記下
`error_message`，整體 agent run 會被標記為 `status="partial"`，**不會**靜默吞錯。

**範例 request**
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

| 欄位 | 說明 |
|---|---|
| agent_run_id | 此次呼叫寫入 `agent_runs` 的 UUID |
| status | `success`、`partial`（有 tool 驗證失敗）、或 `error`（orchestrator 層級失敗） |
| summary.records_analyzed | 新建立的 `incident_analysis` row 數 |
| summary.needs_review | `confidence < 0.65` 的紀錄數 |
| summary.insights_created | 新建立的 `insights` row 數 |
| summary.action_items_created | 新建立的 `action_items` row 數（全部 `status="open"`） |

**可觀測性** — 每次請求會寫：
- 1 筆 `agent_runs`（`task_type="analyze_incidents"`、`model_name`、`latency_ms`、`status`、`input_json` 含 record_count、`output_json` 含 summary 與工具清單）
- 4 筆 `tool_calls`（每個工具一筆）：`tool_name`、各自的 `input_json` / `output_json`、`latency_ms`、JSON 驗證失敗時的 `error_message`

事後追溯就靠這兩張表 — 詳見 [README 的 Observability 章節](../README.zh-TW.md#可觀測性與除錯)。

**錯誤**
- `400` — `{"detail": "No cleaned records to analyze..."}`（請先上傳 ticket，或全部 record 都已分析過）
- `404` — `{"detail": "Project not found"}`
- `422` — project_id 不是合法 UUID
- `500` — LLM provider 不可用或 orchestrator 層級失敗（同時會以 `status="error"` 寫入 `agent_runs`）

---

## Dashboard

### `GET /projects/{project_id}/dashboard`

專案層級的彙總摘要。純 PostgreSQL 聚合 — **不呼叫 LLM**，快速且可重現。
設計用一次 round-trip 餵滿 Streamlit dashboard。

**Path 參數**

| 參數 | 型別 | 說明 |
|---|---|---|
| project_id | UUID | Project ID |

**Query 參數**

| 參數 | 型別 | 預設 | 範圍 | 說明 |
|---|---|---|---|---|
| insights_limit | integer | 5 | 1–50 | `top_insights` 回傳上限 |
| action_items_limit | integer | 10 | 1–100 | `open_action_items` 回傳上限 |
| agent_runs_limit | integer | 5 | 1–50 | `recent_agent_runs` 回傳上限 |

**範例 request**
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

| 欄位 | 來源 | 說明 |
|---|---|---|
| ticket_count | `cleaned_records` | 本 project 已匯入的 ticket 數 |
| category_distribution | `incident_analysis` GROUP BY category | 依數量 desc、再以類別名 asc 排序 |
| severity_distribution | `incident_analysis` GROUP BY severity_score（cast 成 int） | 依 severity asc 排序 |
| needs_review_count | `incident_analysis` WHERE needs_review = true | 低信心、需人工複核的紀錄數 |
| top_insights | `insights` ORDER BY created_at DESC | 最新 insights，上限為 `insights_limit` |
| open_action_items | `action_items` WHERE status='open' | 未處理行動項目，上限為 `action_items_limit` |
| recent_agent_runs | `agent_runs` ORDER BY created_at DESC | 最近 agent runs（chat + analysis），上限為 `agent_runs_limit` |

**錯誤**
- `404` — `{"detail": "Project not found"}`
- `422` — project_id 不是合法 UUID，或 query 參數超出範圍

---

## Observability（可觀測性）

### `GET /projects/{project_id}/agent-runs`

列出某個 project 的 agent runs（最新優先），供 UI 的「Agent 執行紀錄」頁面
或臨時稽核使用。

**Query 參數**

| 參數 | 型別 | 預設 | 範圍 | 說明 |
|---|---|---|---|---|
| limit | integer | 50 | 1–200 | 分頁大小 |
| offset | integer | 0 | ≥ 0 | 分頁 offset |

**Response 200** — `list[AgentRunRead]`：
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

**錯誤**
- `404` — `{"detail": "Project not found"}`
- `422` — 不合法 UUID 或分頁超範圍

---

### `GET /agent-runs/{agent_run_id}/tool-calls`

列出單一 agent run 的 tool calls，**依執行順序**（依 `created_at` asc）。
與 `/agent-runs` 搭配做 drill-down view。

**Response 200** — `list[ToolCallRead]`：
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

**錯誤**
- `404` — `{"detail": "Agent run not found"}`
- `422` — 不合法 UUID
