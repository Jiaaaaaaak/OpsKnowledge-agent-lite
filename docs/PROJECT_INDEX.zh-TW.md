# 專案索引（重要檔案用途）

> 列出專案中重要檔案的用途、呼叫關係與閱讀優先序。內容直接從原始碼讀出。
>
> 相關文件：[`SYSTEM_OVERVIEW.zh-TW.md`](./SYSTEM_OVERVIEW.zh-TW.md)（初學者架構導覽）、[`ARCHITECTURE.zh-TW.md`](./ARCHITECTURE.zh-TW.md)、[`DATA_MODEL.zh-TW.md`](./DATA_MODEL.zh-TW.md)、[`API.zh-TW.md`](./API.zh-TW.md)

「先看懂程度」分三級：

- **★★★ 必懂**（主流程核心）
- **★★ 重要**（次看）
- **★ 需要時再看**

---

## 1. 前端頁面

| 檔案路徑 | 類型 | 主要用途 | 被誰呼叫 | 會呼叫誰 | 先看懂程度 |
|---|---|---|---|---|---|
| `frontend/src/App.tsx` | React 路由進入點 | 定義 7 個頁面路由（React Router v7）、掛 `ProjectProvider` context | 使用者瀏覽器（Vite dev/preview） | `pages/*`、`context/ProjectContext` | ★★★ |
| `frontend/src/pages/ProjectPage.tsx` | 頁面 | 建立／選取作用中專案（`/projects`） | `App.tsx` | `services/`、`context/ProjectContext` | ★★★ |
| `frontend/src/pages/DocumentsPage.tsx` | 頁面 | 上傳 PDF、瀏覽已上傳文件（`/documents`） | `App.tsx` | `services/` | ★★ |
| `frontend/src/pages/ChatPage.tsx` | 頁面 | RAG 問答 — 答案 + 引用（`/chat`） | `App.tsx` | `services/` | ★★★ |
| `frontend/src/pages/AnalysisPage.tsx` | 頁面 | 一鍵執行事件分析 Agent（`/analysis`） | `App.tsx` | `services/` | ★★ |
| `frontend/src/pages/DashboardPage.tsx` | 頁面 | 儀表板：統計圖表、洞察、行動項目（`/dashboard`） | `App.tsx` | `services/` | ★★ |
| `frontend/src/pages/AgentRunsPage.tsx` | 頁面 | 瀏覽 agent_runs，展開 tool_calls（`/agent-runs`） | `App.tsx` | `services/` | ★★ |
| `frontend/src/pages/SystemStatusPage.tsx` | 頁面 | 後端健康狀態檢查（`/status`） | `App.tsx` | `services/` | ★ |

---

## 2. 前端元件

| 檔案路徑 | 類型 | 主要用途 | 被誰呼叫 | 會呼叫誰 | 先看懂程度 |
|---|---|---|---|---|---|
| `frontend/src/components/layout/AppLayout.tsx` | layout | 外層框架（sidebar 導覽列 + 頁面 outlet） | `App.tsx` | `pages/*`（React Router `<Outlet>`） | ★★ |
| `frontend/src/components/ui/` | UI 元件庫 | 共用 button、card、badge 等基礎元件 | 各 page/component | Tailwind CSS | ★ |
| `frontend/src/components/chat/` | chat 元件 | 問答對話介面子元件 | `ChatPage.tsx` | — | ★ |
| `frontend/src/components/dashboard/` | dashboard 元件 | 圖表、統計卡片子元件 | `DashboardPage.tsx` | — | ★ |
| `frontend/src/components/documents/` | document 元件 | 文件上傳、列表子元件 | `DocumentsPage.tsx` | — | ★ |

---

## 3. API client

| 檔案路徑 | 類型 | 主要用途 | 被誰呼叫 | 會呼叫誰 | 先看懂程度 |
|---|---|---|---|---|---|
| `frontend/src/services/` | HTTP service 層 | 用 axios 呼叫後端各端點；Vite proxy 將 `/api` 轉發到 `BACKEND_URL` | 各 `pages/*.tsx` | 後端 FastAPI（HTTP via Vite proxy） | ★★★ |
| `frontend/src/context/ProjectContext.tsx` | React Context | 跨頁面共享當前選取的 project_id | `App.tsx` 包裹、各 page 讀取 | — | ★★ |

---

## 4. 後端 routes

