"""管理員認證 API。

- POST /auth/bootstrap：僅在尚無任何管理員時可用（首次安裝），否則 409。
- GET  /auth/status：回報是否仍需 bootstrap。
- POST /auth/login：成功設 HTTP-only session cookie；未知帳號與錯誤密碼共用同一組 401。
- POST /auth/logout：撤銷 session 並清除 cookie。
- GET  /auth/me：回傳目前 session 對應的管理員。
"""
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.identity import Administrator
from app.schemas.auth import (
    AdminRead,
    AuthStatus,
    BootstrapRequest,
    LoginRequest,
    MessageResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])

# 未知帳號與錯誤密碼共用的通用訊息，不洩漏帳號是否存在。
_INVALID_CREDENTIALS = "Invalid username or password"


def _set_session_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=raw_token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def _session_token(db: Session, raw_token: str | None) -> Administrator:
    """從 cookie 解析目前管理員；無效一律回 401。"""
    admin = auth_service.resolve_session(db, raw_token or "")
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return admin


def _cookie_token(
    raw_token: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> str | None:
    return raw_token


def get_current_admin(
    raw_token: str | None = Depends(_cookie_token),
    db: Session = Depends(get_db),
) -> Administrator:
    return _session_token(db, raw_token)


@router.get("/status", response_model=AuthStatus)
def auth_status(db: Session = Depends(get_db)) -> AuthStatus:
    return AuthStatus(bootstrap_required=auth_service.bootstrap_required(db))


@router.post(
    "/bootstrap", response_model=AdminRead, status_code=status.HTTP_201_CREATED
)
def bootstrap(
    payload: BootstrapRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> Administrator:
    if not auth_service.bootstrap_required(db):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Administrator already exists",
        )
    admin = Administrator(
        username=payload.username,
        password_hash=auth_service.hash_password(payload.password),
    )
    db.add(admin)
    db.flush()
    raw_token, _ = auth_service.create_session(db, admin)
    db.commit()
    db.refresh(admin)
    _set_session_cookie(response, raw_token)
    return admin


@router.post("/login", response_model=AdminRead)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> Administrator:
    admin = auth_service.authenticate(db, payload.username, payload.password)
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_INVALID_CREDENTIALS,
        )
    raw_token, _ = auth_service.create_session(db, admin)
    db.commit()
    _set_session_cookie(response, raw_token)
    return admin


@router.post("/logout", response_model=MessageResponse)
def logout(
    response: Response,
    raw_token: str | None = Depends(_cookie_token),
    db: Session = Depends(get_db),
) -> MessageResponse:
    # 冪等：即使沒有有效 session 也清 cookie 並回 200。
    auth_service.revoke_session(db, raw_token or "")
    db.commit()
    _clear_session_cookie(response)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=AdminRead)
def me(admin: Administrator = Depends(get_current_admin)) -> Administrator:
    return admin
