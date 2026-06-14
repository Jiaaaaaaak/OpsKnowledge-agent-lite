"""
Audit-driven 補強測試（Prompt 13）。

四大主題：
- ETL column normalization：補上既有測試沒覆蓋到的同義字（subsystem / comp /
  sev / pri / resolved_by / remedy / ticket_status）與標題行格式（hyphen / mixed
  case / trailing whitespace）
- Chunking：把 audit 找到的 latent infinite-loop bug（overlap >= chunk_size）
  以「現在會 raise ValueError」鎖死，並補上「分塊內容不含空白頭尾」與「分塊覆蓋
  原文」兩個 invariant
- Prompt construction：補上「同樣輸入產出 byte-for-byte 相同 prompt」的
  determinism 測試
- Dashboard aggregation：以靜態 import 分析證明 dashboard 模組沒有引入 LLM
  provider，鎖死「dashboard 不打 LLM」的承諾

這些測試不重複既有覆蓋（test_etl.py / test_document_service.py / test_chat.py /
test_dashboard.py），只補洞。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services.document_service import DocumentIngestionService
from app.services.etl_service import TicketETLService
from app.services.llm_service import build_rag_prompt


# ──────────────────────────────────────────────────────────────
# 1. ETL column normalization 補洞
# ──────────────────────────────────────────────────────────────


class TestETLNormalizationGaps:
    svc = TicketETLService()

    # ── 既有測試沒涵蓋到的同義字 ────────────────────────────────

    def test_module_from_subsystem(self):
        assert self.svc.normalize_columns({"subsystem": "auth"}) == {"module": "auth"}

    def test_module_from_comp(self):
        assert self.svc.normalize_columns({"comp": "queue"}) == {"module": "queue"}

    def test_priority_from_sev(self):
        assert self.svc.normalize_columns({"sev": "high"}) == {"priority": "high"}

    def test_priority_from_pri(self):
        assert self.svc.normalize_columns({"pri": "low"}) == {"priority": "low"}

    def test_resolution_from_resolved_by(self):
        assert self.svc.normalize_columns({"resolved_by": "ops"}) == {"resolution": "ops"}

    def test_resolution_from_remedy(self):
        assert self.svc.normalize_columns({"remedy": "restart"}) == {"resolution": "restart"}

    def test_resolution_from_resolution_notes(self):
        assert self.svc.normalize_columns({"resolution_notes": "n/a"}) == {"resolution": "n/a"}

    def test_status_from_ticket_status(self):
        assert self.svc.normalize_columns({"ticket_status": "open"}) == {"status": "open"}

    def test_status_from_incident_status(self):
        assert self.svc.normalize_columns({"incident_status": "closed"}) == {"status": "closed"}

    def test_system_from_affected_system(self):
        assert self.svc.normalize_columns({"affected_system": "payments"}) == {"system": "payments"}

    def test_issue_from_error_message(self):
        assert self.svc.normalize_columns({"error_message": "boom"}) == {"issue_description": "boom"}

    def test_issue_from_fault(self):
        assert self.svc.normalize_columns({"fault": "timeout"}) == {"issue_description": "timeout"}

    def test_occurred_at_from_reported_at(self):
        assert self.svc.normalize_columns({"reported_at": "2026-05-01"}) == {"occurred_at": "2026-05-01"}

    def test_occurred_at_from_incident_date(self):
        assert self.svc.normalize_columns({"incident_date": "2026-05-01"}) == {"occurred_at": "2026-05-01"}

    # ── 標題行常見變形 ───────────────────────────────────────

    def test_hyphenated_column_name(self):
        # CSV 標題用連字號（"ticket-id"）也要能映射 — _norm_key 把非字母數字轉底線
        assert self.svc.normalize_columns({"ticket-id": "T1"}) == {"ticket_id": "T1"}

    def test_mixed_case_uppercase_header(self):
        assert self.svc.normalize_columns({"TICKET_ID": "T1"}) == {"ticket_id": "T1"}

    def test_trailing_whitespace_in_header(self):
        # 部份匯出工具會留尾端空白；_norm_key 應 strip
        assert self.svc.normalize_columns({" ticket_id ": "T1"}) == {"ticket_id": "T1"}

    def test_dotted_header(self):
        # "Ticket.ID" 之類也應被視為 ticket_id
        assert self.svc.normalize_columns({"Ticket.ID": "T1"}) == {"ticket_id": "T1"}


# ──────────────────────────────────────────────────────────────
# 2. Chunking 補洞（含 audit 找到的 latent infinite-loop bug）
# ──────────────────────────────────────────────────────────────


class TestChunkingDefensiveGuards:
    """這些參數會讓滑動視窗永遠不前進；防呆應該 raise，而不是 hang 整個 worker。"""

    def test_overlap_equal_to_chunk_size_raises(self):
        # 原始 bug：chunk_size=10, overlap=10 → start = end - overlap = 0 → 無限迴圈
        with pytest.raises(ValueError, match="overlap"):
            DocumentIngestionService._chunk_text("x" * 50, chunk_size=10, overlap=10)

    def test_overlap_greater_than_chunk_size_raises(self):
        with pytest.raises(ValueError, match="overlap"):
            DocumentIngestionService._chunk_text("x" * 50, chunk_size=10, overlap=20)

    def test_negative_overlap_raises(self):
        with pytest.raises(ValueError, match="overlap"):
            DocumentIngestionService._chunk_text("x" * 50, chunk_size=10, overlap=-1)

    def test_zero_chunk_size_raises(self):
        with pytest.raises(ValueError, match="chunk_size"):
            DocumentIngestionService._chunk_text("x" * 50, chunk_size=0, overlap=0)

    def test_negative_chunk_size_raises(self):
        with pytest.raises(ValueError, match="chunk_size"):
            DocumentIngestionService._chunk_text("x" * 50, chunk_size=-1, overlap=0)

    # ── invariant：分塊內容性質 ──────────────────────────────

    def test_no_chunk_has_leading_or_trailing_whitespace(self):
        text = "  alpha   beta  \n\n gamma  delta " * 20
        chunks = DocumentIngestionService._chunk_text(text, chunk_size=30, overlap=5)
        assert chunks  # 至少有一塊
        for c in chunks:
            assert c == c.strip(), f"chunk has untrimmed whitespace: {c!r}"

    def test_chunks_cover_all_non_whitespace_content(self):
        # 合理 chunk_size / overlap 設定下，每個字元都應出現在至少一個 chunk
        text = "abcdefghijklmnopqrstuvwxyz0123456789"
        chunks = DocumentIngestionService._chunk_text(text, chunk_size=10, overlap=3)
        joined = "".join(chunks)
        # 每個字元至少出現一次
        for ch in text:
            assert ch in joined, f"char {ch!r} dropped"


# ──────────────────────────────────────────────────────────────
# 3. Prompt construction 補洞：determinism
# ──────────────────────────────────────────────────────────────


class TestPromptDeterminism:
    """同樣輸入 → byte-for-byte 相同 prompt（避免不小心引入時間 / 亂數 / set 順序）。"""

    _CHUNKS = [
        {"chunk_id": "c1", "content": "alpha", "metadata": {"filename": "a.pdf", "chunk_index": 0}},
        {"chunk_id": "c2", "content": "beta", "metadata": {"filename": "b.pdf", "chunk_index": 1}},
    ]

    def test_same_input_same_prompt(self):
        p1 = build_rag_prompt(self._CHUNKS)
        p2 = build_rag_prompt(self._CHUNKS)
        assert p1 == p2

    def test_empty_input_same_prompt(self):
        assert build_rag_prompt([]) == build_rag_prompt([])

    def test_input_order_preserved_in_prompt(self):
        # 第一個 chunk 標號 [1]，第二個 [2]；換順序對應的標號也跟著換
        prompt_ab = build_rag_prompt(self._CHUNKS)
        prompt_ba = build_rag_prompt(list(reversed(self._CHUNKS)))
        assert prompt_ab != prompt_ba
        # 確保不是因為內容不同：兩個 prompt 都含 alpha 與 beta
        assert "alpha" in prompt_ab and "beta" in prompt_ab
        assert "alpha" in prompt_ba and "beta" in prompt_ba


# ──────────────────────────────────────────────────────────────
# 4. Dashboard aggregation 補洞：靜態鎖死 "no LLM in dashboard" 屬性
# ──────────────────────────────────────────────────────────────


class TestDashboardHasNoLLMDependency:
    """
    用 AST 解析 dashboard.py 的 import 與 attribute access，
    確認沒有引入 llm_service / get_llm_provider / vector_store。
    這把 "dashboard 是純 SQL 唯讀聚合，不打 LLM" 的設計承諾鎖在測試裡。
    """

    @staticmethod
    def _dashboard_source() -> str:
        path = Path(__file__).parent.parent / "app" / "api" / "dashboard.py"
        return path.read_text(encoding="utf-8")

    def test_no_llm_service_import(self):
        tree = ast.parse(self._dashboard_source())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or "llm_service" not in node.module, (
                    f"dashboard.py 不應 import llm_service，但有: {node.module}"
                )
                for alias in node.names:
                    assert "get_llm_provider" not in alias.name
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert "llm_service" not in alias.name

    def test_no_vector_store_import(self):
        # 同理，dashboard 也不該打 vector store
        tree = ast.parse(self._dashboard_source())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or "vector_store" not in node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert "vector_store" not in alias.name

    def test_no_tools_import(self):
        # 也不該呼叫 incident_analysis tools（那是寫入路徑）
        tree = ast.parse(self._dashboard_source())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module is None or "app.tools" not in (node.module or "")
