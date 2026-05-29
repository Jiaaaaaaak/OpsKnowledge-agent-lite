from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    with patch("app.api.health.check_db_connection", return_value=True), \
         patch("app.api.health._check_chroma_connection", return_value=True):
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"
    assert data["chroma"] == "connected"


def test_health_db_unavailable():
    with patch("app.api.health.check_db_connection", return_value=False), \
         patch("app.api.health._check_chroma_connection", return_value=True):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["db"] == "unavailable"
    assert response.json()["chroma"] == "connected"


def test_health_chroma_unavailable():
    with patch("app.api.health.check_db_connection", return_value=True), \
         patch("app.api.health._check_chroma_connection", return_value=False):
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["db"] == "connected"
    assert response.json()["chroma"] == "unavailable"
