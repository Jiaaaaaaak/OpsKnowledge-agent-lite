# Demo 腳本 — OpsKnowledge Agent Lite

[English](DEMO_SCRIPT.md) | 繁體中文

Demo 總時長：**約 3 分鐘**（精簡版）／ 約 8 分鐘（完整 walkthrough）。

---

## 事前準備（Demo 前約 1 分鐘，不計入 demo 時間）

1. `cp .env.example .env` — 預設 mock 模式（不需 API key）。
2. `docker compose up --build` — 等到 `opsknowledge_backend` 顯示
   `Uvicorn running on http://0.0.0.0:8000`。
3. Smoke check：`curl http://localhost:8000/health` → `{"db":"connected","chroma":"connected"}`。
4. 在瀏覽器開啟 `http://localhost:8501`。
5. 準備好：
   - `demo_data/documents/` 內任一份 PDF（IT SOP / 操作手冊）
   - `demo_data/tickets/sample_incidents.csv`（repo 內附）

---

## 3 分鐘 demo 腳本

### 場景 1 · 專案設定（15 秒）

> 「先建立一個 project — 之後所有 upload、chat、analysis 都會 scoped 在這個 project 下。」

- Sidebar → **專案設定**
- 建立新專案：名稱 `IT 維運示範專案` → **建立**
- Sidebar 上的「目前專案」chip 會立刻更新。

### 場景 2 · 上傳 PDF + 工單（35 秒）

> 「兩種資料進場：RAG 用的 SOP PDF、分析用的事件工單。」

- Sidebar → **資料上傳**
- **📄 技術文件 PDF** tab → 上傳 `demo_data/documents/<sop>.pdf` → **上傳技術文件 PDF**
  → 成功 card 顯示 `chunk_count` 與 `page_count`。
- **🎫 事件紀錄檔** tab → 上傳 `sample_incidents.csv` → **上傳事件紀錄檔**
  → metric 列顯示 `原始列數`、`清理後筆數`、`失敗筆數`。

> 重點訴求：「PDF 走 chunk → embed → ChromaDB。Ticket 走欄位同義詞對應正規化
> 進 `cleaned_records`。一個 upload 按鈕背後是兩條獨立 pipeline。」

### 場景 3 · 知識庫問答（RAG）（30 秒）

> 「現在可以針對 SOP 問問題。模型只能用 retrieved chunk 回答 — 如果 PDF 沒寫，
> 它會拒答而不是瞎掰。」

- Sidebar → **知識庫問答**
- 問：`Docker volume 重啟後消失，我該檢查哪些設定？`
- 回答呈現，接著每段引用可展開（filename · chunk_index · snippet）。

> 重點訴求：「每次 chat 都會寫一筆 `agent_runs` 與一筆向量檢索的 `tool_calls`，
> 完全可稽核。」

### 場景 4 · 事件分析 Agent（40 秒）

> 「這就是 agent。一個按鈕觸發 4-tool pipeline：分類、評分、產生洞察、產生
> 行動項目 — 全程結構化 JSON 輸出 + Pydantic 驗證。」

- Sidebar → **事件分析** → **▶️ 執行事件分析**
- 4 個 metric 出現：`已分析筆數`、`需要人工複核`、`產生洞察數`、`行動項目數`。

> 重點訴求：「`需要人工複核` 標記的是 LLM 信心 < 0.65 的工單 — 那是 human-in-the-loop
> 工作佇列。不是裝飾，是運維的入口。」

### 場景 5 · 儀表板（30 秒）

> 「唯讀彙總，純 SQL、不打 LLM — ops lead 看的就是這個。」

- Sidebar → **儀表板**
- 走過：工單總數、需要人工複核、類別長條圖、嚴重程度長條圖、
  重點洞察（可展開）、未處理行動項目表、最近 agent 執行紀錄。

> 重點訴求：「同一張 `agent_runs` 餵 Chat 可觀測性與這頁的『最近執行紀錄』 —
> 一份 log 兩種視角。」

### 場景 6 · Agent 執行紀錄 / 可觀測性（30 秒）

> 「最後是怎麼證明 agent 實際幹了什麼。每次 run 都可查詢。」

- Sidebar → **Agent 執行紀錄**
- 上方表格列出所有 `agent_runs`（chat + analyze）。
- 選最近一次 `analyze_incidents` run。
- 展示 drill-down：status、latency、model；再依序展開 4 個 tool call
  → `input_json` / `output_json` / 各自 latency / 有錯就顯示 `error_message`。

> 收尾：「Black-box LLM agent 變成可事後 debug 的系統：挑一次 run、看每個 tool
> 的確切 input 與 output、找出哪個驗證失敗。這就是可以上線的長相。」

---

## 重點訴求（補問時可用）

- **LLMProvider 抽象** — `LLM_PROVIDER=openai | ollama | mock` 切換後端，
  零應用程式碼變動。同一套 UI 可以打 hosted API、本地 Ollama、或完全離線的 mock。
- **Idempotent agent run** — 重新呼叫 `/analyze/incidents` 只會處理還沒在
  `incident_analysis` 內的紀錄，從不刪舊。
- **LLM 邊界的 Pydantic 驗證** — 每筆結構化輸出都被驗證；失敗會被記到
  `tool_calls.error_message`，不會被靜默吞掉（Rule 12）。
- **Schema 穩定** — Dashboard 與 UI 兩個階段加入時，**零** 新增 column / table；
  全部是既有 10 張表上的 read view。
- **Dashboard 讀寫分離** — Dashboard endpoint 從不呼叫 LLM。快速、確定性、
  可安全自動刷新。

---

## Live demo 失敗的 backup plan

| 失敗 | Fallback |
|---|---|
| ChromaDB 掛掉 | 跳過場景 3（Chat），其他流程照跑 |
| OpenAI 額度用完 | 預設就是 mock 模式 — 沒風險 |
| 自帶 PDF 上傳失敗 | 改用預先放好在 `demo_data/documents/` 的公領域 PDF |
| Demo 機器離線 | Mock 模式整個 stack 都可離線 — 沒外部依賴 |
