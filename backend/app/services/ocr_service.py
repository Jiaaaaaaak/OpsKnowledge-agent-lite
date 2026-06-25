"""掃描 / 影像型 PDF 的 OCR fallback。

只在文件抽取層被呼叫，且只對「抽不到文字」的頁渲染 + Tesseract 辨識，
原生文字頁完全不經過這裡。重依賴（pytesseract / pdf2image / tesseract binary /
poppler）以 lazy import 載入；缺任何一項時 ocr_available() 回 False，呼叫端自動降級
（等同未啟用 OCR），不影響原生文字 PDF 與 CI。
"""
from __future__ import annotations

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_ocr_available: bool | None = None  # 快取偵測結果，避免每份文件都檢查一次


def ocr_available() -> bool:
    """pytesseract + pdf2image 套件與 tesseract binary 是否齊備（lazy、快取）。"""
    global _ocr_available
    if _ocr_available is not None:
        return _ocr_available
    try:
        import pytesseract
        import pdf2image  # noqa: F401  僅確認可 import（poppler 由其在執行期使用）

        pytesseract.get_tesseract_version()  # 確認 tesseract 執行檔真的存在
        _ocr_available = True
    except Exception:
        logger.warning(
            "OCR 不可用（缺 tesseract / poppler 或對應 Python 套件），略過 OCR fallback"
        )
        _ocr_available = False
    return _ocr_available


def ocr_pdf_pages(content: bytes, page_numbers: list[int]) -> dict[int, str]:
    """逐頁（1-based）渲染指定頁並 OCR，回傳 {頁碼: 辨識文字}（空白結果略過）。

    逐頁渲染以控制記憶體；單頁失敗只記 log、跳過該頁，不中斷整份文件匯入。
    """
    if not page_numbers:
        return {}

    import pytesseract
    from pdf2image import convert_from_bytes

    results: dict[int, str] = {}
    for page_num in page_numbers:
        try:
            images = convert_from_bytes(
                content, dpi=settings.ocr_dpi, first_page=page_num, last_page=page_num
            )
            if not images:
                continue
            text = pytesseract.image_to_string(
                images[0], lang=settings.ocr_languages, timeout=settings.ocr_timeout_seconds
            )
            if text.strip():
                results[page_num] = text
        except Exception:
            logger.exception("OCR 第 %s 頁失敗，略過該頁", page_num)
    return results
