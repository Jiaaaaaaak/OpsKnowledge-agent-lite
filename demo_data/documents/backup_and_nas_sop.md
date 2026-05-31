# 備份作業與 NAS 儲存維運標準作業程序（SOP）

> 文件編號：SOP-STORAGE-BACKUP-001
> 適用對象：IT 維運 / 系統整合團隊
> 文件狀態：內部技術文件（範例，所有路徑、主機名稱皆為虛構）

## 一、目的（Purpose）

本 SOP 規範每日 / 每週 / 異地備份（backup）作業與 NAS 儲存的維運流程，
協助維運團隊處理 backup job 失敗、disk full、RAID degraded、
備份資料 corruption 等儲存與備份類事件，確保資料可被正確還原。

## 二、適用範圍（Scope）

- 每日與每週的全量 / 增量 backup job。
- 異地備份同步排程（cron）。
- NAS 儲存的 volume、quota、RAID 與掛載點。
- 資料庫 pg_dump 備份檔的產出與驗證。
- 備份還原（restore）演練與資料完整性驗證。

## 三、常見症狀（Symptoms）

- 每日 backup job 凌晨執行失敗，log 顯示 NAS 掛載點無回應 error。
- 備份目標 NAS 空間不足，全量 backup 失敗 disk full。
- pg_dump 自動備份檔案大小異常為 0，疑似中途中斷。
- 異地備份同步任務連續數天未執行，排程疑似被停用。
- 備份還原驗證發現 checksum 不符或資料不完整，疑似 corruption。
- NAS 硬碟 SMART 報警，RAID 進入 degraded 狀態。
- 研發共用區 storage quota 用罄，使用者無法上傳新檔案。

## 四、可能原因（Possible Causes）

1. **掛載失敗**：NAS 的 NFS / SMB 掛載點無回應，導致 backup job 寫入 error。
2. **空間不足**：備份保留週期過長或舊備份未清理，造成 disk full。
3. **排程異常**：cron 排程被停用或主機重啟後未自動恢復，備份未執行。
4. **中途中斷**：備份過程中磁碟空間不足或連線中斷，產出不完整或 0 byte 檔案。
5. **硬體故障**：NAS 硬碟故障使 RAID degraded，增加資料 corruption 風險。
6. **驗證缺失**：缺乏定期還原演練，問題到需要 restore 時才被發現。
7. **配額限制**：共用區 quota 設定過低，造成寫入被拒。

## 五、故障排除步驟（Troubleshooting Steps）

### 5.1 備份任務失敗（backup job failed）
- 檢視 backup job log，定位失敗階段與錯誤訊息。
- 確認 NAS 掛載點狀態：`mount` / `df -h`，必要時重新掛載 NFS / SMB share。
- 確認目標磁碟剩餘空間，若 disk full 先清理舊備份再手動補跑。

### 5.2 空間與配額問題
- 檢視備份保留策略，清理超過保留週期的舊備份。
- 調整 NAS volume 或共用區 quota，並通知使用者清理大型暫存檔。
- 為儲存使用率設定告警，避免再次 disk full。

### 5.3 排程未執行
- 檢查 cron 排程是否被停用或主機重啟後未恢復。
- 重新啟用排程並補上失敗即時告警通知，確認下次正常觸發。

### 5.4 備份完整性與還原
- 對備份檔進行 checksum 驗證，0 byte 或不符者標記為失效。
- 定期執行 restore 演練，確認資料可被完整還原。
- 若發現 corruption，重建備份鏈並改用增量驗證機制。

### 5.5 RAID 與硬碟故障
- 收到 SMART 報警或 RAID degraded 時，安排更換故障硬碟。
- 更換後監控 RAID rebuild 進度，完成前避免額外高負載寫入。

## 六、升級判準（Escalation Criteria）

符合以下任一條件，應立即升級：

- 關鍵系統的備份連續失敗且短期內無法恢復。
- 需要還原但對應 backup 版本缺失或損毀（corruption）。
- RAID 在 rebuild 期間再有硬碟故障，資料面臨遺失風險。
- 備份目標 NAS 全面不可用，影響所有備份作業。

## 七、預防檢查清單（Prevention Checklist）

- [ ] 每日確認 backup job 執行結果，失敗即告警。
- [ ] 監控 NAS 與備份目標的儲存使用率，設定 80% 告警門檻。
- [ ] 定期檢視並落實備份保留週期，避免空間耗盡。
- [ ] 每月至少一次 restore 演練並驗證資料完整性（checksum）。
- [ ] 監控 RAID 與硬碟 SMART 狀態，預先更換高風險硬碟。
- [ ] 對異地備份同步排程設定獨立的健康檢查與告警。
- [ ] 為共用區 quota 設定合理上限並定期檢討。