| 檔案路徑 | 類型 | 主要用途 | 被誰呼叫 | 會呼叫誰 | 先看懂程度 |
|---|---|---|---|---|---|
| `backend/app/main.py` | FastAPI 進入點 | 建立 app、掛 CORS、註冊 7 個 router | `uvicorn`（docker-compose 啟動指令） | 各 `api/*.py` 的 router、`core/config`、`core/logging` | ★★★ |
| `backend/app/api/chat.py` | route | **RAG 問答** `POST /projects/{id}/chat` | `main.py`（經 HTTP） | `services/vector_store`、`services/llm_service`、`models/agent`、`models/project` | ★★★ |
| `backend/app/api/analyze.py` | route | **事件分析 Agent** `POST /projects/{id}/analyze/incidents`，依序跑 4 工具並寫結果 | `main.py`（經 HTTP） | `tools/incident_analysis`、`services/llm_service`、`models/analysis`、`models/record`、`models/agent` | ★★★ |
| `backend/app/api/documents.py` | route | 上傳 PDF + 語意搜尋 | `main.py`（經 HTTP） | `services/document_service`、`services/vector_store` | ★★ |
| `backend/app/api/uploads.py` | route | 上傳工單（CSV/Excel/JSON） | `main.py`（經 HTTP） | `services/etl_service` | ★★ |
| `backend/app/api/dashboard.py` | route | 儀表板聚合 + agent-runs/tool-calls 查詢（純 SQL，不呼叫 LLM） | `main.py`（經 HTTP） | `models/agent`、`models/analysis`、`models/record`、`schemas/agent` | ★★ |
| `backend/app/api/projects.py` | route | 專案 CRUD（建立/列出/取得） | `main.py`（經 HTTP） | `models/project`、`schemas/project` | ★★ |
| `backend/app/api/health.py` | route | `GET /health`，檢查 DB 與 Chroma 連線 | `main.py`、docker healthcheck | `db/session.check_db_connection`、`chromadb` | ★ |

---

## 5. 後端 services

| 檔案路徑 | 類型 | 主要用途 | 被誰呼叫 | 會呼叫誰 | 先看懂程度 |
|---|---|---|---|---|---|
| `backend/app/services/llm_service.py` | service | LLM provider 抽象（mock/openai/ollama）、`build_rag_prompt`、`format_citations` | `api/chat.py`、`api/analyze.py`、`tools/incident_analysis.py`、`utils/verify_providers.py` | `openai` SDK / `httpx`（ollama）、`core/config` | ★★★ |
| `backend/app/services/vector_store.py` | service | 封裝 ChromaDB：寫入 chunk 向量、相似度搜尋（模組級單例） | `api/chat.py`、`api/documents.py` | `services/embedding_service`、`chromadb`、`core/config` | ★★★ |
| `backend/app/services/embedding_service.py` | service | Embedding provider 抽象（mock=MD5→384維 / openai） | `services/vector_store`、`utils/verify_providers` | `openai` SDK、`core/config` | ★★ |
| `backend/app/services/document_service.py` | service | PDF 解析、滑動視窗切 chunk、寫 PostgreSQL + 送 ChromaDB | `api/documents.py` | `pypdf`、`services/vector_store`（ChunkPayload/add_chunks）、`models/document` | ★★ |
| `backend/app/services/etl_service.py` | service | 工單 ETL：欄位同義詞對應、日期解析、Pydantic 驗證、寫 raw+cleaned | `api/uploads.py` | `models/record`、`csv`/`json`/`openpyxl` | ★★ |
| `backend/app/tools/incident_analysis.py` | agent tools | 4 個工具：classify/severity/insights/action_items，各自驗證輸出並寫 tool_calls | `api/analyze.py` | `services/llm_service`（LLMProvider）、`models/agent`（ToolCall）、`models/record` | ★★★ |

> `tools/` 嚴格說是「Agent 工具層」，但它是事件分析的核心邏輯，故併在此區一起看。

---

## 6. database models

