import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.documents import list_documents

_NOW = datetime.now(timezone.utc)


class _FakeProject:
    def __init__(self, project_id: uuid.UUID) -> None:
        self.id = project_id


class _FakeDocument:
    def __init__(
        self,
        project_id: uuid.UUID,
        filename: str,
        page_count: int,
        chunk_count: int,
    ) -> None:
        self.id = uuid.uuid4()
        self.project_id = project_id
        self.filename = filename
        self.document_type = "pdf"
        self.metadata_ = {"page_count": page_count}
        self.created_at = _NOW
        self.updated_at = _NOW
        self.chunks = [object() for _ in range(chunk_count)]


def _db_override(project: object | None, documents: list[object] | None = None):
    db = MagicMock()
    project_query = MagicMock()
    document_query = MagicMock()

    project_query.filter.return_value.first.return_value = project
    document_query.filter.return_value.order_by.return_value.all.return_value = documents or []
    db.query.side_effect = [project_query, document_query]

    return db


def test_list_project_documents_returns_uploaded_file_summaries() -> None:
    project_id = uuid.uuid4()
    documents = [
        _FakeDocument(project_id, "vpn_sop.pdf", page_count=8, chunk_count=12),
        _FakeDocument(project_id, "backup_sop.pdf", page_count=5, chunk_count=7),
    ]
    db = _db_override(
        project=_FakeProject(project_id),
        documents=documents,
    )

    response = list_documents(project_id, db)

    assert [doc.filename for doc in response] == ["vpn_sop.pdf", "backup_sop.pdf"]
    assert response[0].page_count == 8
    assert response[0].chunk_count == 12
    assert response[0].document_type == "pdf"
    assert response[0].created_at == _NOW.isoformat()


def test_list_project_documents_returns_404_when_project_missing() -> None:
    db = _db_override(project=None)

    with pytest.raises(HTTPException) as exc:
        list_documents(uuid.uuid4(), db)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Project not found"
