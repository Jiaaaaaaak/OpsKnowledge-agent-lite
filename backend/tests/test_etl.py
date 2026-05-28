"""
ETL pipeline 單元測試
涵蓋：欄位名稱正規化、CleanedTicket 驗證、CSV/JSON 解析
"""
import json
from datetime import datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.services.etl_service import (
    CleanedTicket,
    TicketETLService,
    TicketImportSummary,
    _norm_key,
)


# ─────────────────────────────────────────────────────────────
# _norm_key 輔助函式
# ─────────────────────────────────────────────────────────────

class TestNormKey:
    def test_lowercase(self):
        assert _norm_key("TICKET_ID") == "ticket_id"

    def test_strip_spaces(self):
        assert _norm_key("  ticket_id  ") == "ticket_id"

    def test_spaces_to_underscore(self):
        assert _norm_key("ticket id") == "ticket_id"

    def test_hyphens_to_underscore(self):
        assert _norm_key("ticket-id") == "ticket_id"

    def test_multiple_separators(self):
        assert _norm_key("system  name") == "system_name"


# ─────────────────────────────────────────────────────────────
# normalize_columns
# ─────────────────────────────────────────────────────────────

class TestNormalizeColumns:
    def setup_method(self):
        self.svc = TicketETLService()

    def test_canonical_ticket_id(self):
        assert self.svc.normalize_columns({"ticket_id": "TKT-001"})["ticket_id"] == "TKT-001"

    def test_ticket_id_from_space_variant(self):
        assert self.svc.normalize_columns({"ticket id": "TKT-001"})["ticket_id"] == "TKT-001"

    def test_ticket_id_from_id(self):
        assert self.svc.normalize_columns({"id": "TKT-001"})["ticket_id"] == "TKT-001"

    def test_ticket_id_from_case_id(self):
        assert self.svc.normalize_columns({"case_id": "TKT-001"})["ticket_id"] == "TKT-001"

    def test_occurred_at_from_date(self):
        assert self.svc.normalize_columns({"date": "2024-01-01"})["occurred_at"] == "2024-01-01"

    def test_occurred_at_from_created_at(self):
        assert self.svc.normalize_columns({"created_at": "2024-01-01"})["occurred_at"] == "2024-01-01"

    def test_occurred_at_from_timestamp(self):
        assert "occurred_at" in self.svc.normalize_columns({"timestamp": "2024-01-01"})

    def test_system_from_service(self):
        assert self.svc.normalize_columns({"service": "Auth"})["system"] == "Auth"

    def test_system_from_system_name(self):
        assert self.svc.normalize_columns({"system_name": "Auth"})["system"] == "Auth"

    def test_module_from_component(self):
        assert self.svc.normalize_columns({"component": "Login"})["module"] == "Login"

    def test_issue_from_problem(self):
        assert self.svc.normalize_columns({"problem": "Error"})["issue_description"] == "Error"

    def test_issue_from_description(self):
        assert self.svc.normalize_columns({"description": "Error"})["issue_description"] == "Error"

    def test_issue_from_issue(self):
        assert self.svc.normalize_columns({"issue": "Error"})["issue_description"] == "Error"

    def test_resolution_from_fix(self):
        assert self.svc.normalize_columns({"fix": "Rebooted"})["resolution"] == "Rebooted"

    def test_resolution_from_solution(self):
        assert self.svc.normalize_columns({"solution": "Rebooted"})["resolution"] == "Rebooted"

    def test_status_from_state(self):
        assert self.svc.normalize_columns({"state": "open"})["status"] == "open"

    def test_priority_from_severity(self):
        assert self.svc.normalize_columns({"severity": "high"})["priority"] == "high"

    def test_priority_from_urgency(self):
        assert self.svc.normalize_columns({"urgency": "medium"})["priority"] == "medium"

    def test_unknown_column_dropped(self):
        result = self.svc.normalize_columns({"unknown_col": "value"})
        assert "unknown_col" not in result

    def test_mixed_known_unknown(self):
        row = {"ticket_id": "TKT-001", "problem": "Error", "extra": "ignored"}
        result = self.svc.normalize_columns(row)
        assert "ticket_id" in result
        assert "issue_description" in result
        assert "extra" not in result

    def test_case_insensitive(self):
        row = {"TICKET_ID": "TKT-001", "PROBLEM": "Error"}
        result = self.svc.normalize_columns(row)
        assert "ticket_id" in result
        assert "issue_description" in result

    def test_first_match_wins(self):
        # ticket_id 優先於 case_id（依 dict 插入順序）
        row = {"ticket_id": "TKT-001", "case_id": "CASE-999"}
        result = self.svc.normalize_columns(row)
        assert result["ticket_id"] == "TKT-001"

    def test_all_eight_canonical_fields(self):
        row = {
            "ticket_id": "T1", "date": "2024-01-01", "service": "S",
            "component": "M", "problem": "P", "fix": "R",
            "state": "open", "severity": "high",
        }
        result = self.svc.normalize_columns(row)
        for field in ("ticket_id", "occurred_at", "system", "module",
                      "issue_description", "resolution", "status", "priority"):
            assert field in result, f"Missing field: {field}"


