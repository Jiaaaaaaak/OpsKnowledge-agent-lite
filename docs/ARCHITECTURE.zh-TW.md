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

```python
class LLMProvider:
    # Configured via OPENAI_BASE_URL — works with:
    # - OpenAI:  https://api.openai.com/v1
    # - Ollama:  http://localhost:11434/v1  (OpenAI-compatible endpoint)
```

切換供應商只需修改 `.env`，不需更動任何程式碼。
