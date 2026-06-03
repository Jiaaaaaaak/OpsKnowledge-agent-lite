"""
Incident analysis agent tools.

四個工具：classify_incidents、analyze_severity、generate_insights、create_action_items。
每個工具：
  - 以 LLMProvider 取得結構化 JSON 輸出
  - 用 Pydantic 驗證輸出，驗證失敗則記錄 error 並把 tool call 標記為 failed
  - 寫入一筆 tool_calls，包含 input / output / error / latency_ms
  - 回傳 ToolResult 供 orchestrator 後續整合
"""
from __future__ import annotations

import json
import logging
import time
from collections import Counter
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.models.agent import ToolCall
from app.models.record import CleanedRecord
from app.services.ai_tasks import (
    AGENT_TASK_ACTION_ITEMS,
    AGENT_TASK_CLASSIFY,
    AGENT_TASK_INSIGHTS,
    AGENT_TASK_SEVERITY,
    agent_task_marker,
)
from app.services.llm_service import LLMProvider

logger = logging.getLogger(__name__)

CONFIDENCE_REVIEW_THRESHOLD = 0.65

CategoryLiteral = Literal[
    "network_issue",
    "storage_issue",
    "deployment_issue",
    "permission_issue",
    "security_issue",
    "performance_issue",
    "data_quality_issue",
    "unknown",
]

PriorityLiteral = Literal["low", "medium", "high"]


# ── Pydantic models（驗證 LLM 結構化輸出）────────────────────────

class ClassifyOutput(BaseModel):
    category: CategoryLiteral
    reason: str = ""


