import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.project import Project
from app.services.document_service import DocumentIngestionResult, DocumentIngestionService

router = APIRouter(prefix="/projects", tags=["Documents"])


@router.post(
    "/{project_id}/upload/documents",
    response_model=DocumentIngestionResult,
    status_code=status.HTTP_200_OK,
    summary="上傳 PDF 文件（技術手冊 / SOP）",
)
def upload_document(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentIngestionResult:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只接受 PDF 檔案（.pdf）",
        )

    content = file.file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上傳的檔案為空")

    try:
        svc = DocumentIngestionService()
        return svc.ingest(db, project_id, filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
