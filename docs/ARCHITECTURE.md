# Architecture — OpsKnowledge Agent Lite

## Overview

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

## Component Responsibilities

| Component | Responsibility |
|---|---|
| `api/` | Route definitions, request validation, response serialization |
| `services/document_service.py` | PDF parsing, chunking, embedding, ChromaDB storage |
| `services/etl_service.py` | CSV/Excel/JSON ingestion, normalization, PostgreSQL insertion |
| `services/ai_service.py` | Orchestrates LLM tool calls for classification, scoring, insights |
| `services/log_service.py` | Records every AI run to `ai_run_log` table |
| `tools/` | Individual AI tool definitions (structured function call specs) |
| `db/session.py` | SQLAlchemy engine, session factory, `get_db` dependency |
| `core/config.py` | All configuration via environment variables (Pydantic Settings) |
| `LLMProvider` | Abstraction over OpenAI SDK — supports OpenAI or Ollama base URL |

## Data Flow

### Document RAG
```
PDF Upload → pdfplumber parse → text chunks → OpenAI embeddings → ChromaDB
Query → embed question → ChromaDB similarity search → top-k chunks → LLM answer
```

### Incident ETL + AI Analysis

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

## Port Map

| Service | Port |
|---|---|
| FastAPI backend | 8000 |
| Streamlit frontend | 8501 |
| PostgreSQL | 5432 |
| ChromaDB | 8001 |

## LLMProvider Design

```python
class LLMProvider:
    # Configured via OPENAI_BASE_URL — works with:
    # - OpenAI:  https://api.openai.com/v1
    # - Ollama:  http://localhost:11434/v1  (OpenAI-compatible endpoint)
```

Switching between providers requires only `.env` changes, no code changes.
