import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.agent import AgentRun, ToolCall
from app.models.project import Project
from app.schemas.chat import ChatRequest, ChatResponse, Citation
from app.services.llm_service import OpenAICompatibleLLMProvider, build_rag_prompt, format_citations
from app.services.vector_store import get_vector_store

router = APIRouter(prefix="/projects", tags=["Chat"])


@router.post(
    "/{project_id}/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="RAG-based Q&A over a project's embedded documents",
)
def chat(
    project_id: uuid.UUID,
    body: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    total_start = time.monotonic()

    # Step 1: 從 ChromaDB 取回相關 chunk
    retrieval_start = time.monotonic()
    try:
        store = get_vector_store()
        hits = store.search(str(project_id), body.question, body.top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    retrieval_ms = int((time.monotonic() - retrieval_start) * 1000)

    # Step 2: 組裝 RAG prompt
    system_prompt = build_rag_prompt(hits)

    # Step 3: 呼叫 LLM
    llm = OpenAICompatibleLLMProvider()
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

    # Step 4: 格式化引用
    citation_dicts = format_citations(hits)
    citations = [Citation(**c) for c in citation_dicts]

    # 可觀測性：寫入 agent_run + tool_call（成功或失敗皆記錄）
    agent_run_id = uuid.uuid4()
    agent_run = AgentRun(
        id=agent_run_id,
        project_id=project_id,
        task_type="rag_chat",
        model_name=settings.llm_model,
        input_json={"question": body.question, "top_k": body.top_k},
        output_json={"answer": answer, "citation_count": len(citations), "llm_ms": llm_ms, **usage},
        status=llm_status,
        latency_ms=total_ms,
        error_message=llm_error,
    )
    db.add(agent_run)

    tool_call = ToolCall(
        agent_run_id=agent_run_id,
        tool_name="vector_search",
        input_json={"query": body.question, "top_k": body.top_k, "project_id": str(project_id)},
        output_json={"hit_count": len(hits), "chunk_ids": [h["chunk_id"] for h in hits]},
        latency_ms=retrieval_ms,
    )
    db.add(tool_call)
    db.commit()

    if llm_status == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=llm_error or "LLM provider error",
        )

    return ChatResponse(answer=answer, citations=citations)
