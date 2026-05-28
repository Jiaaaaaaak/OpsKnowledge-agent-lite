"""
DocumentIngestionService 單元測試
涵蓋：_chunk_text 分塊邏輯、_extract_pages（mocked）、ingest 主流程（mocked）
"""
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.document_service import DocumentIngestionService


# ─────────────────────────────────────────────────────────────
# _chunk_text 分塊邏輯
# ─────────────────────────────────────────────────────────────

class TestChunkText:

    def test_empty_text_returns_no_chunks(self):
        assert DocumentIngestionService._chunk_text("") == []

    def test_whitespace_only_returns_no_chunks(self):
        assert DocumentIngestionService._chunk_text("   \n\t  ") == []

    def test_short_text_single_chunk(self):
        chunks = DocumentIngestionService._chunk_text("Hello world")
        assert len(chunks) == 1
        assert chunks[0] == "Hello world"

    def test_exact_chunk_size_single_chunk(self):
        text = "a" * 1000
        chunks = DocumentIngestionService._chunk_text(text, chunk_size=1000, overlap=150)
        assert len(chunks) == 1
        assert len(chunks[0]) == 1000

    def test_text_slightly_over_chunk_size_two_chunks(self):
        # 1001 chars → chunk[0]=1000, start=850, chunk[1]=text[850:1001]=151 chars
        text = "a" * 1001
        chunks = DocumentIngestionService._chunk_text(text, chunk_size=1000, overlap=150)
        assert len(chunks) == 2

    def test_chunk_count_for_known_input(self):
        # 2000 chars, size=1000, overlap=150 → starts: 0, 850, 1700 → 3 chunks
        text = "a" * 2000
        chunks = DocumentIngestionService._chunk_text(text, chunk_size=1000, overlap=150)
        assert len(chunks) == 3

    def test_each_chunk_at_most_chunk_size(self):
        text = "x" * 5000
        chunks = DocumentIngestionService._chunk_text(text, chunk_size=1000, overlap=150)
        for chunk in chunks:
            assert len(chunk) <= 1000

    def test_overlap_content_shared_between_adjacent_chunks(self):
        # 1150 chars → chunk[0]=text[0:1000], chunk[1]=text[850:1150]
        # shared: text[850:1000] (150 chars) = chunks[0][-150:] = chunks[1][:150]
        text = "a" * 1150
        chunks = DocumentIngestionService._chunk_text(text, chunk_size=1000, overlap=150)
        assert len(chunks) == 2
        assert chunks[0][-150:] == chunks[1][:150]

    def test_first_chunk_starts_at_text_beginning(self):
        text = "StartOfText" + "x" * 2000
        chunks = DocumentIngestionService._chunk_text(text, chunk_size=1000, overlap=150)
        assert chunks[0].startswith("StartOfText")

    def test_last_chunk_ends_at_text_end(self):
        text = "x" * 2000 + "EndOfText"
        chunks = DocumentIngestionService._chunk_text(text, chunk_size=1000, overlap=150)
        assert chunks[-1].endswith("EndOfText")

    def test_custom_chunk_size(self):
        text = "b" * 600
        chunks = DocumentIngestionService._chunk_text(text, chunk_size=200, overlap=50)
        # starts: 0, 150, 300, 450 → ends: 200, 350, 500, 600 → 4 chunks
        assert len(chunks) == 4

    def test_custom_overlap(self):
        text = "c" * 1100
        chunks_no_overlap = DocumentIngestionService._chunk_text(text, chunk_size=1000, overlap=0)
        chunks_with_overlap = DocumentIngestionService._chunk_text(text, chunk_size=1000, overlap=150)
        # 重疊應產生更多 chunk（或相同），整體涵蓋一定更完整
        assert len(chunks_with_overlap) >= len(chunks_no_overlap)

    def test_strips_leading_trailing_whitespace_in_chunk(self):
        # 讓 text 開頭有空白，確認 strip 有作用
        text = "  " + "a" * 100 + "  "
        chunks = DocumentIngestionService._chunk_text(text)
        assert not chunks[0].startswith(" ")
        assert not chunks[0].endswith(" ")

    def test_single_character_text(self):
        chunks = DocumentIngestionService._chunk_text("X")
        assert chunks == ["X"]


# ─────────────────────────────────────────────────────────────
# _extract_pages（mocked PdfReader）
# ─────────────────────────────────────────────────────────────

