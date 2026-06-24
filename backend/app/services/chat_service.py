import time
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import AgentRun, ToolCall
from app.models.project import Project
from app.schemas.chat import ChatRequest, ChatResponse, Citation
from app.services.llm_service import (
    build_rag_prompt,
    detect_language,
    format_citations,
    get_llm_provider,
    translate_snippet,
)
from app.services.reranker_service import get_reranker_provider
from app.services.retrieval import get_retrieval_service


def run_rag_chat(project_id: uuid.UUID, body: ChatRequest, db: Session) -> ChatResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    total_start = time.monotonic()

    # 第一階段：hybrid 召回。啟用 reranker 時多召回 candidate_k 筆供精排。
    candidate_k = settings.rerank_candidate_k if settings.reranker_enabled else body.top_k
    retrieval_start = time.monotonic()
    try:
        retrieval = get_retrieval_service(db_session=db)
        hits, retrieval_breakdown = retrieval.search(str(project_id), body.question, top_k=candidate_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    retrieval_ms = int((time.monotonic() - retrieval_start) * 1000)

    # 第二階段：cross-encoder 精排。reranker 掛掉時降級為向量順序，不讓 chat 失敗。
    rerank_status = "disabled"
    rerank_ms = 0
    if settings.reranker_enabled and hits:
        rerank_start = time.monotonic()
        try:
            ranked = get_reranker_provider().rerank(body.question, [h["content"] for h in hits])
            hits = [{**hits[idx], "rerank_score": score} for idx, score in ranked][: body.top_k]
            rerank_status = "success"
        except Exception:
            hits = hits[: body.top_k]
            rerank_status = "fallback"
        rerank_ms = int((time.monotonic() - rerank_start) * 1000)
    else:
        hits = hits[: body.top_k]

    system_prompt = build_rag_prompt(hits)
    llm = get_llm_provider()
    llm_start = time.monotonic()
    llm_status = "error"
    llm_error: str | None = None
    answer = ""
    usage: dict = {}
    try:
        answer, usage = llm.complete(system_prompt, body.question)
        llm_status = "success"
    except Exception as exc:
        llm_error = str(exc)
    llm_ms = int((time.monotonic() - llm_start) * 1000)
    total_ms = int((time.monotonic() - total_start) * 1000)

    # 跨語翻譯：偵測提問語言，對「原文語言 ≠ 提問語言」的引用，逐 chunk 將 snippet
    # 翻成提問語言塞進 snippet_translated；同語言不翻。翻譯掛掉時該筆留 None，不讓 chat 失敗。
    citation_dicts = format_citations(hits)
    query_language = detect_language(body.question)
    translate_ms = 0
    translated_count = 0
    translate_failed = 0
    cross_lingual = [c for c in citation_dicts if c["snippet"] and c["source_language"] != query_language]
    if cross_lingual:
        translate_start = time.monotonic()
        for citation in cross_lingual:
            try:
                citation["snippet_translated"] = translate_snippet(
                    citation["snippet"], query_language, provider=llm
                )
                translated_count += 1
            except Exception:
                translate_failed += 1
        translate_ms = int((time.monotonic() - translate_start) * 1000)

    citations = [Citation(**c) for c in citation_dicts]

    agent_run_id = uuid.uuid4()
    db.add(
        AgentRun(
            id=agent_run_id,
            project_id=project_id,
            task_type="rag_chat",
            model_name="mock" if settings.llm_provider == "mock" else settings.llm_model,
            input_json={"question": body.question, "top_k": body.top_k},
            output_json={"answer": answer, "citation_count": len(citations), "llm_ms": llm_ms, **usage},
            status=llm_status,
            latency_ms=total_ms,
            error_message=llm_error,
        )
    )
    db.add(
        ToolCall(
            agent_run_id=agent_run_id,
            tool_name="hybrid_search",
            input_json={"query": body.question, "top_k": candidate_k, "project_id": str(project_id)},
            output_json={
                **retrieval_breakdown,
                "hit_count": len(hits),
                "chunk_ids": [h["chunk_id"] for h in hits],
            },
            latency_ms=retrieval_ms,
        )
    )
    if rerank_status in ("success", "fallback"):
        db.add(
            ToolCall(
                agent_run_id=agent_run_id,
                tool_name="rerank",
                input_json={
                    "candidate_k": candidate_k,
                    "top_k": body.top_k,
                    "model": settings.reranker_model,
                },
                output_json={"status": rerank_status, "returned": len(hits)},
                latency_ms=rerank_ms,
            )
        )
    if cross_lingual:
        db.add(
            ToolCall(
                agent_run_id=agent_run_id,
                tool_name="translate",
                input_json={
                    "target_language": query_language,
                    "candidate_count": len(cross_lingual),
                },
                output_json={
                    "status": "fallback" if translate_failed else "success",
                    "translated": translated_count,
                    "failed": translate_failed,
                },
                latency_ms=translate_ms,
            )
        )
    db.commit()

    if llm_status == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=llm_error or "LLM provider error",
        )

    return ChatResponse(answer=answer, citations=citations)
