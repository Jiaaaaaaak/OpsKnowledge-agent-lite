# OpsKnowledge Agent Lite

[English](README.md) | 繁體中文

一套面向 IT 維運與系統整合情境的企業級 AI + 資料工程概念驗證（POC）專案。

## 語言說明 / Language

**使用者介面**（React 前端）使用**繁體中文**，目標使用情境為台灣／華語環境的
企業內部 IT 維運工具。

**程式碼、API 路徑、資料庫 schema 與技術文件主檔**維持**英文**，符合工程慣例，
也方便國際審閱。

| 層級 | 語言 | 原因 |
|---|---|---|
| React UI 標籤 / 按鈕 / 訊息 | 繁體中文 | 目標使用者為台灣 IT 維運團隊 |
| 程式識別字（函式 / 類別 / 變數） | 英文 | 工程慣例 |
| FastAPI 路徑與 request / response 欄位名 | 英文 | 後端 contract 穩定 |
| 資料庫欄位與資料表名稱 | 英文 | Schema 可攜性 |
| 主檔文件（`README.md`、`docs/*.md`） | 英文 | 國際審閱友善 |
| 鏡像文件（`README.zh-TW.md`、`docs/*.zh-TW.md`） | 繁體中文 | 在地團隊上手 |
| 原始碼註解與 commit message | 繁體中文 | 團隊偏好（見 CLAUDE.md Rule 13） |

## 功能概覽

| 能力 | 說明 |
|---|---|
| 文件 RAG | 上傳 PDF 手冊／SOP → 切塊、嵌入、透過 PostgreSQL + pgvector 檢索 |
| 事件 ETL | 上傳 CSV／Excel／JSON 工單 → 正規化、清洗、寫入 PostgreSQL |
| AI 分析 | 事件分類、嚴重度評分、產生洞察與行動項目 |
| 可觀測性 | 每一次 AI 工具呼叫皆記錄至 PostgreSQL，便於稽核 |
| 儀表板 | 以 React 提供上傳、問答、分析與代理日誌介面 |

## 技術堆疊

- **後端**：Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2
- **資料庫**：PostgreSQL 16
- **向量資料庫**：PostgreSQL + pgvector
- **AI**：相容 OpenAI 介面（可切換至 Ollama）
- **前端**：React (Vite + TypeScript + Tailwind CSS)
- **基礎設施**：Docker Compose

## 快速開始（Docker Compose）

四個步驟，除 `.env` 外不需任何手動設定：

預設面試／展示路線是地端優先：Ollama 負責 LLM，mock 384 維 embedding 負責 pgvector 搜尋。

```bash
# 1. 複製 env 範本（預設 Ollama LLM + mock embedding）
cp .env.example .env

# 2.（選用）若要使用真實模型，編輯 .env
#    - hosted OpenAI：LLM_PROVIDER=openai，並填入 OPENAI_API_KEY
#    - 地端展示維持 LLM_PROVIDER=ollama，使用 Docker Compose 內建 Ollama

# 3. 建置並啟動完整 stack（postgres + pgvector、ollama、backend、frontend）
docker compose up --build -d
# 或用內附的 Makefile：
make up

# 4. 將地端模型下載進 ollama_data volume
make pull-ollama

# 5. 開啟 UI
#    前端（React）：http://localhost:8501
#    後端文件：          http://localhost:8000/docs
#    後端健康檢查：      http://localhost:8000/health
```

停掉所有服務（資料會保留在 named volumes）：
```bash
docker compose down    # 或：make down
```

清掉資料重來（破壞性 — 會刪除 postgres 資料與已下載的 Ollama 模型）：
```bash
make clean              # 會詢問確認
```

### 服務與連接埠

| 服務 | Host port | Container port | 鏡像 / 建置 |
|---|---|---|---|
| frontend（React） | **8501** | 8501 | 由 `frontend/Dockerfile` 建置（`vite preview`） |
| backend（FastAPI） | **8000** | 8000 | 由 `backend/Dockerfile` 建置 |
| postgres + pgvector | **5432** | 5432 | `pgvector/pgvector:pg16` |
| ollama | **11434** | 11434 | `ollama/ollama` |

