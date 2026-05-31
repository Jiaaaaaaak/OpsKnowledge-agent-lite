# OpsKnowledge Agent Lite — Demo Data Pack

這份 demo data 是為了在面試 / POC 展示中，端到端呈現 OpsKnowledge Agent Lite 的能力：
從工單 ETL、事件分類、嚴重度評分、儀表板彙總、行動項目產生，到 SOP 文件匯入與
帶引用（citation）的 RAG 知識問答。

情境設定為一個內部 **IT 維運 / 系統整合團隊**，負責管理基礎設施、部署、VPN、
NAS 儲存、PostgreSQL、Docker、備份作業、防火牆規則與內部 API。

所有資料皆為**虛構範例**，不含任何真實機密、帳密、IP 或私人資訊。

---

## 一、檔案說明（What each file is for）

| 檔案 | 用途 |
| --- | --- |
| `tickets/sample_incidents.csv` | 主要工單資料集（54 筆），使用乾淨欄位 schema，示範 CSV ETL、分類、評分、彙總。 |
| `tickets/sample_incidents_messy_columns.csv` | 同類資料但**欄名凌亂**（id/date/service/...），用來測試欄位正規化（column normalization）。 |
| `tickets/sample_incidents.json` | 10 筆 JSON 格式工單，示範 JSON ETL 與多格式匯入。 |
| `documents/docker_volume_sop.md` | Docker host 與 volume 維運 SOP，供 RAG 知識問答檢索。 |
| `documents/vpn_troubleshooting_sop.md` | VPN 連線故障排除 SOP，供 RAG 檢索。 |
| `documents/postgres_connection_sop.md` | PostgreSQL 連線與效能維運 SOP，供 RAG 檢索。 |
| `documents/backup_and_nas_sop.md` | 備份作業與 NAS 儲存維運 SOP，供 RAG 檢索。 |

### 工單資料涵蓋的事件類別
network_issue、storage_issue、deployment_issue、permission_issue、
security_issue、performance_issue、data_quality_issue，以及備份相關（backup）事件。
並刻意混合：已結案（含 resolution）、未結案（open，無 resolution）、高優先 / critical、
重複出現的問題樣態（例如多次 VPN 斷線、多次 disk full、多次 backup 失敗），以及
描述較模糊、需人工複審（needs_review）的工單。

> **設計細節**：issue_description / resolution 以**繁體中文**撰寫（UI 為繁中），
> 但刻意保留 `VPN`、`502`、`timeout`、`disk full`、`PostgreSQL`、`Docker`、`NAS`、
> `backup`、`access denied` 等英文技術關鍵字 —— 一方面貼近台灣 IT 團隊的真實寫法，
> 另一方面讓分類器與嚴重度評分的關鍵字規則、以及 RAG 檢索都能命中。
> 欄名一律保持**英文**，因為 ETL 期望英文欄位。

---

## 二、ETL 使用的檔案（Files used for ETL）

`tickets/` 底下三個檔案都走 ETL：

- **乾淨 schema**：`sample_incidents.csv`、`sample_incidents.json`
  欄位為 `ticket_id, occurred_at, system, module, issue_description, resolution, status, priority`。
- **欄位正規化測試**：`sample_incidents_messy_columns.csv`
  使用 `id, date, service, component, problem, fix, state, severity` 等別名欄名，
  ETL 應能對應回乾淨 schema（例如 `id → ticket_id`、`date → occurred_at`、
  `service → system`、`component → module`、`problem → issue_description`、
  `fix → resolution`、`state → status`、`severity → priority`）。

時間欄位 `occurred_at` 使用 `YYYY-MM-DD HH:MM:SS`（CSV）與 ISO `YYYY-MM-DDTHH:MM:SS`（JSON），
messy 檔則用 `YYYY/MM/DD` 來測試日期解析容錯。

---

## 三、RAG 使用的檔案（Files used for RAG）

`documents/` 底下四份 SOP（Markdown）作為知識庫來源，內容刻意包含與工單一致的
關鍵字（VPN、DNS、NAS、volume、disk full、Docker、deploy、PostgreSQL、connection、
slow query、backup、RAID、access denied 等），確保問答時能檢索到相關片段並回傳 citation。

每份 SOP 都包含：目的、適用範圍、常見症狀、可能原因、故障排除步驟、升級判準、
預防檢查清單，長度足以切成多個 chunk。

> **注意（文件匯入格式）**：目前的文件匯入服務以 **PDF** 為輸入（`documents/` 已有
> 一個 `sample.pdf` 範例）。若要把這些 `.md` SOP 灌入向量庫，請先轉成 PDF
> （例如用 pandoc / 列印成 PDF）再上傳，或在文件服務支援 Markdown 後直接匯入。
> Markdown 原始檔保留於此，方便檢視與維護內容。

---

## 四、建議展示問題（Suggested demo questions）

針對 RAG 知識問答（應回傳對應 SOP 的引用）：

1. 「VPN 連上之後內部網域 DNS 解析失敗，要怎麼排查？」 → 命中 VPN SOP。
2. 「Docker 部署後容器一直 restart、health check failed，可能原因？」 → 命中 Docker SOP。
3. 「NAS 備份 job 失敗、disk full 時的處理步驟是什麼？」 → 命中 Backup/NAS SOP。
4. 「PostgreSQL connection timeout、連線數滿了怎麼辦？」 → 命中 Postgres SOP。
5. 「主資料庫節點當機 down，failover 流程與升級判準為何？」 → 命中 Postgres SOP。
6. 「RAID 進入 degraded 狀態，該如何處理與預防？」 → 命中 Backup/NAS SOP。

針對工單分析 / 儀表板：

7. 「列出所有 critical 且仍 open 的事件。」
8. 「哪個 system 的事件最多？哪一類（category）最常出現？」
9. 「最近一週的高嚴重度事件趨勢如何？」

---

## 五、預期洞察（Suggested expected insights）

匯入並分析工單後，展示時可預期看到：

- **重複樣態**：VPN 斷線 / 連線上限、NAS disk full / RAID 異常、backup job 失敗
  等問題重複出現，顯示應從預防（容量規劃、排程告警）面改善。
- **分類分佈**：事件可被歸類到 network / storage / deployment / permission /
  security / performance / data_quality，儀表板可依類別與 system 彙總。
- **嚴重度熱點**：標示為 critical 的多為資料庫當機、安全事件（malware / 未停用帳號 /
  未修補 CVE）與 API gateway 大量 502/503，應優先處理。
- **待複審工單**：描述較模糊（如「原因待釐清」「錯誤訊息不明確」）的 open 工單，
  信心分數較低，會被標記為 needs_review，適合示範人工介入流程。
- **行動項目**：對 open 且高優先的事件（如 VPN 容量、CVE 修補、備份版本缺失）
  可自動產生待辦行動項目（action items）。
- **RAG 引用**：知識問答的回答能對應到具體 SOP 段落並附上 citation，
  呈現「資料 → 知識 → 可追溯答案」的完整閉環。
