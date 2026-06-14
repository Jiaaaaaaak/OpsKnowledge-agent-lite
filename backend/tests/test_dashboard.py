"""
Dashboard / observability API 測試。

覆蓋：
- DashboardResponse Pydantic schema validation（CategoryBucket / SeverityBucket / 整體聚合形狀）
- GET /projects/{id}/dashboard happy path 與 404
- GET /projects/{id}/dashboard 空專案回傳合理零值
- GET /projects/{id}/agent-runs 路由與 404
- GET /agent-runs/{id}/tool-calls 路由與 404
- query 參數驗證（limit 範圍）
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dashboard import (
    ActionItemBrief,
    AgentRunBrief,
    CategoryBucket,
    DashboardResponse,
    InsightBrief,
    SeverityBucket,
)
from app.db.session import get_db
from app.main import app
from app.models.agent import AgentRun, ToolCall
from app.models.analysis import ActionItem, IncidentAnalysis, Insight
from app.models.project import Project
from app.models.record import CleanedRecord

_NOW = datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────
# Response schema
# ──────────────────────────────────────────────────────────────


class TestResponseSchemas:
    def test_category_bucket_accepts_str_count(self):
        b = CategoryBucket(category="network_issue", count=20)
        assert b.category == "network_issue"
        assert b.count == 20

    def test_severity_bucket_accepts_int_severity(self):
        b = SeverityBucket(severity=5, count=3)
        assert b.severity == 5

    def test_dashboard_response_assembles(self):
        resp = DashboardResponse(
            project_id=uuid.uuid4(),
            ticket_count=100,
            category_distribution=[CategoryBucket(category="network_issue", count=20)],
            severity_distribution=[SeverityBucket(severity=5, count=3)],
            needs_review_count=4,
            top_insights=[],
            open_action_items=[],
            recent_agent_runs=[],
        )
        assert resp.ticket_count == 100
        assert resp.category_distribution[0].count == 20


# ──────────────────────────────────────────────────────────────
# 共用：建構 db.query side_effect
# 依被查詢的「物件」分流回傳預先設定好的 chain mock
# ──────────────────────────────────────────────────────────────


class _FakeProject:
    def __init__(self, project_id: uuid.UUID | None = None) -> None:
        self.id = project_id or uuid.uuid4()
        self.name = "Demo"


def _chain_returning(value):
    """製造一個無論呼叫 .filter/.order_by/.group_by/.limit/.offset/... 最後 .all/.scalar/.first 都回傳 value 的 mock 鏈。"""
    m = MagicMock()
    m.filter.return_value = m
    m.order_by.return_value = m
    m.group_by.return_value = m
    m.join.return_value = m
    m.limit.return_value = m
    m.offset.return_value = m
    m.all.return_value = value if isinstance(value, list) else []
    m.scalar.return_value = value if isinstance(value, int) else 0
    m.first.return_value = value if not isinstance(value, (list, int)) else None
    return m


def _make_db_with_dashboard_data(
    project: _FakeProject | None,
    ticket_count: int = 0,
    category_rows: list[tuple[str, int]] | None = None,
    severity_rows: list[tuple[int, int]] | None = None,
    needs_review_count: int = 0,
    insights: list[Insight] | None = None,
    action_items: list[ActionItem] | None = None,
    agent_runs: list[AgentRun] | None = None,
):
    """db.query() 依參數型別分流。順序：Project / func.count(...) 各種 / Model 物件。"""
    db = MagicMock()

    # 為 func.count 系列的 .scalar() 結果準備一個 FIFO（依 endpoint 內呼叫順序）
    scalar_queue = [ticket_count, needs_review_count]

    def _side_effect(*args, **_kwargs):
        # 由參數推斷查的是什麼
        if len(args) == 1 and args[0] is Project:
            return _chain_returning(project)
        # 多參數時：第一個若為 IncidentAnalysis.category → category 聚合
        first = args[0]
        if first is IncidentAnalysis.category:
            return _chain_returning(category_rows or [])
        if first is CleanedRecord:
            return _chain_returning([])
        if first is Insight:
            return _chain_returning(insights or [])
        if first is ActionItem:
            return _chain_returning(action_items or [])
        if first is AgentRun:
            return _chain_returning(agent_runs or [])
        # severity_distribution：第一個參數是一個帶 label("sev") 的 cast 表達式
        try:
            if getattr(first, "name", "") == "sev":
                return _chain_returning(severity_rows or [])
        except Exception:
            pass
        # 其餘視為 func.count（ticket_count / needs_review_count）走 scalar
        m = _chain_returning(0)
        m.scalar.return_value = scalar_queue.pop(0) if scalar_queue else 0
        return m

    db.query = MagicMock(side_effect=_side_effect)
    return db


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def _override_db(db):
    def _get():
        yield db

    return _get


# ──────────────────────────────────────────────────────────────
# GET /projects/{id}/dashboard
# ──────────────────────────────────────────────────────────────


def _insight(title="Top: network_issue"):
    i = MagicMock(spec=Insight)
    i.id = uuid.uuid4()
    i.title = title
    i.summary = "summary"
    i.evidence = [{"ticket_id": "INC-001"}]
    i.recommendation = "recommendation"
    i.created_at = _NOW
    return i


def _action_item(priority="high", status="open"):
    a = MagicMock(spec=ActionItem)
    a.id = uuid.uuid4()
    a.title = "Action: investigate"
    a.description = "desc"
    a.priority = priority
    a.owner_role = "ops_lead"
    a.status = status
    a.created_at = _NOW
    return a


def _agent_run(task_type="analyze_incidents", status="success"):
    r = MagicMock(spec=AgentRun)
    r.id = uuid.uuid4()
    r.project_id = uuid.uuid4()
    r.task_type = task_type
    r.model_name = "mock"
    r.input_json = {}
    r.output_json = {}
    r.status = status
    r.latency_ms = 42
    r.error_message = None
    r.created_at = _NOW
    r.updated_at = _NOW
    return r


def test_dashboard_happy_path(client):
    project_id = uuid.uuid4()
    db = _make_db_with_dashboard_data(
        project=_FakeProject(project_id),
        ticket_count=100,
        category_rows=[("network_issue", 20), ("storage_issue", 15)],
        severity_rows=[(1, 5), (3, 30), (5, 3)],
        needs_review_count=4,
        insights=[_insight("Top: network_issue"), _insight("High severity patterns")],
        action_items=[_action_item("high"), _action_item("medium")],
        agent_runs=[_agent_run(), _agent_run(task_type="rag_chat")],
    )
    app.dependency_overrides[get_db] = _override_db(db)

    response = client.get(f"/projects/{project_id}/dashboard")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["project_id"] == str(project_id)
    assert body["ticket_count"] == 100
    assert body["needs_review_count"] == 4

    assert body["category_distribution"] == [
        {"category": "network_issue", "count": 20},
        {"category": "storage_issue", "count": 15},
    ]
    assert body["severity_distribution"] == [
        {"severity": 1, "count": 5},
        {"severity": 3, "count": 30},
        {"severity": 5, "count": 3},
    ]
    assert len(body["top_insights"]) == 2
    assert body["top_insights"][0]["title"] == "Top: network_issue"
    assert len(body["open_action_items"]) == 2
    assert {a["priority"] for a in body["open_action_items"]} == {"high", "medium"}
    assert len(body["recent_agent_runs"]) == 2
    assert body["recent_agent_runs"][1]["task_type"] == "rag_chat"


def test_dashboard_empty_project_returns_zero_counts(client):
    project_id = uuid.uuid4()
    db = _make_db_with_dashboard_data(project=_FakeProject(project_id))
    app.dependency_overrides[get_db] = _override_db(db)

    response = client.get(f"/projects/{project_id}/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["ticket_count"] == 0
    assert body["needs_review_count"] == 0
    assert body["category_distribution"] == []
    assert body["severity_distribution"] == []
    assert body["top_insights"] == []
    assert body["open_action_items"] == []
    assert body["recent_agent_runs"] == []


def test_dashboard_severity_supports_decimal_cast(client):
    # severity_score 在 DB 是 Numeric(5,4) — 端點以 cast(...,INTEGER) 聚合，
    # 但若上游 driver 仍丟 Decimal/float，回傳 schema 必須能 coerce 成 int
    project_id = uuid.uuid4()
    db = _make_db_with_dashboard_data(
        project=_FakeProject(project_id),
        severity_rows=[(Decimal("4"), 2), (5.0, 1)],
    )
    app.dependency_overrides[get_db] = _override_db(db)
    response = client.get(f"/projects/{project_id}/dashboard")
    assert response.status_code == 200
    assert response.json()["severity_distribution"] == [
        {"severity": 4, "count": 2},
        {"severity": 5, "count": 1},
    ]


def test_dashboard_returns_404_when_project_missing(client):
    db = _make_db_with_dashboard_data(project=None)
    app.dependency_overrides[get_db] = _override_db(db)
    response = client.get(f"/projects/{uuid.uuid4()}/dashboard")
    assert response.status_code == 404


def test_dashboard_invalid_uuid_returns_422(client):
    response = client.get("/projects/not-a-uuid/dashboard")
    assert response.status_code == 422


def test_dashboard_rejects_out_of_range_limit(client):
    response = client.get(f"/projects/{uuid.uuid4()}/dashboard?insights_limit=999")
    assert response.status_code == 422


# ──────────────────────────────────────────────────────────────
# GET /projects/{id}/agent-runs
# ──────────────────────────────────────────────────────────────


def test_list_agent_runs_happy_path(client):
    project_id = uuid.uuid4()
    runs = [_agent_run(), _agent_run(task_type="rag_chat", status="error")]
    db = _make_db_with_dashboard_data(project=_FakeProject(project_id), agent_runs=runs)
    app.dependency_overrides[get_db] = _override_db(db)

    response = client.get(f"/projects/{project_id}/agent-runs")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[1]["status"] == "error"


def test_list_agent_runs_returns_404_when_project_missing(client):
    db = _make_db_with_dashboard_data(project=None)
    app.dependency_overrides[get_db] = _override_db(db)
    response = client.get(f"/projects/{uuid.uuid4()}/agent-runs")
    assert response.status_code == 404


def test_list_agent_runs_rejects_out_of_range_pagination(client):
    response = client.get(f"/projects/{uuid.uuid4()}/agent-runs?limit=10000")
    assert response.status_code == 422


# ──────────────────────────────────────────────────────────────
# GET /agent-runs/{id}/tool-calls
# ──────────────────────────────────────────────────────────────


def _tool_call(name: str):
    t = MagicMock(spec=ToolCall)
    t.id = uuid.uuid4()
    t.agent_run_id = uuid.uuid4()
    t.tool_name = name
    t.input_json = {}
    t.output_json = {}
    t.error_message = None
    t.latency_ms = 12
    t.created_at = _NOW
    t.updated_at = _NOW
    return t


def test_list_tool_calls_happy_path(client):
    run = _agent_run()
    tool_calls = [_tool_call("classify_incidents"), _tool_call("analyze_severity")]

    db = MagicMock()

    def _side_effect(*args, **_kwargs):
        first = args[0]
        if first is AgentRun:
            return _chain_returning(run)
        if first is ToolCall:
            return _chain_returning(tool_calls)
        return _chain_returning([])

    db.query = MagicMock(side_effect=_side_effect)
    app.dependency_overrides[get_db] = _override_db(db)

    response = client.get(f"/agent-runs/{run.id}/tool-calls")
    assert response.status_code == 200
    body = response.json()
    assert [t["tool_name"] for t in body] == ["classify_incidents", "analyze_severity"]


def test_list_tool_calls_returns_404_when_run_missing(client):
    db = MagicMock()
    db.query = MagicMock(side_effect=lambda *a, **k: _chain_returning(None))
    app.dependency_overrides[get_db] = _override_db(db)

    response = client.get(f"/agent-runs/{uuid.uuid4()}/tool-calls")
    assert response.status_code == 404


def test_list_tool_calls_invalid_uuid_returns_422(client):
    response = client.get("/agent-runs/not-a-uuid/tool-calls")
    assert response.status_code == 422


# ──────────────────────────────────────────────────────────────
# GET /agent-runs/{id}/analysis-result
# ──────────────────────────────────────────────────────────────


def test_analysis_run_result_happy_path(client):
    run = _agent_run()
    run.output_json = {
        "records_analyzed": 8,
        "needs_review": 2,
        "insights_created": 1,
        "action_items_created": 1,
    }
    insights = [_insight("Top: storage_issue")]
    action_items = [_action_item("high")]

    db = MagicMock()

    def _side_effect(*args, **_kwargs):
        first = args[0]
        if first is AgentRun:
            return _chain_returning(run)
        if first is Insight:
            return _chain_returning(insights)
        if first is ActionItem:
            return _chain_returning(action_items)
        return _chain_returning([])

    db.query = MagicMock(side_effect=_side_effect)
    app.dependency_overrides[get_db] = _override_db(db)

    response = client.get(f"/agent-runs/{run.id}/analysis-result")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["run"]["id"] == str(run.id)
    assert body["run"]["status"] == "success"
    assert body["summary"] == {
        "records_analyzed": 8,
        "needs_review": 2,
        "insights_created": 1,
        "action_items_created": 1,
    }
    assert body["insights"][0]["title"] == "Top: storage_issue"
    assert body["insights"][0]["evidence"] == [{"ticket_id": "INC-001"}]
    assert body["action_items"][0]["priority"] == "high"


def test_analysis_run_result_returns_404_when_run_missing(client):
    db = MagicMock()
    db.query = MagicMock(side_effect=lambda *a, **k: _chain_returning(None))
    app.dependency_overrides[get_db] = _override_db(db)

    response = client.get(f"/agent-runs/{uuid.uuid4()}/analysis-result")
    assert response.status_code == 404


# ──────────────────────────────────────────────────────────────
# GET /projects/{id}/workflow-status
# ──────────────────────────────────────────────────────────────


def test_workflow_status_happy_path(client):
    project_id = uuid.uuid4()
    latest_run = _agent_run()
    latest_run.id = uuid.uuid4()
    latest_run.status = "success"
    scalar_queue = [10, 7, 2, 12, 25]
    db = MagicMock()

    def _side_effect(*args, **_kwargs):
        first = args[0]
        if first is Project:
            return _chain_returning(_FakeProject(project_id))
        if first is AgentRun:
            return _chain_returning(latest_run)
        q = _chain_returning(0)
        q.scalar.return_value = scalar_queue.pop(0)
        return q

    db.query = MagicMock(side_effect=_side_effect)
    app.dependency_overrides[get_db] = _override_db(db)

    response = client.get(f"/projects/{project_id}/workflow-status")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["project_id"] == str(project_id)
    assert body["event"] == {
        "cleaned_ticket_count": 10,
        "analyzed_ticket_count": 7,
        "unanalyzed_ticket_count": 3,
        "latest_run_id": str(latest_run.id),
        "latest_run_status": "success",
    }
    assert body["knowledge"] == {
        "document_count": 2,
        "total_pages": 12,
        "total_chunks": 25,
        "can_chat": True,
    }


def test_workflow_status_returns_404_when_project_missing(client):
    db = MagicMock()

    def _side_effect(*args, **_kwargs):
        if args[0] is Project:
            return _chain_returning(None)
        return _chain_returning(0)

    db.query = MagicMock(side_effect=_side_effect)
    app.dependency_overrides[get_db] = _override_db(db)

    response = client.get(f"/projects/{uuid.uuid4()}/workflow-status")
    assert response.status_code == 404
