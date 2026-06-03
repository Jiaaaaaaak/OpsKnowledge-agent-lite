#!/usr/bin/env python3
"""Debug 工具：用「目前專案的 chunk splitting 邏輯」檢視一份 PDF 會被切成哪些 chunk。

設計重點：
- **不重寫、也不修改任何切塊邏輯**。直接重用 backend 的
  `DocumentIngestionService._extract_pages`、`._join_pages`、`._chunk_text_by_section`，
  並完全比照 `DocumentIngestionService.ingest()` 的流程，
  確保這裡看到的結果與實際匯入時一致。
- 不連線資料庫、不連線 ChromaDB、不產生 embedding；純粹解析 PDF 並印出切塊結果。

用法（建議用 backend 的 venv，才有 pypdf 等相依套件）：
    backend/.venv/bin/python scripts/debug_chunks.py
    backend/.venv/bin/python scripts/debug_chunks.py path/to/your.pdf

每個 chunk 會印出：
    1. filename
    2. page_number
    3. chunk_index
    4. chunk_size（字元數）
    5. section_title
    6. section_level
    7. char_start / char_end
    8. 前 300 字
    9. 後 300 字
   10. 是否低於 min_chunk_size
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# scripts/ 與 backend/ 同層於專案根目錄；把 backend/ 加入 sys.path 才能 import app.*
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_SAMPLE = PROJECT_ROOT / "demo_data" / "documents" / "sample.pdf"

PREVIEW_LEN = 300

# 判斷是否為明顯殘段開頭（以小寫字母、標點或數字開頭，而非章節標題）
import re
_LEFTOVER_START_RE = re.compile(r'^[a-z一-鿿（）、，。：；？！…—\-]')


def _import_service():
    """延遲匯入後端的切塊服務，未安裝相依套件時給出清楚指引。"""
    try:
        from app.services.document_service import (
            DocumentIngestionService,
            _DEFAULT_CHUNK_SIZE,
            _DEFAULT_OVERLAP,
            _DEFAULT_MIN_CHUNK_SIZE,
        )
    except ModuleNotFoundError as exc:
        sys.stderr.write(
            f"[錯誤] 無法匯入後端切塊邏輯：{exc}\n\n"
            "請改用 backend 的虛擬環境執行（內含 pypdf 等相依套件）：\n"
            "    backend/.venv/bin/python scripts/debug_chunks.py\n"
            "或先安裝相依套件：\n"
            "    pip install -r backend/requirements.txt\n"
        )
        sys.exit(1)
    return DocumentIngestionService, _DEFAULT_CHUNK_SIZE, _DEFAULT_OVERLAP, _DEFAULT_MIN_CHUNK_SIZE


def _format_preview(text: str) -> str:
    """把多行片段壓成單行顯示，讓換行不破壞排版（\\n 顯示為字面）。"""
    return text.replace("\n", "\\n")


def _has_leftover_start(text: str) -> bool:
    """判斷 chunk 開頭是否為明顯的 overlap 殘段（非標題、非正常句首）。"""
    first_line = text.split('\n')[0].strip()
    if not first_line:
        return False
    # 以小寫字母或中文標點開頭，且不是已知章節標題格式
    return bool(_LEFTOVER_START_RE.match(first_line))


def debug_chunks(pdf_path: Path) -> int:
    DocumentIngestionService, chunk_size, overlap, min_chunk_size = _import_service()

    content = pdf_path.read_bytes()

    # 比照 ingest()：抽頁 → 過濾空白頁 → 合併 → 章節切分
    all_pages = DocumentIngestionService._extract_pages(content)
    total_pages = len(all_pages)
    non_empty_pages = [(num, text) for num, text in all_pages if text.strip()]

    filename = pdf_path.name

    print("=" * 72)
    print(f"來源檔案    ：{pdf_path}")
    print(f"總頁數      ：{total_pages}")
    print(f"非空白頁數  ：{len(non_empty_pages)}")
    print(f"切塊參數    ：chunk_size={chunk_size}, overlap={overlap}, min_chunk_size={min_chunk_size}")
    print("=" * 72)

    if not non_empty_pages:
        print("\n[警告] 此 PDF 不含可抽取的文字內容（可能為掃描圖檔），沒有任何 chunk。")
        return 0

    full_text, page_offsets = DocumentIngestionService._join_pages(non_empty_pages)
    chunk_dicts = DocumentIngestionService._chunk_text_by_section(full_text, page_offsets)

    # ── 統計摘要 ────────────────────────────────────────────────────────────
    lengths = [c['chunk_size'] for c in chunk_dicts]
    below_min_idx = [i for i, c in enumerate(chunk_dicts) if c['chunk_size'] < min_chunk_size]
    missing_title_idx = [i for i, c in enumerate(chunk_dicts) if not c.get('section_title')]
    leftover_idx = [i for i, c in enumerate(chunk_dicts) if _has_leftover_start(c['content'])]

    print(f"\n統計摘要：")
    if lengths:
        print(f"  總 chunk 數        ：{len(chunk_dicts)}")
        print(f"  平均長度           ：{sum(lengths) / len(lengths):.0f} 字元")
        print(f"  最短               ：{min(lengths)} 字元")
        print(f"  最長               ：{max(lengths)} 字元")
    else:
        print("  （無 chunk）")

    print(
        f"  section_title 缺失 ：{len(missing_title_idx)} 個"
        + (f"（chunk #{missing_title_idx}）" if missing_title_idx else "")
    )
    if below_min_idx:
        print(f"  ⚠ 低於 min_chunk_size({min_chunk_size}) 的 chunk：{below_min_idx}")
    else:
        print(f"  ✓ 沒有低於 min_chunk_size({min_chunk_size}) 的 chunk")
    if leftover_idx:
        print(f"  ⚠ 疑似 overlap 殘段開頭的 chunk：{leftover_idx}")
    else:
        print(f"  ✓ 沒有明顯 overlap 殘段開頭的 chunk")

    # ── 逐 chunk 詳細輸出 ────────────────────────────────────────────────────
    for chunk_index, chunk in enumerate(chunk_dicts):
        chunk_content = chunk['content']
        chunk_len = chunk['chunk_size']
        below_flag = chunk_len < min_chunk_size
        leftover_flag = _has_leftover_start(chunk_content)

        print(f"\n──────── chunk #{chunk_index} ────────")
        print(f"1. filename        ：{filename}")
        print(f"2. page_number     ：{chunk.get('page_number')}")
        print(f"3. chunk_index     ：{chunk_index}")
        print(f"4. chunk_size      ：{chunk_len} 字元")
        print(f"5. section_title   ：{chunk.get('section_title') or '（無）'}")
        print(f"6. section_level   ：{chunk.get('section_level', 'unknown')}")
        print(f"7. char_start/end  ：{chunk.get('char_start')} ~ {chunk.get('char_end')}")
        print(f"8. 前 {PREVIEW_LEN} 字        ：{_format_preview(chunk_content[:PREVIEW_LEN])}")
        print(f"9. 後 {PREVIEW_LEN} 字        ：{_format_preview(chunk_content[-PREVIEW_LEN:])}")
        print(f"10. 低於 min_chunk_size：{'⚠ 是' if below_flag else '否'}")
        print(f"11. 疑似殘段開頭   ：{'⚠ 是' if leftover_flag else '否'}")

    print(f"\n{'=' * 72}")
    print(f"總計產生 {len(chunk_dicts)} 個 chunk。")
    if below_min_idx:
        print(f"⚠ 其中 {len(below_min_idx)} 個 chunk 低於 min_chunk_size={min_chunk_size} 字元。")
    if leftover_idx:
        print(f"⚠ 其中 {len(leftover_idx)} 個 chunk 疑似以 overlap 殘段開頭。")
    if missing_title_idx:
        print(f"ℹ {len(missing_title_idx)} 個 chunk 的 section_title 為空（無法識別章節標題）。")
    print("=" * 72)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="用目前專案的切塊邏輯檢視一份 PDF 的 chunk 結果（debug 用）。"
    )
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default=str(DEFAULT_SAMPLE),
        help=f"要檢視的 PDF 路徑（預設：{DEFAULT_SAMPLE}）",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        sys.stderr.write(f"[錯誤] 找不到檔案：{pdf_path}\n")
        return 1

    return debug_chunks(pdf_path)


if __name__ == "__main__":
    raise SystemExit(main())
