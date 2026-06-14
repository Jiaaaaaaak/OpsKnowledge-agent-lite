from fastapi import APIRouter
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
def health_check() -> HealthResponse:
    db_ok = check_db_connection()
    vector_ok = check_vector_extension()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        db="connected" if db_ok else "unavailable",
        vector="connected" if vector_ok else "unavailable",
    )
