from unittest.mock import patch

from app.api.health import health_check


def test_health_ok():
    with patch("app.api.health.check_db_connection", return_value=True), \
         patch("app.api.health.check_vector_extension", return_value=True):
        response = health_check()
    data = response.model_dump()
    assert data["status"] == "ok"
    assert data["db"] == "connected"
    assert data["vector"] == "connected"
    assert "chroma" not in data


def test_health_db_unavailable():
    with patch("app.api.health.check_db_connection", return_value=False), \
         patch("app.api.health.check_vector_extension", return_value=True):
        response = health_check()
    data = response.model_dump()
    assert data["db"] == "unavailable"
    assert data["vector"] == "connected"


def test_health_vector_unavailable():
    with patch("app.api.health.check_db_connection", return_value=True), \
         patch("app.api.health.check_vector_extension", return_value=False):
        response = health_check()
    data = response.model_dump()
    assert data["db"] == "connected"
    assert data["vector"] == "unavailable"
