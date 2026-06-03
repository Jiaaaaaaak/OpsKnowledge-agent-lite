from __future__ import annotations

import re
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

_DEFAULT_CHUNK_SIZE = 800
_DEFAULT_OVERLAP = 100
_DEFAULT_MIN_CHUNK_SIZE = 100

# 章節標題偵測：支援 Markdown / 中文數字 / 阿拉伯數字 / 羅馬數字 / SOP 常見關鍵字
_SECTION_HEADING_RE = re.compile(
    r'(?m)^(?:'
    r'#{1,6}\s+[^\n]+'                                      # Markdown: ## Title
    r'|[一二三四五六七八九十百][、.][^\n]+'                 # 中文: 一、Title
    r'|\d+(?:\.\d+)*[.、]\s[^\n]+'                          # 阿拉伯: 1. Title / 1.1 Title
    r'|[IVX]{1,4}\.\s[^\n]+'                                # 羅馬: I. Title / II. Title
    r'|(?:Purpose|Scope|Symptoms|Possible\s+Causes|Troubleshooting\s+Steps|'
    r'Resolution|Prevention\s+Checklist|FAQ|Notes|Overview|Introduction|'
    r'Summary|Background|Conclusion|References|Appendix)'
    r'(?:\s*:[^\n]{0,80}|\s*$)'                             # 可選冒號與簡短說明
    r')',
    re.IGNORECASE,
)


