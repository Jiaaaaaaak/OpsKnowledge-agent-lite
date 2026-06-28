"""Auth service 與 API 測試。

涵蓋：Argon2 雜湊、session token 只存 SHA-256、bootstrap 一次性、登入／登出、
過期／撤銷／停用拒絕，以及未知帳號與錯誤密碼回傳同一組通用 401。
"""
from datetime import timedelta

import pytest

from app.core.config import settings
from app.models.base import _utcnow
from app.models.identity import AdminSession, Administrator


# ─────────────────────────────────────────────────────────────
# Service：密碼雜湊與 session token
# ─────────────────────────────────────────────────────────────

def test_password_hash_is_argon2_and_verifies():
    from app.services.auth_service import hash_password, verify_password

    encoded = hash_password("correct horse battery staple")
    assert encoded.startswith("$argon2id$")
    assert verify_password(encoded, "correct horse battery staple") is True
    assert verify_password(encoded, "wrong") is False


def test_session_token_is_stored_only_as_sha256(db_session):
    from app.services.auth_service import create_session, hash_password, hash_token

    admin = Administrator(
        username="admin",
        password_hash=hash_password("correct horse battery staple"),
    )
    db_session.add(admin)
    db_session.flush()

    raw, session = create_session(db_session, admin)

    # 真正的不變式：落地的是 raw 的 SHA-256，且絕不是 raw 本身。
    assert session.token_hash == hash_token(raw)
    assert session.token_hash != raw
    assert len(session.token_hash) == 64
    assert session.administrator_id == admin.id


# ─────────────────────────────────────────────────────────────
# Service：authenticate 通用失敗
# ─────────────────────────────────────────────────────────────

def test_authenticate_unknown_user_returns_none(db_session):
    from app.services.auth_service import authenticate

    assert authenticate(db_session, "ghost", "whatever") is None


def test_authenticate_unknown_user_runs_dummy_verify(db_session, monkeypatch):
    """未知帳號仍須執行一次 verify（constant-time 防 timing），不可短路略過。"""
    import app.services.auth_service as svc

    calls = []
    real_verify = svc.verify_password

    def _spy(encoded, password):
        calls.append(encoded)
        return real_verify(encoded, password)

    monkeypatch.setattr(svc, "verify_password", _spy)

    assert svc.authenticate(db_session, "ghost", "whatever") is None
    # 對未知帳號要以 _DUMMY_HASH 跑一次 verify，耗時才與「帳號存在但密碼錯」相近。
    assert calls == [svc._DUMMY_HASH]


def test_authenticate_wrong_password_returns_none(db_session):
    from app.services.auth_service import authenticate, hash_password

    admin = Administrator(username="admin", password_hash=hash_password("right"))
    db_session.add(admin)
    db_session.flush()

    assert authenticate(db_session, "admin", "wrong") is None
    assert authenticate(db_session, "admin", "right") is not None


def test_authenticate_inactive_admin_returns_none(db_session):
    from app.services.auth_service import authenticate, hash_password

    admin = Administrator(
        username="admin", password_hash=hash_password("right"), is_active=False
    )
    db_session.add(admin)
    db_session.flush()

    assert authenticate(db_session, "admin", "right") is None


# ─────────────────────────────────────────────────────────────
# Service：resolve_session 生命週期
# ─────────────────────────────────────────────────────────────

def _make_admin(db_session, username="admin", active=True):
    from app.services.auth_service import hash_password

    admin = Administrator(
        username=username, password_hash=hash_password("pw"), is_active=active
    )
    db_session.add(admin)
    db_session.flush()
    return admin


def test_resolve_session_returns_admin_for_valid_token(db_session):
    from app.services.auth_service import create_session, resolve_session

    admin = _make_admin(db_session)
    raw, _ = create_session(db_session, admin)

    resolved = resolve_session(db_session, raw)
    assert resolved is not None
    assert resolved.id == admin.id


def test_resolve_session_rejects_expired(db_session):
    from app.services.auth_service import create_session, resolve_session

    admin = _make_admin(db_session)
    raw, session = create_session(db_session, admin)
    session.expires_at = _utcnow() - timedelta(seconds=1)
    db_session.flush()

    assert resolve_session(db_session, raw) is None