| 檔案路徑 | 類型 | 主要用途 | 被誰呼叫 | 會呼叫誰 | 先看懂程度 |
|---|---|---|---|---|---|
| `backend/app/models/base.py` | ORM mixin | 共用主鍵（UUID）與 created/updated 時間欄位 | 所有 model 檔 | `sqlalchemy` | ★ |
| `backend/app/models/project.py` | ORM | `projects` 表 | routes/services 廣泛使用 | `db/session.Base`、`base.py` | ★★ |
| `backend/app/models/document.py` | ORM | `documents`、`document_chunks` 表 | `document_service`、`documents.py` | `Base`、`base.py` | ★★ |
| `backend/app/models/record.py` | ORM | `raw_records`、`cleaned_records` 表 | `etl_service`、`analyze.py`、`dashboard.py`、`tools` | `Base`、`base.py` | ★★ |
| `backend/app/models/analysis.py` | ORM | `incident_analysis`、`insights`、`action_items` 表 | `analyze.py`、`dashboard.py` | `Base`、`base.py` | ★★ |
| `backend/app/models/agent.py` | ORM | `agent_runs`、`tool_calls` 表（可觀測性） | `chat.py`、`analyze.py`、`dashboard.py`、`tools` | `Base`、`base.py` | ★★ |
| `backend/app/models/__init__.py` | 匯總 | 匯入全部 model，讓 `Base.metadata` 認得所有表 | `scripts/create_tables.py` | 上述各 model | ★ |
| `backend/app/db/session.py` | DB 連線 | 建 engine、`SessionLocal`、`get_db`、`Base`、連線檢查 | 幾乎所有 route、`create_tables.py` | `sqlalchemy`、`core/config` | ★★ |

> `schemas/*`（`chat.py`/`project.py`/`document.py`/`record.py`/`analysis.py`/`agent.py`）是 Pydantic 的 API 輸入輸出格式，被對應 route 使用——屬「資料形狀」而非資料庫 model，需要時對照即可（★）。

---

## 7. migrations

| 檔案路徑 | 類型 | 主要用途 | 被誰呼叫 | 會呼叫誰 | 先看懂程度 |
|---|---|---|---|---|---|
| `backend/migrations/001_initial_schema.sql` | SQL DDL | 完整建表 SQL（10 張表+索引），作為 schema 的人讀參考 | （見下方提醒） | — | ★★ |
| `backend/scripts/create_tables.py` | 啟動腳本 | **後端啟動時實際建表**：用 ORM `Base.metadata.create_all` | docker-compose backend 啟動指令（`main.py` 前先跑） | `app.models`、`db/session`、`core/config` | ★★ |

> ⚠️ **重要事實**：後端啟動（`docker-compose.yml:76`）實際跑的是 `create_tables.py`（走 SQLAlchemy ORM 建表），**不是**自動套用那份 `.sql`。`001_initial_schema.sql` 是手寫的對照/參考 DDL。兩者目前看起來一致，但它們是**兩個獨立來源**，改 schema 時要記得兩邊都改，否則會漂移。

---

## 8. ChromaDB 相關

| 檔案路徑 | 類型 | 主要用途 | 被誰呼叫 | 會呼叫誰 | 先看懂程度 |
|---|---|---|---|---|---|
| `backend/app/services/vector_store.py` | service | 唯一直接操作 ChromaDB 的檔（HttpClient、upsert、query） | `chat.py`、`documents.py` | `chromadb`、`embedding_service`、`config` | ★★★ |
| `backend/app/services/embedding_service.py` | service | 產生送進 Chroma 的向量（文字→embedding） | `vector_store` | `openai`/本地 hash、`config` | ★★ |
| `backend/app/core/config.py`（Chroma 段） | 設定 | `chroma_host/port/collection_name` | `vector_store`、`health.py` | `pydantic-settings`、`.env` | ★★ |
| `docker-compose.yml`（chromadb service） | 部署 | 啟動 Chroma 容器（host 8001→container 8000）、`chroma_data` volume | `docker compose` | — | ★ |

> ChromaDB 沒有獨立的 Python 模組；所有互動都集中在 `vector_store.py`，這是看懂向量檢索的單一入口。

---

## 9. 測試檔案

全部在 `backend/tests/`，用 pytest（`make test` 或 `make test-local` 執行）。被誰呼叫 = 測試框架；會呼叫誰 = 對應被測模組。

