#!/usr/bin/env python3
"""將 demo_data/documents 下的 Markdown SOP 轉成簡易 PDF，供 PDF 文件匯入流程使用。

設計重點：
- 純展示用途，不依賴後端應用程式邏輯，可獨立執行。
- 使用 ReportLab 的 MSung-Light（Adobe-CNS1）CID 字型來呈現繁體中文，
  好處是「不需要外掛 .ttf 字型檔」，且會嵌入 ToUnicode 對應表，
  讓後端的 pypdf 仍能把文字抽取回來做 RAG。
- 只做輕量的 Markdown 解析（標題、項目符號、引言、段落），足以保留可讀結構。

字型限制與替代方案請見檔案末端說明，以及 demo_data/README.md。
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

# demo_data 與本腳本的相對位置（scripts/ 與 demo_data/ 同層於專案根目錄）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "demo_data" / "documents"
OUTPUT_DIR = DOCS_DIR / "pdf"

SOURCE_FILES = [
    "docker_volume_sop.md",
    "vpn_troubleshooting_sop.md",
    "postgres_connection_sop.md",
    "backup_and_nas_sop.md",
]

# 繁體中文 CID 字型（Adobe-CNS1），由 ReportLab 內建支援，無需額外字型檔。
CJK_FONT = "MSung-Light"


def _require_reportlab():
    """延遲匯入 ReportLab，未安裝時給出清楚的安裝指引與手動替代方案。"""
    try:
        import reportlab  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "[錯誤] 找不到 reportlab，無法產生 PDF。\n\n"
            "請先安裝相依套件（已加入 backend/requirements.txt）：\n"
            "    pip install -r backend/requirements.txt\n"
            "或單獨安裝：\n"
            "    pip install reportlab\n\n"
            "替代方案（手動匯出，需自行安裝 pandoc 與 CJK 字型）：\n"
            "    pandoc demo_data/documents/docker_volume_sop.md \\\n"
            "        -o demo_data/documents/pdf/docker_volume_sop.pdf \\\n"
            "        --pdf-engine=xelatex -V CJKmainfont='Noto Sans CJK TC'\n"
        )
        sys.exit(1)


def _register_font():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont(CJK_FONT))


def _build_styles():
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    base = getSampleStyleSheet()
    styles = {
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName=CJK_FONT,
                             fontSize=18, leading=24, spaceBefore=6, spaceAfter=12),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName=CJK_FONT,
                             fontSize=14, leading=20, spaceBefore=12, spaceAfter=6),
        "h3": ParagraphStyle("h3", parent=base["Heading3"], fontName=CJK_FONT,
                             fontSize=12, leading=18, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName=CJK_FONT,
                               fontSize=10.5, leading=16, alignment=TA_LEFT),
        "bullet": ParagraphStyle("bullet", parent=base["BodyText"], fontName=CJK_FONT,
                                 fontSize=10.5, leading=16, leftIndent=16,
                                 bulletIndent=4),
        "quote": ParagraphStyle("quote", parent=base["BodyText"], fontName=CJK_FONT,
                                fontSize=9.5, leading=15, leftIndent=12,
                                textColor="#555555"),
    }
    return styles


def _inline(text: str) -> str:
    """跳脫 XML 特殊字元，並把 **粗體** 轉成 ReportLab 的 <b> 標記。"""
    safe = html.escape(text)
    # 簡單的成對 **...** → <b>...</b>（不處理巢狀）
    parts = safe.split("**")
    if len(parts) >= 3:
        out = []
        for i, part in enumerate(parts):
            out.append(part if i % 2 == 0 else f"<b>{part}</b>")
        safe = "".join(out)
    return safe


def _md_to_flowables(md_text: str, styles):
    """把 Markdown 文字轉成 ReportLab flowable 串列（輕量解析）。"""
    from reportlab.platypus import Paragraph, Spacer

    flow = []
    for raw in md_text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            flow.append(Spacer(1, 4))
            continue

        if stripped.startswith("### "):
            flow.append(Paragraph(_inline(stripped[4:]), styles["h3"]))
        elif stripped.startswith("## "):
            flow.append(Paragraph(_inline(stripped[3:]), styles["h2"]))
        elif stripped.startswith("# "):
            flow.append(Paragraph(_inline(stripped[2:]), styles["h1"]))
        elif stripped.startswith(">"):
            flow.append(Paragraph(_inline(stripped.lstrip("> ").rstrip()), styles["quote"]))
        elif stripped.startswith("- ") or stripped.startswith("* "):
            item = stripped[2:]
            # 把 GitHub 任務清單 - [ ] / - [x] 轉成可讀符號
            if item.startswith("[ ] "):
                item = "☐ " + item[4:]
            elif item.startswith("[x] ") or item.startswith("[X] "):
                item = "☑ " + item[4:]
            flow.append(Paragraph(_inline(item), styles["bullet"], bulletText="•"))
        elif stripped[0].isdigit() and ". " in stripped[:4]:
            flow.append(Paragraph(_inline(stripped), styles["body"]))
        else:
            flow.append(Paragraph(_inline(stripped), styles["body"]))
    return flow


def _convert(md_path: Path, styles) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate

    out_path = OUTPUT_DIR / (md_path.stem + ".pdf")
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=md_path.stem,
    )
    doc.build(_md_to_flowables(md_path.read_text(encoding="utf-8"), styles))
    return out_path


def main() -> int:
    _require_reportlab()
    _register_font()
    styles = _build_styles()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    missing = [f for f in SOURCE_FILES if not (DOCS_DIR / f).exists()]
    if missing:
        sys.stderr.write(f"[錯誤] 找不到來源 Markdown：{', '.join(missing)}\n")
        return 1

    print(f"輸出目錄：{OUTPUT_DIR}")
    for name in SOURCE_FILES:
        out = _convert(DOCS_DIR / name, styles)
        size_kb = out.stat().st_size / 1024
        print(f"  ✓ {name} → {out.name} ({size_kb:.0f} KB)")

    print(f"\n完成，共產生 {len(SOURCE_FILES)} 個 PDF。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
