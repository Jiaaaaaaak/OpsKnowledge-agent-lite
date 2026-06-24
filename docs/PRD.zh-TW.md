# 產品需求文件 — OpsKnowledge Agent Lite

[English](PRD.md) | 繁體中文

## 問題

IT／維運團隊需管理大量技術文件（手冊、SOP），但面臨以下困境：

1. 知識被鎖在 PDF 裡 — 難以搜尋與查詢。
2. 缺乏附引用來源追溯的 AI 問答功能。
3. AI 決策缺乏可稽核性 — 難以除錯或信任其輸出。

## 目標使用者

| 使用者 | 角色 |
|---|---|
| IT 維運工程師 | 上傳 SOP、透過 RAG 問答查詢知識庫 |
| （Demo）AI/資料工程面試官 | 評估系統設計與程式碼品質 |

## MVP 範圍

### 包含項目

- [x] 上傳 PDF 文件 → 解析 → 分塊 → 嵌入 → 存入 PostgreSQL + pgvector
- [x] 對文件進行 hybrid search / 附引用來源的 RAG 問答
- [x] 將每次 AI 呼叫記錄至 PostgreSQL（模型、tokens、延遲、結果）
- [x] React 引導式流程 UI：Upload → 確認 → Chat → 檢視
- [x] Docker Compose 部署（PostgreSQL、PostgreSQL + pgvector、backend、frontend）

### 不在範圍內（此 POC）

- 使用者驗證 / 多租戶存取控制
- AI 回應的即時串流
- 正式等級向量資料庫（Pinecone、Weaviate、pgvector）
- Fine-tuning 或自訂模型
- 自動告警 / PagerDuty 整合
- 行動裝置 UI

## 成功標準

1. `/health` 端點在資料庫連線正常時回傳 `{"status": "ok"}`。
2. PDF 可被上傳、分塊，並透過語意搜尋查詢。
3. RAG 問答能回傳附引用來源、可追溯至原始 chunk 的答案。
4. 每次 AI 呼叫皆記錄模型名稱、tokens 與延遲。
5. Demo 可於 10 分鐘內完成端對端走查。

## 系統架構與技術棧

OpsKnowledge Agent Lite 是一套容器化的全端應用。React 單頁應用呼叫 FastAPI 後端，後端將所有資料持久化至 PostgreSQL（透過 pgvector 擴充支援語意搜尋），並將語言／嵌入運算交由可插拔的 AI provider 處理。

| 層級 | 技術 |
|---|---|
| 前端 | React 18、TypeScript、Vite、React Router、Tailwind CSS、lucide-react、axios |
| 前端測試 | Vitest、Testing Library、jsdom |
| 後端 | FastAPI、Uvicorn、SQLAlchemy、Pydantic / pydantic-settings |
| 後端測試 | pytest |
| 資料庫 | PostgreSQL 16 + pgvector（`vector(1024)`） |
| LLM／嵌入 | 可插拔 provider：`mock` / `ollama` / `openai`；地端預設＝Ollama（`qwen2.5:7b-instruct`）作為 LLM ＋ mock 嵌入（維度 1024） |
| 封裝／部署 | Docker Compose（postgres、ollama、backend、frontend） |
| 可觀測性 | `agent_runs` ＋ `tool_calls` 稽核紀錄 |

- **服務埠（host → container）：** 前端 `8501`、後端 `8000`、PostgreSQL `5432`、Ollama `11434`。
- **後端 API 範圍：** `health`、`projects`、`documents`、`uploads`、`chat`、`dashboard`（workflow-status、agent-runs、tool-calls）。
- **AI provider 模型：** `EMBEDDING_PROVIDER` 與 `LLM_PROVIDER` 可各自獨立選擇 `mock`、`ollama` 或 `openai`。內建預設完全離線（`mock`）；專案附帶的 `.env.example` 則以 Ollama 作 LLM、mock 作嵌入，呈現私有／地端風格的展示。

## 系統架構圖

```text
┌──────────────────────────────────────────────────────────┐
│ 前端 — React + Vite   (:8501)                            │
│ 知識庫問答流程 | Agent 執行紀錄 | 系統狀態               │
└──────────────────────────────────────────────────────────┘
                             │  REST API（Axios，/api 代理）
                             ▼
┌──────────────────────────────────────────────────────────┐
│ 後端 — FastAPI   (:8000)                                 │
│ 路由 ： /health /projects /documents /uploads            │
│         /chat /dashboard                                 │
│ 服務 ： document · vector_store · chat · llm             │
└──────────────────────────────────────────────────────────┘
                         │                                         │
                         │ SQLAlchemy                               provider：mock/Ollama/OpenAI
                         ▼                                         ▼
      ┌─────────────────────────────────────┐      ┌─────────────────────────────────┐
      │ PostgreSQL 16 + pgvector  (:5432)   │      │ AI Provider（可插拔）           │
      │ vector(1024) 語意檢索                │      │ 嵌入 + 生成                     │
      │ 稽核：agent_runs / tool_calls       │      │ mock / Ollama(:11434) / OpenAI  │
      └─────────────────────────────────────┘      └─────────────────────────────────┘
```

## 用戶流程

產品以單一引導式、分步驟的工作流程組織。每個步驟會依專案的 `workflow-status` 自動定位，使用者也可返回任一先前可進入的步驟。

### 知識庫問答流程

```mermaid
flowchart TD
    P([選擇 / 建立專案]) --> UP["上傳 PDF 文件"]
    UP -->|"分塊 ＋ 嵌入 → pgvector"| IDX["知識庫就緒"]
    IDX --> ASK["RAG 對話<br/>附引用來源的回答"]
    ASK --> OBS["Agent 執行紀錄 / Tool Calls<br/>檢索可觀測性"]
```
