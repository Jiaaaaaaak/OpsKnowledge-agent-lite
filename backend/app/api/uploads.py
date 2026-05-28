import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.services.etl_service import TicketETLService, TicketImportSummary

router = APIRouter(prefix="/projects", tags=["Uploads"])

_ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".json"}


@router.post(
    "/{project_id}/upload/tickets",
    response_model=TicketImportSummary,
    status_code=status.HTTP_200_OK,
    summary="上傳 Ticket 檔案（CSV / Excel / JSON）",
)
def upload_tickets(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> TicketImportSummary:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    filename = file.filename or ""
    suffix = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支援的檔案格式 '{suffix}'。允許格式：{', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    content = file.file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上傳的檔案為空")

    try:
        svc = TicketETLService()
        return svc.ingest(db, project_id, filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