class SeverityOutput(BaseModel):
    severity_score: int = Field(ge=1, le=5)
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class InsightItem(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    summary: str
    evidence: list[Any] = Field(default_factory=list)
    recommendation: str


class InsightsOutput(BaseModel):
    insights: list[InsightItem]


class ActionItemOut(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str
    priority: PriorityLiteral
    owner_role: str


class ActionItemsOutput(BaseModel):
    action_items: list[ActionItemOut]


class ToolResult(BaseModel):
    """Tool 共用回傳結構。"""

    tool_name: str
    success: bool
    items_processed: int = 0
    error: str | None = None
    latency_ms: int = 0
    output: dict[str, Any] = Field(default_factory=dict)


# ── LLM JSON helper ──────────────────────────────────────────

def _extract_json(text: str) -> str:
    """從 LLM 回應抓出第一段 JSON object。容錯 [mock] 前綴與 ```json fenced block."""
    text = text.strip()
    if text.startswith("[mock]"):
        text = text[len("[mock]"):].strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON object in LLM output: {text[:200]!r}")
    return text[start : end + 1]


def _complete_structured(
    llm: LLMProvider,
    system_prompt: str,
    user_message: str,
    schema: type[BaseModel],
) -> BaseModel:
    raw, _ = llm.complete(system_prompt, user_message)
    return schema.model_validate_json(_extract_json(raw))


# ── Prompts（內含 <<AGENT_TASK:xxx>> 標記讓 MockLLMProvider 走確定性分支）──

_CLASSIFY_SYSTEM = (
    f"{agent_task_marker(AGENT_TASK_CLASSIFY)}\n"
    "You are an IT operations incident classifier. Read the incident and choose ONE category from:\n"
    "network_issue, storage_issue, deployment_issue, permission_issue, security_issue, "
    "performance_issue, data_quality_issue, unknown.\n\n"
    "Reply with ONLY a JSON object. The 'reason' field MUST be written in Traditional Chinese (繁體中文):\n"
    '{"category": "<one of the labels>", "reason": "<簡短原因，使用繁體中文>"}'
)

_SEVERITY_SYSTEM = (
    f"{agent_task_marker(AGENT_TASK_SEVERITY)}\n"
    "You are an IT operations severity analyst. For the given incident, output:\n"
    "- severity_score: integer 1..5\n"
    "- sentiment_score: float -1.0..1.0\n"
    "- confidence: float 0.0..1.0\n"
    "- reason: short justification\n\n"
    "Reply with ONLY a JSON object. The 'reason' field MUST be written in Traditional Chinese (繁體中文):\n"
    '{"severity_score": <int>, "sentiment_score": <float>, "confidence": <float>, "reason": "<簡短說明，使用繁體中文>"}'
)

_INSIGHTS_SYSTEM = (
    f"{agent_task_marker(AGENT_TASK_INSIGHTS)}\n"
    "You are an IT operations analyst. The user message contains category counts and high-severity "
    "ticket samples for a project. Generate project-level insights covering: top categories, "
    "recurring issues, high severity patterns, and operational risks.\n\n"
    "Reply with ONLY a JSON object. ALL text fields (title, summary, recommendation) MUST be written "
    "in Traditional Chinese (繁體中文):\n"
    '{"insights": [{"title": "...", "summary": "...", "evidence": [...], "recommendation": "..."}]}'
)

_ACTION_ITEMS_SYSTEM = (
    f"{agent_task_marker(AGENT_TASK_ACTION_ITEMS)}\n"
    "You are an IT operations planner. The user message contains a list of insights. Generate "
    "concrete action items derived from those insights.\n\n"
    "Reply with ONLY a JSON object. ALL text fields (title, description, owner_role) MUST be written "
    "in Traditional Chinese (繁體中文). The 'priority' field must remain in English (low|medium|high):\n"
    '{"action_items": [{"title": "...", "description": "...", '
    '"priority": "low|medium|high", "owner_role": "..."}]}'
)


# ── 內部：寫 tool_call 紀錄 ─────────────────────────────────────

def _log_tool_call(
    db: Session,
    agent_run_id: UUID,
    tool_name: str,
    input_json: dict,
    output_json: dict,
    error: str | None,
    latency_ms: int,
) -> None:
    db.add(
        ToolCall(
            agent_run_id=agent_run_id,
            tool_name=tool_name,
            input_json=input_json,
            output_json=output_json,
            error_message=error,
            latency_ms=latency_ms,
        )
    )


# ── Tool 1: classify_incidents ─────────────────────────────────

def classify_incidents(
    db: Session,
    llm: LLMProvider,
    project_id: UUID,
    agent_run_id: UUID,
    records: list[CleanedRecord],
) -> ToolResult:
    """為每筆 cleaned record 產生分類標籤。"""
    start = time.monotonic()
    classifications: dict[str, str] = {}
    reasons: dict[str, str] = {}
    failures: list[dict] = []

    for record in records:
        user_msg = json.dumps(
            {
                "ticket_id": record.ticket_id,
                "system": record.system,
                "module": record.module,
                "issue_description": record.issue_description,
            },
            ensure_ascii=False,
        )
        try:
            parsed = _complete_structured(llm, _CLASSIFY_SYSTEM, user_msg, ClassifyOutput)
        except (ValidationError, ValueError) as exc:
            logger.error("classify_incidents validation failed for record %s: %s", record.id, exc)
            failures.append({"record_id": str(record.id), "error": str(exc)})
            continue
        classifications[str(record.id)] = parsed.category
        reasons[str(record.id)] = parsed.reason

    latency_ms = int((time.monotonic() - start) * 1000)
    success = not failures
    category_counts = dict(Counter(classifications.values()))
    error_summary = "; ".join(f["error"] for f in failures[:3])[:500] if failures else None

    _log_tool_call(
        db,
        agent_run_id,
        "classify_incidents",
        input_json={"project_id": str(project_id), "record_count": len(records)},
        output_json={
            "classified": len(classifications),
            "failed": len(failures),
            "categories": category_counts,
        },
        error=error_summary,
        latency_ms=latency_ms,
    )

    return ToolResult(
        tool_name="classify_incidents",
        success=success,
        items_processed=len(classifications),
        error=error_summary,
        latency_ms=latency_ms,
        output={"classifications": classifications, "reasons": reasons, "failures": failures},
    )


# ── Tool 2: analyze_severity ───────────────────────────────────

def analyze_severity(
    db: Session,
    llm: LLMProvider,
    project_id: UUID,
    agent_run_id: UUID,
    records: list[CleanedRecord],
) -> ToolResult:
    """為每筆 cleaned record 評估 severity / sentiment / confidence。"""
    start = time.monotonic()
    severities: dict[str, dict[str, Any]] = {}
    failures: list[dict] = []
    needs_review_count = 0

    for record in records:
        user_msg = json.dumps(
            {
                "ticket_id": record.ticket_id,
                "issue_description": record.issue_description,
                "priority": record.priority,
            },
            ensure_ascii=False,
        )
        try:
            parsed = _complete_structured(llm, _SEVERITY_SYSTEM, user_msg, SeverityOutput)
        except (ValidationError, ValueError) as exc:
            logger.error("analyze_severity validation failed for record %s: %s", record.id, exc)
            failures.append({"record_id": str(record.id), "error": str(exc)})
            continue
        needs_review = parsed.confidence < CONFIDENCE_REVIEW_THRESHOLD
        if needs_review:
            needs_review_count += 1
        severities[str(record.id)] = {
            "severity_score": parsed.severity_score,
            "sentiment_score": parsed.sentiment_score,
            "confidence": parsed.confidence,
            "reason": parsed.reason,
            "needs_review": needs_review,
        }

    latency_ms = int((time.monotonic() - start) * 1000)
    success = not failures
    error_summary = "; ".join(f["error"] for f in failures[:3])[:500] if failures else None

    _log_tool_call(
        db,
        agent_run_id,
        "analyze_severity",
        input_json={"project_id": str(project_id), "record_count": len(records)},
        output_json={
            "scored": len(severities),
            "failed": len(failures),
            "needs_review": needs_review_count,
        },
        error=error_summary,
        latency_ms=latency_ms,
    )

    return ToolResult(
        tool_name="analyze_severity",
        success=success,
        items_processed=len(severities),
        error=error_summary,
        latency_ms=latency_ms,
        output={
            "severities": severities,
            "failures": failures,
            "needs_review": needs_review_count,
        },
    )


# ── Tool 3: generate_insights ──────────────────────────────────

def generate_insights(
    db: Session,
    llm: LLMProvider,
    project_id: UUID,
    agent_run_id: UUID,
    aggregation: dict[str, Any],
) -> ToolResult:
    """根據 incident_analysis 的聚合資料產生 project-level insights。"""
    start = time.monotonic()
    user_msg = json.dumps(aggregation, ensure_ascii=False)
    error: str | None = None
    items: list[InsightItem] = []

    try:
        parsed = _complete_structured(llm, _INSIGHTS_SYSTEM, user_msg, InsightsOutput)
        items = parsed.insights
    except (ValidationError, ValueError) as exc:
        logger.error("generate_insights validation failed: %s", exc)
        error = str(exc)

    latency_ms = int((time.monotonic() - start) * 1000)

    _log_tool_call(
        db,
        agent_run_id,
        "generate_insights",
        input_json={
            "project_id": str(project_id),
            "category_counts": aggregation.get("category_counts", {}),
            "high_severity_count": len(aggregation.get("high_severity_samples", [])),
        },
        output_json={"insights_count": len(items)},
        error=error,
        latency_ms=latency_ms,
    )

    return ToolResult(
        tool_name="generate_insights",
        success=error is None,
        items_processed=len(items),
        error=error,
        latency_ms=latency_ms,
        output={"insights": [i.model_dump() for i in items]},
    )


# ── Tool 4: create_action_items ────────────────────────────────

def create_action_items(
    db: Session,
    llm: LLMProvider,
    project_id: UUID,
    agent_run_id: UUID,
    insights: list[dict],
) -> ToolResult:
    """從 insights 衍生 actionable items。"""
    start = time.monotonic()
    user_msg = json.dumps({"insights": insights}, ensure_ascii=False)
    error: str | None = None
    items: list[ActionItemOut] = []

    try:
        parsed = _complete_structured(llm, _ACTION_ITEMS_SYSTEM, user_msg, ActionItemsOutput)
        items = parsed.action_items
    except (ValidationError, ValueError) as exc:
        logger.error("create_action_items validation failed: %s", exc)
        error = str(exc)

    latency_ms = int((time.monotonic() - start) * 1000)

    _log_tool_call(
        db,
        agent_run_id,
        "create_action_items",
        input_json={"project_id": str(project_id), "insight_count": len(insights)},
        output_json={"action_items_count": len(items)},
        error=error,
        latency_ms=latency_ms,
    )

    return ToolResult(
        tool_name="create_action_items",
        success=error is None,
        items_processed=len(items),
        error=error,
        latency_ms=latency_ms,
        output={"action_items": [i.model_dump() for i in items]},
    )
