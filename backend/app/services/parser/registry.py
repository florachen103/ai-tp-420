"""
解析器分发：按扩展名路由到对应解析器。
新增格式只需在这里加一行。
"""
from __future__ import annotations

from app.models.course import MaterialType
from app.services.parser.av_parser import parse_av
from app.services.parser.base import ParsedDocument, detect_material_type
from app.services.parser.docx_parser import parse_docx
from app.services.parser.markdown_parser import parse_markdown
from app.services.parser.pdf_parser import parse_pdf
from app.services.parser.pptx_parser import parse_pptx
from app.services.parser.xlsx_parser import parse_xlsx


def parse_file(file_path: str, filename: str) -> ParsedDocument:
    mt = detect_material_type(filename)
    if mt == MaterialType.WORD:
        return parse_docx(file_path, filename)
    if mt == MaterialType.PDF:
        return parse_pdf(file_path, filename)
    if mt == MaterialType.PPT:
        return parse_pptx(file_path, filename)
    if mt == MaterialType.EXCEL:
        return parse_xlsx(file_path, filename)
    if mt == MaterialType.MARKDOWN:
        return parse_markdown(file_path, filename)
    if mt in (MaterialType.VIDEO, MaterialType.AUDIO):
        return parse_av(file_path, filename)
    raise ValueError(f"不支持的文件类型: {filename}")
