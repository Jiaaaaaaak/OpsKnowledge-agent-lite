# Demo 腳本 — OpsKnowledge Agent Lite

[English](DEMO_SCRIPT.md) | 繁體中文

Demo 總時長：**約 3 分鐘**（精簡版）／ 約 5 分鐘（完整 walkthrough）。

---

## 事前準備（Demo 前約 1 分鐘，不計入 demo 時間）

1. `cp .env.example .env` — 預設 Ollama LLM + mock embedding。
2. `docker compose up --build -d` — 等到 `opsknowledge_backend` 顯示
   `Uvicorn running on http://0.0.0.0:8000`。
3. `docker compose exec ollama ollama pull qwen2.5:7b-instruct` — 下載地端模型。
4. Smoke check：`curl http://localhost:8000/health` → `{"db":"connected","vector":"connected"}`。
5. 在瀏覽器開啟 `http://localhost:8501`。
6. 準備好：
   - `demo_data/documents/` 內任一份 PDF（IT SOP / 操作手冊）

---

## 3 分鐘 demo 腳本

### 場景 1 · 專案設定（15 秒）

> 「先建立一個 project — 之後所有 upload 與 chat 都會 scoped 在這個 project 下。」

- Sidebar → **專案設定**
- 建立新專案：名稱 `IT 維運示範專案` → **建立**
- Sidebar 上的「目前專案」chip 會立刻更新。

### 場景 2 · 上傳 PDF 文件（30 秒）

> 「SOP PDF 進場做 RAG。每一頁都會被切塊、嵌入，並存入 PostgreSQL + pgvector。」

- Sidebar → **知識庫問答流程**
- 上傳 `demo_data/documents/<sop>.pdf`
  → 成功 card 顯示 `chunk_count` 與 `page_count`。

> 重點訴求：「PDF 走 chunk → embed → PostgreSQL + pgvector。一個 upload 按鈕，
> 完整索引完成，可立即做語意搜尋。」

### 場景 3 · 知識庫問答（RAG）（40 秒）

> 「現在可以針對 SOP 問問題。模型只能用 retrieved chunk 回答 — 如果 PDF 沒寫，
> 它會拒答而不是瞎掰。」

- 流程頁面中，chat 步驟變為 active。
- 問：`Docker volume 重啟後消失，我該檢查哪些設定？`
- 回答呈現，接著每段引用可展開（filename · chunk_index · snippet）。

> 重點訴求：「每次 chat 都會寫一筆 `agent_runs` 與一筆向量檢索的 `tool_calls`，
> 完全可稽核。」

### 場景 4 · Agent 執行紀錄 / 可觀測性（30 秒）

> 「這是怎麼證明 agent 實際幹了什麼。每次 run 都可查詢。」

- Sidebar → **Agent 執行紀錄**
- 上方表格列出所有 `agent_runs`（chat runs）。
- 選最近一次 `rag_chat` run。
- 展示 drill-down：status、latency、model；展開 `vector_search` tool call
  → `input_json` / `output_json` / latency。

> 收尾：「Black-box LLM agent 變成可事後 debug 的系統：挑一次 run、看確切的
> retrieval input 與 output。這就是可以上線的長相。」

### 場景 5 · 系統狀態（15 秒）

> 「快速健康檢查 — 系統狀態頁顯示所有後端服務連線。」

- Sidebar → **系統狀態**
- 展示 DB、vector、API 健康指標。

### 場景 6 · Provider 可切換性（15 秒）

> 「最後一點 — LLM 與 embedding provider 完全可插拔。」

- 展示 `.env` 檔：`LLM_PROVIDER=ollama`、`EMBEDDING_PROVIDER=mock`。
- 說明：只改 `.env` 即可切到 `openai` 或 `mock`，不需改任何程式碼。

---

## 重點訴求（補問時可用）

- **地端優先的 LLMProvider 抽象** — 面試預設 `LLM_PROVIDER=ollama` 搭配
  `EMBEDDING_PROVIDER=mock`。同一套 UI 仍可只改 `.env` 切到 hosted OpenAI 或完全 mock。
- **LLM 邊界的 Pydantic 驗證** — 每筆結構化輸出都被驗證；失敗會被記到
  `tool_calls.error_message`，不會被靜默吞掉（Rule 12）。
- **workflow-status 讀寫分離** — workflow-status endpoint 從不呼叫 LLM。快速、確定性、
  可安全自動刷新。
- **Provider 可切換性** — `mock`、`ollama`、`openai` — 改一行 `.env`，不改程式。

---

## Live demo 失敗的 backup plan

| 失敗 | Fallback |
|---|---|
| PostgreSQL + pgvector 掛掉 | 跳過場景 3（Chat），展示 upload 與 observability 頁面 |
| Ollama 模型尚未下載 | 執行 `docker compose exec ollama ollama pull qwen2.5:7b-instruct`；若需立刻 fallback，改 `LLM_PROVIDER=mock` |
| 自帶 PDF 上傳失敗 | 改用預先放好在 `demo_data/documents/` 的公領域 PDF |
| Demo 機器離線 | 模型已事先下載時，Ollama + mock embedding 可全地端執行 |
