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

多模態匯入：對「可抽取文字過少」的頁（掃描 / 影像型 PDF）會渲染後以 Tesseract OCR
辨識（`chi_tra+chi_sim+eng`，並正規化為繁體中文），由 `OCR_*` 設定控制。當缺少
`tesseract`/`poppler` 時自動降級。`ocr_page_count` 回報有多少頁是經 OCR 補回文字。

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
  "source_path": "data/uploads/{project_id}/documents/network_sop.pdf",
  "ocr_page_count": 0
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
      "snippet": "To restart PostgreSQL...",
      "source_language": "en",
      "snippet_translated": null
    }
  ]
}
```

Citation 欄位：
- `source_language` — 來源 chunk 偵測到的語言（`"zh"` / `"en"`）。
- `snippet_translated` — 將 snippet 翻成提問語言；僅在 chunk 語言與提問語言不同時填入，
  否則為 `null`。（支援跨語作答，例如英文文件搭配中文提問。）

當模型輸出簡體中文時，答案會正規化為繁體中文（台灣）；同時 LLM 也被要求以提問語言作答。

檢索行為：
- Chat 使用與 `/search` 相同的 hybrid search service（固定流程：hybrid 檢索 → 選擇性
  rerank → 作答；`task_type="rag_chat"`）。
- 若 `RERANKER_ENABLED=true`，fusion 後的候選 chunks 會再經 cross-encoder reranker 排序。
- 每次請求會寫入一筆 `agent_runs`。
- 每次請求會寫入一筆 `tool_calls`，`tool_name="hybrid_search"`。
- 若有啟用 rerank，會額外寫入一筆 `tool_calls`，`tool_name="rerank"`。
- 若有跨語 snippet 被翻譯，會寫入一筆 `tool_name="translate"` 的 `tool_calls`。

### `POST /projects/{project_id}/agent-chat`

對專案文件的自主 agent 問答。不同於 `/chat` 的固定流程，這裡由 LLM 自己透過單一
`search_documents(query, strategy)` 工具決定要不要檢索、查什麼、查幾次、用哪種檢索策略，
最後再作答。`strategy` 為 `hybrid`（預設，通用）、`keyword`（錯誤碼、指令名、設定鍵、ID
等精確詞）或 `vector`（概念 / 語意題）之一。整個迴圈以 `AGENT_MAX_STEPS` 作安全上限。

Request / Response shape 與 `/chat` 完全相同（`ChatRequest` → `ChatResponse`，含
`source_language` / `snippet_translated` citation 欄位）。

可觀測性：
- 每次請求寫入一筆 `agent_runs`，`task_type="agent_chat"`；其 `output_json` 含
  `search_count` 與 `stop_reason`（`"completed"` 或 `"max_steps"`）。
- 每次 agent 檢索寫入一筆 `tool_calls`，`tool_name="search_documents"`（`input_json` 含
  `query` 與 `strategy`）。
- 若有跨語 snippet 被翻譯，會寫入一筆 `tool_name="translate"` 的 `tool_calls`。

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
