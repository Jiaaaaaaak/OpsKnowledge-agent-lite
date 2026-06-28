from unittest.mock import patch

from fastapi import Response, status

from app.api.health import health_check


def test_opsweave_settings_expose_redis_and_secure_cookie_defaults():
    from app.core.config import Settings

    cfg = Settings(_env_file=None)
    assert cfg.app_name == "OpsWeave"
    assert cfg.redis_url == "redis://localhost:6379/0"
    assert cfg.session_cookie_name == "opsweave_session"
    assert cfg.session_cookie_secure is False
    assert cfg.session_cookie_samesite == "lax"
    assert cfg.session_ttl_hours == 24


def _call_health() -> tuple[Response, dict]:
    response = Response()
    result = health_check(response)
    return response, result.model_dump()


def test_health_ok():
    with patch("app.api.health.check_db_connection", return_value=True), \
         patch("app.api.health.check_vector_extension", return_value=True):
        response, data = _call_health()
    assert data["status"] == "ok"
    assert data["db"] == "connected"
    assert data["vector"] == "connected"
    assert "chroma" not in data
    # 健康時維持預設 200。
    assert response.status_code == status.HTTP_200_OK


def test_health_db_unavailable():
    with patch("app.api.health.check_db_connection", return_value=False), \
         patch("app.api.health.check_vector_extension", return_value=True):
        response, data = _call_health()
    assert data["db"] == "unavailable"
    assert data["vector"] == "connected"
    # 核心依賴掛掉必須回 503 + degraded，否則 compose healthcheck 會誤判 healthy。
    assert data["status"] == "degraded"
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_health_vector_unavailable():
    with patch("app.api.health.check_db_connection", return_value=True), \
         patch("app.api.health.check_vector_extension", return_value=False):
        response, data = _call_health()
    assert data["db"] == "connected"
    assert data["vector"] == "unavailable"
    assert data["status"] == "degraded"
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
