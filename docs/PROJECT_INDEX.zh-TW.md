# 專案索引 — OpsKnowledge Agent Lite

這份索引反映目前的程式結構：hybrid search RAG（`/chat`）、自主 tool-calling agent（`/agent-chat`）、多語跨語檢索與 OCR 多模態匯入。

## 1. 前端

| 檔案路徑 | 主要用途 |
|---|---|
| `frontend/src/App.tsx` | React Router 設定 |
| `frontend/src/components/layout/Sidebar.tsx` | 側邊欄主導覽 |
| `frontend/src/components/layout/Header.tsx` | 頁首標題與描述 |
| `frontend/src/context/ProjectContext.tsx` | 目前專案狀態 |
| `frontend/src/pages/ProjectPage.tsx` | 建立 / 選擇專案 |
| `frontend/src/pages/KnowledgeWorkflowPage.tsx` | 知識庫上傳與 RAG chat 主流程 |
| `frontend/src/pages/AgentRunsPage.tsx` | Agent runs / tool calls 可觀測性 |
| `frontend/src/pages/SystemStatusPage.tsx` | API / DB / pgvector 狀態 |
| `frontend/src/services/api.ts` | Axios API client |

## 2. 後端路由

| 檔案路徑 | 端點 | 主要用途 |
|---|---|---|
| `backend/app/main.py` | app setup | 註冊 router 與 CORS |
| `backend/app/api/health.py` | `GET /health` | 健康檢查 |
| `backend/app/api/projects.py` | `/projects/` | 專案 CRUD |
| `backend/app/api/documents.py` | `/upload/documents`、`/documents`、`/search` | PDF ingestion、文件列表、hybrid search |
| `backend/app/api/chat.py` | `/chat`、`/agent-chat` | RAG 問答（固定流程）與自主 agent 問答 |
| `backend/app/api/dashboard.py` | `/workflow-status`、`/agent-runs`、`/tool-calls` | 工作流程狀態與可觀測性 |

## 3. 後端服務

| 檔案路徑 | 主要用途 |
|---|---|
| `backend/app/services/document_service.py` | PDF 解析、切 chunk、建立 `documents` / `document_chunks`；OCR fallback |
| `backend/app/services/ocr_service.py` | 掃描 / 影像頁的 Tesseract OCR（lazy import、缺套件自動降級） |
| `backend/app/services/embedding_service.py` | Embedding provider 抽象：mock / openai / ollama（多語 bge-m3） |
| `backend/app/services/vector_store.py` | 寫入 pgvector embedding，執行 dense vector search |
| `backend/app/services/retrieval/` | Hybrid retrieval：vector、keyword、RRF fusion；`search(..., strategy)` |
| `backend/app/services/reranker_service.py` | 選用 TEI reranker provider |
| `backend/app/services/llm_service.py` | LLM provider（含 tool-calling）、RAG prompt、citations、語言偵測 / 翻譯 / 簡轉繁 |
| `backend/app/services/chat_service.py` | RAG chat（`/chat`）orchestration 與 audit logging |
| `backend/app/services/agent_service.py` | 自主 agent chat（`/agent-chat`）：tool-calling 迴圈與 audit logging |

## 4. 資料模型

| 檔案路徑 | 主要用途 |
|---|---|
| `backend/app/models/project.py` | `projects` |
| `backend/app/models/document.py` | `documents`、`document_chunks` |
| `backend/app/models/agent.py` | `agent_runs`、`tool_calls` |
| `backend/app/schemas/*.py` | API request / response schemas |

## 5. 資料庫與部署

| 檔案路徑 | 主要用途 |
|---|---|
| `backend/migrations/001_initial_schema.sql` | 初始 schema |
| `backend/app/db/session.py` | SQLAlchemy engine、session、pgvector/schema repair helpers |
| `backend/scripts/create_tables.py` | 建表與補索引腳本 |
| `docker-compose.yml` | postgres、ollama、reranker、backend、frontend |
| `.env.example` | Provider、DB、reranker 設定範本 |

## 6. 測試

| 測試檔 | 覆蓋重點 |
|---|---|
| `backend/tests/test_document_service.py` | PDF parsing / chunking / ingestion |
| `backend/tests/test_vector_store.py` | pgvector 寫入與 dense search |
| `backend/tests/test_retrieval.py` | keyword retriever、RRF fusion、hybrid service fallback |
| `backend/tests/test_chat.py` | RAG chat、hybrid_search tool call、reranker fallback |
| `backend/tests/test_agent.py` | 自主 agent chat：tool-calling 迴圈、strategy 選擇、stop_reason |
| `backend/tests/test_ocr_service.py` | OCR fallback 與缺套件時的降級 |
| `backend/tests/test_documents_api.py` | 文件 API schema |
| `backend/tests/test_dashboard.py` | workflow-status、agent-runs、tool-calls |
| `frontend/src/pages/KnowledgeWorkflowPage.test.tsx` | 知識庫流程狀態 |

## 7. 建議閱讀順序

1. `README.md`
2. `docs/ARCHITECTURE.md`
3. `backend/app/services/retrieval/service.py`
4. `backend/app/services/chat_service.py`
5. `frontend/src/pages/KnowledgeWorkflowPage.tsx`
