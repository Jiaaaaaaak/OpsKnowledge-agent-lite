# 引導式工作流程 UI/UX 重新設計

日期：2026-06-14

## 目標

將專案介面從多個分散功能頁，重新整理為以任務為中心的引導式工作流程。這次要解決的主要問題是導覽不清楚、長時間 AI 操作缺少明確 loading 回饋，以及事件分析完成後沒有清楚的結果落點。

這次重新設計涵蓋兩個主要使用流程：

- 事件洞察：選擇專案、匯入事件、AI 分析、查看分析結果。
- 知識庫問答：選擇專案、上傳文件與建立索引、使用 RAG 問答並查看引用來源。

## 已確認決策

- 使用兩條獨立的 guided workflow，不合併成一條大型流程。
- 舊路由先保留或導向新流程，以維持相容性；但不再放在主要側欄導覽。
- 這一版先用前端階段式進度來處理長時間分析，不做真實後端 job 進度。
- 新增後端結果 API 與 run-level 資料關聯，讓事件分析結果頁能顯示單次分析真正產出的資料。
- RAG chat 本身就是知識庫流程的結果區，不新增獨立的 RAG 結果頁。

## 資訊架構

主要側欄導覽應改為：

- 事件洞察流程
- 知識庫問答流程
- 分析儀表板
- Agent 執行紀錄
- 系統狀態

既有路由如 `/incident-upload`、`/analysis`、`/document-upload`、`/chat` 在遷移期間應保留或導向新 workflow，但不再作為主要側欄入口。

## 事件洞察流程

路由：`/insights/workflow`

步驟：

1. 專案
   - 若尚未選擇專案，顯示必須選擇專案的狀態，並提供選擇或建立專案的動作。
   - 若已有專案，將此步驟標示為完成。

2. 匯入事件
   - 沿用目前 CSV、Excel、JSON 工單匯入能力。
   - 顯示匯入結果：原始列數、清理後筆數、失敗筆數。
   - 成功匯入後，允許使用者進入分析步驟。

3. AI 分析
   - 呼叫既有事件分析 endpoint。
   - 等待期間顯示階段式進度：
     - 分類事件
     - 判斷嚴重程度
     - 產生洞察
     - 建立行動項目
   - 進度為前端預估，在 API 真正完成前不可顯示 100%。
   - 成功後導向 `/analysis/result/:agentRunId`。
   - 失敗時停留在分析步驟，顯示重試與 Agent 執行紀錄入口。

4. 分析結果
   - 顯示該次 agent run 的分析結果。
   - 包含 run 摘要、產生的洞察、產生的行動項目、run metadata 與後續動作。
   - CTA 應包含：
     - 查看完整儀表板
     - 查看 Agent Run 詳細紀錄
     - 再次匯入事件

步驟定位應自動判斷，但不能過度限制使用者：

- 沒有專案：停在 Step 1。
- 有專案但沒有事件資料：停在 Step 2。
- 有尚未分析的事件資料：停在 Step 3。
- 有最近分析結果：Step 4 可用。
- 使用者仍可回到先前可用的步驟。

## 知識庫問答流程

路由：`/knowledge/workflow`

步驟：

1. 專案
   - 與事件流程共用「必須選擇專案」的行為。

2. 知識庫
   - 沿用目前 PDF 上傳能力。
   - 顯示文件與索引狀態：文件數、總頁數、總 chunks。
   - 顯示文件處理的階段式回饋：
     - 上傳文件
     - 文件切塊
     - 建立向量索引
     - 完成

3. 提問
   - 將既有 chat UI 嵌入或重構進 workflow。
   - Chat 即為 RAG 的結果區。
   - 在 chat 上方顯示知識庫狀態。
   - 保留可展開的引用來源。
   - 保留 Top K 控制。
   - 回答中顯示較小的階段式狀態，例如檢索知識庫、生成回答。

若沒有任何文件，workflow 應停在知識庫步驟，並禁止直接提問。

## 後端設計

替事件分析輸出新增 run-level 關聯：

- `insights.agent_run_id UUID NULL REFERENCES agent_runs(id) ON DELETE SET NULL`
- `action_items.agent_run_id UUID NULL REFERENCES agent_runs(id) ON DELETE SET NULL`

新增索引：

- `idx_insights_agent_run_id`
- `idx_action_items_agent_run_id`

更新 `run_incident_analysis`，讓產生的 insights 與 action items 寫入目前的 `agent_run_id`。

新增：

`GET /agent-runs/{agent_run_id}/analysis-result`