### 啟動順序

`docker-compose.yml` 用 healthcheck 串起服務，只有依賴真的 ready 之後才會起：

```
postgres (pg_isready)  ─┐
                        ├─► backend（依賴 service_healthy 後才起）
ollama (ollama list)   ─┘             │
                                      └─► frontend（backend /health 通過後才起）
```

Backend 容器啟動時會自動跑 `python scripts/create_tables.py && uvicorn ...`，
schema 在 API 開放前就會建好。

### 常用 Make target

```bash
make up           # 背景建置並啟動
make down         # 停止（保留資料）
make logs         # tail 全部服務（logs-backend / logs-frontend / ... 看單一）
make logs-ollama  # tail Ollama logs
make ps           # 看 container 狀態
make health       # curl /health 並 pretty-print
make test         # 在 backend 容器內跑 pytest
make pull-ollama  # 將預設地端 LLM 模型下載進 ollama_data
make psql         # 開 postgres 容器的 psql shell
make clean        # ⚠️ 停 stack + 刪 volume（會問確認）
```

### Provider 模式

| 模式 | 環境變數 | API key | 說明 |
|---|---|---|---|
| **ollama-local**（預設） | `LLM_PROVIDER=ollama`、`EMBEDDING_PROVIDER=mock` | 不需要 | 地端 Ollama 回答 + 確定性 384 維 embedding 寫入 pgvector |
| **mock** | `EMBEDDING_PROVIDER=mock`、`LLM_PROVIDER=mock` | 不需要 — `OPENAI_API_KEY` 可留空 | 完全確定性的離線 provider；適合測試 |
| **openai** | `EMBEDDING_PROVIDER=openai`、`LLM_PROVIDER=openai` | 需要有效的 `OPENAI_API_KEY` | hosted LLM + OpenAI 相容 embedding；embedding 會要求 384 維 |

