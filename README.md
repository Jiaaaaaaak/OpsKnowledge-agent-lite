# OpsKnowledge Agent Lite

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
# 編輯 .env — 設定 OPENAI_API_KEY

# 2. 啟動所有服務
docker compose up --build

# 3. 驗證
curl http://localhost:8000/health
# 於瀏覽器開啟 http://localhost:8501
```

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
- [x] 步驟 3：事件 ETL（`POST /projects/{id}/upload/tickets` — CSV／Excel／JSON → PostgreSQL）
- [ ] 步驟 4：AI 分析工具（分類、評分、洞察）
- [ ] 步驟 5：可觀測性層（AI 執行日誌）
- [ ] 步驟 6：Streamlit 儀表板（完整版）
- [ ] 步驟 7：測試與最終文件
