# OpsWeave 重寫設計

[English](2026-06-28-opsweave-rewrite-design.md) | 繁體中文

## 1. 目標

將本儲存庫重寫為 **OpsWeave**：一套自架、單一組織使用的 AI 營運平台。
Manager Agent 負責協調獨立 Specialist Agent，使用者可透過 WebChat 與外部
聊天渠道交辦工作，管理員則透過 React Control Plane 管理 Agent、任務、
知識、排程、使用者、整合與稽核資料。

CoStaff 僅作為產品與流程參考。OpsWeave 採乾淨重寫，不複製 CoStaff
原始碼或資產。既有 OpsKnowledge 資料不需遷移；其 RAG 能力保留為內建
Knowledge Agent。

## 2. 第一版範圍

### 包含

- Manager、Knowledge、Coding、Business Analysis 四個 Agent。
- 每個 Agent 獨立容器，透過 A2A 溝通。
- MCP 工具與逐 Agent 白名單。
- WebChat、Telegram、Discord、LINE。
- Dashboard、Chat、Projects、Tasks、Knowledge、Agents、Automation、
  Diary、Channels、Integrations、Users、Runs and Logs、Settings。
- Epic、Story、Task、依賴、Comment、Attempt、Event。
- Reminder 與 Recurring Work。
- API 與 Skill Registry。
- PostgreSQL、pgvector、Redis、Dramatiq Worker。
- Gemini、OpenAI-compatible、Ollama，以及逐 Agent 模型設定。
- 單機 Docker Compose 部署。

### 不包含

- 舊 OpsKnowledge 資料遷移。
- 多租戶、Multi-Core、商業 License 限制。
- Kubernetes、多主機調度。
- ERP／CRM 等企業服務的啟停控制。

## 3. 架構

FastAPI Control Plane 負責認證、身份核准、會話、專案、任務、Agent
登記、設定與管理 API。HTTP request 不直接執行耗時 Agent 工作；所有工作
先持久化，再交給 Redis＋Dramatiq。

PostgreSQL 是業務狀態唯一真相，Redis 僅負責佇列與短期協調。Worker 負責
派工、重試、排程、依賴釋放、callback 與通知。Worker 使用 lease、
heartbeat、資料庫鎖與 idempotency key，確保程序中斷後可以安全恢復。

四個 Agent 分工如下：

- Manager：分類、規劃、取得確認與派工，不執行專業工作。
- Knowledge：文件索引、全文與向量混合檢索、rerank、引用回答。
- Coding：在隔離 workspace 內執行程式與檔案工作。
- Business Analysis：資料解讀、圖表、報告與商業摘要。

Agent 透過版本化 manifest 登記 A2A endpoint 與能力。Manifest 必須通過
JSON Schema 驗證；Control Plane 不以寫死的容器名稱發現 Agent。

Core MCP 提供 progress、task comment、artifact publish、file list 與
notification。每個 Agent 都透過 ToolGrant 取得最小權限。Manager 只看得到
編排工具與 A2A Agent，不繼承 Specialist 的內部工具。

四個 Channel Adapter 共用同一份 contract：正規化訊息與附件、解析 opaque
identity、連接 Conversation、接收非同步結果與 artifact。任一外部 Channel
缺少 token 時可獨立停用，不影響 WebChat 或 Control Plane 啟動。

## 4. 資料模型

### Identity 與 Chat

- `User`
- `ChannelIdentity`
- `Conversation`
- `Message`

平台原始 ID 不作為公開 ID。系統使用 HMAC 派生的 opaque identity；需要反查
的 routing value 加密保存。

### Agent Registry

- `AgentDefinition`
- `AgentEndpoint`
- `ModelConfig`
- `ToolGrant`

### Project Work

- `Epic`
- `Story`
- `Task`
- `TaskDependency`
- `TaskComment`
- `TaskAttempt`
- `TaskEvent`
- `Artifact`

### Knowledge

- `KnowledgeBase`
- `Document`
- `DocumentChunk`
- `Citation`

`DocumentChunk` 同時保存全文檢索欄位、檢索 metadata 與 pgvector embedding。

### Automation 與 Integration

- `Reminder`
- `RecurringWork`
- `RecurringWorkRun`
- `Diary`
- `SkillConfig`
- `ApiConfig`

## 5. 任務狀態

主要流程：

```text
backlog -> queued -> running -> succeeded
```

其他狀態：

- `retry_scheduled`：可重試失敗，等待 backoff。
- `failed`：不可重試或已耗盡重試。
- `cancelled`：尚未完成前由使用者或管理員取消。

依賴未完成的任務停在 `backlog`。多重依賴使用 `TaskDependency` 外鍵表示。
全部上游成功後，系統以 transaction 將下游轉成 `queued`。上游失敗或取消時，
下游維持 blocked，UI 提供重試、更換依賴、跳過或取消。

每次狀態變更都寫入 immutable `TaskEvent`；每次真正執行或重試建立新的
`TaskAttempt`，不覆蓋舊錯誤與 metrics。

## 6. 派工與 Callback

