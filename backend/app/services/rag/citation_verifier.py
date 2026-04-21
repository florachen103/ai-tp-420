"""
答句引用校验：LLM 偶尔会「编号溢出」（引用 [S9] 但其实只有 5 条 sources）或乱挂。
后端在把答案返给前端前做一次核对：
  - 抽出答案中出现的所有 [S\\d+] 编号
  - 超出可用范围的编号：从正文里剥掉，记录日志
  - 统计每个 source 实际被引用几次，回写到 sources[i]["citations"] 便于前端侧栏排序
  - 若答案里一个引用都没有（违背 Prompt 要求），触发 info 日志，便于后续观测 Prompt 命中率

保持最轻量：不改写正文语义，只做编号层面的清洗。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from loguru import logger

_CITATION_RE = re.compile(r"\[S(\d+)\]")


@dataclass
class CitationAudit:
    used_indices: list[int]          # 答案里真实出现的合法编号（按首次出现顺序）
    removed_indices: list[int]       # 被剥掉的非法编号
    citations_count: dict[int, int]  # {source_index: 被引用次数}


def verify_and_clean_citations(answer: str, *, source_count: int) -> tuple[str, CitationAudit]:
    """返回 (清洗后的答案, 审计结果)。`source_count` 是当前 sources 长度。"""
    used_order: list[int] = []
    used_set: set[int] = set()
    removed: list[int] = []
    counts: dict[int, int] = {}

    def _replace(m: re.Match[str]) -> str:
        idx = int(m.group(1))
        if 1 <= idx <= source_count:
            counts[idx] = counts.get(idx, 0) + 1
            if idx not in used_set:
                used_set.add(idx)
                used_order.append(idx)
            return m.group(0)
        removed.append(idx)
        return ""

    cleaned = _CITATION_RE.sub(_replace, answer or "")
    # 剥掉引用后可能留下多余空白 / 连续标点，做一次轻量规整
    cleaned = re.sub(r"[ \t]+([，。；,.;])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)

    audit = CitationAudit(
        used_indices=used_order,
        removed_indices=removed,
        citations_count=counts,
    )

    if removed:
        logger.info(
            "RAG citation: removed out-of-range indices {} (available=1..{})",
            removed, source_count,
        )
    if source_count > 0 and not used_order:
        logger.info("RAG citation: answer has no [Sn] citation (source_count={})", source_count)

    return cleaned, audit
