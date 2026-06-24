"""
Workflow status 與可觀測性 API。

- GET /projects/{project_id}/workflow-status
    回傳該專案的知識庫就緒狀態（文件數 / 頁數 / chunk 數 / 是否可問答）。
    純 SQL 聚合，不呼叫 LLM。

- GET /projects/{project_id}/agent-runs
    列出該 project 的所有 agent_runs（最新優先）。

- GET /agent-runs/{agent_run_id}/tool-calls
    列出某次 agent_run 對應的所有 tool_calls（依 created_at 升冪 = 執行順序）。
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import cast, func
from sqlalchemy.dialects.postgresql import INTEGER
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agent import AgentRun, ToolCall
from app.models.document import Document, DocumentChunk
from app.models.project import Project
from app.schemas.agent import AgentRunRead, ToolCallRead

router = APIRouter(tags=["Dashboard"])


# ── Response schemas ─────────────────────────────────────────


class KnowledgeWorkflowStatus(BaseModel):
    document_count: int
    total_pages: int
    total_chunks: int
    can_chat: bool


class WorkflowStatusResponse(BaseModel):
    project_id: uuid.UUID
    knowledge: KnowledgeWorkflowStatus


# ── Helper ───────────────────────────────────────────────────


def _project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


# ── GET /projects/{project_id}/workflow-status ───────────────


@router.get(
    "/projects/{project_id}/workflow-status",
    response_model=WorkflowStatusResponse,
    summary="Get project workflow readiness status",
)
def get_workflow_status(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> WorkflowStatusResponse:
    _project_or_404(db, project_id)

    document_count = (
        db.query(func.count(Document.id))
        .filter(Document.project_id == project_id)
        .scalar()
        or 0
    )
    page_total = (
        db.query(func.coalesce(func.sum(cast(Document.metadata_["page_count"].astext, INTEGER)), 0))
        .filter(Document.project_id == project_id)
        .scalar()
        or 0
    )
    chunk_total = (
        db.query(func.count(DocumentChunk.id))
        .join(Document, DocumentChunk.document_id == Document.id)
        .filter(Document.project_id == project_id)
        .scalar()
        or 0
    )

    return WorkflowStatusResponse(
        project_id=project_id,
        knowledge=KnowledgeWorkflowStatus(
            document_count=int(document_count),
            total_pages=int(page_total),
            total_chunks=int(chunk_total),
            can_chat=int(document_count) > 0 and int(chunk_total) > 0,
        ),
    )


# ── GET /projects/{project_id}/agent-runs ────────────────────


@router.get(
    "/projects/{project_id}/agent-runs",
    response_model=list[AgentRunRead],
    summary="List agent runs for a project (most recent first)",
)
def list_agent_runs(
    project_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[AgentRun]:
    _project_or_404(db, project_id)
    return (
        db.query(AgentRun)
        .filter(AgentRun.project_id == project_id)
        .order_by(AgentRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


# ── GET /agent-runs/{agent_run_id}/tool-calls ────────────────


@router.get(
    "/agent-runs/{agent_run_id}/tool-calls",
    response_model=list[ToolCallRead],
    summary="List tool calls for an agent run (in execution order)",
)
def list_tool_calls(
    agent_run_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[ToolCall]:
    run = db.query(AgentRun).filter(AgentRun.id == agent_run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent run not found"
        )
    return (
        db.query(ToolCall)
        .filter(ToolCall.agent_run_id == agent_run_id)
        .order_by(ToolCall.created_at.asc())
        .all()
    )
