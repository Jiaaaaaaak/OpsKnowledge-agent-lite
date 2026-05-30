# 系統架構 — OpsKnowledge Agent Lite

[English](ARCHITECTURE.md) | 繁體中文

## 總覽

```mermaid
graph TD
    subgraph Frontend["Frontend (Streamlit :8501)"]
        UI_Upload[Upload Page]
        UI_Chat[Chat / Q&A Page]
        UI_Dashboard[Dashboard Page]
        UI_Logs[Agent Logs Page]
    end

    subgraph Backend["Backend (FastAPI :8000)"]
        API[REST API Layer]
        SVC_DOC[Document Service]
        SVC_ETL[ETL Service]
        SVC_AI[AI Analysis Service]
        SVC_LOG[Observability Service]
        LLM[LLMProvider\n(OpenAI / Ollama)]
    end

    subgraph Storage["Storage"]
        PG[(PostgreSQL\n:5432)]
        CHROMA[(ChromaDB\n:8001)]
    end

    UI_Upload --> API
    UI_Chat --> API
    UI_Dashboard --> API
    UI_Logs --> API

    API --> SVC_DOC
    API --> SVC_ETL
    API --> SVC_AI
    API --> SVC_LOG

    SVC_DOC --> CHROMA
    SVC_DOC --> LLM
    SVC_ETL --> PG
    SVC_AI --> LLM
    SVC_AI --> PG
    SVC_LOG --> PG
```

## 元件職責

| 元件 | 職責 |
|---|---|
| `api/` | 路由定義、請求驗證、回應序列化 |
| `services/document_service.py` | PDF 解析、分塊，接著嵌入並寫入 ChromaDB（透過注入的 `VectorStoreService`） |
| `services/embedding_service.py` | `EmbeddingProvider` 介面與 `OpenAIEmbeddingProvider`；之後替換本地 embedding 的接點 |
| `services/vector_store.py` | 封裝 ChromaDB 的 `VectorStoreService`：upsert chunk 向量、以專案為範圍的相似度搜尋 |
| `services/llm_service.py` | `LLMProvider` 介面與 `OpenAICompatibleLLMProvider`；`build_rag_prompt` 和 `format_citations` 純函式 |
| `services/etl_service.py` | CSV/Excel/JSON 匯入、正規化、寫入 PostgreSQL |
| `services/ai_service.py` | 調度 LLM 工具呼叫，執行分類、評分、洞察 |
| `services/log_service.py` | 將每次 AI 執行記錄至 `ai_run_log` 資料表 |
| `tools/` | 各個 AI 工具定義（結構化 function call 規格） |
| `db/session.py` | SQLAlchemy engine、session factory、`get_db` 相依注入 |
| `core/config.py` | 透過環境變數集中管理所有設定（Pydantic Settings） |
| `LLMProvider` | OpenAI SDK 的抽象層 — 支援 OpenAI 或 Ollama base URL |

## 資料流

### 文件 RAG

```
POST /projects/{id}/upload/documents
  │
  ├─ 副檔名驗證（.pdf only）
  │
  ├─ _extract_pages()  pypdf.PdfReader → [(page_num, text), ...]
  │    └─ 非文字 PDF（掃描圖檔）→ 400 Bad Request
  │
  ├─ _save_file()  寫入 data/uploads/{project_id}/documents/{filename}
  │
  ├─ documents INSERT（filename, document_type="pdf", source_path, metadata.page_count）
  │
  ├─ 逐頁 _chunk_text()  滑動視窗（chunk_size=1000, overlap=150）
  │    └─ 每個 chunk（明確指定 uuid）→ document_chunks INSERT
  │         metadata: { filename, page_number, chunk_size }
  │
  ├─ VectorStoreService.add_chunks()  嵌入所有 chunk → ChromaDB upsert
  │    ├─ id = document_chunks.id（PG 與 ChromaDB 使用相同 UUID）
  │    ├─ metadata: { project_id, document_id, chunk_id, filename, chunk_index }
  │    └─ 在 db.commit() 之前執行 — embedding 失敗即中止上傳（不留下半套資料）
  │
  └─ 回傳 DocumentIngestionResult
       { document_id, filename, page_count, chunk_count, source_path }

GET /projects/{id}/search?query=...&top_k=5
  └─ 嵌入 query → ChromaDB query（where project_id == {id}）→ top-k chunks
       每筆 hit：{ chunk_id, content, metadata, distance, score }
       chunk_id 可 1:1 對回 PostgreSQL 的 document_chunks 列
```

### RAG Chat

