from unittest.mock import patch

import pytest
from fastapi import Response, status

from app.api.health import health_check


def test_opsweave_settings_expose_redis_and_secure_cookie_defaults():
    from app.core.config import Settings

    cfg = Settings(_env_file=None)
    assert cfg.app_name == "OpsWeave"
    assert cfg.redis_url == "redis://localhost:6379/0"
    assert cfg.session_cookie_name == "opsweave_session"
    # 程式預設 secure-by-default：session cookie 內含 bearer token，未設環境變數的正式
    # 部署也不得用明文 HTTP 傳遞。本機 HTTP 開發由 .env 設 SESSION_COOKIE_SECURE=false 覆蓋。
    assert cfg.session_cookie_secure is True
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


# ─────────────────────────────────────────────────────────────
# Task 4：營運健康聚合（service 層）
# ─────────────────────────────────────────────────────────────

def _patch_checks(monkeypatch, database="connected", vector="connected", redis="connected"):
    monkeypatch.setattr("app.services.health_service.check_database", lambda: database)
    monkeypatch.setattr("app.services.health_service.check_vector", lambda: vector)
    monkeypatch.setattr("app.services.health_service.check_redis", lambda: redis)


def test_operational_health_ok_when_all_connected(monkeypatch):
    from app.services.health_service import build_operational_health

    _patch_checks(monkeypatch)
    result = build_operational_health()

    assert result["status"] == "ok"
    assert result["services"] == {
        "api": "ok",
        "database": "connected",
        "vector": "connected",
        "redis": "connected",
    }
    # pulse 必須帶齊四個數值欄位，供狀態列即時顯示。
    pulse = result["pulse"]
    for key in ("cpu_percent", "memory_percent", "disk_percent", "uptime_seconds"):
        assert isinstance(pulse[key], (int, float))
    assert "checked_at" in result


def test_operational_health_degrades_when_redis_is_down(monkeypatch):
    from app.services.health_service import build_operational_health

    _patch_checks(monkeypatch, redis="disconnected")
    result = build_operational_health()

    # 任一依賴掛掉就整體 degraded，讓狀態列/儀表板能立即反映。
    assert result["status"] == "degraded"
    assert result["services"]["redis"] == "disconnected"


def test_operational_health_degrades_when_database_is_down(monkeypatch):
    from app.services.health_service import build_operational_health

    _patch_checks(monkeypatch, database="disconnected")
    result = build_operational_health()

    assert result["status"] == "degraded"
    assert result["services"]["database"] == "disconnected"


def test_check_redis_returns_disconnected_on_failure(monkeypatch):
    """Redis 連線失敗只能降級為 disconnected，不得讓健康檢查整個拋例外。"""
    from app.services import health_service

    class _BoomClient:
        def ping(self):
            raise OSError("connection refused")

    monkeypatch.setattr(health_service.redis, "from_url", lambda *a, **k: _BoomClient())
    assert health_service.check_redis() == "disconnected"


def test_check_redis_uses_one_second_socket_timeout(monkeypatch):
    """快速失敗是 _REDIS_TIMEOUT_SECONDS 存在的理由，必須釘住 connect/read 都帶 1 秒。"""
    from app.services import health_service

    captured = {}

    class _OkClient:
        def ping(self):
            return True

        def close(self):
            pass

    def _fake_from_url(url, **kwargs):
        captured.update(kwargs)
        return _OkClient()

    monkeypatch.setattr(health_service.redis, "from_url", _fake_from_url)

    assert health_service.check_redis() == "connected"
    assert captured["socket_connect_timeout"] == 1.0
    assert captured["socket_timeout"] == 1.0


def test_pulse_failure_degrades_to_none_without_raising(monkeypatch):
    """主機 metrics 取不到時，健康端點不得 500：pulse 以 None 回報、結構維持完整。"""
    from app.services import health_service

    _patch_checks(monkeypatch)
    monkeypatch.setattr(
        health_service.psutil,
        "virtual_memory",
        lambda: (_ for _ in ()).throw(OSError("cgroup unavailable")),
    )

    result = health_service.build_operational_health()

    assert result["pulse"] == {
        "cpu_percent": None,
        "memory_percent": None,
        "disk_percent": None,
        "uptime_seconds": None,
    }
    # pulse 壞掉不算依賴失敗，整體狀態仍由 services 決定（此處全 connected → ok）。
    assert result["status"] == "ok"


# ─────────────────────────────────────────────────────────────
# Task 4：營運健康聚合（API 層，需登入）
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_operations_health_requires_auth(client):
    resp = await client.get("/api/operations/health")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_operations_health_returns_aggregate_for_admin(client, monkeypatch):
    _patch_checks(monkeypatch)
    await client.post(
        "/auth/bootstrap", json={"username": "root", "password": "s3cret-pass"}
    )

    resp = await client.get("/api/operations/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert set(body["services"]) == {"api", "database", "vector", "redis"}
    assert set(body["pulse"]) == {
        "cpu_percent",
        "memory_percent",
        "disk_percent",
        "uptime_seconds",
    }
    assert "checked_at" in body
