# Demo 腳本 — OpsKnowledge Agent Lite

[English](DEMO_SCRIPT.md) | 繁體中文

總 Demo 時間：約 8 分鐘。

---

## 事前準備（Demo 前）

1. `docker compose up --build` — 所有服務皆已啟動。
2. 於瀏覽器開啟 `http://localhost:8501`。
3. 在 `demo_data/` 中準備好範例 PDF 與 incident CSV。

---

## 場景 1：健康檢查（30 秒）

> 「先讓各位看到後端已啟動且連線正常。」

```bash
curl http://localhost:8000/health | jq
```

預期輸出：
```json
{"status":"ok","version":"0.1.0","db":"connected","chroma":"configured"}
```

---

## 場景 2：上傳 PDF（1.5 分鐘）

> 「我們上傳一份 IT SOP — 例如網路故障排除指南。」

1. 進入 **Upload** 頁面。
2. 拖放 `demo_data/documents/sample_sop.pdf`。
3. 展示：解析 → 分塊 → 嵌入 → 存入 ChromaDB。

---

## 場景 3：知識問答（1.5 分鐘）

> 「接著我們針對該文件提問。」

1. 進入 **Chat** 頁面。
2. 輸入：`What is the escalation procedure for P1 incidents?`
3. 展示 RAG 檢索：標示出最相關的 chunks，再呈現 LLM 回答。

---

## 場景 4：事件 ETL（1.5 分鐘）

> 「我們匯入原始的 incident 工單 — 通常雜亂且格式不一致。」

1. 進入 **Upload** 頁面 → Incident Records 分頁。
2. 上傳 `demo_data/tickets/sample_incidents.csv`。
3. 展示：PostgreSQL 中已正規化的資料列，以及清洗後的 category/severity 欄位。

---

## 場景 5：AI 分析（1.5 分鐘）

> 「接著執行由 AI 驅動的分類與嚴重度評分。」

1. 進入 **Dashboard** 頁面。
2. 觸發分析執行。
3. 展示：每筆 incident 都得到 `predicted_category`、`severity_score`、`insight`、`action_items`。

---

## 場景 6：代理日誌 / 可觀測性（1 分鐘）

> 「每一次 AI 呼叫都會被記錄 — 模型、tokens、延遲、結果。」

1. 進入 **Agent Logs** 頁面。
2. 展示表格：run_type、model、prompt_tokens、completion_tokens、latency_ms。
3. 強調：「這就是在正式環境中稽核 AI 決策的方式。」

---

## 重點訴求（Talking Points）

- **LLMProvider 抽象層**：只需修改 `.env` 即可將 OpenAI 換成 Ollama — 不需更動程式碼。
- **以 PostgreSQL 做可觀測性**：完整稽核軌跡，可查詢、可匯出。
- **以 ChromaDB 做 RAG**：對私有文件進行語意檢索，無需 fine-tuning。
- **模組化服務**：每個服務都可獨立擴充或替換。
