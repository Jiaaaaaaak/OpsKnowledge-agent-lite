from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import BaseModel
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentChunk

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

    @staticmethod
    def _chunk_text(
        text: str,
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        overlap: int = _DEFAULT_OVERLAP,
    ) -> list[str]:
        """滑動視窗分塊，回傳非空 chunk 清單."""
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

        chunk_index = 0
        for page_num, page_text in non_empty_pages:
            for chunk_content in self._chunk_text(page_text):
                db.add(DocumentChunk(
                    document_id=doc.id,
                    chunk_index=chunk_index,
                    content=chunk_content,
                    metadata_={
                        "filename": filename,
                        "page_number": page_num,
                        "chunk_size": len(chunk_content),
                    },
                ))
                chunk_index += 1

        db.commit()

        return DocumentIngestionResult(
            document_id=doc.id,
            filename=filename,
            page_count=total_pages,
            chunk_count=chunk_index,
            source_path=source_path,
        )
