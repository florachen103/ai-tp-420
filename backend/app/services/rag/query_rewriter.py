"""
查询改写（Query Rewrite）：把学员口语化提问扩展成多个语义变体，再一起交给向量召回。

典型场景：
  原始问：「头疼怎么办？」
  扩展成：["偏头痛的处理方法", "头部疼痛 止痛药选择", "头疼 常见原因 应对"]

设计原则：
1. 短查询（≤ 5 字）意图不明，直接跳过改写，只用原文（避免把 "退货" 扩成一堆无关领域）。
2. 失败容错：模型超时 / 输出不合格都不抛异常，直接返回空列表 → 上游退化为单查询检索。
3. 用低温度 + JSON 模式要求，避免返回散文；若对齐失败，用正则兜底抽 2~4 条变体。
4. 扩展数量受控（≤ 4），防止把召回池撑爆。
"""
from __future__ import annotations

import json
import re

from loguru import logger

from app.services.ai.provider import get_ai_provider, safe_json_loads

_MAX_EXPANSIONS = 4
_MIN_QUERY_CHARS = 5  # 太短的问题不改写（意图不稳）

_REWRITE_SYSTEM = """你是一个企业内训知识库检索改写器。任务：把学员提问改写成 2~4 个
更利于向量检索的短查询，风格更接近课件书面表达。

规则：
1. 保留原问题的核心实体与意图，不要扩展到无关领域。
2. 每条改写 ≤ 25 个字，使用陈述性短语/关键词串，不是完整问句。
3. 针对同义词、专业术语、常见口语→书面语做变换；可加上重要上位词/下位词。
4. 不要编造课件里可能不存在的具体数字、型号或品牌名。
5. 只输出 JSON，格式：{"queries": ["...", "..."]}。禁止任何解释文字。"""


_REWRITE_USER_TEMPLATE = """原始问题：{question}

请输出 2~4 个改写后的检索短语（JSON）。"""


_FALLBACK_SPLIT_RE = re.compile(r"[\n，,、；;]+")


def rewrite_query(question: str, *, max_expansions: int = _MAX_EXPANSIONS) -> list[str]:
    """返回不含原问题的扩展列表。失败时返回 []，上游按单查询继续检索。"""
    q = (question or "").strip()
    if len(q) < _MIN_QUERY_CHARS:
        return []

    ai = get_ai_provider()
    try:
        raw = ai.chat(
            messages=[
                {"role": "system", "content": _REWRITE_SYSTEM},
                {"role": "user", "content": _REWRITE_USER_TEMPLATE.format(question=q)},
            ],
            temperature=0.1,
            max_tokens=220,
            response_format="json_object",
        )
    except Exception as e:
        logger.debug("query rewrite skipped (provider error): {}", e)
        return []

    expansions: list[str] = []
    try:
        data = safe_json_loads(raw)
        if isinstance(data, dict):
            items = data.get("queries") or data.get("expansions") or []
        elif isinstance(data, list):
            items = data
        else:
            items = []
        for item in items:
            s = str(item).strip().strip('"').strip("'")
            if s and s != q:
                expansions.append(s)
    except (ValueError, TypeError, json.JSONDecodeError):
        for frag in _FALLBACK_SPLIT_RE.split(raw or ""):
            s = frag.strip().strip('"').strip("'").strip("-").strip("·").strip()
            if s and len(s) <= 60 and s != q:
                expansions.append(s)

    uniq: list[str] = []
    seen: set[str] = set()
    for s in expansions:
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(s)
        if len(uniq) >= max_expansions:
            break
    return uniq
