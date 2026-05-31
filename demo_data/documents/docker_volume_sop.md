# Docker 主機與 Volume 維運標準作業程序（SOP）

> 文件編號：SOP-INFRA-DOCKER-001
> 適用對象：IT 維運 / 系統整合團隊
> 文件狀態：內部技術文件（範例，所有主機名稱與設定皆為虛構）

## 一、目的（Purpose）

本 SOP 旨在規範 Docker host 與容器 volume 的日常維運、故障排除與預防作業，
確保容器化的內部服務（例如報表服務、internal API）在部署（deploy / rollout）與
儲存（volume / disk）層面維持穩定運作，降低因 disk full、容器反覆 restart 或
deploy pipeline failed 所造成的服務中斷。

## 二、適用範圍（Scope）

- 所有承載內部服務的 docker host 節點。
- 私有 image registry 的儲存與清理。
- 容器掛載的 named volume 與 bind mount，以及對應的 NAS / NFS 掛載點。
- 由 CI 觸發的 deploy pipeline 與 rollout 流程。
- 不包含資料庫本身的備份策略，該部分請參考備份與 NAS 儲存 SOP。

## 三、常見症狀（Symptoms）

- 容器部署（docker deploy）後反覆 restart，health check failed。
- docker host 出現 disk full，無法 pull image 或啟動新容器。
- 私有 registry push / pull image 失敗並回報 error。
- 跨容器網路封包遺失，服務間呼叫 latency 不穩定。
- 容器 memory 使用率偏高，偶發 OOM 被 kill。
- 高峰期 CPU throttling 嚴重，回應時間明顯拉長 slow。
- deploy pipeline 在 build 或部署階段中止 failed，rollout 無法完成。

## 四、可能原因（Possible Causes）

1. **磁碟空間不足**：dangling image、舊版 tag、容器 log 長期堆積導致 disk full。
2. **設定缺漏**：docker-compose 或 manifest 缺少必要環境變數、資源限制設定錯誤。
3. **映像檔問題**：registry 憑證過期、image 損毀或啟動指令錯誤。
4. **資源限制不當**：未設定 memory / CPU limit，造成單一容器吃光節點資源。
5. **網路設定**：overlay network MTU 設定錯誤或 DNS 解析異常。
6. **掛載失敗**：volume 對應的 NAS / NFS 掛載點無回應，容器讀寫共用檔案 error。

## 五、故障排除步驟（Troubleshooting Steps）

### 5.1 先確認節點健康狀態
- 檢查磁碟使用率：`df -h`，確認是否 disk full。
- 檢查容器狀態與重啟次數：`docker ps -a`、`docker stats`。
- 查看容器日誌定位錯誤：`docker logs <container>`，注意 health check failed 訊息。

### 5.2 處理 disk full
- 清理未使用映像與快取：`docker image prune`、`docker system df` 評估占用。
- 移除 dangling image 與停止的容器，輪替過大的容器 log。
- 為 registry 設定 garbage collection（GC）排程，避免舊 image tag 無限堆積。

### 5.3 處理部署失敗（deploy / rollout failed）
- 比對 docker-compose / manifest 與上一版差異，確認環境變數與資源限制。
- 確認可從私有 registry 正常 pull image，必要時更新 registry 憑證。
- 若新版相容性異常造成呼叫端 broken，先 **回滾（rollback）** 至前一穩定版本，
  再於測試環境重現並修正後重新部署。

### 5.4 處理資源與網路問題
- 為容器設定合理的 memory / CPU limit，避免 OOM 與 CPU throttling。
- 重建 overlay network 並檢查 MTU；確認容器內 DNS 可正常解析。
- 驗證 volume 對應的 NAS 掛載點可讀寫，必要時重新掛載。

## 六、升級判準（Escalation Criteria）

符合以下任一條件，應於 30 分鐘內升級至資深維運工程師或主管：

- 核心 internal API 服務全面 down 且 30 分鐘內無法恢復。
- disk full 影響多個容器且清理後仍無法釋放足夠空間。
- registry 不可用導致所有部署停擺。
- 疑似映像或節點遭異常存取（與 security SOP 交叉處理）。
- 需要重啟整台 docker host 並可能影響其他服務時。

## 七、預防檢查清單（Prevention Checklist）

- [ ] 每日檢查各 docker host 磁碟使用率，設定 80% 告警門檻。
- [ ] 啟用 image prune 與 registry GC 定期排程。
- [ ] 所有容器皆設定 memory 與 CPU limit。
- [ ] 部署前於測試環境完成 health check 與相容性驗證。
- [ ] 保留最近數個穩定版本以利快速 rollback。
- [ ] 監控容器 restart 次數與 OOM 事件，異常即告警。
- [ ] 定期確認 volume 掛載點與 NAS 連通性。