# ─────────────────────────────────────────────────────────────
# CleanedTicket 驗證
# ─────────────────────────────────────────────────────────────

class TestCleanedTicket:

    def _base(self, **overrides) -> dict:
        data = {"ticket_id": "TKT-001", "issue_description": "Something broke"}
        data.update(overrides)
        return data

    def test_minimal_valid(self):
        t = CleanedTicket(**self._base())
        assert t.ticket_id == "TKT-001"
        assert t.issue_description == "Something broke"
        assert t.system == "unknown"
        assert t.module == "unknown"
        assert t.status == "unknown"
        assert t.priority == "unknown"
        assert t.occurred_at is None
        assert t.resolution is None

    def test_full_valid(self):
        t = CleanedTicket(
            ticket_id="TKT-002",
            occurred_at="2024-01-15 09:00:00",
            system="Auth Service",
            module="Login",
            issue_description="Login failed",
            resolution="Restarted pods",
            status="resolved",
            priority="high",
        )
        assert t.system == "Auth Service"
        assert t.module == "Login"
        assert t.resolution == "Restarted pods"
        assert t.status == "resolved"
        assert t.priority == "high"

    def test_missing_ticket_id_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            CleanedTicket(issue_description="Error")
        assert "ticket_id" in str(exc_info.value)

    def test_empty_ticket_id_raises(self):
        with pytest.raises(ValidationError):
            CleanedTicket(**self._base(ticket_id="   "))

    def test_missing_issue_description_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            CleanedTicket(ticket_id="TKT-001")
        assert "issue_description" in str(exc_info.value)

    def test_empty_issue_description_raises(self):
        with pytest.raises(ValidationError):
            CleanedTicket(**self._base(issue_description=""))

    def test_whitespace_stripped_ticket_id(self):
        t = CleanedTicket(**self._base(ticket_id="  TKT-001  "))
        assert t.ticket_id == "TKT-001"

    def test_whitespace_stripped_description(self):
        t = CleanedTicket(**self._base(issue_description="  Error  "))
        assert t.issue_description == "Error"

    def test_empty_system_defaults_to_unknown(self):
        assert CleanedTicket(**self._base(system="")).system == "unknown"

    def test_none_system_defaults_to_unknown(self):
        assert CleanedTicket(**self._base(system=None)).system == "unknown"

    def test_none_module_defaults_to_unknown(self):
        assert CleanedTicket(**self._base(module=None)).module == "unknown"

    def test_whitespace_status_defaults_to_unknown(self):
        assert CleanedTicket(**self._base(status="   ")).status == "unknown"

    def test_none_priority_defaults_to_unknown(self):
        assert CleanedTicket(**self._base(priority=None)).priority == "unknown"

    def test_occurred_at_iso_string(self):
        t = CleanedTicket(**self._base(occurred_at="2024-03-15T09:30:00"))
        assert isinstance(t.occurred_at, datetime)
        assert t.occurred_at.year == 2024
        assert t.occurred_at.month == 3

    def test_occurred_at_date_only(self):
        t = CleanedTicket(**self._base(occurred_at="2024-03-15"))
        assert isinstance(t.occurred_at, datetime)
        assert t.occurred_at.day == 15

    def test_occurred_at_space_separated(self):
        t = CleanedTicket(**self._base(occurred_at="2024-06-01 12:00:00"))
        assert isinstance(t.occurred_at, datetime)

    def test_occurred_at_invalid_becomes_none(self):
        t = CleanedTicket(**self._base(occurred_at="not-a-date"))
        assert t.occurred_at is None

    def test_occurred_at_none_stays_none(self):
        assert CleanedTicket(**self._base(occurred_at=None)).occurred_at is None

    def test_resolution_none_stays_none(self):
        assert CleanedTicket(**self._base(resolution=None)).resolution is None

    def test_resolution_empty_becomes_none(self):
        assert CleanedTicket(**self._base(resolution="")).resolution is None

    def test_resolution_value_preserved(self):
        t = CleanedTicket(**self._base(resolution="Restarted service"))
        assert t.resolution == "Restarted service"


