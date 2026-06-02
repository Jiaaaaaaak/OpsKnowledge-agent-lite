from __future__ import annotations

from io import BytesIO
import logging
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentChunk

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.vector_store import VectorStoreService

UPLOAD_DIR = Path("data/uploads")

_DEFAULT_CHUNK_SIZE = 1000
_DEFAULT_OVERLAP = 150


class DocumentIngestionResult(BaseModel):
    document_id: UUID
    filename: str
    page_count: int
    chunk_count: int
    source_path: str


class DocumentIngestionService:

    def __init__(self, vector_store: "VectorStoreService | None" = None) -> None:
        # 注入 vector store 才會做 embedding；未注入時（如單元測試）僅寫入 PostgreSQL。
        self._vector_store = vector_store

    @staticmethod
    def _chunk_text(
        text: str,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        overlap: int = _DEFAULT_OVERLAP,
    ) -> list[str]:
        """滑動視窗分塊，回傳非空 chunk 清單."""
        # 防呆：avoid infinite loop when caller passes chunk_size <= overlap
        # (start = end - overlap 在這種情況下不會前進)
        if chunk_size <= 0:
            raise ValueError(f"chunk_size must be positive, got {chunk_size}")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError(
                f"overlap must satisfy 0 <= overlap < chunk_size; got overlap={overlap}, chunk_size={chunk_size}"
            )
        text = text.strip()
        if not text:
            return []
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(text):
                break
            start = end - overlap
        return chunks

    @staticmethod
    def _extract_pages(content: bytes) -> list[tuple[int, str]]:
        """解析 PDF，回傳 [(1-based 頁碼, 頁面文字)] 的完整頁面清單."""
        try:
            reader = PdfReader(BytesIO(content))
        except Exception as exc:
            raise ValueError(f"無法解析 PDF 檔案：{exc}") from exc
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]

    def _save_file(self, project_id: UUID, filename: str, content: bytes) -> Path:
        dest_dir = UPLOAD_DIR / str(project_id) / "documents"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filename
        dest.write_bytes(content)
        return dest

    def ingest(
        self,
        db: Session,
        project_id: UUID,
        filename: str,
        content: bytes,
    ) -> DocumentIngestionResult:
        """儲存 PDF 至磁碟、抽取文字分塊、寫入資料庫，回傳匯入摘要."""
        all_pages = self._extract_pages(content)
        total_pages = len(all_pages)

        non_empty_pages = [(num, text) for num, text in all_pages if text.strip()]
        if not non_empty_pages:
            raise ValueError("PDF 不含可抽取的文字內容（可能為掃描圖檔）")

        source_path = str(self._save_file(project_id, filename, content))

        doc = Document(
            id=uuid4(),  # 先產生 id，供下方 chunk 設定 FK 與回傳結果使用（避免依賴 flush 時機）
            project_id=project_id,
            filename=filename,
            document_type="pdf",
            source_path=source_path,
            metadata_={"page_count": total_pages},
        )
        db.add(doc)

        from app.services.vector_store import ChunkPayload

        chunk_index = 0
        payloads: list[ChunkPayload] = []
        for page_num, page_text in non_empty_pages:
            for chunk_content in self._chunk_text(page_text):
                chunk_id = uuid4()  # 先產生 id，使 ChromaDB 的 id 與此筆 document_chunks.id 一致
                db.add(DocumentChunk(
                    id=chunk_id,
                    document_id=doc.id,
                    chunk_index=chunk_index,
                    content=chunk_content,
                    metadata_={
                        "filename": filename,
                        "page_number": page_num,
                        "chunk_size": len(chunk_content),
                    },
                ))
                payloads.append(ChunkPayload(
                    chunk_id=str(chunk_id),
                    document_id=str(doc.id),
                    project_id=str(project_id),
                    filename=filename,
                    chunk_index=chunk_index,
                    content=chunk_content,
                ))
                chunk_index += 1

        # 先 embed 並寫入 ChromaDB，成功後才 commit；embedding 失敗則不留下半套資料。
        vector_chunk_ids: list[str] = []
        if self._vector_store is not None:
            self._vector_store.add_chunks(payloads)
            vector_chunk_ids = [p.chunk_id for p in payloads]

        try:
            db.commit()
        except Exception:
            db.rollback()
            if self._vector_store is not None and vector_chunk_ids:
                try:
                    self._vector_store.delete_chunks(vector_chunk_ids)
                except Exception:
                    logger.exception("failed to delete ChromaDB chunks after PostgreSQL commit failure")
            raise

        return DocumentIngestionResult(
            document_id=doc.id,
            filename=filename,
            page_count=total_pages,
            chunk_count=chunk_index,
            source_path=source_path,
        )