| 檔案路徑 | 行數 | 測試對象 | 先看懂程度 |
|---|---|---|---|
| `tests/test_chat.py` | 347 | `api/chat.py`（RAG 問答流程） | ★★ |
| `tests/test_analyze.py` | 438 | `api/analyze.py`（4 工具 agent 編排） | ★★ |
| `tests/test_etl.py` | 412 | `services/etl_service.py`（欄位對應、驗證） | ★★ |
| `tests/test_mock_providers.py` | 377 | `llm_service`/`embedding_service` 的 mock 行為 | ★★ |
| `tests/test_dashboard.py` | 377 | `api/dashboard.py`（聚合查詢） | ★ |
| `tests/test_document_service.py` | 283 | `services/document_service.py`（PDF 切塊） | ★ |
| `tests/test_audit_gaps.py` | 225 | 邊界/缺口稽核 | ★ |
| `tests/test_projects.py` | 151 | `api/projects.py` | ★ |
| `tests/test_vector_store.py` | 101 | `services/vector_store.py` | ★ |
| `tests/test_schema_metadata.py` | 75 | schema / metadata 驗證 | ★ |
| `tests/test_embedding_service.py` | 42 | `embedding_service.py` | ★ |
| `tests/test_db_init.py` | 38 | 建表/DB 初始化 | ★ |
| `tests/test_health.py` | 36 | `api/health.py` | ★ |
| `tests/__init__.py` | 0 | 套件標記 | — |

> 測試對象依**檔名與被測模組**對應推得；各檔內部具體斷言未逐行細讀。`test_audit_gaps.py` 的確切涵蓋範圍需開檔才能確認。

---

## 10. 設定檔

| 檔案路徑 | 類型 | 主要用途 | 被誰呼叫 | 會呼叫誰 | 先看懂程度 |
|---|---|---|---|---|---|
| `backend/app/core/config.py` | 設定載入 | 用 pydantic-settings 讀 `.env`，集中所有設定（DB/Chroma/provider/模型） | 幾乎所有後端模組 | `pydantic-settings`、`.env`（絕對路徑錨定） | ★★★ |
| `.env` | 環境變數 | 實際生效的設定值（本機） | `config.py`、docker-compose `env_file` | — | ★★★ |
| `.env.example` | 環境變數範本 | 安全範本 + 各變數說明（mock/openai/ollama 切換） | 人（`cp .env.example .env`） | — | ★★ |
| `docker-compose.yml` | 編排 | 定義 4 服務、port、volume、healthcheck、啟動指令 | `docker compose` / `Makefile` | 各 Dockerfile、`.env` | ★★ |
| `Makefile` | 指令集 | `up/down/test/psql/clean` 等常用指令（專案指令來源） | 開發者 `make ...` | `docker compose`、`curl` | ★★ |
| `backend/Dockerfile` | 映像 | 後端容器建置 | `docker compose build` | `backend/requirements.txt` | ★ |
| `frontend/Dockerfile` | 映像 | 前端容器建置（Node 20，`npm run build` + `vite preview`） | `docker compose build` | `frontend/package.json` | ★ |
| `backend/requirements.txt` | 依賴 | 後端 Python 套件 | Dockerfile / pip | — | ★ |
| `frontend/package.json` | 依賴 | 前端 Node.js 套件（React、Vite、Tailwind、axios 等） | Dockerfile / npm | — | ★ |
| `backend/app/core/logging.py` | 設定 | 統一 logging 格式 | `main.py`、`create_tables.py` | `logging` | ★ |
| `backend/app/utils/verify_providers.py` | 工具腳本 | 驗證 LLM/Embedding provider 是否能呼叫（不洩漏金鑰） | 開發者手動執行 | `get_llm_provider`、`get_embedding_provider`、`config` | ★ |
| `CLAUDE.md` | 專案規範 | 18 條工作/安全規則 | 人 / AI 助手 | — | ★ |

---

## 給初學者的「閱讀順序」建議

若要最快看懂主流程，建議按這個順序讀 ★★★ 檔案：

1. `frontend/src/App.tsx` → `frontend/src/pages/ChatPage.tsx` → `frontend/src/services/`（看使用者怎麼發請求）
2. `backend/app/main.py`（看路由怎麼掛）
3. `backend/app/api/chat.py`（看一條完整 RAG 請求）
4. `backend/app/services/vector_store.py` + `embedding_service.py`（看檢索）
5. `backend/app/services/llm_service.py`（看 mock/真 AI 切換）
6. `backend/app/core/config.py`（看所有設定來源）
7. 進階：`backend/app/api/analyze.py` + `tools/incident_analysis.py`（看 4 工具 agent）

---

## 附註（誠實揭露）

- 呼叫關係（被誰呼叫 / 會呼叫誰）依 import 關係與實際讀過的程式碼整理；前端→後端為 HTTP 呼叫，非直接 import。
- 測試檔的「測試對象」依檔名與被測模組對應推得，未逐行細讀每個斷言。
- 本文件未修改任何程式碼，僅為閱讀說明。
