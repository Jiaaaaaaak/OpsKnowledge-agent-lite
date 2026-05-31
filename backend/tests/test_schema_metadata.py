"""
Schema/model consistency tests for SQLAlchemy columns named ``metadata``.

SQLAlchemy reserves ``metadata`` on declarative models, so ORM classes expose the
JSONB column as ``metadata_``. Public Pydantic schemas should still expose the
API/database contract name: ``metadata``.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.schemas.document import DocumentChunkRead, DocumentRead
from app.schemas.record import CleanedRecordRead

_NOW = datetime.now(timezone.utc)


class _OrmObject:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


def test_document_read_exposes_metadata_column_from_orm_metadata_alias() -> None:
    doc = _OrmObject(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        filename="sop.pdf",
        document_type="pdf",
        source_path="data/uploads/sop.pdf",
        metadata_={"page_count": 3},
        created_at=_NOW,
        updated_at=_NOW,
    )

    data = DocumentRead.model_validate(doc).model_dump()

    assert data["metadata"] == {"page_count": 3}


def test_document_chunk_read_exposes_metadata_column_from_orm_metadata_alias() -> None:
    chunk = _OrmObject(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=2,
        content="restart procedure",
        metadata_={"filename": "sop.pdf", "page_number": 1},
        created_at=_NOW,
    )

    data = DocumentChunkRead.model_validate(chunk).model_dump()

    assert data["metadata"] == {"filename": "sop.pdf", "page_number": 1}


def test_cleaned_record_read_exposes_metadata_column_from_orm_metadata_alias() -> None:
    record = _OrmObject(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        ticket_id="TKT-1",
        occurred_at=None,
        system="billing",
        module="api",
        issue_description="timeout",
        resolution=None,
        status="open",
        priority="high",
        metadata_={"source_row": 7},
        created_at=_NOW,
        updated_at=_NOW,
    )

    data = CleanedRecordRead.model_validate(record).model_dump()

    assert data["metadata"] == {"source_row": 7}
