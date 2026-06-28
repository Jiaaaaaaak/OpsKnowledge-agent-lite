from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

from app.api.auth import get_current_admin
from app.core.config import settings
from app.db.session import check_db_connection, check_vector_extension
from app.models.identity import Administrator
from app.services.health_service import build_operational_health

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str
    db: str
    vector: str


class OperationalPulse(BaseModel):
    # 主機 metrics 取不到時以 None 回報（見 health_service._pulse），故為 Optional。
    cpu_percent: float | None
    memory_percent: float | None
    disk_percent: float | None
    uptime_seconds: int | None


class OperationalServices(BaseModel):
    api: str
    database: str
    vector: str
    redis: str


class OperationalHealthResponse(BaseModel):
    status: str
    services: OperationalServices
    pulse: OperationalPulse
    checked_at: str


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


@router.get(
    "/operations/health",
    response_model=OperationalHealthResponse,
    tags=["Health"],
)
def operational_health(
    _admin: Administrator = Depends(get_current_admin),
) -> OperationalHealthResponse:
    # 需登入的營運明細：聚合依賴狀態與主機 pulse，供儀表板與固定狀態列輪詢。
    # 這是資料端點而非 liveness probe，因此即使 degraded 仍回 200，由前端依 status 呈現。
    return OperationalHealthResponse(**build_operational_health())
