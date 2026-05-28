# Product Requirements Document — OpsKnowledge Agent Lite

English | [繁體中文](PRD.zh-TW.md)

## Problem

IT/Operations teams manage large volumes of technical documentation (manuals, SOPs) and incident records (tickets, maintenance logs), but:

1. Knowledge is siloed in PDFs — hard to search and query.
2. Incident data is inconsistent across systems — different formats, missing fields.
3. There is no AI-assisted triage, classification, or insight generation.
4. No auditability for AI decisions — hard to debug or trust outputs.

## Target Users

| User | Role |
|---|---|
| IT Operations Engineer | Uploads SOPs, queries knowledge base, reviews AI analysis |
| System Integration Engineer | Uploads incident CSVs, reviews ETL output and severity scores |
| Team Lead / Manager | Reviews dashboard summaries and action items |
| (Demo) AI/Data Engineer Interviewer | Evaluates system design and code quality |

## MVP Scope

### Included

- [x] Upload PDF documents → parse → chunk → embed → store in ChromaDB
- [x] Semantic search / RAG Q&A over documents
- [x] Upload CSV/Excel/JSON incident records → ETL → PostgreSQL
- [x] AI classification of incident category
- [x] AI severity scoring (P1–P4)
- [x] AI insight generation and action item suggestions
- [x] Logging of every AI call to PostgreSQL (model, tokens, latency, result)
- [x] Streamlit dashboard: Upload / Chat / Dashboard / Agent Logs
- [x] Docker Compose deployment (PostgreSQL, ChromaDB, backend, frontend)

### Out of Scope (for this POC)

- User authentication / multi-tenant access control
- Real-time streaming of AI responses
- Production-grade vector DB (Pinecone, Weaviate, pgvector)
- Fine-tuning or custom models
- Automated alerting / PagerDuty integration
- Mobile UI

## Success Criteria

1. `/health` endpoint returns `{"status": "ok"}` with DB connected.
2. A PDF can be uploaded, chunked, and queried via semantic search.
3. A CSV of incidents can be uploaded, cleaned, and stored in PostgreSQL.
4. AI correctly classifies and scores at least 80% of sample incidents.
5. Every AI invocation is recorded with model name, tokens, and latency.
6. Demo can be walked through end-to-end in under 10 minutes.
