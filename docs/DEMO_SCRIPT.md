# Demo Script — OpsKnowledge Agent Lite

English | [繁體中文](DEMO_SCRIPT.zh-TW.md)

Total demo time: **~3 minutes** (tight script) / ~8 minutes (full walkthrough).

---

## Setup (before demo, ~1 min — not counted in demo time)

1. `cp .env.example .env` — defaults are mock mode (no API key needed).
2. `docker compose up --build` — wait until `opsknowledge_backend` reports
   `Uvicorn running on http://0.0.0.0:8000`.
3. Smoke check: `curl http://localhost:8000/health` → `{"db":"connected","chroma":"connected"}`.
4. Open `http://localhost:8501` in browser.
5. Have ready:
   - A PDF in `demo_data/documents/` (any IT SOP / manual)
   - `demo_data/tickets/sample_incidents.csv` (ships with the repo)

---

## 3-minute demo script

### Scene 1 · Project Setup (15s)

> "First I create a project — every upload, chat, and analysis is scoped to a project."

- Sidebar → **Project Setup**
- Create new: name `IT Operations Demo` → **Create**
- The active project chip in the sidebar updates immediately.

### Scene 2 · Upload PDF + Tickets (35s)

> "Two kinds of data go in: SOP PDFs for RAG, and incident tickets for analysis."

- Sidebar → **Upload**
- Tab **PDF Documents** → upload `demo_data/documents/<sop>.pdf` → **Upload PDF**
  → success card shows `chunk_count` and `page_count`.
- Tab **Incident Tickets** → upload `sample_incidents.csv` → **Upload Tickets**
  → metrics row shows `raw_count`, `cleaned_count`, `failed_count`.

> Talking point: "PDF is chunked → embedded → ChromaDB. Tickets are normalized via
> column-synonym mapping into `cleaned_records`. Both happen behind one upload click."

### Scene 3 · Knowledge Chat (RAG) (30s)

> "Now I can ask the SOP a question. The model is only allowed to answer from
> retrieved chunks — if the PDF doesn't cover it, it refuses rather than fabricating."

- Sidebar → **Knowledge Chat**
- Ask: `What should I check if a Docker volume disappears after restart?`
- The answer renders, followed by an expandable citation per chunk
  (filename · chunk_index · snippet).

> Talking point: "Every chat call writes one `agent_runs` row and one
> `tool_calls` row for the vector retrieval — fully auditable."

### Scene 4 · Incident Analysis Agent (40s)

> "This is the agent. One button fires a 4-tool pipeline that classifies, scores,
> generates insights, and produces action items — all with structured-JSON output
> validated by Pydantic."

- Sidebar → **Incident Analysis** → **▶️ Run Incident Analysis**
- 4 metrics appear: `records_analyzed`, `needs_review`, `insights_created`,
  `action_items_created`.

> Talking point: "`needs_review` flags tickets where the LLM confidence < 0.65 —
> that's the human-in-the-loop queue. Not a decoration; it's an operational input."

### Scene 5 · Dashboard (30s)

> "Read-only aggregation, pure SQL, no LLM call — this is what the ops lead sees."

- Sidebar → **Dashboard**
- Walk through: ticket count, needs_review count, category bar chart, severity
  bar chart, top insights (expandable), open action items table, recent agent runs.

> Talking point: "Same `agent_runs` table powers both Chat observability and this
> 'recent runs' panel — one log surface, two views."

### Scene 6 · Agent Logs / Observability (30s)

> "And here's how I prove what the agent actually did. Every run is queryable."

- Sidebar → **Agent Logs**
- Top table lists all `agent_runs` (chat + analyze).
- Select the most recent `analyze_incidents` run.
- Show drill-down: status, latency, model, then expand each of the 4 tool calls
  → input_json / output_json / per-tool latency / error_message if any.

> Closing line: "Black-box LLM agent turned into a system you can debug after the
> fact: pick a run, see every tool's exact input and output, find the validation
> failure if any. That's what makes it shippable."

---

## Talking Points (use any if questions arise)

- **LLMProvider abstraction** — `LLM_PROVIDER=openai | ollama | mock` swaps the
  backend with no application code change. The same UI runs against a hosted API,
  a local Ollama box, or fully offline mock providers.
- **Idempotent agent run** — re-running `/analyze/incidents` only processes
  records not yet in `incident_analysis`. Never deletes prior analysis.
- **Pydantic at the LLM boundary** — every structured output is validated; failures
  are surfaced into `tool_calls.error_message`, not silently swallowed (Rule 12).
- **Schema stability** — Prompt 10 (Dashboard) and Prompt 11 (this UI) added zero
  new columns / tables; everything is a read view over the existing 10 tables.
- **Dashboard read/write split** — Dashboard endpoint never calls the LLM. Fast,
  deterministic, safe to auto-refresh.

---

## Backup plan if something fails live

| Failure | Fallback |
|---|---|
| ChromaDB down | Skip Scene 3 (Chat); the rest of the flow still works |
| OpenAI quota exhausted | Already on mock mode by default — no risk |
| Upload fails on a custom PDF | Use the public-domain PDF you pre-staged in `demo_data/documents/` |
| Demo machine offline | The whole stack runs offline in mock mode — no external dependency |
