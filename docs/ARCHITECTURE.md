# Architecture — OpsKnowledge Agent Lite

English | [繁體中文](ARCHITECTURE.zh-TW.md)

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
POST /projects/{id}/upload/documents
  │
  ├─ Extension validation (.pdf only)
  │
  ├─ _extract_pages()  pypdf.PdfReader → [(page_num, text), ...]
  │    └─ Non-text PDF (scanned image) → 400 Bad Request
  │
  ├─ _save_file()  write to data/uploads/{project_id}/documents/{filename}
  │
  ├─ documents INSERT (filename, document_type="pdf", source_path, metadata.page_count)
  │
  ├─ Per-page _chunk_text()  sliding window (chunk_size=1000, overlap=150)
  │    └─ Each chunk → document_chunks INSERT
  │         metadata: { filename, page_number, chunk_size }
  │
  └─ Return DocumentIngestionResult
       { document_id, filename, page_count, chunk_count, source_path }

Query → embed question → ChromaDB similarity search → top-k chunks → LLM answer
(embedding pipeline to be implemented in Step 4)
```

### Incident ETL + AI Analysis

```
POST /projects/{id}/upload/tickets
  │
  ├─ Extension validation (.csv / .xlsx / .json)
  │
  ├─ Format parsing
  │    ├─ CSV  → stdlib csv.DictReader
  │    ├─ JSON → stdlib json.loads (supports list / wrapped object / single object)
  │    └─ XLSX → openpyxl (lazy import)
  │
  ├─ Per-row processing
  │    ├─ RawRecord INSERT (raw data, regardless of validation outcome)
  │    ├─ normalize_columns()  column synonym mapping → standard column names
  │    ├─ CleanedTicket(Pydantic)  strip / empty→None / required validation / defaults
  │    │    ├─ Success → CleanedRecord INSERT
  │    │    └─ Failure → append to errors[], raw_records still retained
  │    └─ db.commit()
  │
  └─ Return TicketImportSummary
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