```
POST /projects/{id}/chat  { question, top_k }
  │
  ├─ Project 404 防護
  │
  ├─ VectorStoreService.search(project_id, question, top_k)
  │    └─ 嵌入問題 → ChromaDB query（where project_id == {id}）→ top-k hits
  │         每筆 hit：{ chunk_id, content, metadata, distance, score }
  │
  ├─ build_rag_prompt(hits)
  │    └─ 編號 context 區塊 + 幻覺防護規則
  │
  ├─ OpenAICompatibleLLMProvider.complete(system_prompt, question)
  │    └─ temperature=0.1，model 由 LLM_MODEL 環境變數決定
  │
  ├─ format_citations(hits)
  │    └─ { document_id, chunk_id, filename, chunk_index, snippet(≤200 字元) }
  │
  ├─ AgentRun INSERT（task_type="rag_chat", status, latency_ms, input_json, output_json）
  │    └─ ToolCall INSERT（tool_name="vector_search", latency_ms, hit_count, chunk_ids）
  │
  └─ 回傳 ChatResponse  { answer, citations[] }
       citations 透過 chunk_id == document_chunks.id 對回 PostgreSQL
```

### 事件 ETL + AI 分析

```
POST /projects/{id}/upload/tickets
  │
  ├─ 副檔名驗證（.csv / .xlsx / .json）
  │
  ├─ 格式解析
  │    ├─ CSV  → stdlib csv.DictReader
  │    ├─ JSON → stdlib json.loads（支援 list / wrapped object / single object）
  │    └─ XLSX → openpyxl（lazy import）
  │
  ├─ 逐列處理
  │    ├─ RawRecord INSERT（原始資料，無論是否通過驗證）
  │    ├─ normalize_columns()  欄位同義詞對應 → 標準欄位名稱
  │    ├─ CleanedTicket(Pydantic)  strip / empty→None / 必填驗證 / 預設值
  │    │    ├─ 成功 → CleanedRecord INSERT
  │    │    └─ 失敗 → 記入 errors[]，raw_records 仍保留
  │    └─ db.commit()
  │
  └─ 回傳 TicketImportSummary
       { raw_count, cleaned_count, failed_count, errors }

Incident batch → LLM classify + score → AI results → PostgreSQL (incident_analysis table)
Every LLM call → log tokens/latency → PostgreSQL (agent_runs table)
```

## 連接埠對應

| 服務 | 連接埠 |
|---|---|
| FastAPI 後端 | 8000 |
| Streamlit 前端 | 8501 |
| PostgreSQL | 5432 |
| ChromaDB | 8001 |

## LLMProvider 設計

LLM 後端被封裝在只有一個方法的抽象介面之後，因此可以在不動到 RAG／chat 流程的
情況下替換。`get_llm_provider()` 會依 `LLM_PROVIDER` 環境變數選擇具體實作。

```python
class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_message: str) -> tuple[str, dict]:
        """回傳 (answer_text, usage_metadata)。"""

class OpenAICompatibleLLMProvider(LLMProvider):
    # 透過 OpenAI SDK 呼叫雲端 API（OPENAI_API_KEY、OPENAI_BASE_URL、LLM_MODEL）。
    def complete(self, system_prompt, user_message): ...

class OllamaLLMProvider(LLMProvider):
    # 本地 / 地端模型。透過 httpx 直接呼叫 Ollama 原生 HTTP API（/api/chat），
    # 不經過 OpenAI SDK、不需 API key、資料不離開主機。
    # 由 OLLAMA_BASE_URL / OLLAMA_MODEL 設定；Ollama 服務無法連線時會丟出明確的 RuntimeError。
    def complete(self, system_prompt, user_message): ...

class MockLLMProvider(LLMProvider):
    # 確定性、離線；供 CI / 本地開發使用（無網路呼叫）。
    def complete(self, system_prompt, user_message): ...
```

| `LLM_PROVIDER` | 實作 | 後端 | 使用情境 |
|---|---|---|---|
| `openai` | `OpenAICompatibleLLMProvider` | OpenAI 相容 API（SDK） | 快速 POC／雲端展示 |
| `ollama` | `OllamaLLMProvider` | 本地 Ollama 伺服器（原生 HTTP） | 私有／地端部署 |
| `mock` | `MockLLMProvider` | 無（確定性） | CI／離線本地開發 |

**切換 provider 只需修改 `.env`**（`LLM_PROVIDER`，再加上對應的 `OPENAI_*` 或
`OLLAMA_*` 設定）。新增 provider 只需實作 `complete()` 並在 `get_llm_provider()`
中註冊。

> **雲端 vs 地端的範圍：** `openai` 路徑用於低設定成本的快速 POC；`ollama` 路徑則為
> 私有／地端情境預備好，讓 LLM 能在客戶網路內執行。注意目前這層抽象只涵蓋 **LLM**，
> embedding 仍由 `EMBEDDING_PROVIDER`（`openai` / `mock`）決定，因此要做到完全地端，
> 還需要一個本地 embedding provider（未來的 `EmbeddingProvider` 實作，模式與此相同）。
