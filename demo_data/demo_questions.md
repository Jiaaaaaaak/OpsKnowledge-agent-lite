# OpsKnowledge Agent Lite — Demo 問題集與展示腳本

本檔提供面試 / POC 展示時可直接使用的問題清單與流程說明。
所有 RAG 問題都對應到 `demo_data/documents/` 下實際存在的 SOP 內容，確保檢索得到引用（citation）。
工單分析問題對應 `demo_data/tickets/` 匯入後的資料。

> 對應資料來源：
> - 工單：`tickets/sample_incidents.csv`（54 筆）、`sample_incidents_messy_columns.csv`（17 筆）、`sample_incidents.json`（10 筆）
> - 文件：`documents/pdf/` 下的 4 份 SOP（由 `scripts/generate_demo_pdfs.py` 產生）

---

## 1. RAG 技術文件問答（Traditional Chinese）

每題後標註預期命中的 SOP，方便展示時對照回傳的 citation 是否正確。

### Docker（docker_volume_sop）
1. Docker container 部署後一直 restart、health check failed，應該先檢查哪些設定？ → *Docker SOP*
2. docker host 出現 disk full 無法啟動新容器時，有哪些清理步驟？ → *Docker SOP*
3. 容器掛載的 volume 對應到 NAS，開機後讀不到共用檔案，可能是什麼原因？ → *Docker SOP*
4. 新版內部 API 部署後相容性異常造成呼叫端 broken，應該如何回滾與重新部署？ → *Docker SOP*

### VPN（vpn_troubleshooting_sop）
5. 使用者連上 VPN 後內部域名無法解析、DNS 查詢 timeout，排查順序是什麼？ → *VPN SOP*
6. VPN 同時連線數逼近授權上限導致新使用者無法登入，該如何處理與預防？ → *VPN SOP*
7. 特定分公司透過 VPN 無法連到 NAS，應該檢查哪些路由與防火牆設定？ → *VPN SOP*
8. VPN 伺服器憑證即將到期，升級判準與預防檢查清單為何？ → *VPN SOP*

### PostgreSQL（postgres_connection_sop）
9. PostgreSQL connection timeout、連線數達到 max_connections 上限，可能有哪些原因？ → *Postgres SOP*
10. 報表 slow query 拖垮資料庫、CPU 接近滿載，要怎麼定位與優化？ → *Postgres SOP*
11. 主資料庫節點當機 down 時，failover 流程與升級判準是什麼？ → *Postgres SOP*
12. 主從 replication lag 持續擴大，read replica 資料落後，應如何排除？ → *Postgres SOP*

### 備份與 NAS（backup_and_nas_sop）
13. 每日 backup job 失敗時，如何判斷是容量（disk full）、掛載 / 權限還是網路問題？ → *Backup/NAS SOP*
14. NAS 硬碟 SMART 報警、RAID 進入 degraded 狀態，處理與 rebuild 期間要注意什麼？ → *Backup/NAS SOP*
15. 備份還原驗證發現 checksum 不符、疑似 corruption，該如何處理？ → *Backup/NAS SOP*

> 跨文件綜合題（可展示多來源檢索）：
> 16. 「半夜 VPN 斷線，導致備份 job 連不到 NAS 而失敗」這種連鎖事件，應該分別參考哪些 SOP 的哪些步驟？ → *VPN SOP + Backup/NAS SOP*

---

## 2. 事件分析問答（Traditional Chinese）

匯入工單並執行事件分析後可詢問（對應分類、嚴重度、needs_review 等輸出）：

1. 這批事件最常見的問題類型（category）是什麼？分佈如何？
2. 哪些系統（system）的高嚴重度（severity_score 4–5）事件最多？
3. 哪些事件被標記為需要人工複核（needs_review）？為什麼信心分數偏低？
4. 目前仍未結案（status = open）且優先度為 high / critical 的事件有哪些？
5. 有哪些重複發生的維運風險樣態？（例如 VPN 斷線、NAS disk full、backup job 失敗）
6. 根據目前資料，應該優先補強或新建哪些 SOP？
7. 安全相關事件（security_issue）有哪些？嚴重度與處理狀態為何？
8. 哪些事件描述較模糊、缺少明確解決方案，適合作為流程改善的標的？
9. 最近一段期間，事件數量與嚴重度的趨勢如何？是否有惡化跡象？
10. 請為目前 open 的高優先事件各產生一條可指派的行動項目（action item）。

