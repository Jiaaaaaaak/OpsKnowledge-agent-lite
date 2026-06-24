import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.agent_service import run_agent_chat
from app.services.chat_service import run_rag_chat

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
    return run_rag_chat(project_id, body, db)


@router.post(
    "/{project_id}/agent-chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Autonomous agent Q&A: the LLM decides whether/what/how to retrieve",
)
def agent_chat(
    project_id: uuid.UUID,
    body: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    return run_agent_chat(project_id, body, db)