> **面試展示採地端優先。** 主要路線使用 `ollama` 回答、`mock` embedding 做穩定的
> 本地向量搜尋。需要 hosted model 品質時仍可切到 `openai`。切換只需修改 `.env`，
> 不需更動應用程式碼。詳見下方[本地模型 provider（Ollama）](#本地模型-providerollama)。

### 從地端 Ollama 模式切換到 OpenAI

系統預設以 **Ollama LLM + mock embedding** 出貨。要接上真正的 OpenAI 相容 API：

1. 在專案根目錄 `.env`（即 `cp .env.example .env` 建立的那份）設定 provider 與金鑰
   （model／base URL 已有預設值）。設定已錨定到這份根目錄 `.env`，不論從哪個目錄啟動都會讀到：
   ```bash
   LLM_PROVIDER=openai
   EMBEDDING_PROVIDER=openai
   EMBEDDING_DIMENSIONS=384
   OPENAI_API_KEY=sk-...你的真實金鑰...
   # 選填覆寫：
   # OPENAI_BASE_URL=https://api.openai.com/v1
   # LLM_MODEL=gpt-4o-mini
   # EMBEDDING_MODEL=text-embedding-3-small
   ```
2. 在啟動應用程式**之前**，先驗證 provider 是否真的能呼叫：
   ```bash
   cd backend
   python -m app.utils.verify_providers
   ```
   （此模組位於 `backend/` 底下，需從該目錄執行；但它仍會讀取根目錄的 `.env`。）
   會印出目前 provider 名稱，送出一次短 LLM 請求與一次短 embedding 請求，
   並回報 `PASS` / `FAIL`。它**絕不會印出 API 金鑰**（只顯示遮罩後的摘要），
   失敗時以非 0 結束碼結束，可用於 CI；金鑰缺漏或無效時會回傳清楚的錯誤。

> `EMBEDDING_DIMENSIONS=384` 很重要，因為 pgvector 欄位是 `vector(384)`。
> 切回地端展示模式則是：`LLM_PROVIDER=ollama`、`EMBEDDING_PROVIDER=mock`。

### 主機名稱：Docker vs 本機

應用程式透過 `POSTGRES_*` 設定連線到 PostgreSQL + pgvector
（沒有 `DATABASE_URL`，詳見 `backend/app/core/config.py`）。

- **Docker Compose** 會將 `POSTGRES_HOST` 覆寫為 `postgres`。pgvector 是該
  PostgreSQL service 裡的 extension，不是獨立 hostname。
- **Docker Compose** 會將 `OLLAMA_BASE_URL` 覆寫為 `http://ollama:11434`。
- **本機（不使用 Docker）** 使用 `.env.example` 預設的 `localhost`。

## Mock 模式（不需 API key）

如果要完全確定性測試、不要發出地端模型請求，可以把兩個 provider 都切成 mock：

| Provider | 環境變數 | 行為 |
|---|---|---|
| `MockEmbeddingProvider` | `EMBEDDING_PROVIDER=mock` | 回傳 384 維單位向量（MD5 seeded，不打網路） |
| `MockLLMProvider` | `LLM_PROVIDER=mock` | 從 retrieved context 擷取片段，回傳帶 `[mock]` 前綴的答案 |

```bash
# .env — 這是 .env.example 的預設，不需要編輯：
EMBEDDING_PROVIDER=mock
LLM_PROVIDER=mock
# OPENAI_API_KEY 留空 — mock 模式下會被忽略
```

### Mock 模式能跑什麼
- Backend 單元測試，零外部呼叫
- `POST /projects/{id}/upload/documents` — PDF 解析、切 chunk、寫入 PostgreSQL；
  embedding 在本地產生並存入 PostgreSQL + pgvector（PostgreSQL + pgvector 仍需執行中）
- `GET /projects/{id}/search` — 用 mock 向量做檢索並回結果
- `POST /projects/{id}/chat` — 回確定性的 mock 答案 + 引用；
  `agent_runs` 與 `tool_calls` 仍會寫入 PostgreSQL

### 需要真實 API key 才能拿到的
- 真正可用品質的回答（真實 LLM 推理）
- 真正具語意相關性的搜尋結果（真實 embedding 相似度）

### 跑全套測試（不需外部服務）
```bash
cd backend
PYTHONPATH=. pytest tests/ -v
```

### 本地快速 smoke test（需要 PostgreSQL + pgvector 在跑）
```bash
cp .env.example .env
# 編輯 .env：設定 EMBEDDING_PROVIDER=mock  LLM_PROVIDER=mock
#           並設定 POSTGRES_* 指向你的 PostgreSQL + pgvector 服務

cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python scripts/create_tables.py

# 啟動 server
PYTHONPATH=. uvicorn app.main:app --reload

# 在另一個 terminal：
PROJECT_ID=$(curl -s -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Mock Test"}' | jq -r '.id')

# 驗證 health（db 與 vector 應該都顯示 "connected"）
curl http://localhost:8000/health

# 上傳 PDF 並問問題（mock provider、不需 API key）
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/upload/documents" \
  -F "file=@demo_data/documents/your_manual.pdf"

curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/chat" \
  -H "Content-Type: application/json" \
  -d '{"question": "What does this document cover?", "top_k": 3}'
# 回應：{ "answer": "[mock] ...", "citations": [...] }
```

## 本地模型 Provider（Ollama）

針對私有／地端情境，LLM 可透過 [Ollama](https://ollama.com) 完全在本地硬體上執行，
不需 OpenAI 帳號、資料不離開主機。`OllamaLLMProvider` 直接呼叫 Ollama 原生 HTTP
API（`/api/chat`）。

```bash
# 1. 讓應用程式指向 Ollama（.env）
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
# Docker Compose 會在 backend 容器內使用內建 ollama service。
DOCKER_OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
# embedding 與 LLM 獨立 — 可維持 EMBEDDING_PROVIDER=mock（離線）或 =openai
EMBEDDING_PROVIDER=mock

# 2. 啟動 compose，並把模型下載進 ollama_data volume
docker compose up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b-instruct
```

這是唯一需要的改動 — 不需更動任何應用程式碼。若 Ollama 伺服器無法連線，`/chat`
會以明確錯誤回應（例如 *「無法連線到 Ollama … 請確認 Ollama 服務已啟動」*），
而不是卡住或回傳捏造的答案。

> **範圍：** 這個 provider 只涵蓋 **LLM**。embedding 仍由 `EMBEDDING_PROVIDER`
> （`openai` / `mock`）選擇。要做到完全地端，還需要一個本地 embedding provider —
> `EmbeddingProvider` 介面支援以相同方式新增。面試展示建議維持
> `LLM_PROVIDER=ollama`、`EMBEDDING_PROVIDER=mock`：可展示地端模型操作，同時讓向量搜尋穩定且相依較少。

## 本機開發（不使用 Docker）

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 另行啟動 PostgreSQL 與 PostgreSQL + pgvector 後，執行：
PYTHONPATH=. uvicorn app.main:app --reload

# 執行測試
PYTHONPATH=. pytest tests/ -v
```

## 資料庫初始化

**方式 A — Python 腳本（建議用於本機開發）：**
```bash
cd backend
cp ../.env.example ../.env   # 設定 POSTGRES_* 變數
PYTHONPATH=. python scripts/create_tables.py
```

**方式 B — 原生 SQL（psql）：**
```bash
psql -h localhost -U opsuser -d opsknowledge -f backend/migrations/001_initial_schema.sql
```

**方式 C — Docker Compose（首次啟動時自動建立）：**
```bash
docker compose up --build
# 接著在 backend 容器內執行腳本：
docker compose exec backend python scripts/create_tables.py
```

**驗證資料表是否建立成功：**
```sql
-- 連線後執行：
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

## 專案結構

```
opsknowledge-agent-lite/
  backend/           FastAPI 服務
    app/
      core/          設定、日誌
      api/           路由處理器
      models/        SQLAlchemy ORM 模型
      schemas/       Pydantic 請求／回應結構
      services/      商業邏輯
      tools/         AI 工具定義（LLM function call）
      db/            資料庫連線、遷移
      utils/         共用輔助函式
    tests/
  frontend/          React UI (Vite + TypeScript + Tailwind CSS)
  docs/              架構、PRD、資料模型、API 文件
  demo_data/         供 Demo 用的範例工單與 PDF
  docker-compose.yml
```

## 上傳 PDF 文件

```bash
# 上傳 PDF 技術手冊或 SOP
PROJECT_ID=$(curl -s -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name":"IT Operations Demo"}' | jq -r '.id')

curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/upload/documents" \
  -F "file=@demo_data/documents/your_manual.pdf"

# 預期回應
# {
#   "document_id": "...",
#   "filename": "your_manual.pdf",
#   "page_count": 24,
#   "chunk_count": 87,
#   "source_path": "data/uploads/.../your_manual.pdf"
# }
```

> **備註：** 請將公眾領域的手冊（例如開源 SOP PDF、RFC 文件）放入
> `demo_data/documents/` 供 Demo 使用。此目錄下的檔案不會納入 git 追蹤。
> 上傳的檔案會儲存於 `backend/data/uploads/`。

> **嵌入：** 上傳時每個 chunk 會被嵌入並索引至 PostgreSQL + pgvector。地端 Ollama
> 展示預設使用 mock embedding，不需要 API key。openai 模式則需要 `.env` 內設定有效的 `OPENAI_API_KEY`；未設定時上傳會以
> 清楚的錯誤訊息失敗（不留下半套資料）。

## Chat（RAG 問答）

```bash
# 對已上傳的文件提問
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Docker volume data disappeared after container restart. What should I check?",
    "top_k": 5
  }'

# 預期回應
# {
#   "answer": "請確認以下項目：\n- 執行 `docker inspect <container>` 並查看 Mounts 欄位。\n- 確認 volume 類型不是 `tmpfs`。\n- 確認 docker-compose.yml 的 volumes: 已正確宣告。",
#   "citations": [
#     {
#       "document_id": "7c1d...",
#       "chunk_id": "9b2c...",
#       "filename": "docker_operations.pdf",
#       "chunk_index": 3,
#       "snippet": "Docker volumes persist data outside container lifecycle..."
#     }
#   ]
# }
```

> **幻覺控制：** 模型被指示只根據已取回的 context 回答。若 context 不足，
> 會以固定措辭回應而非捏造答案。每次請求皆寫入一筆 `agent_runs` 與一筆
> `tool_calls`（retrieval 步驟）至 PostgreSQL，確保可稽核性。

## 搜尋文件

```bash
# 對專案內已嵌入的 chunk 做語意搜尋
curl "http://localhost:8000/projects/${PROJECT_ID}/search?query=how%20to%20restart%20the%20service&top_k=5"

# 預期回應
# {
#   "project_id": "...",
#   "query": "how to restart the service",
#   "top_k": 5,
#   "results": [
#     {
#       "chunk_id": "9b2c...",          # == PostgreSQL 的 document_chunks.id
#       "content": "To restart the service, run ...",
#       "metadata": { "project_id": "...", "document_id": "...",
#                     "chunk_id": "9b2c...", "filename": "network_sop.pdf",
#                     "chunk_index": 12 },
#       "distance": 0.18,
#       "score": 0.82
#     }
#   ]
# }
```

> 搜尋回傳的每個 `chunk_id` 等同 PostgreSQL 的 `document_chunks.id` UUID，
> 因此可將搜尋結果對回完整資料列：
> `SELECT * FROM document_chunks WHERE id = '<chunk_id>';`

## 上傳事件工單

```bash
# 1. 建立專案，取得 project_id
PROJECT_ID=$(curl -s -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name":"IT Operations Demo"}' | jq -r '.id')

# 2. 上傳 CSV（也支援 .xlsx、.json）
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/upload/tickets" \
  -F "file=@demo_data/tickets/sample_incidents.csv"

# 預期回應
# {
#   "raw_count": 22,
#   "cleaned_count": 22,
#   "failed_count": 0,
#   "errors": []
# }
```

## 在 PostgreSQL 中驗證資料

```sql
-- 確認 raw_records 原始資料
SELECT id, source_file, raw_json->>'ticket_id' AS ticket_id, created_at
FROM raw_records
WHERE project_id = '<your-project-id>'
ORDER BY created_at
LIMIT 5;

-- 確認 cleaned_records 清洗結果
SELECT ticket_id, occurred_at, system, module, status, priority
FROM cleaned_records
WHERE project_id = '<your-project-id>'
ORDER BY occurred_at
LIMIT 10;

-- 統計各 priority 分佈
SELECT priority, COUNT(*) FROM cleaned_records
WHERE project_id = '<your-project-id>'
GROUP BY priority;
```

## 事件分析 Agent

匯入工單後，呼叫多工具事件分析 agent。它會串接 4 個 LLM 驅動的工具，
結果寫入 PostgreSQL，同時留下完整稽核紀錄。

```bash
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/analyze/incidents"

# 預期回應
# {
#   "agent_run_id": "9c8f3b1a-0f4c-4f1d-9b65-1c0c3a86a512",
#   "status": "success",
#   "summary": {
#     "records_analyzed": 20,
#     "needs_review": 3,
#     "insights_created": 5,
#     "action_items_created": 4
#   }
# }
```

**4 個工具（依序執行）**

| # | 工具 | 寫入 |
|---|---|---|
| 1 | `classify_incidents` — 將每筆 ticket 分類 | （與工具 2 合併寫入 `incident_analysis`） |
| 2 | `analyze_severity` — 嚴重度 1-5、情緒、信心、`needs_review` 旗標 | `incident_analysis` |
| 3 | `generate_insights` — 專案層級的模式與建議 | `insights` |
| 4 | `create_action_items` — 由 insights 衍生的後續行動 | `action_items`（全部 `status="open"`） |

每個工具向 LLM 索取結構化 JSON 並以 Pydantic 驗證；驗證失敗會被記錄而非
靜默吞掉。端點是 idempotent 的 — 重跑時會略過已在 `incident_analysis` 內的紀錄。
完整 API 參考：[docs/API.zh-TW.md](docs/API.zh-TW.md#事件分析-agent)。

## 前端（React）

React UI 是跑完整 demo 流程的推薦方式，鏡像了後端 API surface，
也就是面試官或利害關係人實際會看到的東西。

### 頁面

| 頁面 | 用途 |
|---|---|
| 專案設定 | 建立或選擇目前專案 |
| 文件上傳 | 上傳 PDF（RAG 語料） |
| 事件上傳 | 上傳事件 ticket（CSV / Excel / JSON → ETL → cleaned_records） |
| 知識庫問答 | RAG 問答 — 回答 + 引用（filename、chunk index、snippet） |
| 事件分析 | 一鍵「執行事件分析」— 觸發 4-tool agent 並顯示摘要 |
| 分析儀表板 | 工單總數、重點洞察、未處理行動項目 |
| Agent 執行紀錄 | 瀏覽 `agent_runs`；選一筆 drill 進它的 `tool_calls`（每個工具的 input / output / 錯誤 / 延遲） |

### 用 Docker 跑（demo 推薦）
```bash
docker compose up --build
# UI:      http://localhost:8501
# Backend: http://localhost:8000
```
`BACKEND_URL=http://backend:8000` 由 `docker-compose.yml` 注入，React 容器透過
compose 網路連到 backend（Vite proxy `/api` → backend）。

### 本機跑（無 Docker）
```bash
# 先啟動 backend（參考上方「本機開發」），再：
cd frontend
npm install
npm run dev
# UI: http://localhost:5173
```

Vite dev server 會透過 `/api` proxy 轉發到 `http://localhost:8000`，
不需額外設定 `BACKEND_URL`。

## Demo Flow（端到端，mock 模式）

```bash
# 1. 建立 project
PROJECT_ID=$(curl -s -X POST http://localhost:8000/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name":"IT Operations Demo"}' | jq -r '.id')

# 2. 上傳 SOP PDF（RAG 語料）
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/upload/documents" \
  -F "file=@demo_data/documents/your_manual.pdf"

# 3. 上傳事件 ticket（CSV / Excel / JSON）
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/upload/tickets" \
  -F "file=@demo_data/tickets/sample_incidents.csv"

# 4. 跑事件分析 agent
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/analyze/incidents"

# 5. 向 SOP 語料問問題
curl -X POST "http://localhost:8000/projects/${PROJECT_ID}/chat" \
  -H "Content-Type: application/json" \
  -d '{"question":"How do I respond to a Docker volume outage?","top_k":5}'
```

## 可觀測性與除錯

每次 agent 呼叫都會寫一筆 `agent_runs` + 每個 tool call 一筆 `tool_calls`。
這兩張表是主要的除錯面 — 沒有其他 log 可對照。

```sql
-- 最近 10 次 agent run（chat + analysis）
SELECT id, task_type, model_name, status, latency_ms, created_at
FROM agent_runs
WHERE project_id = '<your-project-id>'
ORDER BY created_at DESC
LIMIT 10;

-- 某次 analysis run 的所有 tool calls（依執行順序）
SELECT tool_name, latency_ms, error_message, output_json
FROM tool_calls
WHERE agent_run_id = '<回應中的 agent_run_id>'
ORDER BY created_at;

-- 找出有 tool 驗證失敗的 run
SELECT ar.id, ar.task_type, ar.status, tc.tool_name, tc.error_message
FROM agent_runs ar
JOIN tool_calls tc ON tc.agent_run_id = ar.id
WHERE tc.error_message IS NOT NULL
ORDER BY ar.created_at DESC;
```

碰到狀況時的判讀：
- **`agent_runs.status = "partial"`** → 至少有一個 tool 的 LLM 輸出沒通過 Pydantic
  驗證。看那個 tool 的 `tool_calls.error_message` 看 parse 錯誤，再看
  `tool_calls.input_json` 看送出去的內容。Orchestrator 不會 retry —
  partial run 會保留其他 tool 已產出的結果。
- **`agent_runs.status = "error"`** → Orchestrator 層級失敗（LLM provider 連不上、
  DB 錯誤等）。`agent_runs.error_message` 就是 exception 訊息。
- **分類 / 嚴重度看起來怪** → `classify_incidents` 與 `analyze_severity` 的
  `tool_calls.output_json` 有彙總；join `incident_analysis` 鑽下去看單筆。
- **延遲高** → 比較 `tool_calls.latency_ms` 找出慢的 step（用真實 LLM 時通常是
  per-record 的工具）。

## Troubleshooting

| 症狀 | 可能原因 | 解法 |
|---|---|---|
| `make up` 跳 `.env 不存在` | 首次設定沒做 | `cp .env.example .env` 後重試 |
| port 5432 / 8000 / 8501 衝突 | 本機已有 Postgres / 另一個 dev server 佔用 | 停掉那個 process，或改 `docker-compose.yml` host 側的 port mapping（例 `"5433:5432"`） |
| `backend` 容器一直重啟 | Schema migration 失敗（postgres 還沒真的 ready，或舊 schema 卡 volume） | `make logs-backend` 看 traceback；如 schema 有變，`make clean` 砍 volume（破壞性） |
| Frontend 顯示 `無法連線到後端 (http://backend:8000)` | Backend 容器 down 或還沒 healthy | `make ps` 看狀態；`make logs-backend` 找原因 |
| Chat / analysis 跳 `OPENAI_API_KEY` 錯 | `.env` 設了 `LLM_PROVIDER=openai` 但 key 空 | 填 `OPENAI_API_KEY` 或改回 `LLM_PROVIDER=mock` |
| Ollama 模式 backend 連不到服務 | `ollama` service 不健康、模型尚未下載，或 `DOCKER_OLLAMA_BASE_URL` 指到錯的 endpoint | 先看 `docker compose ps ollama`；再執行 `docker compose exec ollama ollama pull qwen2.5:7b-instruct`，或改 `DOCKER_OLLAMA_BASE_URL` 指到外部 endpoint |
| `make test-local` 跳 `ModuleNotFoundError` | 本機 `.venv` 不存在或舊 | `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` |
| 重啟後 Postgres / pgvector 資料神祕消失 | 有人下了 `docker compose down -v` 或 `make clean` | volume 是被刻意刪掉的 — 重新匯入。下次用 `make down`（不帶 `-v`）保留資料 |
| Windows / WSL2 bind mount 路徑問題 | Volume mount 用 Linux 路徑 | 所有指令都在 WSL2 內執行，不要用 PowerShell |

## 實作進度

- [x] 步驟 1：專案骨架、health 端點、Docker Compose
- [x] 步驟 2-pre：PostgreSQL 資料模型（10 張資料表、ORM 模型、Pydantic 結構、SQL 遷移）
- [x] 步驟 2：PDF 匯入 → RAG 流程（`POST /projects/{id}/upload/documents`）
- [x] 步驟 2b：嵌入 + PostgreSQL + pgvector 向量儲存與搜尋（`GET /projects/{id}/search`）
- [x] 步驟 3：事件 ETL（`POST /projects/{id}/upload/tickets` — CSV / Excel / JSON → PostgreSQL）
- [x] Prompt 7：RAG chat API（`POST /projects/{id}/chat` — retrieval → LLM → 回答 + 引用）
- [x] Prompt 7：可觀測性 — 每次 chat 請求都寫 `agent_runs` + `tool_calls`
- [x] 步驟 4：事件分析 agent（`POST /projects/{id}/analyze/incidents` — 4 個工具、結構化 JSON、Pydantic 驗證、完整 agent_runs / tool_calls 追溯）
- [x] 步驟 5：Dashboard 與 Observability 唯讀 API（`GET /projects/{id}/dashboard`、`/agent-runs`、`/agent-runs/{id}/tool-calls`）
- [x] 步驟 6：React 7 頁面 demo UI（繁體中文，Vite + TypeScript + Tailwind CSS）
- [x] 本地模型 provider（Ollama）— 原生 HTTP LLM provider，供私有／地端部署
- [ ] 步驟 8+：本地 embedding provider、其他 agent 工具
