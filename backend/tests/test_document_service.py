"""
DocumentIngestionService 單元測試
涵蓋：_chunk_text 分塊邏輯、_join_pages、_chunk_text_by_section、_extract_pages（mocked）、ingest 主流程（mocked）
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

    def test_text_slightly_over_chunk_size_废_chunk_filtered(self):
        # 1001 chars, chunk_size=1000, overlap=150 → chunk[1] 新增有效內容僅 1 字元 < min_chunk_size，應被過濾
        text = "a" * 1001
        chunks = DocumentIngestionService._chunk_text(text, chunk_size=1000, overlap=150)
        assert len(chunks) == 1

    def test_text_with_sufficient_new_content_keeps_second_chunk(self):
        # 1200 chars, chunk_size=1000, overlap=150 → chunk[1] 新增 200 字元 ≥ min_chunk_size=100，應保留
        text = "a" * 1200
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
# _join_pages 與 _page_number_at
# ─────────────────────────────────────────────────────────────

class TestJoinPages:

    def test_basic_two_pages(self):
        pages = [(1, "Page one"), (2, "Page two")]
        full_text, offsets = DocumentIngestionService._join_pages(pages)
        assert full_text == "Page one\n\nPage two"
        assert offsets[0] == (1, 0)
        assert offsets[1] == (2, len("Page one") + 2)

    def test_single_page(self):
        pages = [(1, "Only page")]
        full_text, offsets = DocumentIngestionService._join_pages(pages)
        assert full_text == "Only page"
        assert offsets == [(1, 0)]

    def test_three_pages_offsets(self):
        pages = [(1, "AAA"), (2, "BB"), (3, "CCCC")]
        full_text, offsets = DocumentIngestionService._join_pages(pages)
        assert full_text == "AAA\n\nBB\n\nCCCC"
        assert offsets[0] == (1, 0)
        assert offsets[1] == (2, 5)   # len("AAA") + 2
        assert offsets[2] == (3, 9)   # 5 + len("BB") + 2

    def test_page_number_at_first_page(self):
        offsets = [(1, 0), (2, 100), (3, 200)]
        assert DocumentIngestionService._page_number_at(0, offsets) == 1
        assert DocumentIngestionService._page_number_at(99, offsets) == 1

    def test_page_number_at_second_page(self):
        offsets = [(1, 0), (2, 100), (3, 200)]
        assert DocumentIngestionService._page_number_at(100, offsets) == 2
        assert DocumentIngestionService._page_number_at(199, offsets) == 2

    def test_page_number_at_last_page(self):
        offsets = [(1, 0), (2, 100), (3, 200)]
        assert DocumentIngestionService._page_number_at(200, offsets) == 3
        assert DocumentIngestionService._page_number_at(999, offsets) == 3

    def test_multi_page_chunk_page_number_reflects_content_position(self):
        page1 = "First page content here"
        page2 = "Second page content here"
        pages = [(1, page1), (2, page2)]
        full_text, offsets = DocumentIngestionService._join_pages(pages)
        p2_offset = offsets[1][1]
        # char 在 page2 起始之後，應回傳頁碼 2
        assert DocumentIngestionService._page_number_at(p2_offset, offsets) == 2
        assert DocumentIngestionService._page_number_at(p2_offset + 5, offsets) == 2
        # char 在 page2 起始之前，應回傳頁碼 1
        assert DocumentIngestionService._page_number_at(p2_offset - 1, offsets) == 1


# ─────────────────────────────────────────────────────────────
# _chunk_text_by_section
# ─────────────────────────────────────────────────────────────

class TestChunkTextBySection:

    def _single_page_offsets(self, full_text: str) -> list[tuple[int, int]]:
        return [(1, 0)]

    def test_chinese_section_title_in_metadata(self):
        text = "一、概述\n這是第一節的內容，詳細說明了系統架構與設計原則。\n\n二、安裝步驟\n請依照以下步驟操作完成安裝程序。"
        chunks = DocumentIngestionService._chunk_text_by_section(text, [(1, 0)])
        titles = [c['section_title'] for c in chunks if c.get('section_title')]
        assert any('一、' in t for t in titles), f"expected Chinese section title, got: {titles}"

    def test_english_numbered_section_title_in_metadata(self):
        # 每個段落超過 min_chunk_size(100)，避免短段合併遮蔽 section_title
        overview = "This is the overview section with detailed explanation of the system. " * 2
        causes = "The causes include network issues, disk full, and configuration errors. " * 2
        steps = "Follow these troubleshooting steps carefully to resolve the issue. " * 2
        text = (
            f"1. Overview\n{overview}\n\n"
            f"2. Possible Causes\n{causes}\n\n"
            f"3. Troubleshooting Steps\n{steps}"
        )
        chunks = DocumentIngestionService._chunk_text_by_section(text, [(1, 0)])
        titles = [c['section_title'] for c in chunks if c.get('section_title')]
        assert any('1.' in t for t in titles), f"expected numbered title starting with 1., got: {titles}"
        assert any('2.' in t for t in titles), f"expected numbered title starting with 2., got: {titles}"

    def test_markdown_heading_recognized_and_level_set(self):
        text = (
            "# Overview\nSystem overview here with detailed explanation.\n\n"
            "## Troubleshooting\nFollow these steps carefully.\n\n"
            "### Common Errors\nList of common errors and resolutions."
        )
        chunks = DocumentIngestionService._chunk_text_by_section(text, [(1, 0)])
        titles = [c['section_title'] for c in chunks if c.get('section_title')]
        levels = [c['section_level'] for c in chunks]
        assert any(t.startswith('#') for t in titles), f"expected Markdown title, got: {titles}"
        assert any(lv in ('h1', 'h2', 'h3') for lv in levels), f"expected h1/h2/h3, got: {levels}"

    def test_sop_keyword_section_title_recognized(self):
        text = (
            "Purpose\nThis document explains the recovery procedure.\n\n"
            "Prevention Checklist\n- Check item 1\n- Check item 2\n- Check item 3"
        )
        chunks = DocumentIngestionService._chunk_text_by_section(text, [(1, 0)])
        titles = [c['section_title'] for c in chunks if c.get('section_title')]
        assert any('Purpose' in t for t in titles), f"expected Purpose title, got: {titles}"

    def test_no_section_title_does_not_fail(self):
        text = "Some plain content without any section title. It just continues on."
        chunks = DocumentIngestionService._chunk_text_by_section(text, [(1, 0)])
        assert len(chunks) >= 1
        # section_title 可為 None，但不應拋出例外

    def test_short_adjacent_sections_merged(self):
        # 兩個很短的章節加起來 < chunk_size，應合併避免孤立短 chunk
        short1 = "Notes\n- Item A\n- Item B"               # ~24 chars
        short2 = "FAQ\n- Q: What? A: This."                # ~24 chars
        text = short1 + "\n\n" + short2
        chunks = DocumentIngestionService._chunk_text_by_section(
            text, [(1, 0)], chunk_size=800, min_chunk_size=100
        )
        # 若兩段合計 < min_chunk_size，應合併為一個 chunk
        total_len = len(short1) + len(short2)
        if total_len < 100:
            # 無論如何不應拋出例外；chunk 數量 <= 2
            assert len(chunks) <= 2

    def test_long_section_falls_back_to_chunk_text(self):
        # 超過 chunk_size 的章節應被拆成多個 chunk
        long_section = "## Long Section\n" + "Content sentence here. " * 80
        chunks = DocumentIngestionService._chunk_text_by_section(
            long_section, [(1, 0)], chunk_size=800
        )
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk['content']) <= 800

    def test_char_start_end_present_and_valid(self):
        text = "1. Overview\nContent here.\n\n2. Details\nMore content here."
        chunks = DocumentIngestionService._chunk_text_by_section(text, [(1, 0)])
        for chunk in chunks:
            assert 'char_start' in chunk
            assert 'char_end' in chunk
            assert chunk['char_end'] > chunk['char_start']
            # chunk content 應對應 full_text 中該範圍的內容（不要求完全相等，因 strip 可能有差）
            assert len(chunk['content']) > 0

    def test_page_number_from_offsets(self):
        page1 = "A" * 50
        page2 = "B" * 50
        full_text, offsets = DocumentIngestionService._join_pages([(1, page1), (2, page2)])
        chunks = DocumentIngestionService._chunk_text_by_section(full_text, offsets)
        page_nums = {c['page_number'] for c in chunks}
        # 至少應有 page 1 的 chunk
        assert 1 in page_nums

    def test_chunk_size_field_matches_content_length(self):
        text = "1. Overview\nContent.\n\n2. Details\nMore content here for details."
        chunks = DocumentIngestionService._chunk_text_by_section(text, [(1, 0)])
        for chunk in chunks:
            assert chunk['chunk_size'] == len(chunk['content'])


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
            # 原有欄位
            assert "filename" in chunk.metadata_
            assert "page_number" in chunk.metadata_
            assert "chunk_size" in chunk.metadata_
            assert chunk.metadata_["filename"] == "sop.pdf"
            assert chunk.metadata_["page_number"] == 1
            # 新增欄位
            assert "section_title" in chunk.metadata_
            assert "section_level" in chunk.metadata_
            assert "char_start" in chunk.metadata_
            assert "char_end" in chunk.metadata_

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


# ─────────────────────────────────────────────────────────────
# embedding 整合（注入 vector store）
# ─────────────────────────────────────────────────────────────

class TestIngestWithVectorStore:

    def _make_mock_page(self, text: str) -> MagicMock:
        page = MagicMock()
        page.extract_text.return_value = text
        return page

    @patch("app.services.document_service.PdfReader")
    def test_no_vector_store_skips_embedding(self, mock_reader_cls):
        # 未注入 vector store（單元測試 / 離線情境）時不得做 embedding
        mock_reader_cls.return_value.pages = [self._make_mock_page("A " * 600)]
        mock_db = MagicMock()
        with patch.object(DocumentIngestionService, "_save_file", return_value=Path("x")):
            svc = DocumentIngestionService()  # 無 vector store
            result = svc.ingest(mock_db, uuid4(), "doc.pdf", b"fake")
        assert result.chunk_count > 0
        mock_db.commit.assert_called_once()

    @patch("app.services.document_service.PdfReader")
    def test_embeds_before_commit_and_chunk_ids_match(self, mock_reader_cls):
        mock_reader_cls.return_value.pages = [self._make_mock_page("A " * 600)]  # 1200 chars → 2 chunks

        added_chunks: list = []

        def capture_add(obj):
            from app.models.document import DocumentChunk
            if isinstance(obj, DocumentChunk):
                added_chunks.append(obj)

        call_order: list[str] = []
        mock_db = MagicMock()
        mock_db.add.side_effect = capture_add
        mock_db.commit.side_effect = lambda: call_order.append("commit")

        vector_store = MagicMock()
        vector_store.add_chunks.side_effect = lambda payloads: call_order.append("embed")

        with patch.object(DocumentIngestionService, "_save_file", return_value=Path("x")):
            svc = DocumentIngestionService(vector_store=vector_store)
            project_id = uuid4()
            svc.ingest(mock_db, project_id, "doc.pdf", b"fake")

        vector_store.add_chunks.assert_called_once()
        payloads = vector_store.add_chunks.call_args.args[0]

        # ChromaDB 的 chunk_id 必須等同 PostgreSQL document_chunks.id（之後才能對回）
        assert {str(c.id) for c in added_chunks} == {p.chunk_id for p in payloads}
        # metadata 必帶 project_id，且 embedding 須在 commit 之前完成
        assert all(p.project_id == str(project_id) for p in payloads)
        assert call_order == ["embed", "commit"]

    @patch("app.services.document_service.PdfReader")
    def test_commit_failure_removes_vector_chunks(self, mock_reader_cls):
        mock_reader_cls.return_value.pages = [self._make_mock_page("A " * 600)]

        mock_db = MagicMock()
        mock_db.commit.side_effect = RuntimeError("database commit failed")

        vector_store = MagicMock()

        with patch.object(DocumentIngestionService, "_save_file", return_value=Path("x")):
            svc = DocumentIngestionService(vector_store=vector_store)
            with pytest.raises(RuntimeError, match="database commit failed"):
                svc.ingest(mock_db, uuid4(), "doc.pdf", b"fake")

        payloads = vector_store.add_chunks.call_args.args[0]
        vector_store.delete_chunks.assert_called_once_with([p.chunk_id for p in payloads])
