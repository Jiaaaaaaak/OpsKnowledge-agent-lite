# Reranker Two-Stage Retrieval Implementation Plan (Plan B)

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. Implement task-by-task; keep the test suite green after every task.

**Goal:** Add a second-stage **reranker** (cross-encoder `BAAI/bge-reranker-v2-m3`, served by HuggingFace TEI) to the RAG retrieval pipeline. Stage 1 recalls `candidate_k` chunks from pgvector; stage 2 reranks them and keeps the final `top_k` for the LLM. The feature is **opt-in** (config-gated) and **degrades gracefully** to vector-only if the reranker is disabled or unreachable, so CI and the existing 154-test suite are unaffected.

**Why:** Per the reranker reference (ihower.tw/blog/12227), a cross-encoder reorders candidates far more accurately than embedding distance alone — even a weaker first stage + reranker beats single-stage retrieval. `bge-reranker-v2-m3` is open-source, self-hostable, and multilingual (matches the cross-lingual story: English docs + Chinese questions), and is the same BGE-M3 family as the Plan A embedding (`bge-m3`).

**Prerequisite:** Plan A merged/active (Ollama `bge-m3` embedding, `vector(1024)`, cross-lingual recall working on branch `rag-multilingual-rerank`). Reranker only improves *ordering*; it cannot recover a relevant chunk that stage-1 never recalled, so Plan A must be in place first.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL + pgvector, Ollama (`bge-m3`), HuggingFace **text-embeddings-inference (TEI)** serving `bge-reranker-v2-m3`, Docker Compose, pytest.

---

## Architecture

```text
question ──> [stage 1] pgvector cosine recall  (candidate_k, e.g. 30)
                 │  VectorStoreService.search(project_id, q, candidate_k)
                 ▼
            [stage 2] TEI /rerank  (bge-reranker-v2-m3, cross-encoder)
                 │  RerankerProvider.rerank(q, [chunk.content ...])
                 ▼
            take top_k (e.g. 5) ──> build_rag_prompt ──> LLM (Ollama qwen2.5)

observability: ToolCall("vector_search") + ToolCall("rerank") under one AgentRun
fallback:      reranker disabled OR error  ->  keep stage-1 order, slice top_k
```

- **New container** `reranker` (TEI) — Ollama cannot serve cross-encoders.
- **New module** `app/services/reranker_service.py` — `RerankerProvider` abstraction with a TEI implementation and a no-op fallback, mirroring the existing `embedding_service` / `llm_service` provider pattern.
- **Config-gated** by `RERANKER_ENABLED` (default `false`). Default-off keeps `pytest` and `LLM_PROVIDER=mock` CI runs unchanged.

## File Structure

- Modify `docker-compose.yml`: add `reranker` service + `reranker_data` volume; backend `depends_on` + `RERANKER_BASE_URL` override.
- Modify `backend/app/core/config.py`: add reranker settings.
- Create `backend/app/services/reranker_service.py`: `RerankerProvider` ABC, `TeiRerankerProvider`, `NoopRerankerProvider`, `get_reranker_provider()`.
- Modify `backend/app/services/chat_service.py`: two-stage retrieval + `rerank` ToolCall + fallback.
- Modify `.env` and `.env.example`: `RERANKER_*` vars (documented, safe default off).
- Modify `Makefile`: optional `logs-reranker` target + note that TEI self-downloads the model.
- Create `backend/tests/test_reranker_service.py`: provider parsing/sorting/factory/error tests (mock httpx).
- Modify `backend/tests/test_chat.py`: two-stage-enabled, fallback, and default-disabled paths.

No change needed to `vector_store.py` (its `search(..., top_k)` is reused with `candidate_k`) or to the `document_chunks` schema.

---

## Task 1: Add Reranker Configuration

**Files:** `backend/app/core/config.py`, `.env.example`, `.env`

- [ ] **Step 1: Add settings fields** (after the Ollama block in `config.py`):

```python
    # Reranker (second-stage cross-encoder via HF text-embeddings-inference)
    reranker_enabled: bool = False
    reranker_base_url: str = "http://localhost:8080"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_candidate_k: int = 30          # stage-1 recall count before reranking
    reranker_timeout_seconds: float = 30.0
```

- [ ] **Step 2: Document in `.env.example`** (new section), defaulting OFF so a fresh clone runs without the extra container:

