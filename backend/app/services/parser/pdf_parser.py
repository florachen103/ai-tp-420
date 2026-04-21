"""PDF 解析：优先文字层抽取；无文字层时自动 OCR 兜底。

常见失败场景：Mac 用「屏幕截图 → 导出 PDF」得到的 PDF 是纯图片（无文字层），
必须走 OCR 才能抽到文本。因此如果 OCR 依赖缺失，我们直接抛出清晰错误，
让上层能把可执行的修复建议返回给前端，而不是笼统地报「未提取到可用文本」。
"""
from __future__ import annotations

import pdfplumber
from loguru import logger

_OCR_IMPORT_ERROR: str | None = None
try:
    import pytesseract
    from pdf2image import convert_from_path
except Exception as _e:  # OCR 依赖未安装时不影响系统启动，只在遇到无文字层 PDF 时暴露
    pytesseract = None  # type: ignore[assignment]
    convert_from_path = None  # type: ignore[assignment]
    _OCR_IMPORT_ERROR = f"{type(_e).__name__}: {_e}"

from app.core.config import settings
from app.models.course import MaterialType
from app.services.parser.base import ParsedDocument, ParsedSection

# 单页有效文字阈值：Mac 截图 PDF 偶尔会混入极少量 metadata / 水印字符，
# 但不足以支撑语义切片。低于该阈值的页面也按"文字层缺失"处理。
_MIN_TEXT_CHARS_PER_PAGE = 8


def _ocr_deps_available() -> bool:
    return pytesseract is not None and convert_from_path is not None


def parse_pdf(file_path: str, filename: str) -> ParsedDocument:
    sections: list[ParsedSection] = []
    page_count = 0
    text_pages = 0  # 文字层抽到有效文本的页数
    with pdfplumber.open(file_path) as pdf:
        page_count = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            # 抽表格追加
            try:
                tables = page.extract_tables() or []
                for t in tables:
                    rows = [" | ".join((c or "").strip().replace("\n", " ") for c in row) for row in t]
                    if rows:
                        text += "\n\n【表格】\n" + "\n".join(rows)
            except Exception:
                pass

            text = text.strip()
            if len(text) >= _MIN_TEXT_CHARS_PER_PAGE:
                text_pages += 1
                sections.append(ParsedSection(
                    title=f"第 {i + 1} 页",
                    content=text,
                    order_idx=i,
                    meta={"page": i + 1},
                ))

    ocr_used = False
    ocr_pages_tried = 0
    ocr_pages_got_text = 0

    if not sections and settings.PDF_OCR_FALLBACK_ENABLED:
        if not _ocr_deps_available():
            # 依赖缺失时直接报错，让上层把可执行的修复建议返回给前端
            raise RuntimeError(
                "该 PDF 没有文字层（常见于 Mac 截图导出 PDF、扫描件），需要 OCR 才能抽文本；"
                "但后端容器未安装 OCR 依赖（需要系统包 tesseract-ocr / poppler-utils，以及 "
                "Python 包 pytesseract / pdf2image）。请重建后端与 worker 镜像：\n"
                "  docker compose build --no-cache backend worker && docker compose up -d backend worker\n"
                f"原始导入错误：{_OCR_IMPORT_ERROR or 'unknown'}"
            )

        ocr_used = True
        max_pages = max(1, min(page_count or 1, settings.PDF_OCR_MAX_PAGES))
        logger.warning(
            "pdf text extraction empty, fallback to OCR: file={}, pages={}, ocr_pages={}, lang={}",
            filename,
            page_count,
            max_pages,
            settings.PDF_OCR_LANG,
        )
        for i in range(max_pages):
            ocr_pages_tried += 1
            try:
                images = convert_from_path(
                    file_path,
                    dpi=settings.PDF_OCR_DPI,
                    first_page=i + 1,
                    last_page=i + 1,
                    fmt="png",
                )
            except Exception as e:
                # poppler 缺失或坏 PDF 都会命中这里；一页失败不中断整篇
                logger.exception("pdf2image convert_from_path failed at page {}: {}", i + 1, e)
                continue
            if not images:
                continue
            try:
                text = (pytesseract.image_to_string(images[0], lang=settings.PDF_OCR_LANG) or "").strip()
            except Exception as e:
                logger.exception("pytesseract image_to_string failed at page {}: {}", i + 1, e)
                continue
            if len(text) < _MIN_TEXT_CHARS_PER_PAGE:
                continue
            ocr_pages_got_text += 1
            sections.append(
                ParsedSection(
                    title=f"第 {i + 1} 页（OCR）",
                    content=text,
                    order_idx=i,
                    meta={"page": i + 1, "ocr": True},
                )
            )

    return ParsedDocument(
        filename=filename,
        material_type=MaterialType.PDF,
        sections=sections,
        meta={
            "page_count": page_count or len(sections),
            "text_pages": text_pages,
            "ocr_fallback_used": ocr_used,
            "ocr_deps_available": _ocr_deps_available(),
            "ocr_pages_tried": ocr_pages_tried,
            "ocr_pages_got_text": ocr_pages_got_text,
            "ocr_sections": sum(1 for s in sections if (s.meta or {}).get("ocr")),
        },
    )
