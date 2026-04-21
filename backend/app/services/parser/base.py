"""
解析层的通用数据结构：所有格式（Word/PDF/PPT/Excel）统一解析成 ParsedDocument。
下游（分块 → embedding）就不用关心文件类型差异。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable

from app.models.course import MaterialType


@dataclass
class ParsedSection:
    """一个语义段：一章、一页 PPT、一个 Excel sheet、一段 Word 小节。"""
    title: str  # 如 "第一章 产品介绍" / "Slide 3" / "Sheet: 客户名单"
    content: str  # 纯文本，图片用占位符
    order_idx: int = 0
    meta: dict = field(default_factory=dict)  # 页码、图片路径、表格结构等


@dataclass
class ParsedDocument:
    filename: str
    material_type: MaterialType
    sections: list[ParsedSection] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        return "\n\n".join(f"# {s.title}\n\n{s.content}" for s in self.sections if s.content.strip())


# 扩展名到类型的映射
_EXT_MAP: dict[str, MaterialType] = {
    ".doc": MaterialType.WORD,
    ".docx": MaterialType.WORD,
    ".pdf": MaterialType.PDF,
    ".ppt": MaterialType.PPT,
    ".pptx": MaterialType.PPT,
    ".xls": MaterialType.EXCEL,
    ".xlsx": MaterialType.EXCEL,
    ".csv": MaterialType.EXCEL,
    ".mp4": MaterialType.VIDEO,
    ".mov": MaterialType.VIDEO,
    ".mkv": MaterialType.VIDEO,
    ".mp3": MaterialType.AUDIO,
    ".wav": MaterialType.AUDIO,
    ".m4a": MaterialType.AUDIO,
    ".md": MaterialType.MARKDOWN,
    ".markdown": MaterialType.MARKDOWN,
    ".txt": MaterialType.MARKDOWN,
}


def detect_material_type(filename: str) -> MaterialType:
    ext = os.path.splitext(filename)[1].lower()
    return _EXT_MAP.get(ext, MaterialType.OTHER)
