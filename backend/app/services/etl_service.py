from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError, model_validator
from sqlalchemy.orm import Session

from app.models.record import CleanedRecord, RawRecord


# ────────────────────────────────────────────────
# 欄位同義詞對應表
# ────────────────────────────────────────────────

def _norm_key(key: str) -> str:
    """正規化欄位名稱：小寫、去首尾空白、非字母數字轉底線."""
    return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")


_SYNONYMS: dict[str, list[str]] = {
    "ticket_id": [
        "ticket_id", "ticket id", "id", "case_id", "case id", "ticket", "ticketid",
    ],
    "occurred_at": [
        "occurred_at", "occurred at", "date", "created_at", "timestamp",
        "datetime", "time", "reported_at", "report_date", "incident_date",
    ],
    "system": [
        "system", "service", "system_name", "system name", "service_name",
        "affected_system",
    ],
    "module": [
        "module", "component", "comp", "subsystem",
    ],
    "issue_description": [
        "issue_description", "issue description", "issue", "description",
        "problem", "desc", "detail", "error_message", "fault",
    ],
    "resolution": [
        "resolution", "fix", "solution", "resolved_by", "remedy",
        "resolution_notes",
    ],
    "status": [
        "status", "state", "ticket_status", "incident_status",
    ],
    "priority": [
        "priority", "severity", "sev", "pri", "urgency",
    ],
}

# 反向對應：正規化同義詞 → 標準欄位名稱
_REVERSE_MAP: dict[str, str] = {}
for _canonical, _syns in _SYNONYMS.items():
    for _syn in _syns:
        _REVERSE_MAP[_norm_key(_syn)] = _canonical


# ────────────────────────────────────────────────
# 日期解析
# ────────────────────────────────────────────────

_DATETIME_FORMATS = [
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y",
    "%m/%d/%Y",
]


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# ────────────────────────────────────────────────
# 內部 Pydantic 驗證模型
# ────────────────────────────────────────────────

class CleanedTicket(BaseModel):
    ticket_id: str
    occurred_at: datetime | None = None
    system: str = "unknown"
    module: str = "unknown"
    issue_description: str
    resolution: str | None = None
    status: str = "unknown"
    priority: str = "unknown"

    @model_validator(mode="before")
    @classmethod
    def _strip_and_fill(cls, data: dict[str, Any]) -> dict[str, Any]:
        def _clean(v: Any) -> Any:
            if isinstance(v, str):
                return v.strip() or None
            return v

        cleaned = {k: _clean(v) for k, v in data.items()}

        # 必填欄位：ticket_id
        if cleaned.get("ticket_id") is None:
            raise ValueError("ticket_id 為必填欄位，且不可為空")
        cleaned["ticket_id"] = str(cleaned["ticket_id"]).strip()
        if not cleaned["ticket_id"]:
            raise ValueError("ticket_id 不可為空字串")

        # 必填欄位：issue_description
        if cleaned.get("issue_description") is None:
            raise ValueError("issue_description 為必填欄位，且不可為空")
        cleaned["issue_description"] = str(cleaned["issue_description"]).strip()
        if not cleaned["issue_description"]:
            raise ValueError("issue_description 不可為空字串")

        # 選填欄位：缺值或空值補預設 "unknown"
        for field in ("system", "module", "status", "priority"):
            v = cleaned.get(field)
            if v is None:
                cleaned[field] = "unknown"
            else:
                cleaned[field] = str(v).strip() or "unknown"

        # resolution：空值轉 None
        if cleaned.get("resolution") is not None:
            cleaned["resolution"] = str(cleaned["resolution"]).strip() or None

        # occurred_at：嘗試解析為 datetime
        if cleaned.get("occurred_at") is not None:
            cleaned["occurred_at"] = _parse_datetime(cleaned["occurred_at"])

        return cleaned


# ────────────────────────────────────────────────
# 回傳摘要結構
# ────────────────────────────────────────────────

class TicketImportError(BaseModel):
    row: int
    raw_ticket_id: str | None
    error: str


class TicketImportSummary(BaseModel):
    raw_count: int
    cleaned_count: int
    failed_count: int
    errors: list[TicketImportError]


# ────────────────────────────────────────────────
# ETL Service
# ────────────────────────────────────────────────

