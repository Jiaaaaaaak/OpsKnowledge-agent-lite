#!/usr/bin/env python3
"""Debug 工具：用「目前專案的 chunk splitting 邏輯」檢視一份 PDF 會被切成哪些 chunk。

設計重點：
- **不重寫、也不修改任何切塊邏輯**。直接重用 backend 的
  `DocumentIngestionService._extract_pages` 與 `._chunk_text`，
  並完全比照 `DocumentIngestionService.ingest()` 產生 chunk_index 與 metadata 的方式，
  確保這裡看到的結果與實際匯入時一致。
- 不連線資料庫、不連線 ChromaDB、不產生 embedding；純粹解析 PDF 並印出切塊結果。

用法（建議用 backend 的 venv，才有 pypdf 等相依套件）：
    backend/.venv/bin/python scripts/debug_chunks.py
    backend/.venv/bin/python scripts/debug_chunks.py path/to/your.pdf

每個 chunk 會印出：
    1. chunk index
    2. 字數（字元數）
    3. 前 200 字
    4. 後 200 字
    5. metadata（與 ingest() 寫入 document_chunks.metadata 的內容一致）
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

PREVIEW_LEN = 200


def _import_service():
    """延遲匯入後端的切塊服務，未安裝相依套件時給出清楚指引。"""
    try:
        from app.services.document_service import DocumentIngestionService
    except ModuleNotFoundError as exc:
        sys.stderr.write(
            f"[錯誤] 無法匯入後端切塊邏輯：{exc}\n\n"
            "請改用 backend 的虛擬環境執行（內含 pypdf 等相依套件）：\n"
            "    backend/.venv/bin/python scripts/debug_chunks.py\n"
            "或先安裝相依套件：\n"
            "    pip install -r backend/requirements.txt\n"
        )
        sys.exit(1)
    return DocumentIngestionService


def _format_preview(text: str) -> str:
    """把多行片段壓成單行顯示，讓換行不破壞排版（\\n 顯示為字面）。"""
    return text.replace("\n", "\\n")


def debug_chunks(pdf_path: Path) -> int:
    DocumentIngestionService = _import_service()

    content = pdf_path.read_bytes()

    # 比照 ingest()：先抽取所有頁面，再只保留非空白頁，chunk_index 跨頁累加。
    all_pages = DocumentIngestionService._extract_pages(content)
    total_pages = len(all_pages)
    non_empty_pages = [(num, text) for num, text in all_pages if text.strip()]

    filename = pdf_path.name

    print("=" * 72)
    print(f"來源檔案    ：{pdf_path}")
    print(f"總頁數      ：{total_pages}")
    print(f"非空白頁數  ：{len(non_empty_pages)}")
    print(f"切塊參數    ：chunk_size=1000, overlap=150（DocumentIngestionService 預設）")
    print("=" * 72)

    if not non_empty_pages:
        print("\n[警告] 此 PDF 不含可抽取的文字內容（可能為掃描圖檔），沒有任何 chunk。")
        return 0

    chunk_index = 0
    for page_num, page_text in non_empty_pages:
        for chunk_content in DocumentIngestionService._chunk_text(page_text):
            # metadata 與 ingest() 寫入 document_chunks.metadata 的結構完全一致
            metadata = {
                "filename": filename,
                "page_number": page_num,
                "chunk_size": len(chunk_content),
            }

            print(f"\n──────── chunk #{chunk_index} ────────")
            print(f"1. chunk index：{chunk_index}")
            print(f"2. 字數（字元）：{len(chunk_content)}")
            print(f"3. 前 {PREVIEW_LEN} 字：{_format_preview(chunk_content[:PREVIEW_LEN])}")
            print(f"4. 後 {PREVIEW_LEN} 字：{_format_preview(chunk_content[-PREVIEW_LEN:])}")
            print(f"5. metadata  ：{metadata}")

            chunk_index += 1

    print(f"\n{'=' * 72}")
    print(f"總計產生 {chunk_index} 個 chunk。")
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
