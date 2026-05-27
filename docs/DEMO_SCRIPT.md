# Demo Script — OpsKnowledge Agent Lite

Total demo time: ~8 minutes.

---

## Setup (before demo)

1. `docker compose up --build` — all services running.
2. Open `http://localhost:8501` in browser.
3. Have sample PDF and incident CSV ready in `demo_data/`.

---

## Scene 1: Health Check (30s)

> "Let me show you the backend is running and connected."

```bash
curl http://localhost:8000/health | jq
```

Expected output:
```json
{"status":"ok","version":"0.1.0","db":"connected","chroma":"configured"}
```

---

## Scene 2: Upload a PDF (1.5 min)

> "We upload an IT SOP — for example, a network troubleshooting guide."

1. Go to **Upload** page.
2. Drag and drop `demo_data/documents/sample_sop.pdf`.
3. Show: parsed → chunked → embedded → stored in ChromaDB.

---

## Scene 3: Knowledge Q&A (1.5 min)

> "Now let's ask a question against the document."

1. Go to **Chat** page.
2. Type: `What is the escalation procedure for P1 incidents?`
3. Show RAG retrieval: top chunks highlighted, then LLM answer.

---

## Scene 4: Incident ETL (1.5 min)

> "We ingest raw incident tickets — often messy, inconsistent."

1. Go to **Upload** page → Incident Records tab.
2. Upload `demo_data/tickets/sample_incidents.csv`.
3. Show: normalized rows in PostgreSQL, cleaned category/severity fields.

---

## Scene 5: AI Analysis (1.5 min)

> "Now we run AI-powered classification and severity scoring."

1. Go to **Dashboard** page.
2. Trigger analysis run.
3. Show: each incident gets `predicted_category`, `severity_score`, `insight`, `action_items`.

---

## Scene 6: Agent Logs / Observability (1 min)

> "Every AI call is logged — model, tokens, latency, result."

1. Go to **Agent Logs** page.
2. Show table: run_type, model, prompt_tokens, completion_tokens, latency_ms.
3. Highlight: "This is how you audit AI decisions in production."

---

## Talking Points

- **LLMProvider abstraction**: Swap OpenAI for Ollama by changing `.env` — no code change.
- **PostgreSQL for observability**: Full audit trail, queryable, exportable.
- **ChromaDB for RAG**: Semantic retrieval over private documents without fine-tuning.
- **Modular services**: Each service can be scaled or replaced independently.
