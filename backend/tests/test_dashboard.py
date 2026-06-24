"""
Workflow status / observability API 測試。

覆蓋：
- GET /projects/{id}/workflow-status happy path 與 404
- GET /projects/{id}/agent-runs 路由、404 與 pagination 驗證
- GET /agent-runs/{id}/tool-calls 路由、404 與 422
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.agent import AgentRun, ToolCall
from app.models.project import Project

_NOW = datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────
# 共用：建構 db.query side_effect
# ──────────────────────────────────────────────────────────────


class _FakeProject:
    def __init__(self, project_id: uuid.UUID | None = None) -> None:
        self.id = project_id or uuid.uuid4()
        self.name = "Demo"


def _chain_returning(value):
    """製造一個無論呼叫 .filter/.order_by/.join/.limit/.offset/... 最後 .all/.scalar/.first 都回傳 value 的 mock 鏈。"""
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


def _agent_run(task_type="rag_chat", status="success"):
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


# ──────────────────────────────────────────────────────────────
# GET /projects/{id}/workflow-status
# ──────────────────────────────────────────────────────────────


def test_workflow_status_happy_path(client):
    project_id = uuid.uuid4()
    scalar_queue = [2, 12, 25]
    db = MagicMock()

    def _side_effect(*args, **_kwargs):
        first = args[0]
        if first is Project:
            return _chain_returning(_FakeProject(project_id))
        q = _chain_returning(0)
        q.scalar.return_value = scalar_queue.pop(0)
        return q

    db.query = MagicMock(side_effect=_side_effect)
    app.dependency_overrides[get_db] = _override_db(db)

    response = client.get(f"/projects/{project_id}/workflow-status")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["project_id"] == str(project_id)
    assert "event" not in body
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


# ──────────────────────────────────────────────────────────────
# GET /projects/{id}/agent-runs
# ──────────────────────────────────────────────────────────────


def test_list_agent_runs_happy_path(client):
    project_id = uuid.uuid4()
    runs = [_agent_run(), _agent_run(task_type="rag_chat", status="error")]
    db = MagicMock()

    def _side_effect(*args, **_kwargs):
        first = args[0]
        if first is Project:
            return _chain_returning(_FakeProject(project_id))
        if first is AgentRun:
            return _chain_returning(runs)
        return _chain_returning([])

    db.query = MagicMock(side_effect=_side_effect)
    app.dependency_overrides[get_db] = _override_db(db)

    response = client.get(f"/projects/{project_id}/agent-runs")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[1]["status"] == "error"


def test_list_agent_runs_returns_404_when_project_missing(client):
    db = MagicMock()
    db.query = MagicMock(side_effect=lambda *a, **k: _chain_returning(None))
    app.dependency_overrides[get_db] = _override_db(db)
    response = client.get(f"/projects/{uuid.uuid4()}/agent-runs")
    assert response.status_code == 404


def test_list_agent_runs_rejects_out_of_range_pagination(client):
    response = client.get(f"/projects/{uuid.uuid4()}/agent-runs?limit=10000")
    assert response.status_code == 422


# ──────────────────────────────────────────────────────────────
# GET /agent-runs/{id}/tool-calls
# ──────────────────────────────────────────────────────────────


def test_list_tool_calls_happy_path(client):
    run = _agent_run()
    tool_calls = [_tool_call("retrieve_chunks"), _tool_call("compose_answer")]

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
    assert [t["tool_name"] for t in body] == ["retrieve_chunks", "compose_answer"]


def test_list_tool_calls_returns_404_when_run_missing(client):
    db = MagicMock()
    db.query = MagicMock(side_effect=lambda *a, **k: _chain_returning(None))
    app.dependency_overrides[get_db] = _override_db(db)

    response = client.get(f"/agent-runs/{uuid.uuid4()}/tool-calls")
    assert response.status_code == 404


def test_list_tool_calls_invalid_uuid_returns_422(client):
    response = client.get("/agent-runs/not-a-uuid/tool-calls")
    assert response.status_code == 422
