# 系統架構 — OpsKnowledge Agent Lite

[English](ARCHITECTURE.md) | 繁體中文

## 總覽

```mermaid
graph TD
    subgraph Frontend["Frontend (React :8501)"]
        UI_Workflow[知識庫問答流程]
        UI_Logs[Agent 執行紀錄]
        UI_Status[系統狀態]
    end

    subgraph Backend["Backend (FastAPI :8000)"]
        API[REST API Layer]
        SVC_DOC[Document Service\n(+ OCR fallback)]
        SVC_CHAT[Chat Service\n(/chat)]
        SVC_AGENT[Agent Service\n(/agent-chat)]
        SVC_LOG[Observability Service]
        LLM[LLMProvider\n(OpenAI / Ollama)]
    end

    subgraph Storage["Storage"]
        PGVECTOR[(PostgreSQL + pgvector\n:5432)]
    end

    UI_Workflow --> API
    UI_Logs --> API
    UI_Status --> API

    API --> SVC_DOC
    API --> SVC_CHAT
    API --> SVC_AGENT
    API --> SVC_LOG

    SVC_DOC --> PGVECTOR
    SVC_DOC --> LLM
    SVC_CHAT --> LLM
    SVC_CHAT --> PGVECTOR
    SVC_AGENT --> LLM
    SVC_AGENT --> PGVECTOR
    SVC_LOG --> PGVECTOR
```

## 元件職責

| 元件 | 職責 |
|---|---|
| `api/` | 路由定義、請求驗證、回應序列化 |
| `services/document_service.py` | PDF 解析、分塊，接著嵌入並寫入 PostgreSQL + pgvector（透過注入的 `VectorStoreService`）；對掃描 / 影像頁有 OCR fallback |
| `services/ocr_service.py` | 對「可抽取文字過少」的頁做 Tesseract OCR；lazy-import `pytesseract`/`pdf2image`，缺少時自動降級 |
| `services/embedding_service.py` | `EmbeddingProvider` 介面與 `OpenAIEmbeddingProvider`；之後替換本地 embedding 的接點 |
| `services/vector_store.py` | 封裝 PostgreSQL + pgvector 的 `VectorStoreService`：upsert chunk 向量、以專案為範圍的相似度搜尋 |
| `services/retrieval/` | 模組化 hybrid retrieval：pgvector 語意召回、PostgreSQL full-text 召回、reciprocal-rank fusion |
| `services/reranker_service.py` | 選用第二階段 cross-encoder reranker，用於重排 fusion 後的候選 chunk |
| `services/llm_service.py` | `LLMProvider` 介面與 `OpenAICompatibleLLMProvider`；`build_rag_prompt` 和 `format_citations` 純函式 |
| `services/chat_service.py` | RAG 問答（`/chat`）：檢索 → 提示 → LLM → 引用來源（固定流程） |
| `services/agent_service.py` | 自主 agent 問答（`/agent-chat`）：由 LLM 透過 `search_documents` 工具決定要不要查、查什麼、查幾次、用哪種策略，以 `AGENT_MAX_STEPS` 作上限 |
| `services/retrieval/service.py` | `HybridRetrievalService.search(..., strategy)`，strategy ∈ `hybrid`（預設）/ `keyword` / `vector` |
| `models/agent.py` | `agent_runs` 與 `tool_calls` persistence models，供 chat 與觀測路由使用 |
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
  ├─ _extract_pages_with_ocr()  pypdf.PdfReader → [(page_num, text), ...]
  │    ├─ 可抽取文字 < OCR_MIN_CHARS 的頁 → 渲染 + Tesseract OCR
  │    │    （chi_tra+chi_sim+eng，正規化為繁體中文）；OCR_ENABLED=false 或缺 tesseract/poppler 時略過
  │    └─ OCR 後仍無文字 → 400 Bad Request
  │
  ├─ _save_file()  寫入 data/uploads/{project_id}/documents/{filename}
  │
  ├─ documents INSERT（filename, document_type="pdf", source_path,
  │    metadata.{page_count, ocr_page_count}）
  │
  ├─ 逐頁 _chunk_text()  滑動視窗（chunk_size=1000, overlap=150）
  │    └─ 每個 chunk（明確指定 uuid）→ document_chunks INSERT
  │         metadata: { filename, page_number, chunk_size }
  │
  ├─ VectorStoreService.add_chunks()  嵌入所有 chunk → PostgreSQL + pgvector upsert
  │    ├─ id = document_chunks.id（PG 與 PostgreSQL + pgvector 使用相同 UUID）
  │    ├─ metadata: { project_id, document_id, chunk_id, filename, chunk_index }
  │    ├─ 寫 embedding 前先 flush chunk 列（讓 content + embedding 原子寫入）
  │    └─ 在 db.commit() 之前執行 — embedding 失敗即中止上傳（不留下半套資料）
  │
  └─ 回傳 DocumentIngestionResult
       { document_id, filename, page_count, chunk_count, source_path, ocr_page_count }

