"""
ocr_service 單元測試。

OCR 是掃描 / 影像型 PDF 的 fallback：只對抽不到文字的頁渲染 + Tesseract 辨識。
這裡 mock pdf2image / pytesseract，驗證「逐頁處理、單頁失敗不中斷、空白略過」，
不依賴真實 tesseract binary。
"""
from unittest.mock import MagicMock, patch

from app.services import ocr_service


def test_ocr_pdf_pages_empty_input_returns_empty():
    assert ocr_service.ocr_pdf_pages(b"x", []) == {}


def test_ocr_pdf_pages_ocrs_each_requested_page():
    fake_img = MagicMock()
    with patch("pdf2image.convert_from_bytes", return_value=[fake_img]) as mock_conv, \
         patch("pytesseract.image_to_string", return_value="辨識文字"):
        out = ocr_service.ocr_pdf_pages(b"pdf", [2, 5])

    assert out == {2: "辨識文字", 5: "辨識文字"}
    # 逐頁渲染（控記憶體）：每頁各呼叫一次 convert
    assert mock_conv.call_count == 2


def test_ocr_pdf_pages_skips_failed_page_without_aborting():
    # 單頁渲染/辨識失敗只略過該頁，其餘頁仍正常。
    def fake_convert(content, dpi, first_page, last_page):
        if first_page == 1:
            raise RuntimeError("render failed")
        return [MagicMock()]

    with patch("pdf2image.convert_from_bytes", side_effect=fake_convert), \
         patch("pytesseract.image_to_string", return_value="ok"):
        out = ocr_service.ocr_pdf_pages(b"x", [1, 2])

    assert out == {2: "ok"}


def test_ocr_pdf_pages_skips_blank_result():
    with patch("pdf2image.convert_from_bytes", return_value=[MagicMock()]), \
         patch("pytesseract.image_to_string", return_value="   \n  "):
        assert ocr_service.ocr_pdf_pages(b"x", [1]) == {}


def test_ocr_available_caches_result():
    # 偵測結果應快取，避免每份文件重複檢查。
    ocr_service._ocr_available = True
    try:
        assert ocr_service.ocr_available() is True
    finally:
        ocr_service._ocr_available = None
