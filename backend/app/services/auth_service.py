"""管理員認證與伺服器端 session。

設計重點：
- 密碼以 Argon2id 雜湊；DB 不存明文。
- session token 由 secrets.token_urlsafe(32) 產生；DB 只存其 SHA-256 hex，
  原始 token 僅透過 HTTP-only cookie 交給瀏覽器。
- 未知帳號仍執行一次 dummy Argon2 verify，降低「帳號是否存在」的 timing 區別；
  authenticate 對未知帳號、錯誤密碼、停用帳號一律回 None（呼叫端回同一組通用 401）。
- session 失效條件：撤銷（revoked_at）、過期（expires_at）、或所屬管理員已停用。
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.base import _utcnow
from app.models.identity import AdminSession, Administrator

_hasher = PasswordHasher()

# 未知帳號時拿來做 dummy verify 的固定雜湊，讓「帳號不存在」與「密碼錯誤」耗時相近。
_DUMMY_HASH = _hasher.hash("dummy-password-for-constant-time-verify")

_TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(encoded: str, password: str) -> bool:
    try:
        return _hasher.verify(encoded, password)
    except VerifyMismatchError:
        return False
    except Exception:
        # 雜湊格式損毀等情況視為驗證失敗，不對外拋出。
        return False


def _as_aware_utc(value: datetime) -> datetime:
    """把 DB 取回的時間正規化成 aware UTC。

    PostgreSQL 的 timezone 欄位會回 aware datetime，但 SQLite 等後端可能回 naive，
    直接與 aware now 比較會 TypeError。naive 值視為 UTC，確保比較在各後端都正確。
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def bootstrap_required(db: Session) -> bool:
    """尚未建立任何管理員時為 True；首次安裝才允許 bootstrap。"""
    return db.query(Administrator.id).first() is None


def authenticate(db: Session, username: str, password: str) -> Administrator | None:
    admin = db.query(Administrator).filter(Administrator.username == username).first()
    if admin is None:
        # 帳號不存在也跑一次 verify，避免以回應時間推斷帳號存在與否。
        verify_password(_DUMMY_HASH, password)
        return None
    if not verify_password(admin.password_hash, password):
        return None
    if not admin.is_active:
        return None
    return admin


def create_session(db: Session, admin: Administrator) -> tuple[str, AdminSession]:
    """建立 session，回傳 (原始 token, AdminSession)。DB 只存 token 的 SHA-256。"""
    raw_token = generate_token()
    session = AdminSession(
        administrator_id=admin.id,
        token_hash=hash_token(raw_token),
        expires_at=_utcnow() + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(session)
    db.flush()
    return raw_token, session


def resolve_session(db: Session, raw_token: str) -> Administrator | None:
    """以原始 token 解析出有效 session 的管理員；任一失效條件成立即回 None。"""
    if not raw_token:
        return None
    session = (
        db.query(AdminSession)
        .filter(AdminSession.token_hash == hash_token(raw_token))
        .first()
    )
    if session is None:
        return None
    if session.revoked_at is not None:
        return None
    if _as_aware_utc(session.expires_at) <= _utcnow():
        return None
    admin = session.administrator
    if admin is None or not admin.is_active:
        return None
    return admin


def revoke_session(db: Session, raw_token: str) -> None:
    """撤銷 token 對應的 session（若存在且尚未撤銷）；冪等。"""
    if not raw_token:
        return
    session = (
        db.query(AdminSession)
        .filter(AdminSession.token_hash == hash_token(raw_token))
        .first()
    )
    if session is not None and session.revoked_at is None:
        session.revoked_at = _utcnow()
        db.flush()
