from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.config import settings
from app.db.session import check_db_connection, check_vector_extension

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
    vector: str


@router.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check(response: Response) -> HealthResponse:
    db_ok = check_db_connection()
    vector_ok = check_vector_extension()
    healthy = db_ok and vector_ok
    # 核心依賴（DB / pgvector）不可用時回 503，避免「API 活著但不可用」被判定 healthy，
    # 誤導 compose healthcheck、自動恢復與 UI 狀態。
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="ok" if healthy else "degraded",
        version=settings.app_version,
        db="connected" if db_ok else "unavailable",
        vector="connected" if vector_ok else "unavailable",
    )