```bash
# ── Reranker (optional second-stage retrieval) ───────────────────────────────
# When true, recall RERANK_CANDIDATE_K chunks from pgvector, then rerank with
# bge-reranker-v2-m3 (served by the `reranker` TEI container) and keep top_k.
# Leave false to use single-stage vector retrieval (no extra container needed).
RERANKER_ENABLED=false
RERANKER_BASE_URL=http://localhost:8080
# Docker Compose overrides RERANKER_BASE_URL for the backend container.
DOCKER_RERANKER_BASE_URL=http://reranker:80
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANK_CANDIDATE_K=30
RERANKER_TIMEOUT_SECONDS=30
```

- [ ] **Step 3: Mirror keys into local `.env`** (set `RERANKER_ENABLED=true` only after Task 4’s container is up).

- [ ] **Step 4: Verify** — `cd backend && PYTHONPATH=. python -c "from app.core.config import settings; print(settings.reranker_enabled, settings.rerank_candidate_k)"` prints `False 30`.

## Task 2: Reranker Provider Module

**Files:** Create `backend/app/services/reranker_service.py`

- [ ] **Step 1: Implement provider abstraction + TEI + no-op**:

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.config import settings


class RerankerProvider(ABC):
    @abstractmethod
    def rerank(self, query: str, documents: list[str]) -> list[tuple[int, float]]:
        """Return [(original_index, score), ...] sorted by relevance desc."""


class NoopRerankerProvider(RerankerProvider):
    """Identity reranker — preserves stage-1 order. Used when disabled / in CI."""

    def rerank(self, query: str, documents: list[str]) -> list[tuple[int, float]]:
        return [(i, 0.0) for i in range(len(documents))]


class TeiRerankerProvider(RerankerProvider):
    """Calls HF text-embeddings-inference /rerank (bge-reranker-v2-m3)."""

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self._base_url = (base_url or settings.reranker_base_url).rstrip("/")
        self._timeout = timeout if timeout is not None else settings.reranker_timeout_seconds

    def rerank(self, query: str, documents: list[str]) -> list[tuple[int, float]]:
        if not documents:
            return []
        import httpx

        url = f"{self._base_url}/rerank"
        try:
            resp = httpx.post(
                url,
                json={"query": query, "texts": documents},
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Reranker 回傳錯誤狀態 {exc.response.status_code}：請確認 TEI 已載入 "
                f"{settings.reranker_model}。"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"無法連線到 reranker（{url}）：請確認 reranker 容器已啟動。原始錯誤：{exc}"
            ) from exc

        # TEI returns [{"index": i, "score": s}, ...] sorted by score desc
        data = resp.json()
        return [(int(item["index"]), float(item["score"])) for item in data]


def get_reranker_provider() -> RerankerProvider:
    if settings.reranker_enabled:
        return TeiRerankerProvider()
    return NoopRerankerProvider()
```

- [ ] **Step 2: Verify** — `cd backend && PYTHONPATH=. python -m compileall -q app` passes.

## Task 3: Wire Two-Stage Retrieval Into Chat

**Files:** `backend/app/services/chat_service.py`

- [ ] **Step 1: Recall `candidate_k`, then rerank to `top_k`.** Replace the single `store.search(...)` call with a recall + rerank block, threaded through the existing `retrieval_ms` timing:

```python
candidate_k = settings.rerank_candidate_k if settings.reranker_enabled else body.top_k
hits = store.search(str(project_id), body.question, candidate_k)

rerank_status = "disabled"
rerank_ms = 0
if settings.reranker_enabled and hits:
    rerank_start = time.monotonic()
    try:
        ranked = get_reranker_provider().rerank(body.question, [h["content"] for h in hits])
        hits = [{**hits[idx], "rerank_score": score} for idx, score in ranked][: body.top_k]
        rerank_status = "success"
    except Exception:
        hits = hits[: body.top_k]          # graceful fallback: keep vector order
        rerank_status = "fallback"
    rerank_ms = int((time.monotonic() - rerank_start) * 1000)
else:
    hits = hits[: body.top_k]
```

- [ ] **Step 2: Record a `rerank` ToolCall** under the same `AgentRun` (only when reranking ran), so it surfaces in Agent Runs / tool-calls:

```python
if rerank_status in ("success", "fallback"):
    db.add(ToolCall(
        agent_run_id=agent_run_id,
        tool_name="rerank",
        input_json={"candidate_k": candidate_k, "top_k": body.top_k, "model": settings.reranker_model},
        output_json={"status": rerank_status, "returned": len(hits)},
        latency_ms=rerank_ms,
    ))
