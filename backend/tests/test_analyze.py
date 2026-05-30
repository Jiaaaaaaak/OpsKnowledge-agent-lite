"""
incident analysis agent tools + POST /projects/{id}/analyze/incidents 測試。

涵蓋：
- MockLLMProvider 對 4 個 AGENT_TASK 的 JSON 輸出
- _extract_json 容錯（[mock] 前綴、```json fenced block、原始 JSON）
- ClassifyOutput / SeverityOutput Pydantic 驗證 happy path 與 invalid path
- classify_incidents / analyze_severity / generate_insights / create_action_items 個別 tool
- orchestrator endpoint 成功路徑（記錄寫入 agent_runs + 4 筆 tool_calls）
- orchestrator endpoint 邊界：project 不存在、無 cleaned_records
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.analyze import analyze_incidents as analyze_endpoint
from app.db.session import get_db
from app.main import app
from app.models.agent import AgentRun, ToolCall
from app.models.analysis import ActionItem, IncidentAnalysis, Insight
from app.services.llm_service import MockLLMProvider
from app.tools.incident_analysis import (
    ActionItemsOutput,
    ClassifyOutput,
    InsightsOutput,
    SeverityOutput,
    _extract_json,
    analyze_severity,
    classify_incidents,
    create_action_items,
    generate_insights,
)

_NOW = datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────
# MockLLMProvider agent task branches
# ──────────────────────────────────────────────────────────────

class TestMockClassify:
    def test_network_keyword_classified(self):
        out = MockLLMProvider()._mock_classify(
            json.dumps({"issue_description": "API returned 502 due to connection timeout"})
        )
        parsed = json.loads(out)
        assert parsed["category"] == "network_issue"

    def test_storage_keyword_classified(self):
        out = MockLLMProvider._mock_classify(
            json.dumps({"issue_description": "Disk full on the volume"})
        )
        assert json.loads(out)["category"] == "storage_issue"

    def test_unknown_when_no_match(self):
        out = MockLLMProvider._mock_classify(
            json.dumps({"issue_description": "Something happened"})
        )
        assert json.loads(out)["category"] == "unknown"

    def test_output_parses_into_pydantic_schema(self):
        out = MockLLMProvider._mock_classify(
            json.dumps({"issue_description": "Permission denied for IAM role"})
        )
        parsed = ClassifyOutput.model_validate_json(out)
        assert parsed.category == "permission_issue"


class TestMockSeverity:
    def test_critical_keyword_returns_5(self):
        out = MockLLMProvider._mock_severity(
            json.dumps({"issue_description": "Production outage, critical urgent"})
        )
        sev = SeverityOutput.model_validate_json(out)
        assert sev.severity_score == 5
        assert sev.sentiment_score < 0
        assert sev.confidence >= 0.65

    def test_no_keyword_returns_low_confidence_when_empty(self):
        out = MockLLMProvider._mock_severity(json.dumps({"issue_description": ""}))
        sev = SeverityOutput.model_validate_json(out)
        assert sev.confidence < 0.65  # → needs_review

    def test_pydantic_rejects_out_of_range(self):
        with pytest.raises(ValidationError):
            SeverityOutput.model_validate_json(
                json.dumps(
                    {"severity_score": 7, "sentiment_score": 0, "confidence": 0.5, "reason": "x"}
                )
            )

    def test_pydantic_rejects_sentiment_out_of_range(self):
        with pytest.raises(ValidationError):
            SeverityOutput.model_validate_json(
                json.dumps(
                    {"severity_score": 3, "sentiment_score": 2.0, "confidence": 0.5, "reason": "x"}
                )
            )


class TestMockInsights:
    def test_generates_one_insight_per_category(self):
        out = MockLLMProvider._mock_insights(
            json.dumps(
                {
                    "category_counts": {"network_issue": 5, "storage_issue": 2},
                    "high_severity_samples": [],
                }
            )
        )
        parsed = InsightsOutput.model_validate_json(out)
        assert len(parsed.insights) == 2
        titles = [i.title for i in parsed.insights]
        assert any("network_issue" in t for t in titles)

    def test_adds_high_severity_insight_when_present(self):
        out = MockLLMProvider._mock_insights(
            json.dumps(
                {
                    "category_counts": {"network_issue": 1},
                    "high_severity_samples": [{"ticket_id": "T1", "category": "network_issue", "severity": 5}],
                }
            )
        )
        parsed = InsightsOutput.model_validate_json(out)
        titles = [i.title.lower() for i in parsed.insights]
        assert any("high severity" in t for t in titles)

    def test_empty_aggregation_still_produces_one_insight(self):
        out = MockLLMProvider._mock_insights(json.dumps({}))
        parsed = InsightsOutput.model_validate_json(out)
        assert len(parsed.insights) == 1


class TestMockActionItems:
    def test_one_item_per_insight(self):
        insights = [
            {"title": "Top category: network_issue", "recommendation": "Add monitoring."},
            {"title": "High severity patterns", "recommendation": "Run post-mortem."},
        ]
        out = MockLLMProvider._mock_action_items(json.dumps({"insights": insights}))
        parsed = ActionItemsOutput.model_validate_json(out)
        assert len(parsed.action_items) == 2

    def test_high_severity_insight_yields_high_priority(self):
        insights = [{"title": "High severity patterns", "recommendation": "Triage."}]
        parsed = ActionItemsOutput.model_validate_json(
            MockLLMProvider._mock_action_items(json.dumps({"insights": insights}))
        )
        assert parsed.action_items[0].priority == "high"


# ──────────────────────────────────────────────────────────────
# _extract_json 容錯
# ──────────────────────────────────────────────────────────────

class TestExtractJson:
    def test_plain_json(self):
        assert _extract_json('{"a": 1}') == '{"a": 1}'

    def test_strips_mock_prefix(self):
        assert _extract_json('[mock] {"a": 1}') == '{"a": 1}'

    def test_strips_json_fence(self):
        assert _extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_extracts_object_with_surrounding_text(self):
        assert _extract_json('prefix text {"x": 2} suffix') == '{"x": 2}'

    def test_raises_when_no_object(self):
        with pytest.raises(ValueError):
            _extract_json("no json here")


# ──────────────────────────────────────────────────────────────
# Tools (with real MockLLMProvider, mocked DB)
# ──────────────────────────────────────────────────────────────


def _fake_record(ticket_id: str, desc: str, priority: str = "medium"):
    r = MagicMock()
    r.id = uuid.uuid4()
    r.ticket_id = ticket_id
    r.system = "payments"
    r.module = "checkout"
    r.issue_description = desc
    r.priority = priority
    return r


class TestClassifyIncidentsTool:
    def test_happy_path_writes_tool_call_and_returns_results(self):
        db = MagicMock()
        agent_run_id = uuid.uuid4()
        project_id = uuid.uuid4()
        records = [
            _fake_record("T1", "API connection timeout to upstream"),
            _fake_record("T2", "Permission denied for IAM role"),
        ]

        result = classify_incidents(db, MockLLMProvider(), project_id, agent_run_id, records)

        assert result.success is True
        assert result.items_processed == 2
        cats = result.output["classifications"]
        assert cats[str(records[0].id)] == "network_issue"
        assert cats[str(records[1].id)] == "permission_issue"

        added = [c.args[0] for c in db.add.call_args_list]
        tool_call = next(o for o in added if isinstance(o, ToolCall))
        assert tool_call.tool_name == "classify_incidents"
        assert tool_call.agent_run_id == agent_run_id
        assert tool_call.error_message is None
        assert tool_call.output_json["classified"] == 2

    def test_invalid_llm_output_marks_tool_call_failed(self):
        db = MagicMock()
        bad_llm = MagicMock()
        bad_llm.complete.return_value = ("not a json", {})
        records = [_fake_record("T1", "anything")]

        result = classify_incidents(db, bad_llm, uuid.uuid4(), uuid.uuid4(), records)

        assert result.success is False
        assert result.items_processed == 0
        added = [c.args[0] for c in db.add.call_args_list]
        tool_call = next(o for o in added if isinstance(o, ToolCall))
        assert tool_call.error_message is not None
        assert tool_call.output_json["failed"] == 1


class TestAnalyzeSeverityTool:
    def test_low_confidence_marks_needs_review(self):
        db = MagicMock()
        # empty desc + unknown priority → mock returns confidence 0.4 (< 0.65 threshold)
        records = [_fake_record("T1", "", priority="unknown")]
        result = analyze_severity(db, MockLLMProvider(), uuid.uuid4(), uuid.uuid4(), records)
        assert result.success is True
        sev = result.output["severities"][str(records[0].id)]
        assert sev["needs_review"] is True
        assert sev["confidence"] < 0.65

    def test_critical_keyword_high_severity(self):
        db = MagicMock()
        records = [_fake_record("T1", "Production outage, all services down")]
        result = analyze_severity(db, MockLLMProvider(), uuid.uuid4(), uuid.uuid4(), records)
        sev = result.output["severities"][str(records[0].id)]
        assert sev["severity_score"] == 5
        assert sev["needs_review"] is False


class TestGenerateInsightsTool:
    def test_returns_insights_and_logs_tool_call(self):
        db = MagicMock()
        result = generate_insights(
            db,
            MockLLMProvider(),
            uuid.uuid4(),
            uuid.uuid4(),
            {"category_counts": {"network_issue": 3}, "high_severity_samples": []},
        )
        assert result.success is True
        assert result.items_processed >= 1
        added = [c.args[0] for c in db.add.call_args_list]
        tool_call = next(o for o in added if isinstance(o, ToolCall))
        assert tool_call.tool_name == "generate_insights"

    def test_invalid_output_sets_error(self):
        db = MagicMock()
        bad_llm = MagicMock()
        bad_llm.complete.return_value = ("garbage", {})
        result = generate_insights(db, bad_llm, uuid.uuid4(), uuid.uuid4(), {})
        assert result.success is False
        assert result.error is not None


class TestCreateActionItemsTool:
    def test_produces_action_items_with_open_status_in_orchestrator(self):
        # 工具本身回傳 priority/owner_role；status="open" 由 orchestrator 賦值
        db = MagicMock()
        insights = [{"title": "Top category: network_issue", "recommendation": "Add alerting."}]
        result = create_action_items(db, MockLLMProvider(), uuid.uuid4(), uuid.uuid4(), insights)
        assert result.success is True
        assert result.output["action_items"][0]["priority"] in ("low", "medium", "high")


# ──────────────────────────────────────────────────────────────
# Endpoint：POST /projects/{id}/analyze/incidents
# ──────────────────────────────────────────────────────────────


class _FakeProject:
    def __init__(self, project_id: uuid.UUID) -> None:
        self.id = project_id
        self.name = "Test Project"
        self.created_at = _NOW
        self.updated_at = _NOW


def _setup_db_mock(project: _FakeProject | None, records: list, analyzed_ids: set):
    """為 analyze 端點建構 db.query(...) 的回應。"""
    db = MagicMock()

    def _query(model):
        q = MagicMock()
        if model.__name__ == "Project":
            q.filter.return_value.first.return_value = project
        elif model.__name__ == "CleanedRecord":
            q.filter.return_value.order_by.return_value.all.return_value = records
        else:
            # IncidentAnalysis.record_id 查詢：回傳 (record_id,) tuples
            q.filter.return_value.all.return_value = [(rid,) for rid in analyzed_ids]
        return q

    # 直接 patch query：注意實際 code 呼叫 db.query(IncidentAnalysis.record_id) — 此時
    # IncidentAnalysis.record_id 是欄位物件，沒有 __name__。為簡化，分流由 spec 決定：
    db.query = MagicMock(side_effect=_query_side_effect_factory(project, records, analyzed_ids))
    return db


def _query_side_effect_factory(project, records, analyzed_ids):
    from app.models.analysis import IncidentAnalysis
    from app.models.project import Project
    from app.models.record import CleanedRecord

    def _side_effect(arg):
        q = MagicMock()
        if arg is Project:
            q.filter.return_value.first.return_value = project
            return q
        if arg is CleanedRecord:
            q.filter.return_value.order_by.return_value.all.return_value = records
            return q
        # IncidentAnalysis.record_id column
        q.filter.return_value.all.return_value = [(rid,) for rid in analyzed_ids]
        return q

    return _side_effect


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def test_analyze_endpoint_happy_path(client):
    project_id = uuid.uuid4()
    records = [
        _fake_record("INC-001", "API returned 502 due to network timeout", "high"),
        _fake_record("INC-002", "Permission denied accessing IAM role"),
        _fake_record("INC-003", "Disk full on volume"),
    ]
    db = _setup_db_mock(_FakeProject(project_id), records, analyzed_ids=set())

    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    with patch("app.api.analyze.settings") as mock_settings:
        mock_settings.llm_provider = "mock"
        mock_settings.llm_model = "gpt-4o-mini"
        with patch("app.api.analyze.get_llm_provider", return_value=MockLLMProvider()):
            response = client.post(f"/projects/{project_id}/analyze/incidents")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success"
    assert body["summary"]["records_analyzed"] == 3
    assert body["summary"]["insights_created"] >= 1
    assert body["summary"]["action_items_created"] >= 1

    # 驗證寫了哪些 DB 物件
    added = [c.args[0] for c in db.add.call_args_list]
    assert any(isinstance(o, AgentRun) for o in added)
    assert sum(isinstance(o, ToolCall) for o in added) == 4
    assert sum(isinstance(o, IncidentAnalysis) for o in added) == 3
    assert any(isinstance(o, Insight) for o in added)
    assert any(isinstance(o, ActionItem) for o in added)

    # AgentRun 狀態與 model
    agent_run = next(o for o in added if isinstance(o, AgentRun))
    assert agent_run.task_type == "analyze_incidents"
    assert agent_run.status == "success"
    assert agent_run.project_id == project_id
    assert agent_run.output_json["tools_run"] == [
        "classify_incidents",
        "analyze_severity",
        "generate_insights",
        "create_action_items",
    ]

    # action items 必須是 status="open"
    for item in (o for o in added if isinstance(o, ActionItem)):
        assert item.status == "open"

    db.commit.assert_called_once()


def test_analyze_endpoint_returns_404_when_project_missing(client):
    db = _setup_db_mock(project=None, records=[], analyzed_ids=set())

    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    response = client.post(f"/projects/{uuid.uuid4()}/analyze/incidents")
    assert response.status_code == 404


def test_analyze_endpoint_400_when_no_records_to_analyze(client):
    project_id = uuid.uuid4()
    db = _setup_db_mock(_FakeProject(project_id), records=[], analyzed_ids=set())

    def _override():
        yield db

    app.dependency_overrides[get_db] = _override
    response = client.post(f"/projects/{project_id}/analyze/incidents")
    assert response.status_code == 400
    assert "No cleaned records" in response.json()["detail"]


def test_analyze_endpoint_invalid_project_uuid_returns_422(client):
    response = client.post("/projects/not-a-uuid/analyze/incidents")
    assert response.status_code == 422
