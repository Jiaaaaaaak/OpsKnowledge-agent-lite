from __future__ import annotations

import logging
import time
import uuid
from collections import Counter
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import AgentRun
from app.models.analysis import ActionItem, IncidentAnalysis, Insight
from app.models.project import Project
from app.models.record import CleanedRecord
from app.services.analysis_constants import ACTION_ITEM_STATUS_OPEN
from app.services.llm_service import get_llm_provider
from app.tools.incident_analysis import (
    analyze_severity,
    classify_incidents,
    create_action_items,
    generate_insights,
)

logger = logging.getLogger(__name__)


class AnalyzeSummary(BaseModel):
    records_analyzed: int
    needs_review: int
    insights_created: int
    action_items_created: int


class AnalyzeResponse(BaseModel):
    agent_run_id: uuid.UUID
    status: str
    summary: AnalyzeSummary


def run_incident_analysis(project_id: uuid.UUID, db: Session) -> AnalyzeResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    analyzed_ids = {
        row[0]
        for row in db.query(IncidentAnalysis.record_id)
        .filter(IncidentAnalysis.project_id == project_id)
        .all()
    }
    records: list[CleanedRecord] = (
        db.query(CleanedRecord)
        .filter(CleanedRecord.project_id == project_id)
        .order_by(CleanedRecord.created_at)
        .all()
    )
    records_to_analyze = [r for r in records if r.id not in analyzed_ids]

    if not records_to_analyze:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No cleaned records to analyze. Upload tickets via "
                "POST /projects/{project_id}/upload/tickets first, or all records are already analyzed."
            ),
        )

    agent_run_id = uuid.uuid4()
    llm = get_llm_provider()
    model_name = "mock" if settings.llm_provider == "mock" else settings.llm_model

    total_start = time.monotonic()
    run_status = "success"
    error_message: str | None = None
    summary = AnalyzeSummary(
        records_analyzed=0, needs_review=0, insights_created=0, action_items_created=0
    )
    tool_names_run: list[str] = []

    try:
        cls_result = classify_incidents(db, llm, project_id, agent_run_id, records_to_analyze)
        tool_names_run.append(cls_result.tool_name)

        sev_result = analyze_severity(db, llm, project_id, agent_run_id, records_to_analyze)
        tool_names_run.append(sev_result.tool_name)

        analyses_created = 0
        category_counter: Counter[str] = Counter()
        high_severity_samples: list[dict[str, Any]] = []
        needs_review_total = 0

        for record in records_to_analyze:
            rid = str(record.id)
            cat = cls_result.output["classifications"].get(rid)
            sev = sev_result.output["severities"].get(rid)
            if cat is None or sev is None:
                continue

            db.add(
                IncidentAnalysis(
                    project_id=project_id,
                    record_id=record.id,
                    category=cat,
                    severity_score=Decimal(str(sev["severity_score"])),
                    sentiment_score=Decimal(str(sev["sentiment_score"])),
                    confidence=Decimal(str(sev["confidence"])),
                    needs_review=bool(sev["needs_review"]),
                    reason=sev["reason"],
                )
            )
            analyses_created += 1
            category_counter[cat] += 1
            if sev["needs_review"]:
                needs_review_total += 1
            if int(sev["severity_score"]) >= 4:
                high_severity_samples.append(
                    {
                        "ticket_id": record.ticket_id,
                        "category": cat,
                        "severity": int(sev["severity_score"]),
                    }
                )

        aggregation = {
            "category_counts": dict(category_counter),
            "high_severity_samples": high_severity_samples,
            "total_analyzed": analyses_created,
        }
        ins_result = generate_insights(db, llm, project_id, agent_run_id, aggregation)
        tool_names_run.append(ins_result.tool_name)

        insights_created = 0
        for ins in ins_result.output["insights"]:
            db.add(
                Insight(
                    project_id=project_id,
                    title=ins["title"][:500],
                    summary=ins["summary"],
                    evidence=ins.get("evidence", []),
                    recommendation=ins["recommendation"],
                )
            )
            insights_created += 1

        ai_result = create_action_items(
            db, llm, project_id, agent_run_id, ins_result.output["insights"]
        )
        tool_names_run.append(ai_result.tool_name)

        action_items_created = 0
        for ai in ai_result.output["action_items"]:
            db.add(
                ActionItem(
                    project_id=project_id,
                    title=ai["title"][:500],
                    description=ai["description"],
                    priority=ai["priority"],
                    owner_role=ai["owner_role"],
                    status=ACTION_ITEM_STATUS_OPEN,
                )
            )
            action_items_created += 1

        summary = AnalyzeSummary(
            records_analyzed=analyses_created,
            needs_review=needs_review_total,
            insights_created=insights_created,
            action_items_created=action_items_created,
        )

        all_success = (
            cls_result.success
            and sev_result.success
            and ins_result.success
            and ai_result.success
        )
        if not all_success:
            run_status = "partial"
            error_message = next(
                (
                    r.error
                    for r in (cls_result, sev_result, ins_result, ai_result)
                    if r.error
                ),
                None,
            )
    except Exception as exc:
        logger.exception("analyze_incidents orchestrator failed")
        run_status = "error"
        error_message = str(exc)

    latency_ms = int((time.monotonic() - total_start) * 1000)

    db.add(
        AgentRun(
            id=agent_run_id,
            project_id=project_id,
            task_type="analyze_incidents",
            model_name=model_name,
            input_json={
                "project_id": str(project_id),
                "record_count": len(records_to_analyze),
            },
            output_json={
                **summary.model_dump(),
                "tools_run": tool_names_run,
            },
            status=run_status,
            latency_ms=latency_ms,
            error_message=error_message,
        )
    )
    db.commit()

    if run_status == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message or "Agent run failed",
        )

    return AnalyzeResponse(agent_run_id=agent_run_id, status=run_status, summary=summary)