```

- [ ] **Step 3: Add the import** `from app.services.reranker_service import get_reranker_provider`.

- [ ] **Step 4: Verify** — `PYTHONPATH=. pytest tests/test_chat.py -q` passes (default disabled = unchanged behavior).

## Task 4: Add the TEI Reranker Container

**Files:** `docker-compose.yml`, `.env`

- [ ] **Step 1: Add the service + volume**:

```yaml
  reranker:
    image: ghcr.io/huggingface/text-embeddings-inference:cpu-1.5
    container_name: opsknowledge_reranker
    restart: unless-stopped
    command: ["--model-id", "BAAI/bge-reranker-v2-m3"]
    ports:
      - "8080:80"
    volumes:
      - reranker_data:/data    # model cache; first start downloads ~2GB
```

Add `reranker_data:` under top-level `volumes:`.

- [ ] **Step 2: Let the backend reach it** — under `backend.environment` add:

```yaml
      RERANKER_BASE_URL: ${DOCKER_RERANKER_BASE_URL:-http://reranker:80}
```

> **Caveat:** the TEI CPU image may not ship `curl`/`wget`, so a compose `healthcheck` is unreliable; prefer **no** `depends_on: condition: service_healthy` for reranker. The app already tolerates a cold/missing reranker via the Task 3 fallback. GPU users can switch to `ghcr.io/huggingface/text-embeddings-inference:1.5` (CUDA) for much lower latency.

- [ ] **Step 3: Bring it up and sanity-check `/rerank`**:

```bash
docker compose up -d reranker
# wait for first-time model download, then:
curl -fsS http://localhost:8080/rerank \
  -H 'Content-Type: application/json' \
  -d '{"query":"how to restart the database","texts":["重啟資料庫服務的步驟","unrelated billing policy"]}'
```

Expected: JSON array where the Chinese DB-restart text gets the higher score and `index` 0.

- [ ] **Step 4: Enable + restart backend** — set `RERANKER_ENABLED=true` in `.env`, then `docker compose up -d backend` (recreate so env_file is re-read; `restart` alone does not pick up `.env` changes).

## Task 5: Tests

**Files:** Create `backend/tests/test_reranker_service.py`; modify `backend/tests/test_chat.py`

- [ ] **Step 1: Reranker provider unit tests** (mock `httpx.post`):
  - `NoopRerankerProvider` returns identity order.
  - `TeiRerankerProvider.rerank` parses `[{"index","score"}]` and preserves TEI’s order; empty input → no HTTP call.
  - `get_reranker_provider()` returns Noop when `reranker_enabled=False`, TEI when `True`.
  - HTTP status / connection errors raise `RuntimeError` with actionable message.

- [ ] **Step 2: Chat two-stage tests**:
  - Enabled: stage-1 recall `candidate_k`, mocked reranker reorders, final length == `top_k`, a `rerank` ToolCall is recorded.
  - Fallback: reranker raises → answer still returns, hits = vector order sliced to `top_k`, ToolCall status `fallback`.
  - Disabled (default): no `rerank` ToolCall, behavior identical to pre-Plan-B.

- [ ] **Step 3: Verify** — `PYTHONPATH=. pytest tests/ -q` stays green (≥ 154 + new tests) with `RERANKER_ENABLED` unset/false.

## Task 6: End-to-End Verification

- [ ] **Step 1:** Upload an English PDF to a project (UI or `uploadDocument`).
- [ ] **Step 2:** Ask a Chinese operational question; confirm a coherent Chinese answer with citations.
- [ ] **Step 3:** Open **Agent Runs → tool-calls** for that run; confirm both `vector_search` and `rerank` ToolCalls appear, with `rerank` showing `candidate_k`/`top_k`/`status`.
- [ ] **Step 4:** Toggle `RERANKER_ENABLED=false`, recreate backend, re-ask; confirm it still answers (single-stage) — proves graceful degradation.

---

## Risks / Notes

- **Resources:** one extra container + ~2GB model download. CPU reranking of ~30 candidates adds latency (hundreds of ms to seconds); the existing 180s LLM timeout absorbs it. Lower `RERANK_CANDIDATE_K` (e.g. 20) for demos; raise it for accuracy.
- **Default-off is load-bearing:** keep `RERANKER_ENABLED=false` as the shipped default so CI, `make test`, and mock-mode demos need no reranker container.
- **Fallback is mandatory:** never let a reranker outage break chat — Task 3 must slice stage-1 order on any reranker exception.
- **Sequencing:** Tasks 1–3 + 5 are pure backend (testable without the container). Task 4 introduces infra. Land them as one feature commit or split (code first, then compose) — each must leave the suite green.

## Final Recommendation

Implement on the current `rag-multilingual-rerank` branch after Plan A is verified end-to-end. Ship with `RERANKER_ENABLED=false`; enable it in the demo `.env` once the container is healthy. Treat the `rerank` ToolCall as a deliberate observability feature — it visibly demonstrates two-stage retrieval in the Agent Runs UI.
