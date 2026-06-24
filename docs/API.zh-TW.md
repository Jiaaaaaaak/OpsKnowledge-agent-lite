# API 參考 — OpsKnowledge Agent Lite

[English](API.md) | 繁體中文

Base URL: `http://localhost:8000`

互動式文件：`http://localhost:8000/docs`

---

## Health

### `GET /health`

回傳服務狀態，包含 PostgreSQL 與 pgvector 連線。

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

建立專案。

```json
{
  "name": "IT Operations Demo",
  "description": "Demo project for technical manuals"
}
```

### `GET /projects/`

列出專案，依建立時間由新到舊排序。

### `GET /projects/{project_id}`

依 UUID 取得單一專案。

---

## Documents

### `POST /projects/{project_id}/upload/documents`

上傳 PDF 技術手冊或 SOP。後端會抽取文字、切 chunk、將 metadata 寫入
PostgreSQL、建立 embedding 並寫入 pgvector。`document_chunks.search_vector`
generated column 也會建立文字索引，供 hybrid search 的 keyword 分支使用。

Request:
- `multipart/form-data`
- 欄位 `file`
- 僅支援 `.pdf`

Response:

```json
{
  "document_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "filename": "network_sop.pdf",
  "page_count": 24,
  "chunk_count": 87,
  "source_path": "data/uploads/{project_id}/documents/network_sop.pdf"
}
```

### `GET /projects/{project_id}/documents`

列出專案已上傳文件。

### `GET /projects/{project_id}/search`

對已索引的 chunks 做 hybrid search。後端會執行：

1. pgvector dense retrieval
2. PostgreSQL full-text retrieval：`websearch_to_tsquery('english', query)`
3. 依 `chunk_id` 做 reciprocal-rank fusion

Query parameters:

| 參數 | 必填 | 預設 | 說明 |
|---|---:|---:|---|
| `query` | 是 | — | 搜尋文字 |
| `top_k` | 否 | 5 | 回傳 chunk 數，1-50 |

範例：

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

使用專案文件的 RAG 內容回答問題。

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
      "snippet": "To restart PostgreSQL..."
    }
  ]
}
```

檢索行為：
- Chat 使用與 `/search` 相同的 hybrid search service。
- 若 `RERANKER_ENABLED=true`，fusion 後的候選 chunks 會再經 cross-encoder reranker 排序。
- 每次請求會寫入一筆 `agent_runs`。
- 每次請求會寫入一筆 `tool_calls`，`tool_name="hybrid_search"`。
- 若有啟用 rerank，會額外寫入一筆 `tool_calls`，`tool_name="rerank"`。

---

## Workflow Status

### `GET /projects/{project_id}/workflow-status`

回傳專案的知識庫工作流程就緒狀態。

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

列出專案最近的 agent runs，由新到舊排序。

Query parameters:

| 參數 | 預設 | 說明 |
|---|---:|---|
| `limit` | 50 | 最大筆數，1-200 |
| `offset` | 0 | 分頁 offset |

### `GET /agent-runs/{agent_run_id}/tool-calls`

依執行順序列出某次 agent run 的 tool calls。

---

## 錯誤慣例

- `400` — 上傳格式錯誤、空檔案、或 PDF 無可抽取文字
- `404` — 找不到 project 或 agent run
- `422` — UUID 格式錯誤、缺少必填欄位、或 query parameter 不合法
- `500` — embedding、retrieval 或 LLM provider 無法使用
