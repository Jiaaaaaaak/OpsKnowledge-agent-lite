# OpsKnowledge Agent Lite

[English](README.md) | 繁體中文

一套面向 IT 維運與系統整合情境的企業級 AI + 資料工程概念驗證（POC）專案。

## 功能概覽

| 能力 | 說明 |
|---|---|
| 文件 RAG | 上傳 PDF 手冊／SOP → 切塊、嵌入、透過 ChromaDB 檢索 |
| 事件 ETL | 上傳 CSV／Excel／JSON 工單 → 正規化、清洗、寫入 PostgreSQL |
| AI 分析 | 事件分類、嚴重度評分、產生洞察與行動項目 |
| 可觀測性 | 每一次 AI 工具呼叫皆記錄至 PostgreSQL，便於稽核 |
| 儀表板 | 以 Streamlit 提供上傳、問答、分析與代理日誌介面 |

## 技術堆疊

- **後端**：Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2
- **資料庫**：PostgreSQL 16
- **向量資料庫**：ChromaDB
- **AI**：相容 OpenAI 介面（可切換至 Ollama）
- **前端**：Streamlit
- **基礎設施**：Docker Compose

## 快速開始

```bash
# 1. 取得專案並設定環境變數
cp .env.example .env
# .env 預設為 mock 模式（EMBEDDING_PROVIDER=mock、LLM_PROVIDER=mock），
# 不需要任何 API key。要使用真實模型請參考下方「Provider 模式」。

# 2. 啟動所有服務
docker compose up --build

# 3. 驗證
curl http://localhost:8000/health
# 於瀏覽器開啟 http://localhost:8501
```

### Provider 模式

| 模式 | 環境變數 | API key | 說明 |
|---|---|---|---|
| **mock**（預設） | `EMBEDDING_PROVIDER=mock`、`LLM_PROVIDER=mock` | 不需要 — `OPENAI_API_KEY` 可留空 | 確定性本地 provider；可完全離線跑完整流程 |
| **openai** | `EMBEDDING_PROVIDER=openai`、`LLM_PROVIDER=openai` | 需要有效的 `OPENAI_API_KEY` | 呼叫 OpenAI 相容 API 取得真實嵌入與回答 |
| **ollama**（LLM） | `LLM_PROVIDER=ollama`（搭配 `EMBEDDING_PROVIDER=openai` 或 `mock`） | LLM 不需 API key | 呼叫本機 Ollama 伺服器取得回答 — 供私有／地端部署使用 |

> **雲端 API vs 本地模型。** `openai` provider 用於**快速 POC** — 設定成本最低、
> 開箱即用的品質佳。`ollama` provider 則為**私有／地端部署**預備，讓 LLM 在客戶
> 網路內執行、資料不離開主機。切換只需修改一行 `.env`（`LLM_PROVIDER`），不需更動
> 任何應用程式碼。詳見下方[本地模型 provider（Ollama）](#本地模型-providerollama)。

### 主機名稱：Docker vs 本機

應用程式透過 `POSTGRES_HOST` / `CHROMA_HOST` 連線到 PostgreSQL 與 ChromaDB
（沒有 `DATABASE_URL`，詳見 `backend/app/core/config.py`）。

- **Docker Compose** 會將其覆寫為服務名稱 `postgres` 與 `chromadb`
  （定義於 `docker-compose.yml`），因此容器網路不需要修改 `.env`。
- **本機（不使用 Docker）** 使用 `.env.example` 預設的 `localhost`。

## 本地模型 Provider（Ollama）

針對私有／地端情境，LLM 可透過 [Ollama](https://ollama.com) 完全在本地硬體上執行，
不需 OpenAI 帳號、資料不離開主機。`OllamaLLMProvider` 直接呼叫 Ollama 原生 HTTP
API（`/api/chat`）。

```bash
# 1. 安裝並啟動 Ollama，再下載模型
ollama serve                       # 在 :11434 啟動本地伺服器
ollama pull qwen2.5:7b-instruct

# 2. 讓應用程式指向 Ollama（.env）
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct
# embedding 與 LLM 獨立 — 可維持 EMBEDDING_PROVIDER=mock（離線）或 =openai
EMBEDDING_PROVIDER=mock
```

這是唯一需要的改動 — 不需更動任何應用程式碼。若 Ollama 伺服器無法連線，`/chat`
會以明確錯誤回應（例如 *「無法連線到 Ollama … 請確認 Ollama 服務已啟動」*），
而不是卡住或回傳捏造的答案。

> **範圍：** 這個 provider 只涵蓋 **LLM**。embedding 仍由 `EMBEDDING_PROVIDER`
> （`openai` / `mock`）選擇。要做到完全地端，還需要一個本地 embedding provider —
> `EmbeddingProvider` 介面支援以相同方式新增。Ollama **不是一般展示的必要條件**：
> 預設的 mock 模式即可在零外部相依的情況下跑完整個流程。

## 本機開發（不使用 Docker）

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 另行啟動 PostgreSQL 與 ChromaDB 後，執行：
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
psql -h localhost -U opsuser -d opsknowledge -f migrations/001_initial_schema.sql
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
  frontend/          Streamlit UI
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

> **嵌入：** 上傳時每個 chunk 會被嵌入並索引至 ChromaDB。mock 模式（預設）不需要
> API key。openai 模式則需要 `.env` 內設定有效的 `OPENAI_API_KEY`；未設定時上傳會以
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

## 實作進度

- [x] 步驟 1：專案骨架、health 端點、Docker Compose
- [x] 步驟 2-pre：PostgreSQL 資料模型（10 張資料表、ORM 模型、Pydantic 結構、SQL 遷移）
- [x] 步驟 2：PDF 匯入 → RAG 流程（`POST /projects/{id}/upload/documents`）
- [x] 步驟 2b：嵌入 + ChromaDB 向量儲存與搜尋（`GET /projects/{id}/search`）
- [x] 步驟 3：事件 ETL（`POST /projects/{id}/upload/tickets` — CSV／Excel／JSON → PostgreSQL）
- [ ] 步驟 4：AI 分析工具（分類、評分、洞察）
- [ ] 步驟 5：可觀測性層（AI 執行日誌）
- [ ] 步驟 6：Streamlit 儀表板（完整版）
- [ ] 步驟 7：測試與最終文件
- [x] 本地模型 provider（Ollama）— 原生 HTTP LLM provider，供私有／地端部署