GET /projects/{id}/search?query=...&top_k=5
  └─ HybridRetrievalService.search(project_id, query, top_k)
       ├─ VectorRetriever → 嵌入 query → pgvector cosine search
       ├─ KeywordRetriever → PostgreSQL websearch_to_tsquery full-text search
       └─ ReciprocalRankFusion → 依 chunk_id 去重並回傳 top-k chunks
       每筆 hit：{ chunk_id, content, metadata, fusion_score, sources, scores }
       chunk_id 可 1:1 對回 PostgreSQL 的 document_chunks 列
```

### RAG Chat

```
POST /projects/{id}/chat  { question, top_k }
  │
  ├─ Project 404 防護
  │
  ├─ HybridRetrievalService.search(project_id, question, candidate_k)
  │    └─ vector recall + full-text recall + reciprocal-rank fusion
  │         每筆 hit：{ chunk_id, content, metadata, fusion_score, sources, scores }
  │
  ├─ 選用 reranker
  │    └─ 若 RERANKER_ENABLED=true，重排 fused candidates 並保留 top_k
  │
  ├─ build_rag_prompt(hits)
  │    └─ 編號 context 區塊 + 幻覺防護規則
  │
  ├─ LLMProvider.complete(system_prompt, question)
  │    ├─ temperature=0.1，model 由 LLM_MODEL 環境變數決定
  │    └─ 答案正規化為繁體中文（OpenCC s2twp）
  │
  ├─ format_citations(hits)
  │    ├─ { document_id, chunk_id, filename, chunk_index, snippet(≤200 字元),
  │    │    source_language, snippet_translated }
  │    └─ 跨語 snippet（chunk 語言 ≠ 提問語言）翻成提問語言；同語言 → snippet_translated=null
  │
  ├─ AgentRun INSERT（task_type="rag_chat", status, latency_ms, input_json, output_json）
  │    ├─ ToolCall INSERT（tool_name="hybrid_search", vector/keyword/fused counts, chunk_ids）
  │    ├─ 選用 ToolCall INSERT（tool_name="rerank", status, returned）
  │    └─ 選用 ToolCall INSERT（tool_name="translate", translated/failed counts）
  │
  └─ 回傳 ChatResponse  { answer, citations[] }
       citations 透過 chunk_id == document_chunks.id 對回 PostgreSQL
```

### Agent Chat

```
POST /projects/{id}/agent-chat  { question, top_k }
  │
  ├─ Project 404 防護
  │
  ├─ Agent 迴圈（≤ AGENT_MAX_STEPS）：LLMProvider.complete_with_tools(messages, [search_documents])
  │    ├─ 由 LLM 決定：直接作答，或呼叫 search_documents(query, strategy)
  │    │    strategy ∈ hybrid（預設）/ keyword（精確詞）/ vector（語意題）
  │    ├─ 每次呼叫 → HybridRetrievalService.search(..., strategy)；hits 餵回 LLM
  │    └─ LLM 作答即結束（stop_reason="completed"），或達到上限
  │         （stop_reason="max_steps"，強制以已取得結果作答）
  │
  ├─ 答案正規化為繁體中文；引用跨多次檢索去重後，再翻譯跨語 snippet（同 /chat）
  │
  ├─ AgentRun INSERT（task_type="agent_chat"；output_json 含 search_count, stop_reason）
  │    ├─ 每次檢索一筆 ToolCall INSERT（tool_name="search_documents", input {query, strategy}）
  │    └─ 選用 ToolCall INSERT（tool_name="translate"）
  │
  └─ 回傳 ChatResponse  { answer, citations[] }（shape 與 /chat 相同）
```

## 連接埠對應

| 服務 | 連接埠 |
|---|---|
| FastAPI 後端 | 8000 |
| React 前端（Vite + TypeScript + Tailwind） | 8501 |
| PostgreSQL + pgvector | 5432 |

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

`/agent-chat` 另需 provider 實作 `complete_with_tools(messages, tools)`（tool-calling），
供 agent 迴圈使用。`MockLLMProvider` 會回傳確定性的 tool-call，讓 agent 流程在 CI 不需
真實模型即可跑完。LLM 輸出的簡體中文（答案與 `zh` 翻譯）會以 OpenCC `s2twp` 正規化為
繁體中文（台灣）。

> **雲端 vs 地端的範圍：** `openai` 路徑用於低設定成本的快速 POC；`ollama` 路徑則為
> 私有／地端情境預備好，讓 LLM 能在客戶網路內執行。注意目前這層抽象只涵蓋 **LLM**，
> embedding 仍由 `EMBEDDING_PROVIDER`（`openai` / `mock`）決定，因此要做到完全地端，
> 還需要一個本地 embedding provider（未來的 `EmbeddingProvider` 實作，模式與此相同）。
