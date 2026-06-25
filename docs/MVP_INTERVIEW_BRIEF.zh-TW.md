# OpsKnowledge Agent Lite — MVP 面試展示備忘

## 3 分鐘 Demo 流程

1. 開場定位：
   - 這是一個面向 IT 維運 SOP / 技術手冊的 RAG 知識庫。
   - 目標是讓維運人員用中文提問，從上傳文件中取得可追溯、有引用來源的回答。

2. 建立知識庫：
   - 進入 `http://localhost:8501`。
   - 選擇或建立專案。
   - 在「知識庫問答流程」上傳 PDF。
   - 說明 ingestion 流程：PDF 抽字、掃描頁 OCR fallback、章節優先 chunk、embedding 寫入 PostgreSQL + pgvector。

3. 問答展示：
   - 用中文問一個維運問題。
   - 展示回答與引用來源。
   - 說明檢索流程：pgvector 語意檢索 + PostgreSQL keyword search + RRF fusion，必要時可接 reranker。

4. Agent 可觀測性：
   - 進入「Agent 執行紀錄」。
   - 展示每次 run 的 model、latency、tool calls。
   - 說明 agent-chat 會讓 LLM 決定查什麼、查幾次、用 hybrid / keyword / vector 哪種策略，但非閒聊問題會被強制至少檢索一次，避免憑空回答。

5. 系統狀態：
   - 進入「系統狀態」。
   - 展示 API、PostgreSQL、pgvector connected。
   - 說明 `/health` 在 DB 或 pgvector 不可用時會回 degraded / 503，避免部署健康檢查誤判。

## 技術重點

- Backend：FastAPI、SQLAlchemy、Pydantic v2。
- DB：PostgreSQL 16 + pgvector，schema 由 Alembic migration 管理。
- Retrieval：vector search、keyword search、RRF fusion、optional reranker。
- LLM provider：mock / Ollama / OpenAI-compatible，可用環境變數切換。
- 文件處理：PDF parsing、OCR fallback、upload/page/chunk limits、檔名清洗與 document id 防覆寫。
- 前端：React + Vite + Tailwind，單一 guided workflow。
- 可觀測性：`agent_runs` 與 `tool_calls` 記錄每次問答與工具呼叫。

## 常見追問回答

**為什麼用 PostgreSQL + pgvector，而不是獨立 vector DB？**

MVP 目標是降低部署複雜度。文件 metadata、chunks、audit logs、vector index 都在同一個 PostgreSQL 裡，Docker Compose 一套就能跑；未來資料量上來再拆專用 vector DB 也可以。

**如何避免 LLM 幻覺？**

Prompt 明確要求只根據 retrieved context 回答；agent 模式下非閒聊問題會由程式強制至少檢索一次；回答附 citations，稽核頁也能看到實際查了哪些 chunks。

**中文提問、英文文件可以嗎？**

可以。預設可用 Ollama 的 `bge-m3` 多語 embedding 做跨語檢索；回答會正規化成台灣繁體中文，跨語引用可附翻譯 snippet。

**如果文件是掃描 PDF？**

抽不到足夠文字的頁會走 OCR fallback。OCR 缺套件或單頁失敗時會降級，不影響原生文字 PDF；也有 per-page timeout，避免單頁卡住整份匯入。

**目前 MVP 還沒做什麼？**

還沒有正式 auth / RBAC、文件刪除管理、streaming answer、完整 CI pipeline、production-grade observability。這些是下一階段，不混進 MVP 是為了降低面試展示風險。

## 最終驗證指令

```bash
make test
cd frontend && npm run test
cd frontend && npm run build
docker compose exec backend sh -c "alembic upgrade head && alembic current"
docker compose exec backend python3 -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health',timeout=2).read().decode())"
```
