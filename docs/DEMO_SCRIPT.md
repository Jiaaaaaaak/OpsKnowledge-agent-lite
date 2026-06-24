# Demo Script — OpsKnowledge Agent Lite

English | [繁體中文](DEMO_SCRIPT.zh-TW.md)

Total demo time: **~3 minutes** (tight script) / ~5 minutes (full walkthrough).

---

## Setup (before demo, ~1 min — not counted in demo time)

1. `cp .env.example .env` — defaults to Ollama LLM + mock embeddings.
2. `docker compose up --build -d` — wait until `opsknowledge_backend` reports
   `Uvicorn running on http://0.0.0.0:8000`.
3. `docker compose exec ollama ollama pull qwen2.5:7b-instruct` — pull the local model.
4. Smoke check: `curl http://localhost:8000/health` → `{"db":"connected","vector":"connected"}`.
5. Open `http://localhost:8501` in browser.
6. Have ready:
   - A PDF in `demo_data/documents/` (any IT SOP / manual)

---

## 3-minute demo script

### Scene 1 · Project Setup (15s)

> "First I create a project — every upload and chat is scoped to a project."

- Sidebar → **Project Setup**
- Create new: name `IT Operations Demo` → **Create**
- The active project chip in the sidebar updates immediately.

### Scene 2 · Upload PDF Documents (30s)

> "SOP PDFs go in for RAG. Each page is chunked, embedded, and stored in PostgreSQL + pgvector."

- Sidebar → **Knowledge Workflow**
- Upload `demo_data/documents/<sop>.pdf`
  → success card shows `chunk_count` and `page_count`.

> Talking point: "PDF is chunked → embedded → PostgreSQL + pgvector. One upload click,
> fully indexed and ready for hybrid search."

### Scene 3 · Knowledge Chat (RAG) (40s)

> "Now I can ask the SOP a question. The model is only allowed to answer from
> retrieved chunks — if the PDF doesn't cover it, it refuses rather than fabricating."

- In the workflow page, the chat step becomes active.
- Ask: `What should I check if a Docker volume disappears after restart?`
- The answer renders, followed by an expandable citation per chunk
  (filename · chunk_index · snippet).

> Talking point: "Every chat call writes one `agent_runs` row and one
> `tool_calls` row for the vector retrieval — fully auditable."

### Scene 4 · Agent Runs / Observability (30s)

> "Here's how I prove what the agent actually did. Every run is queryable."

- Sidebar → **Agent Runs**
- Top table lists all `agent_runs` (chat runs).
- Select the most recent `rag_chat` run.
- Show drill-down: status, latency, model, then expand the `hybrid_search` tool call
  → input_json / output_json / latency.

> Closing line: "Black-box LLM agent turned into a system you can debug after the
> fact: pick a run, see the exact retrieval input and output. That's what makes it shippable."

### Scene 5 · System Status (15s)

> "Quick health check — the system status page shows all backend service connectivity."

- Sidebar → **System Status**
- Show DB, vector, and API health indicators.

### Scene 6 · Provider Switchability (15s)

> "One last thing — the LLM and embedding providers are fully pluggable."

- Show `.env` file: `LLM_PROVIDER=ollama`, `EMBEDDING_PROVIDER=mock`.
- Explain: switch to `openai` or `mock` by changing `.env` only, no code changes.

---

## Talking Points (use any if questions arise)

- **Local-first LLMProvider abstraction** — default interview mode is
  `LLM_PROVIDER=ollama` with `EMBEDDING_PROVIDER=mock`. The same UI can still switch
  to hosted OpenAI or fully deterministic mock providers with `.env` only.
- **Pydantic at the LLM boundary** — every structured output is validated; failures
  are surfaced into `tool_calls.error_message`, not silently swallowed (Rule 12).
- **Observability read/write split** — workflow-status endpoint never calls the LLM. Fast,
  deterministic, safe to auto-refresh.
- **Provider switchability** — `mock`, `ollama`, `openai` — one `.env` change, no code change.

---

## Backup plan if something fails live

| Failure | Fallback |
|---|---|
| PostgreSQL + pgvector down | Skip Scene 3 (Chat); show the upload and observability pages |
| Ollama model missing | Run `docker compose exec ollama ollama pull qwen2.5:7b-instruct`; switch `LLM_PROVIDER=mock` if you need an immediate fallback |
| Upload fails on a custom PDF | Use the public-domain PDF you pre-staged in `demo_data/documents/` |
| Demo machine offline | Ollama + mock embeddings run locally once the model is already pulled |