# ─────────────────────────────────────────────────────────────
# 檔案解析（不需 DB）
# ─────────────────────────────────────────────────────────────

class TestParseCSV:
    def setup_method(self):
        self.svc = TicketETLService()

    def test_basic(self):
        content = b"ticket_id,problem\nTKT-001,Some error\nTKT-002,Another"
        rows = self.svc._parse_csv(content)
        assert len(rows) == 2
        assert rows[0]["ticket_id"] == "TKT-001"
        assert rows[1]["problem"] == "Another"

    def test_bom_utf8(self):
        content = "ticket_id,problem\nTKT-001,Error".encode("utf-8-sig")
        rows = self.svc._parse_csv(content)
        assert "ticket_id" in rows[0]

    def test_empty_data_raises(self):
        with pytest.raises(ValueError, match="CSV"):
            self.svc._parse_csv(b"ticket_id,problem")

    def test_empty_values_preserved(self):
        content = b"ticket_id,problem\nTKT-001,"
        rows = self.svc._parse_csv(content)
        assert rows[0]["problem"] == ""


class TestParseJSON:
    def setup_method(self):
        self.svc = TicketETLService()

    def test_top_level_list(self):
        data = [{"ticket_id": "T1", "problem": "Error"}]
        rows = self.svc._parse_json(json.dumps(data).encode())
        assert len(rows) == 1

    def test_wrapped_records_key(self):
        data = {"records": [{"ticket_id": "T1", "problem": "Error"}]}
        rows = self.svc._parse_json(json.dumps(data).encode())
        assert len(rows) == 1

    def test_wrapped_data_key(self):
        data = {"data": [{"ticket_id": "T1", "problem": "Error"}]}
        rows = self.svc._parse_json(json.dumps(data).encode())
        assert len(rows) == 1

    def test_single_object_treated_as_one_row(self):
        data = {"ticket_id": "T1", "problem": "Error"}
        rows = self.svc._parse_json(json.dumps(data).encode())
        assert len(rows) == 1

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            self.svc._parse_json(b'"just a string"')


# ─────────────────────────────────────────────────────────────
# API 端點：POST /projects/{project_id}/upload/tickets
# ─────────────────────────────────────────────────────────────

class TestUploadTicketsEndpoint:
    def setup_method(self):
        from app.main import app
        self.client = TestClient(app)

    def _make_csv(self, rows: list[str]) -> bytes:
        header = "ticket_id,date,service,component,problem,resolution,state,severity"
        return ("\n".join([header] + rows)).encode()

    def _db_override(self, project=None):
        from app.db.session import get_db
        from app.main import app

        def _get_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = project
            yield db

        return _get_db, get_db, app

    def test_project_not_found_returns_404(self):
        from app.db.session import get_db
        from app.main import app

        def _get_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = None
            yield db

        app.dependency_overrides[get_db] = _get_db
        try:
            response = self.client.post(
                f"/projects/{uuid4()}/upload/tickets",
                files={"file": ("test.csv", b"ticket_id,problem\nT1,Error", "text/csv")},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 404

    def test_unsupported_extension_returns_400(self):
        from app.db.session import get_db
        from app.main import app

        fake_project = MagicMock()

        def _get_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = fake_project
            yield db

        app.dependency_overrides[get_db] = _get_db
        try:
            response = self.client.post(
                f"/projects/{uuid4()}/upload/tickets",
                files={"file": ("data.txt", b"some content", "text/plain")},
            )
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 400

    def test_valid_csv_returns_summary(self):
        from app.db.session import get_db
        from app.main import app

        fake_project = MagicMock()

        def _get_db():
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = fake_project
            yield db

        csv_content = self._make_csv([
            "TKT-001,2024-01-15,Auth Service,Login,Users locked out,Rolled back update,resolved,high",
            "TKT-002,2024-01-16,Database,Primary Node,DB failover,Promoted replica,resolved,critical",
        ])

        with patch("app.api.uploads.TicketETLService") as MockSvc:
            MockSvc.return_value.ingest.return_value = TicketImportSummary(
                raw_count=2, cleaned_count=2, failed_count=0, errors=[]
            )
            app.dependency_overrides[get_db] = _get_db
            try:
                response = self.client.post(
                    f"/projects/{uuid4()}/upload/tickets",
                    files={"file": ("tickets.csv", csv_content, "text/csv")},
                )
            finally:
                app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["raw_count"] == 2
        assert data["cleaned_count"] == 2
        assert data["failed_count"] == 0
        assert data["errors"] == []