class TicketETLService:

    def normalize_columns(self, row: dict[str, Any]) -> dict[str, Any]:
        """將輸入列的欄位名稱對應到標準欄位名稱；未匹配的欄位略過."""
        result: dict[str, Any] = {}
        for col, value in row.items():
            canonical = _REVERSE_MAP.get(_norm_key(col))
            if canonical and canonical not in result:  # 先到先得
                result[canonical] = value
        return result

    # ── 格式解析 ──────────────────────────────────

    def _parse_csv(self, content: bytes) -> list[dict[str, Any]]:
        text = content.decode("utf-8-sig")  # 支援含 BOM 的 UTF-8
        reader = csv.DictReader(io.StringIO(text))
        rows = [dict(row) for row in reader]
        if not rows:
            raise ValueError("CSV 檔案不含資料列")
        return rows

    def _parse_json(self, content: bytes) -> list[dict[str, Any]]:
        data = json.loads(content)
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            for key in ("records", "data", "tickets", "incidents", "items"):
                if key in data and isinstance(data[key], list):
                    rows = data[key]
                    break
            else:
                rows = [data]  # 單筆物件
        else:
            raise ValueError("JSON 格式不支援：需為物件陣列或含 records/data 等鍵的物件")
        rows = [r for r in rows if isinstance(r, dict)]
        if not rows:
            raise ValueError("JSON 檔案不含有效資料列")
        return rows

    def _parse_xlsx(self, content: bytes) -> list[dict[str, Any]]:
        import openpyxl  # lazy import，避免未安裝時影響非 xlsx 的功能

        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        headers: list[str] = []
        rows: list[dict[str, Any]] = []

        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                headers = [
                    str(c) if c is not None else f"col_{j}"
                    for j, c in enumerate(row)
                ]
                continue
            cells = [self._cell_to_str(v) for v in row]
            if all(v is None for v in cells):
                continue  # 跳過全空列
            rows.append(dict(zip(headers, cells)))

        wb.close()
        if not rows:
            raise ValueError("Excel 檔案不含資料列")
        return rows

    @staticmethod
    def _cell_to_str(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, float):
            return str(int(value)) if value.is_integer() else str(value)
        s = str(value).strip()
        return s or None

    def _parse_file(self, filename: str, content: bytes) -> list[dict[str, Any]]:
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix == "csv":
            return self._parse_csv(content)
        if suffix == "json":
            return self._parse_json(content)
        if suffix == "xlsx":
            return self._parse_xlsx(content)
        raise ValueError(f"不支援的檔案格式：.{suffix}，允許格式：.csv、.xlsx、.json")

    # ── 主流程 ────────────────────────────────────

    @staticmethod
    def _format_error(exc: ValidationError) -> str:
        parts = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err["loc"]) if err["loc"] else "general"
            parts.append(f"{loc}: {err['msg']}")
        return "; ".join(parts)

    def ingest(
        self,
        db: Session,
        project_id: UUID,
        filename: str,
        content: bytes,
    ) -> TicketImportSummary:
        """解析上傳檔案，寫入 raw_records 及 cleaned_records，回傳匯入摘要."""
        rows = self._parse_file(filename, content)

        errors: list[TicketImportError] = []
        cleaned_count = 0

        for i, row in enumerate(rows, start=1):
            # 每筆原始資料無論是否通過驗證，都存入 raw_records
            db.add(RawRecord(
                project_id=project_id,
                source_file=filename,
                raw_json=row,
            ))

            normalized = self.normalize_columns(row)

            # 提前取得 ticket_id 字串，供錯誤回報使用
            raw_ticket_id = str(normalized.get("ticket_id") or "").strip() or None

            try:
                ticket = CleanedTicket(**normalized)
            except ValidationError as exc:
                errors.append(TicketImportError(
                    row=i,
                    raw_ticket_id=raw_ticket_id,
                    error=self._format_error(exc),
                ))
                continue

            db.add(CleanedRecord(
                project_id=project_id,
                ticket_id=ticket.ticket_id,
                occurred_at=ticket.occurred_at,
                system=ticket.system,
                module=ticket.module,
                issue_description=ticket.issue_description,
                resolution=ticket.resolution,
                status=ticket.status,
                priority=ticket.priority,
                metadata_={},
            ))
            cleaned_count += 1

        db.commit()

        return TicketImportSummary(
            raw_count=len(rows),
            cleaned_count=cleaned_count,
            failed_count=len(errors),
            errors=errors,
        )