def _heading_level(text: str) -> str:
    """從標題文字推斷章節層級。"""
    text = text.strip()
    m = re.match(r'^(#{1,6})\s', text)
    if m:
        levels = {1: 'h1', 2: 'h2', 3: 'h3', 4: 'h4', 5: 'h5', 6: 'h6'}
        return levels.get(len(m.group(1)), 'h6')
    if re.match(r'^[一二三四五六七八九十百][、.]', text):
        return 'numbered'
    if re.match(r'^\d+(?:\.\d+)*[.、]\s', text):
        return 'numbered'
    if re.match(r'^[IVX]{1,4}\.\s', text):
        return 'numbered'
    return 'keyword'


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
        min_chunk_size: int = _DEFAULT_MIN_CHUNK_SIZE,
    ) -> list[str]:
        """滑動視窗分塊，過濾有效內容不足的廢 chunk，回傳非空 chunk 清單.

        過濾規則（min_chunk_size > 0 時啟用）：
        - 第一個 chunk 一律保留（保護短文件不消失）。
        - 後續 chunk：若「新增有效內容」= len(chunk) - overlap < min_chunk_size，
          視為近乎重複的 overlap 廢 chunk，予以丟棄。
        """
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

        # 過濾廢 chunk：非第一個 chunk 若新增有效內容不足時丟棄。
        # 門檻取 min(min_chunk_size, overlap)：
        #   - overlap 大（如 150）→ 門檻高，能過濾近乎全部是 overlap 的廢 chunk。
        #   - overlap 小（如 3）→ 門檻低，避免誤刪有效的末尾小 chunk。
        # len(chunks) <= 1 時跳過（整頁文字極短，保留唯一 chunk 避免短文件消失）。
        if len(chunks) > 1 and min_chunk_size > 0 and overlap > 0:
            effective_min_new = min(min_chunk_size, overlap)
            filtered = [chunks[0]]
            for chunk in chunks[1:]:
                if len(chunk) - overlap >= effective_min_new:
                    filtered.append(chunk)
            chunks = filtered

        return chunks

    @staticmethod
    def _extract_pages(content: bytes) -> list[tuple[int, str]]:
        """解析 PDF，回傳 [(1-based 頁碼, 頁面文字)] 的完整頁面清單."""
        try:
            reader = PdfReader(BytesIO(content))
        except Exception as exc:
            raise ValueError(f"無法解析 PDF 檔案：{exc}") from exc
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]

    @staticmethod
    def _join_pages(pages: list[tuple[int, str]]) -> tuple[str, list[tuple[int, int]]]:
        """合併多頁文字，回傳 (全文, [(page_num, char_start), ...])。"""
        parts: list[str] = []
        page_offsets: list[tuple[int, int]] = []
        offset = 0
        for page_num, text in pages:
            page_offsets.append((page_num, offset))
            parts.append(text)
            offset += len(text) + 2  # "\n\n" 分隔符佔 2 字元
        return "\n\n".join(parts), page_offsets

    @staticmethod
    def _page_number_at(char_pos: int, page_offsets: list[tuple[int, int]]) -> int:
        """根據 char offset 反查頁碼。"""
        result = page_offsets[0][0]
        for pn, start in page_offsets:
            if char_pos >= start:
                result = pn
            else:
                break
        return result

    @staticmethod
    def _chunk_text_by_section(
        full_text: str,
        page_offsets: list[tuple[int, int]],
        chunk_size: int = _DEFAULT_CHUNK_SIZE,
        overlap: int = _DEFAULT_OVERLAP,
        min_chunk_size: int = _DEFAULT_MIN_CHUNK_SIZE,
    ) -> list[dict]:
        """按章節邊界優先切分，回傳含 metadata 的 chunk 字典清單。

        每個字典包含：content, section_title, section_level,
        char_start, char_end, page_number, chunk_size。
        """
        heading_matches = list(_SECTION_HEADING_RE.finditer(full_text))
        boundaries = [m.start() for m in heading_matches] + [len(full_text)]

        # 建立 sections：(sec_start, sec_end, title, level)
        sections: list[tuple[int, int, str | None, str]] = []
        first_boundary = boundaries[0] if heading_matches else len(full_text)
        if first_boundary > 0:
            sections.append((0, first_boundary, None, 'unknown'))
        for i, m in enumerate(heading_matches):
            title = m.group().strip()
            level = _heading_level(title)
            sections.append((m.start(), boundaries[i + 1], title, level))

        if not sections:
            sections.append((0, len(full_text), None, 'unknown'))

        # 逐 section 產生 raw chunks
        raw_chunks: list[dict] = []
        for sec_start, sec_end, title, level in sections:
            sec_text = full_text[sec_start:sec_end].strip()
            if not sec_text:
                continue

            # 找到 stripped text 在 full_text 中的實際起始位置
            actual_start = full_text.find(sec_text, sec_start)
            if actual_start == -1:
                actual_start = sec_start

            if len(sec_text) <= chunk_size:
                raw_chunks.append({
                    'content': sec_text,
                    'section_title': title,
                    'section_level': level,
                    'char_start': actual_start,
                    'char_end': actual_start + len(sec_text),
                })
            else:
                # 超出 chunk_size，fallback 到 _chunk_text，追蹤各子 chunk 位置
                sub_chunks = DocumentIngestionService._chunk_text(
                    sec_text, chunk_size, overlap, min_chunk_size
                )
                sub_pos = 0
                for sub in sub_chunks:
                    search_from = max(0, sub_pos - overlap)
                    idx = sec_text.find(sub, search_from)
                    if idx == -1:
                        idx = sub_pos
                    abs_start = actual_start + idx
                    raw_chunks.append({
                        'content': sub,
                        'section_title': title,
                        'section_level': level,
                        'char_start': abs_start,
                        'char_end': abs_start + len(sub),
                    })
                    sub_pos = idx + len(sub) - overlap
                    if sub_pos < 0:
                        sub_pos = 0

        # 合併相鄰短 chunk，避免孤立的 100~250 字元 chunk
        merged: list[dict] = []
        for chunk in raw_chunks:
            should_merge = (
                merged
                and (
                    len(chunk['content']) < min_chunk_size
                    or len(merged[-1]['content']) < min_chunk_size
                )
                and len(merged[-1]['content']) + len(chunk['content']) + 1 <= chunk_size
            )
            if should_merge:
                prev = merged[-1]
                prev['content'] = prev['content'] + '\n' + chunk['content']
                prev['char_end'] = chunk['char_end']
                if prev['section_title'] is None and chunk['section_title'] is not None:
                    prev['section_title'] = chunk['section_title']
                    prev['section_level'] = chunk['section_level']
            else:
                merged.append(dict(chunk))

        # 補充 page_number 與 chunk_size
        for chunk in merged:
            chunk['page_number'] = DocumentIngestionService._page_number_at(
                chunk['char_start'], page_offsets
            )
            chunk['chunk_size'] = len(chunk['content'])

        return merged

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

        # 全文合併 → 章節優先切分
        full_text, page_offsets = self._join_pages(non_empty_pages)
        chunk_dicts = self._chunk_text_by_section(full_text, page_offsets)

        chunk_index = 0
        payloads: list[ChunkPayload] = []
        for chunk_dict in chunk_dicts:
            chunk_id = uuid4()
            chunk_content = chunk_dict['content']
            db.add(DocumentChunk(
                id=chunk_id,
                document_id=doc.id,
                chunk_index=chunk_index,
                content=chunk_content,
                metadata_={
                    "filename": filename,
                    "page_number": chunk_dict['page_number'],
                    "chunk_size": chunk_dict['chunk_size'],
                    "section_title": chunk_dict.get('section_title'),
                    "section_level": chunk_dict.get('section_level', 'unknown'),
                    "char_start": chunk_dict['char_start'],
                    "char_end": chunk_dict['char_end'],
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
