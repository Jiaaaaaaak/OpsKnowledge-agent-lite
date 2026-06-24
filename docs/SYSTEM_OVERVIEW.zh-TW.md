# 系統總覽 — OpsKnowledge Agent Lite

這是一個面向 IT 維運文件的 RAG 知識庫展示專案。系統匯入 PDF SOP / 技術手冊，切成 chunks，建立 PostgreSQL full-text 與 pgvector 索引，透過 hybrid search + 選用 reranker 找出 context，再由 LLM 產生附引用來源的回答。每次 RAG chat 都會寫入 `agent_runs` 與 `tool_calls`，方便面試展示可觀測性。

## 1. 服務組成

| 服務 | 連接埠 | 用途 |
|---|---:|---|
| frontend | 8501 | React + Vite 前端 |
| backend | 8000 | FastAPI API |
| postgres + pgvector | 5432 | 文件、chunks、向量、full-text index、稽核紀錄 |
| ollama | 11434 | 地端 LLM provider |
| reranker | 8080 | 選用 TEI cross-encoder reranker |

## 2. 主要前端頁面

| 檔案 | 用途 |
|---|---|
| `ProjectPage.tsx` | 建立 / 選擇專案 |
| `KnowledgeWorkflowPage.tsx` | 上傳文件、查看知識庫狀態、進行 RAG 問答 |
| `AgentRunsPage.tsx` | 查看 `agent_runs` 與 `tool_calls` |
| `SystemStatusPage.tsx` | 查看 API / DB / pgvector 狀態 |

## 3. 後端 API

| 路由檔 | 端點 | 用途 |
|---|---|---|
| `api/health.py` | `GET /health` | 健康檢查 |
| `api/projects.py` | `GET/POST /projects/`、`GET /projects/{id}` | 專案 CRUD |
| `api/documents.py` | `POST /projects/{id}/upload/documents`、`GET /projects/{id}/documents`、`GET /projects/{id}/search` | PDF ingestion 與 hybrid search |
| `api/chat.py` | `POST /projects/{id}/chat` | RAG 問答 |
| `api/dashboard.py` | `GET /projects/{id}/workflow-status`、agent-runs、tool-calls | 工作流程狀態與可觀測性 |

## 4. 核心資料表

| 資料表 | 用途 |
|---|---|
| `projects` | 專案 |
| `documents` | PDF metadata 與檔案路徑 |
| `document_chunks` | chunk 原文、`embedding vector(1024)`、generated `search_vector`、metadata |
| `agent_runs` | 每次 RAG chat 的執行紀錄 |
| `tool_calls` | `hybrid_search` 與選用 `rerank` 的工具層 trace |

## 5. 檢索流程

```text
User question
  └─ HybridRetrievalService
       ├─ VectorRetriever → pgvector cosine search
       ├─ KeywordRetriever → PostgreSQL full-text search
       └─ ReciprocalRankFusion → merge by chunk_id
            └─ optional RerankerProvider
                 └─ build_rag_prompt → LLM → answer + citations
```

## 6. Provider 模式

| Provider | 用途 |
|---|---|
| `mock` | 離線、確定性測試與 demo |
| `ollama` | 地端 LLM |
| `openai` | OpenAI-compatible hosted provider |

目前 embedding 維度為 `1024`，需與 `document_chunks.embedding vector(1024)` 保持一致。

## 7. 可觀測性

每次 `POST /projects/{id}/chat` 會寫入：

- `agent_runs`：task type、model、input/output、latency、status
- `tool_calls`：`hybrid_search` 的 vector/keyword/fused counts 與 chunk ids
- 若啟用 reranker，額外寫入 `tool_calls.tool_name="rerank"`