回傳內容應包含：

- Agent run metadata：id、project_id、task_type、model_name、status、latency_ms、created_at、error_message。
- `AgentRun.output_json` 裡的 summary：records_analyzed、needs_review、insights_created、action_items_created。
- 該次 run 產生的 insights。
- 該次 run 產生的 action items。

新增：

`GET /projects/{project_id}/workflow-status`

回傳內容應包含：

- 事件狀態：
  - cleaned ticket count
  - analyzed ticket count
  - unanalyzed ticket count
  - latest incident analysis run id and status
- 知識庫狀態：
  - document count
  - total pages
  - total chunks
  - can_chat boolean

前端應使用此 status API 來定位 workflow step，不再從多個無關 endpoint 自行推測流程狀態。

## 前端元件

盡量建立共用 workflow 元件：

- `WorkflowStepper`
  - 顯示完成、目前、可用、鎖定狀態。
  - 允許回到可用步驟。

- `ProjectRequiredState`
  - 尚未選擇專案時的共用空狀態。

- `UploadPanel`
  - 可配置的上傳 UI，用於事件資料與文件。
  - 支援檔案類型文案、接受副檔名、loading 文字與成功摘要。

- `WorkflowStatusPanel`
  - 顯示專案層級 workflow 狀態，例如未分析事件數、最近 run、文件數、頁數、chunks。

- `AnalysisProgressPanel`
  - 事件分析專用的階段式進度面板。

- `AnalysisResultPage`
  - 呼叫並渲染 `/agent-runs/{agentRunId}/analysis-result`。

- `EventInsightsWorkflowPage`
  - 管理事件洞察 workflow 的 step state 與導覽。

- `KnowledgeWorkflowPage`
  - 管理知識庫 workflow 的 step state，並嵌入或重構 chat 行為。

沿用既有 Tailwind、`Card`、`Button` 與 lucide icons。視覺風格應維持偏作業型、精簡、可掃描，不做成 marketing landing page。

## Loading 與錯誤處理

事件分析：

- 預估進度可依階段前進，但 API 完成前應停在完成前的狀態。
- 成功後短暫顯示完成狀態，再導向結果頁。
- 遇到「沒有可分析資料」時，提供匯入更多事件或開啟最近結果的動作。
- 失敗時顯示失敗階段、錯誤訊息、重試動作與 Agent 執行紀錄入口。

知識庫問答：

- 沒有專案時停在專案步驟。
- 沒有文件時停在知識庫步驟。
- Chat 失敗時保留使用者問題並提供重試。
- 成功回答時，引用來源需保持可見且可展開。

結果頁：

- 找不到 run 時，顯示 not found 狀態，並提供回事件 workflow 的 CTA。
- run 存在但沒有 linked insights 或 action items 時，顯示 run summary 與解釋性的空狀態。

## 測試計畫

後端測試：

- Migration 或 schema 測試確認 `agent_run_id` 欄位與索引存在。
- Analysis service 會將 `agent_run_id` 寫入產生的 insights 與 action items。
- Analysis result endpoint 只回傳指定 run 的資料。
- Workflow status endpoint 正確計算 cleaned、analyzed、unanalyzed、document、page、chunk totals。

前端測試：

- Workflow step positioning：無專案、無資料、可分析、有結果等狀態。
- 事件分析成功後導向 `/analysis/result/:agentRunId`。
- 事件分析失敗後停留在分析步驟並顯示重試。
- 知識庫沒有文件時不能進入 chat。
- 知識庫有文件時可以進入 chat。
- 分析結果頁能渲染 summary、insights、action items。

手動驗證：

- 建立或選擇專案 -> 匯入事件 -> 執行分析 -> 看到階段式 loading -> 進入 run result -> 開啟 dashboard。
- 建立或選擇專案 -> 上傳 PDF -> 進入 chat -> 提問 -> 檢查 citations。
- 確認側欄只顯示新的主要 workflow 入口，以及 dashboard、Agent Runs、系統狀態。

## 遷移策略

在同一個 feature branch 實作，但第一版保留舊路由：

1. 新增後端 run 關聯、結果 API、狀態 API。
2. 新增共用 workflow 元件。
3. 建立事件洞察 workflow 與結果頁。
4. 使用既有 chat 行為建立知識庫 workflow。
5. 更新側欄主要導覽。
6. 確認 workflow 覆蓋舊功能後，再 redirect 或保留舊路由。

這樣可以讓產品體驗變乾淨，同時降低立即移除舊頁造成破壞的風險。
