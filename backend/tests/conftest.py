"""Auth 測試共用 fixture。

提供真實（但 in-memory SQLite）的 SQLAlchemy session，讓 auth service 與 API
能在不依賴 PostgreSQL 的情況下，驗證 session 落地、過期、撤銷等行為。
API 測試一律走 httpx ASGITransport，避開 baseline 已知的 TestClient／AnyIO 卡死。
"""
import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base
from app.models.identity import AdminSession, Administrator


@pytest.fixture()
def db_session():
    # StaticPool + 單一共享連線，確保整個測試期間都看同一份 in-memory 資料。
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # 只建立 auth 相關資料表，避免牽動需要 pgvector 的文件資料表。
    Base.metadata.create_all(
        bind=engine,
        tables=[Administrator.__table__, AdminSession.__table__],
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest_asyncio.fixture()
async def client(db_session):
    """以共享的 db_session 覆寫 get_db，並用 ASGITransport 直接打 ASGI app。"""
    import httpx

    from app.db.session import get_db
    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = httpx.ASGITransport(app=app)
    # 用 https base_url，讓 secure session cookie 能在 client cookie jar 正常往返
    # （預設 session_cookie_secure=True；明文 http 下瀏覽器/httpx 不會回送 Secure cookie）。
    async with httpx.AsyncClient(
        transport=transport, base_url="https://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