1. WebChat 或 Channel Adapter 傳入正規化訊息。
2. Manager 分類為對話、立即工作、Reminder、Recurring Work 或 Project Work。
3. 需要確認的實質工作先顯示計畫。
4. 核准後原子建立單一 Task 或依賴圖。
5. Dispatcher 排入第一個可執行 Task。
6. Worker 使用 task-scoped session 經 A2A 呼叫 Agent。
7. Progress 寫入 TaskEvent 並即時送往 UI。
8. Agent 回傳結構化 Result Envelope。
9. 系統驗證 artifact，保存 Attempt 結果。
10. Callback Worker 將 system callback 注入原 Conversation，由 Manager 產生
    使用者語言摘要。
11. Notifier 將文字與附件送回原 Channel。
12. 成功完成後釋放下游依賴。

Result Envelope 包含 `status`、`summary`、`artifacts`、`error_code`、
安全的 `error_message`、metrics 與選填的結構化資料。

## 7. 前端

React UI 採 Modern Bento。固定精簡頂欄顯示整體健康、PostgreSQL、Vector、
模型與執行中任務；點擊後展開服務詳情，不保留獨立 System Status 頁。

左側導覽分組：

- Workspace：Dashboard、Chat、Projects、Tasks、Knowledge。
- AI Team：Agents、Automation、Diary。
- Operations：Channels、Integrations、Users、Runs and Logs、Settings。

Dashboard 保留四個區塊：

- System Pulse
- Knowledge Metrics
- Agent Workload
- Activity and Alerts

三條主要流程：

- 對話派工：需求、計畫、確認、非同步 Task、進度、原會話 callback。
- 專案執行：Epic／Story、依賴圖、Kanban／Queue、Attempt、Comment、Artifact。
- 知識工作：Knowledge Base、文件索引、引用回答、交給 BA 製作報告。

Task 與 Agent 狀態使用 SSE，即時串流失敗時降級為 polling。手機版使用
drawer 與真正單欄卡片。預設 UI 為繁體中文；API 與程式 contract 使用英文。

## 8. 安全

- 管理員密碼使用 Argon2id。
- Browser Auth 使用 secure、HTTP-only、SameSite cookie。
- 新 Channel Identity 預設 `pending`，核准前不可執行 Agent 工具。
- Secrets 與 API headers 加密保存，讀取 API 不回傳明文。
- 外部 URL 檢查 scheme、DNS、redirect、loopback、private network 與 metadata endpoint。
- 上傳限制 extension、MIME、大小、頁數與安全路徑。
- Agent workspace 預設私有，只有明確 publish 的 shared artifact 可交付。
- UI 只顯示 correlation ID，不顯示 stack trace。
- 危險操作必須明確確認。

## 9. 錯誤恢復

- 可重試錯誤採指數退避，預設最多三次。
- Worker heartbeat 與 lease expiry 負責程序中斷恢復。
- Idempotency key 與 transaction lock 防止重複完成。
- Callback 與通知各有獨立 delivery attempt 與重試。
- 所有宣告 artifact 通過位置、存在、大小與 checksum 驗證後，Task 才能
  標記 `succeeded`。
- 失敗依賴鏈不自動繼續。
- 管理員可重試 attempt、從特定 Task 續跑、取消 chain 或替換依賴。

## 10. 測試與完成條件

所有功能遵循 TDD。

- Unit：狀態機、身份、Result Envelope、ToolGrant、URL policy、Provider。
- Integration：PostgreSQL、pgvector、Redis、Dramatiq、排程、lease、重試、callback。
- Contract：A2A manifest／envelope、MCP tools、Channel Adapter。
- Frontend：Vitest＋Testing Library。
- E2E：Playwright 驗證管理員 onboarding、身份核准、WebChat 派工、進度、
  callback、artifact 與恢復操作。
- Telegram、Discord、LINE 各自具有 adapter smoke test。

第一版只有在全新 Docker Compose 能完成以下流程時才算完成：

1. 建立管理員。
2. 外部 Channel 無 token 時仍能使用 WebChat。
3. 獨立設定及啟用外部 Channel。
4. 核准新的 Channel 使用者。
5. 登記並 health-check 四個 Agent。
6. 向四個 Agent 派工。
7. 顯示即時進度與 Attempt 歷史。
8. 將 callback 與 artifact 送回原 Conversation。
9. 執行 Reminder 與 Recurring Work。
10. 任務執行中重啟 Worker，且能恢復而不重複完成。

## 11. 交付策略

開發分支為 `feat/opsweave-rewrite`。既有應用允許被取代，但實作必須切成可獨立
驗證的垂直切片，每個切片完成後 Docker Compose 與自動化測試都需保持可執行。

實作順序：

1. 儲存庫與 runtime 基礎。
2. Identity 與 Control Plane 認證。
3. 任務狀態機與可靠 Worker。
4. A2A／MCP contract 與 Manager 派工。
5. Knowledge、Coding、Business Analysis Agent。
6. WebChat 與 callback。
7. 外部 Channel Adapter。
8. Projects、Automation、Diary、Registry。
9. 完整 Modern Bento 前端與營運強化。