def test_resolve_session_rejects_expired_after_reload(db_session):
    """強制從 DB 重讀：SQLite 回 naive datetime，驗 _as_aware_utc 的 naive 分支。"""
    from app.services.auth_service import create_session, resolve_session

    admin = _make_admin(db_session)
    raw, session = create_session(db_session, admin)
    session.expires_at = _utcnow() - timedelta(seconds=1)
    db_session.commit()
    db_session.expire_all()  # 清掉 identity map，下次存取會重新查 DB（naive expires_at）

    assert resolve_session(db_session, raw) is None


def test_resolve_session_rejects_revoked(db_session):
    from app.services.auth_service import create_session, resolve_session

    admin = _make_admin(db_session)
    raw, session = create_session(db_session, admin)
    session.revoked_at = _utcnow()
    db_session.flush()

    assert resolve_session(db_session, raw) is None


def test_resolve_session_rejects_inactive_admin(db_session):
    from app.services.auth_service import create_session, resolve_session

    admin = _make_admin(db_session)
    raw, _ = create_session(db_session, admin)
    admin.is_active = False
    db_session.flush()

    assert resolve_session(db_session, raw) is None


def test_resolve_session_rejects_unknown_token(db_session):
    from app.services.auth_service import resolve_session

    assert resolve_session(db_session, "not-a-real-token") is None


# ─────────────────────────────────────────────────────────────
# API：bootstrap / status / login / logout / me
# ─────────────────────────────────────────────────────────────

_COOKIE = settings.session_cookie_name


@pytest.mark.asyncio
async def test_status_reports_bootstrap_required_when_empty(client):
    resp = await client.get("/auth/status")
    assert resp.status_code == 200
    assert resp.json() == {"bootstrap_required": True}


@pytest.mark.asyncio
async def test_bootstrap_creates_admin_and_sets_cookie(client):
    resp = await client.post(
        "/auth/bootstrap", json={"username": "root", "password": "s3cret-pass"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["username"] == "root"
    # 回應不得洩漏任何雜湊。
    assert "password_hash" not in body
    assert "token_hash" not in body
    assert _COOKIE in resp.cookies

    status = await client.get("/auth/status")
    assert status.json() == {"bootstrap_required": False}


@pytest.mark.asyncio
async def test_bootstrap_twice_returns_409(client):
    first = await client.post(
        "/auth/bootstrap", json={"username": "root", "password": "s3cret-pass"}
    )
    assert first.status_code == 201

    second = await client.post(
        "/auth/bootstrap", json={"username": "root2", "password": "another-pass"}
    )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_login_success_sets_cookie_and_returns_admin(client, db_session):
    from app.services.auth_service import hash_password

    db_session.add(
        Administrator(username="ops", password_hash=hash_password("good-pass"))
    )
    db_session.commit()

    resp = await client.post(
        "/auth/login", json={"username": "ops", "password": "good-pass"}
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "ops"
    assert _COOKIE in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password_and_unknown_user_share_401(client, db_session):
    from app.services.auth_service import hash_password

    db_session.add(
        Administrator(username="ops", password_hash=hash_password("good-pass"))
    )
    db_session.commit()

    wrong = await client.post(
        "/auth/login", json={"username": "ops", "password": "bad"}
    )
    unknown = await client.post(
        "/auth/login", json={"username": "ghost", "password": "bad"}
    )

    assert wrong.status_code == 401
    assert unknown.status_code == 401
    # 通用 401：兩者 detail 必須一致，不洩漏帳號是否存在。
    assert wrong.json()["detail"] == unknown.json()["detail"]


@pytest.mark.asyncio
async def test_me_requires_session(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_admin_after_bootstrap(client):
    await client.post(
        "/auth/bootstrap", json={"username": "root", "password": "s3cret-pass"}
    )
    resp = await client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "root"


@pytest.mark.asyncio
async def test_logout_revokes_session(client):
    await client.post(
        "/auth/bootstrap", json={"username": "root", "password": "s3cret-pass"}
    )
    assert (await client.get("/auth/me")).status_code == 200

    logout = await client.post("/auth/logout")
    assert logout.status_code == 200

    # 登出後同一 client（cookie 已清）再打 /me 應為 401。
    assert (await client.get("/auth/me")).status_code == 401
