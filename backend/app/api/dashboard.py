"""
Dashboard 與可觀測性 API。

- GET /projects/{project_id}/dashboard
    一次回傳專案層級摘要：tickets / category / severity / needs_review /
    top insights / open action items / recent agent runs。純 SQL 聚合，
    不呼叫 LLM，確保快速且結果可重現。

- GET /projects/{project_id}/agent-runs
    列出該 project 的所有 agent_runs（最新優先）。

- GET /agent-runs/{agent_run_id}/tool-calls
    列出某次 agent_run 對應的所有 tool_calls（依 created_at 升冪 = 執行順序）。
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import cast, desc, func
from sqlalchemy.dialects.postgresql import INTEGER
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agent import AgentRun, ToolCall
from app.models.analysis import ActionItem, IncidentAnalysis, Insight
from app.models.document import Document, DocumentChunk
from app.models.project import Project
from app.models.record import CleanedRecord
from app.schemas.agent import AgentRunRead, ToolCallRead
from app.services.analysis_constants import ACTION_ITEM_STATUS_OPEN

router = APIRouter(tags=["Dashboard"])


# ── Response schemas ─────────────────────────────────────────


class CategoryBucket(BaseModel):
    category: str
    count: int


class SeverityBucket(BaseModel):
    severity: int
    count: int


class InsightBrief(BaseModel):
    id: uuid.UUID
    title: str
    summary: str
    recommendation: str


class AnalysisInsightBrief(InsightBrief):
    evidence: list[Any]


class ActionItemBrief(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    priority: str
    owner_role: str
    status: str


class AgentRunBrief(BaseModel):
    id: uuid.UUID
    task_type: str
    model_name: str
    status: str
    latency_ms: int | None
    created_at: Any  # 由 SQLAlchemy 帶來 datetime；Pydantic 自動序列化


class DashboardResponse(BaseModel):
    project_id: uuid.UUID
    ticket_count: int
    category_distribution: list[CategoryBucket]
    severity_distribution: list[SeverityBucket]
    needs_review_count: int
    top_insights: list[InsightBrief]
    open_action_items: list[ActionItemBrief]
    recent_agent_runs: list[AgentRunBrief]


class AnalysisResultRun(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID | None
    task_type: str
    model_name: str
    status: str
    latency_ms: int | None
    created_at: Any
    error_message: str | None


class AnalysisResultSummary(BaseModel):
    records_analyzed: int = 0
    needs_review: int = 0
    insights_created: int = 0
    action_items_created: int = 0


class AnalysisRunResultResponse(BaseModel):
    run: AnalysisResultRun
    summary: AnalysisResultSummary
    insights: list[AnalysisInsightBrief]
    action_items: list[ActionItemBrief]


class EventWorkflowStatus(BaseModel):
    cleaned_ticket_count: int
    analyzed_ticket_count: int
    unanalyzed_ticket_count: int
    latest_run_id: uuid.UUID | None
    latest_run_status: str | None


class KnowledgeWorkflowStatus(BaseModel):
    document_count: int
    total_pages: int
    total_chunks: int
    can_chat: bool


class WorkflowStatusResponse(BaseModel):
    project_id: uuid.UUID
    event: EventWorkflowStatus
    knowledge: KnowledgeWorkflowStatus


# ── Helper ───────────────────────────────────────────────────


def _project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


# ── GET /projects/{project_id}/dashboard ─────────────────────


@router.get(
    "/projects/{project_id}/dashboard",
    response_model=DashboardResponse,
    summary="Project-level aggregated dashboard (PostgreSQL only, no LLM call)",
)
def get_dashboard(
    project_id: uuid.UUID,
    insights_limit: int = Query(default=5, ge=1, le=50),
    action_items_limit: int = Query(default=10, ge=1, le=100),
    agent_runs_limit: int = Query(default=5, ge=1, le=50),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    _project_or_404(db, project_id)

    ticket_count = (
        db.query(func.count(CleanedRecord.id))
        .filter(CleanedRecord.project_id == project_id)
        .scalar()
        or 0
    )

    category_rows = (
        db.query(IncidentAnalysis.category, func.count(IncidentAnalysis.id))
        .filter(IncidentAnalysis.project_id == project_id)
        .group_by(IncidentAnalysis.category)
        .order_by(desc(func.count(IncidentAnalysis.id)), IncidentAnalysis.category)
        .all()
    )
    category_distribution = [
        CategoryBucket(category=cat, count=cnt) for cat, cnt in category_rows
    ]

    # severity_score 是 Numeric(5,4)；以整數 bucket 聚合
    severity_expr = cast(IncidentAnalysis.severity_score, INTEGER)
    severity_rows = (
        db.query(severity_expr.label("sev"), func.count(IncidentAnalysis.id))
        .filter(IncidentAnalysis.project_id == project_id)
        .group_by(severity_expr)
        .order_by(severity_expr)
        .all()
    )
    severity_distribution = [
        SeverityBucket(severity=int(sev), count=cnt) for sev, cnt in severity_rows
    ]

    needs_review_count = (
        db.query(func.count(IncidentAnalysis.id))
        .filter(
            IncidentAnalysis.project_id == project_id,
            IncidentAnalysis.needs_review.is_(True),
        )
        .scalar()
        or 0
    )

    top_insights_rows = (
        db.query(Insight)
        .filter(Insight.project_id == project_id)
        .order_by(Insight.created_at.desc())
        .limit(insights_limit)
        .all()
    )
    top_insights = [
        InsightBrief(
            id=i.id, title=i.title, summary=i.summary, recommendation=i.recommendation
        )
        for i in top_insights_rows
    ]

    open_action_items_rows = (
        db.query(ActionItem)
        .filter(ActionItem.project_id == project_id, ActionItem.status == ACTION_ITEM_STATUS_OPEN)
        .order_by(ActionItem.created_at.desc())
        .limit(action_items_limit)
        .all()
    )
    open_action_items = [
        ActionItemBrief(
            id=a.id,
            title=a.title,
            description=a.description,
            priority=a.priority,
            owner_role=a.owner_role,
            status=a.status,
        )
        for a in open_action_items_rows
    ]

    recent_agent_runs_rows = (
        db.query(AgentRun)
        .filter(AgentRun.project_id == project_id)
        .order_by(AgentRun.created_at.desc())
        .limit(agent_runs_limit)
        .all()
    )
    recent_agent_runs = [
        AgentRunBrief(
            id=r.id,
            task_type=r.task_type,
            model_name=r.model_name,
            status=r.status,
            latency_ms=r.latency_ms,
            created_at=r.created_at,
        )
        for r in recent_agent_runs_rows
    ]

    return DashboardResponse(
        project_id=project_id,
        ticket_count=int(ticket_count),
        category_distribution=category_distribution,
        severity_distribution=severity_distribution,
        needs_review_count=int(needs_review_count),
        top_insights=top_insights,
        open_action_items=open_action_items,
        recent_agent_runs=recent_agent_runs,
    )


@router.get(
    "/agent-runs/{agent_run_id}/analysis-result",
    response_model=AnalysisRunResultResponse,
    summary="Get run-specific incident analysis result",
)
def get_analysis_run_result(
    agent_run_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> AnalysisRunResultResponse:
    run = db.query(AgentRun).filter(AgentRun.id == agent_run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent run not found",
        )

    insights = (
        db.query(Insight)
        .filter(Insight.agent_run_id == agent_run_id)
        .order_by(Insight.created_at.asc())
        .all()
    )
    action_items = (
        db.query(ActionItem)
        .filter(ActionItem.agent_run_id == agent_run_id)
        .order_by(ActionItem.created_at.asc())
        .all()
    )
    output = run.output_json or {}

    return AnalysisRunResultResponse(
        run=AnalysisResultRun(
            id=run.id,
            project_id=run.project_id,
            task_type=run.task_type,
            model_name=run.model_name,
            status=run.status,
            latency_ms=run.latency_ms,
            created_at=run.created_at,
            error_message=run.error_message,
        ),
        summary=AnalysisResultSummary(
            records_analyzed=int(output.get("records_analyzed", 0) or 0),
            needs_review=int(output.get("needs_review", 0) or 0),
            insights_created=int(output.get("insights_created", 0) or 0),
            action_items_created=int(output.get("action_items_created", 0) or 0),
        ),
        insights=[
            AnalysisInsightBrief(
                id=i.id,
                title=i.title,
                summary=i.summary,
                evidence=i.evidence,
                recommendation=i.recommendation,
            )
            for i in insights
        ],
        action_items=[
            ActionItemBrief(
                id=a.id,
                title=a.title,
                description=a.description,
                priority=a.priority,
                owner_role=a.owner_role,
                status=a.status,
            )
            for a in action_items
        ],
    )


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

    cleaned_count = (
        db.query(func.count(CleanedRecord.id))
        .filter(CleanedRecord.project_id == project_id)
        .scalar()
        or 0
    )
    analyzed_count = (
        db.query(func.count(IncidentAnalysis.id))
        .filter(IncidentAnalysis.project_id == project_id)
        .scalar()
        or 0
    )
    latest_run = (
        db.query(AgentRun)
        .filter(AgentRun.project_id == project_id, AgentRun.task_type == "analyze_incidents")
        .order_by(AgentRun.created_at.desc())
        .first()
    )
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
        event=EventWorkflowStatus(
            cleaned_ticket_count=int(cleaned_count),
            analyzed_ticket_count=int(analyzed_count),
            unanalyzed_ticket_count=max(int(cleaned_count) - int(analyzed_count), 0),
            latest_run_id=latest_run.id if latest_run else None,
            latest_run_status=latest_run.status if latest_run else None,
        ),
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