class TestExtractPages:

    @patch("app.services.document_service.PdfReader")
    def test_returns_all_pages_including_empty(self, mock_reader_cls):
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page one text"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = ""  # 空白頁

        mock_reader_cls.return_value.pages = [mock_page1, mock_page2]

        pages = DocumentIngestionService._extract_pages(b"fake")
        assert len(pages) == 2
        assert pages[0] == (1, "Page one text")
        assert pages[1] == (2, "")

    @patch("app.services.document_service.PdfReader")
    def test_page_numbers_are_one_based(self, mock_reader_cls):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "text"
        mock_reader_cls.return_value.pages = [mock_page]

        pages = DocumentIngestionService._extract_pages(b"fake")
        assert pages[0][0] == 1  # 頁碼從 1 開始

    @patch("app.services.document_service.PdfReader")
    def test_invalid_pdf_raises_value_error(self, mock_reader_cls):
        mock_reader_cls.side_effect = Exception("bad pdf bytes")

        with pytest.raises(ValueError, match="無法解析"):
            DocumentIngestionService._extract_pages(b"not a pdf")


# ─────────────────────────────────────────────────────────────
# ingest 主流程（mocked DB + mocked PDF）
# ─────────────────────────────────────────────────────────────

class TestIngest:

    def _make_mock_page(self, text: str) -> MagicMock:
        page = MagicMock()
        page.extract_text.return_value = text
        return page

    @patch("app.services.document_service.PdfReader")
    def test_ingest_creates_document_and_chunks(self, mock_reader_cls):
        page1_text = "Section one content. " * 60   # ~1260 chars → 2 chunks
        page2_text = "Section two content. " * 40   # ~840 chars  → 1 chunk
        mock_reader_cls.return_value.pages = [
            self._make_mock_page(page1_text),
            self._make_mock_page(page2_text),
        ]

        mock_db = MagicMock()

        with patch.object(DocumentIngestionService, "_save_file", return_value=Path("data/uploads/test.pdf")):
            svc = DocumentIngestionService()
            result = svc.ingest(mock_db, uuid4(), "manual.pdf", b"fake_bytes")

        assert result.filename == "manual.pdf"
        assert result.page_count == 2
        assert result.chunk_count > 0
        assert result.source_path == "data/uploads/test.pdf"
        mock_db.commit.assert_called_once()

    @patch("app.services.document_service.PdfReader")
    def test_ingest_empty_pdf_raises(self, mock_reader_cls):
        mock_reader_cls.return_value.pages = [self._make_mock_page("")]

        mock_db = MagicMock()
        with patch.object(DocumentIngestionService, "_save_file", return_value=Path("data/uploads/empty.pdf")):
            svc = DocumentIngestionService()
            with pytest.raises(ValueError, match="文字"):
                svc.ingest(mock_db, uuid4(), "empty.pdf", b"fake_bytes")

    @patch("app.services.document_service.PdfReader")
    def test_chunk_metadata_contains_required_keys(self, mock_reader_cls):
        page_text = "Content for metadata test. " * 30  # ~810 chars
        mock_reader_cls.return_value.pages = [self._make_mock_page(page_text)]

        added_chunks: list = []

        def capture_add(obj):
            from app.models.document import DocumentChunk
            if isinstance(obj, DocumentChunk):
                added_chunks.append(obj)

        mock_db = MagicMock()
        mock_db.add.side_effect = capture_add

        with patch.object(DocumentIngestionService, "_save_file", return_value=Path("x")):
            svc = DocumentIngestionService()
            svc.ingest(mock_db, uuid4(), "sop.pdf", b"fake")

        assert len(added_chunks) >= 1
        for chunk in added_chunks:
            assert "filename" in chunk.metadata_
            assert "page_number" in chunk.metadata_
            assert "chunk_size" in chunk.metadata_
            assert chunk.metadata_["filename"] == "sop.pdf"
            assert chunk.metadata_["page_number"] == 1

    @patch("app.services.document_service.PdfReader")
    def test_chunk_indices_are_sequential(self, mock_reader_cls):
        # 兩頁，chunk_index 應跨頁連續遞增
        mock_reader_cls.return_value.pages = [
            self._make_mock_page("A " * 600),  # 1200 chars → 2 chunks
            self._make_mock_page("B " * 600),
        ]

        added_chunks: list = []

        def capture_add(obj):
            from app.models.document import DocumentChunk
            if isinstance(obj, DocumentChunk):
                added_chunks.append(obj)

        mock_db = MagicMock()
        mock_db.add.side_effect = capture_add

        with patch.object(DocumentIngestionService, "_save_file", return_value=Path("x")):
            svc = DocumentIngestionService()
            svc.ingest(mock_db, uuid4(), "doc.pdf", b"fake")

        indices = [c.chunk_index for c in added_chunks]
        assert indices == list(range(len(indices)))
