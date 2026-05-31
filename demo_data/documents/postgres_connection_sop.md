# PostgreSQL 連線與效能維運標準作業程序（SOP）

> 文件編號：SOP-DB-PG-001
> 適用對象：IT 維運 / 系統整合團隊
> 文件狀態：內部技術文件（範例，所有資料庫名稱、帳號皆為虛構）

## 一、目的（Purpose）

本 SOP 規範 PostgreSQL 資料庫在連線（connection）、效能（performance）、
複寫（replication）與權限（permission）方面的故障排除與維運作業，
協助維運團隊處理 connection timeout、slow query、主節點當機 down 等事件，
維持內部 API 與報表服務的資料庫穩定。

## 二、適用範圍（Scope）

- 主資料庫節點與 read replica。
- 應用程式連線池與 max_connections 設定。
- 慢查詢（slow query）與索引（index）優化。
- 資料庫層級的存取權限（schema / role）。
- 不含 pg_dump 備份策略細節，請參考備份與 NAS 儲存 SOP。

## 三、常見症狀（Symptoms）

- 應用程式回報 PostgreSQL connection timeout，連線被拒。
- 連線數達到 max_connections 上限。
- 報表查詢 latency 飆高，單筆 slow query 數十秒，CPU 接近滿載。
- 主從 replication lag 持續擴大，read replica 資料落後。
- 批次作業期間大量 row lock 等待，前台交易變慢 degraded。
- 主資料庫節點當機 down，寫入操作全面中斷。
- 新進工程師連線時 access denied，無法存取開發 schema。

## 四、可能原因（Possible Causes）

1. **連線耗盡**：連線池過大或閒置連線未釋放，耗盡 max_connections。
2. **缺少索引**：資料量成長後常用查詢缺少適當 index，造成 slow query 與高 CPU。
3. **長交易卡住**：未提交的長交易卡住 WAL，導致 replication lag 擴大。
4. **鎖競爭**：大批次交易在尖峰時段執行，造成 row lock 等待。
5. **節點故障**：硬體或資源問題導致主節點 down，需要 failover。
6. **權限設定**：role 未授予對應 schema 的存取權，造成 access denied。
7. **網路抖動**：應用與資料庫之間網路不穩，造成間歇性連線中斷 timeout。

## 五、故障排除步驟（Troubleshooting Steps）

### 5.1 連線問題（connection timeout）
- 檢視目前連線數與來源：查詢 `pg_stat_activity`，找出大量 idle 連線。
- 確認應用端連線池設定是否過大或未正確釋放連線。
- 必要時調整連線池大小、關閉閒置連線，或評估導入連線中介層。

### 5.2 效能問題（slow query / 高 CPU）
- 透過慢查詢日誌或 `pg_stat_statements` 找出高成本查詢。
- 以 `EXPLAIN ANALYZE` 分析執行計畫，為熱點欄位建立索引並更新統計資訊。
- 將大型批次作業移到離峰時段，降低對前台 latency 的影響。

### 5.3 複寫與鎖問題
- 監控 replication lag，找出卡住 WAL 的長交易並處理。
- 對於 row lock 等待，拆分大批次交易、縮短交易範圍。

### 5.4 主節點當機（outage / failover）
- 確認主節點確實不可用後，切換至 standby 節點完成 failover。
- 切換後驗證應用連線字串與資料一致性，並事後檢討自動切換機制。

### 5.5 權限問題（access denied）
- 確認使用者 role 與目標 schema 的授權對應。
- 補上必要的 read / write 權限，並更新權限申請流程紀錄。

## 六、升級判準（Escalation Criteria）

符合以下任一條件，應立即升級：

- 主資料庫 down 且 standby 無法順利接手，造成寫入中斷。
- 連線耗盡導致核心服務全面無法存取且調整後仍無法緩解。
- replication 嚴重落後，read replica 提供的資料明顯不正確。
- 疑似資料遭未授權存取（轉 security SOP 處理）。

## 七、預防檢查清單（Prevention Checklist）

- [ ] 監控連線數並設定接近 max_connections 的告警門檻。
- [ ] 定期檢視慢查詢報告，主動為高頻查詢建立索引。
- [ ] 監控 replication lag 與長交易，異常即告警。
- [ ] 規範大型批次作業的執行時段，避開尖峰。
- [ ] 定期演練 failover，確認 standby 可正常接手。
- [ ] 以最小權限原則管理 schema / role 授權，並定期稽核。
- [ ] 監控應用與資料庫之間的網路品質，降低間歇性 timeout。
