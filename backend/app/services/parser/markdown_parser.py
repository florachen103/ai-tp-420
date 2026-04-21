"""Markdown/纯文本解析：按一级/二级标题切分。"""
from __future__ import annotations

import re

from app.models.course import MaterialType
from app.services.parser.base import ParsedDocument, ParsedSection

_HEADING = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def parse_markdown(file_path: str, filename: str) -> ParsedDocument:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    sections: list[ParsedSection] = []
    matches = list(_HEADING.finditer(text))
    if not matches:
        sections.append(ParsedSection(title="正文", content=text.strip(), order_idx=0))
    else:
        for idx, m in enumerate(matches):
            title = m.group(2).strip()
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if body:
                sections.append(ParsedSection(title=title, content=body, order_idx=idx))
    return ParsedDocument(
        filename=filename,
        material_type=MaterialType.MARKDOWN,
        sections=sections,
    )