---

## 3. 儀表板講解重點（Dashboard Talking Points）

面試時看著儀表板，建議依序帶出以下幾點，把「資料 → 洞察 → 行動」說成一條故事線：

- **Category distribution（事件類別分佈）**
  - 指出事件如何被自動歸類到 network / storage / deployment / permission / security / performance / data_quality。
  - 重點話術：分佈不是平均的——可凸顯哪一類（如 network_issue、storage_issue）占比最高，代表團隊資源該往哪裡投。

- **Severity distribution（嚴重度分佈）**
  - 說明 severity_score 1–5 的分佈，標出 critical（4–5）集中在哪些 system。
  - 重點話術：嚴重度不是靠人工拍板，而是依描述關鍵字（outage / down / 502 / timeout）與 priority 綜合評分，可一致、可重現。

- **Needs review（待人工複核）**
  - 解釋當模型信心分數低於門檻（約 0.65）時會標記 needs_review，避免「假裝有信心」。
  - 重點話術：這是 human-in-the-loop 設計——模糊工單（如「原因待釐清」）交回人工，展現可靠度而非黑箱。

- **Top insights（重點洞察）**
  - 帶出重複樣態（VPN 斷線、disk full、backup 失敗）與熱點 system。
  - 重點話術：把零散工單彙整成「系統性風險」，而不是逐筆救火。

- **Action items（行動項目）**
  - 展示針對 open + 高優先事件自動產生的待辦（如 CVE 修補、VPN 容量擴充、備份版本缺失）。
  - 重點話術：分析不只給結論，還能落地成可指派的工作。

- **Agent runs 與 tool calls（代理執行與工具呼叫）**
  - 打開 agent log，展示每次分析背後呼叫了哪些工具（分類、評分、檢索）、輸入輸出與耗時。
  - 重點話術：流程可觀測、可稽核、可回放——出問題時能追溯是哪一步、用了什麼資料，而非「模型說了算」。

---

## 4. 預期 Demo 故事線（約 3 分鐘）

| 時間 | 步驟 | 操作 | 想傳達的重點 |
| --- | --- | --- | --- |
| 0:00–0:30 | **上傳工單** | 上傳 `tickets/sample_incidents.csv`（必要時再上傳 messy CSV 與 JSON） | 多格式 ETL + 欄位正規化：凌亂欄名 / JSON 也能進同一套 schema |
| 0:30–1:00 | **上傳 SOP PDF** | 上傳 `documents/pdf/` 下 4 份 SOP | 建立知識庫；文件被切成多個 chunk 並向量化 |
| 1:00–1:40 | **RAG 問答** | 問第 1 節任一題，例如「VPN 連上後 DNS 解析失敗的排查順序？」 | 回答附 **citation**，可點回原始 SOP 段落——答案可追溯 |
| 1:40–2:20 | **執行事件分析** | 對匯入的工單跑分類 + 嚴重度評分 | 自動分類、評分、標記 needs_review；展示 human-in-the-loop |
| 2:20–2:45 | **檢視儀表板** | 打開 dashboard | 類別 / 嚴重度分佈、重點洞察、行動項目——零散工單變成系統性風險 |
| 2:45–3:00 | **檢視代理日誌** | 打開 agent_runs / tool_calls | 流程可觀測、可稽核：每一步用了什麼工具與資料都看得到 |

> 收尾一句話：
> 「從一份凌亂的工單表，到帶引用的知識問答、可解釋的分類評分，再到可指派的行動項目——
> 整條流程都可追溯、可重現，這就是把 LLM 用在維運場景時最重要的可靠度。」
