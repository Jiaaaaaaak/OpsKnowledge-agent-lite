import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

_NOW = datetime.now(timezone.utc)


class _FakeProject:
    """Minimal Project lookalike compatible with Pydantic from_attributes."""

    def __init__(
        self,
        name: str = "Demo Project",
        description: str | None = "A description",
        project_id: uuid.UUID | None = None,
    ) -> None:
        self.id = project_id or uuid.uuid4()
        self.name = name
        self.description = description
        self.created_at = _NOW
        self.updated_at = _NOW


def _db_override(projects: list | None = None, single: object | None = None):
    """Returns a get_db override that mimics SQLAlchemy query chains."""

    def _get_db():
        db = MagicMock()
        db.query.return_value.order_by.return_value.all.return_value = projects or []
        db.query.return_value.filter.return_value.first.return_value = single
        yield db

    return _get_db


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────
# POST /projects/
# ─────────────────────────────────────────────────────────────

def test_create_project_returns_201(client: TestClient) -> None:
    fake = _FakeProject("IT Operations Demo", "Demo project")

    app.dependency_overrides[get_db] = _db_override()

    with patch("app.api.projects.Project", return_value=fake):
        response = client.post(
            "/projects/",
            json={"name": "IT Operations Demo", "description": "Demo project"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "IT Operations Demo"
    assert data["description"] == "Demo project"
    assert "id" in data
    assert "created_at" in data


def test_create_project_without_description(client: TestClient) -> None:
    fake = _FakeProject("Minimal Project", None)

    app.dependency_overrides[get_db] = _db_override()

    with patch("app.api.projects.Project", return_value=fake):
        response = client.post("/projects/", json={"name": "Minimal Project"})

    assert response.status_code == 201
    assert response.json()["description"] is None


def test_create_project_missing_name_returns_422(client: TestClient) -> None:
    app.dependency_overrides[get_db] = _db_override()
    response = client.post("/projects/", json={"description": "no name"})
    assert response.status_code == 422


# ─────────────────────────────────────────────────────────────
# GET /projects/
# ─────────────────────────────────────────────────────────────

def test_list_projects_returns_200(client: TestClient) -> None:
    projects = [
        _FakeProject("Project A"),
        _FakeProject("Project B"),
    ]
    app.dependency_overrides[get_db] = _db_override(projects=projects)

    response = client.get("/projects/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Project A"
    assert data[1]["name"] == "Project B"


def test_list_projects_empty(client: TestClient) -> None:
    app.dependency_overrides[get_db] = _db_override(projects=[])

    response = client.get("/projects/")

    assert response.status_code == 200
    assert response.json() == []


# ─────────────────────────────────────────────────────────────
# GET /projects/{project_id}
# ─────────────────────────────────────────────────────────────

def test_get_project_found(client: TestClient) -> None:
    project_id = uuid.uuid4()
    fake = _FakeProject("Found Project", project_id=project_id)
    app.dependency_overrides[get_db] = _db_override(single=fake)

    response = client.get(f"/projects/{project_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Found Project"
    assert data["id"] == str(project_id)


def test_get_project_not_found_returns_404(client: TestClient) -> None:
    app.dependency_overrides[get_db] = _db_override(single=None)

    response = client.get(f"/projects/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_get_project_invalid_uuid_returns_422(client: TestClient) -> None:
    response = client.get("/projects/not-a-uuid")
    assert response.status_code == 422
