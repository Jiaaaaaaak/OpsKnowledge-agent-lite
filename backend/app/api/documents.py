import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.document import Document
from app.models.project import Project
from app.services.document_service import DocumentIngestionResult, DocumentIngestionService
from app.services.retrieval import get_retrieval_service
from app.services.vector_store import get_vector_store

router = APIRouter(prefix="/projects", tags=["Documents"])


class DocumentSummary(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    filename: str
    document_type: str
    page_count: int
    chunk_count: int
    created_at: str


@router.get(
    "/{project_id}/documents",
    response_model=list[DocumentSummary],
    status_code=status.HTTP_200_OK,
    summary="列出專案已上傳文件",
)
def list_documents(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[DocumentSummary]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    documents = (
        db.query(Document)
        .filter(Document.project_id == project_id)
        .order_by(Document.created_at.desc())
        .all()
    )

    return [
        DocumentSummary(
            id=doc.id,
            project_id=doc.project_id,
            filename=doc.filename,
            document_type=doc.document_type,
            page_count=int((doc.metadata_ or {}).get("page_count") or 0),
            chunk_count=len(doc.chunks),
            created_at=doc.created_at.isoformat(),
        )
        for doc in documents
    ]


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

    # 只讀到上限 + 1 byte：避免把超大檔整個塞進記憶體才發現超標。
    max_bytes = settings.max_upload_mb * 1024 * 1024
    content = file.file.read(max_bytes + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上傳的檔案為空")
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"檔案超過大小上限 {settings.max_upload_mb} MB",
        )

    try:
        svc = DocumentIngestionService(vector_store=get_vector_store(db_session=db))
        return svc.ingest(db, project_id, filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        # 例如缺少 OPENAI_API_KEY，無法產生 embedding
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


class DocumentSearchHit(BaseModel):
    chunk_id: str
    content: str
    metadata: dict
    distance: float | None = None
    score: float | None = None
    fusion_score: float | None = None
    sources: list[str] = Field(default_factory=list)
    scores: dict[str, float | None] = Field(default_factory=dict)


class DocumentSearchResponse(BaseModel):
    project_id: uuid.UUID
    query: str
    top_k: int
    results: list[DocumentSearchHit]


@router.get(
    "/{project_id}/search",
    response_model=DocumentSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="在專案文件中做語意相似度搜尋",
)
def search_documents(
    project_id: uuid.UUID,
    query: str = Query(..., min_length=1, description="搜尋字串"),
    top_k: int = Query(5, ge=1, le=50, description="回傳的最相似 chunk 數"),
    db: Session = Depends(get_db),
) -> DocumentSearchResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    try:
        retrieval = get_retrieval_service(db_session=db)
        hits, _breakdown = retrieval.search(str(project_id), query, top_k=top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return DocumentSearchResponse(
        project_id=project_id,
        query=query,
        top_k=top_k,
        results=[DocumentSearchHit(**hit) for hit in hits],
    )
