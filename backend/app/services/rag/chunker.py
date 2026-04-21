"""
文本分块。策略：
- 按章节 → 按句子合并，目标 chunk_size 字符
- 相邻 chunk 保留 overlap 衔接，不在句中硬切
- 过滤掉低信息量切片（过短、全是页码/空白/重复 header）
- 同一文档内做归一化去重，避免 PPT/PDF 把同一页反复抽出相同字
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.config import settings
from app.services.parser.base import ParsedDocument


@dataclass
class TextChunk:
    content: str
    order_idx: int
    chapter: str
    meta: dict


_SENT_SPLIT = re.compile(r"(?<=[。！？；.!?;\n])")
_WHITESPACE_RE = re.compile(r"\s+")
# 切片最少有效字符数：低于该值基本不足以独立回答问题
MIN_CHARS_PER_CHUNK = 20


def _split_sentences(text: str) -> list[str]:
    parts = _SENT_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


def _normalize_for_dedup(text: str) -> str:
    return _WHITESPACE_RE.sub("", (text or "").strip().lower())


def chunk_text(
    text: str,
    *,
    chunk_size: int = settings.CHUNK_SIZE,
    overlap: int = settings.CHUNK_OVERLAP,
) -> list[str]:
    """按句合并到目标大小，末端保留 overlap 字符到下一个 chunk。"""
    sentences = _split_sentences(text)
    chunks: list[str] = []
    buf = ""
    for sent in sentences:
        if len(buf) + len(sent) <= chunk_size:
            buf += sent
        else:
            if buf:
                chunks.append(buf)
            tail = buf[-overlap:] if overlap and buf else ""
            buf = tail + sent
    if buf:
        chunks.append(buf)
    return chunks


def chunk_document(doc: ParsedDocument) -> list[TextChunk]:
    """按 ParsedSection 分章节，再在章节内细分。同文档去重，过滤低信息量。"""
    out: list[TextChunk] = []
    seen_keys: set[str] = set()
    order = 0
    for section in doc.sections:
        for piece in chunk_text(section.content):
            clean = piece.strip()
            if len(clean) < MIN_CHARS_PER_CHUNK:
                continue
            key = _normalize_for_dedup(clean)[:240]
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            out.append(TextChunk(
                content=clean,
                order_idx=order,
                chapter=section.title,
                meta={**section.meta, "source_section": section.title},
            ))
            order += 1
    return out
