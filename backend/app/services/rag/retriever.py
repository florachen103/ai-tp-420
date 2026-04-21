"""
RAG 检索：给一个查询文本 → 在某课程（或全库）中找到最相关的若干 chunk。

做了 5 件事让结果更「智能」：

1. **查询改写（可选）**：上游可先把口语问题扩成 2~4 个语义变体（术语、同义词、问法），
   这里对每个变体分别做向量召回，对同一 chunk 取「最高命中分」，避免单一问法漏召。
2. **混合召回**：向量召回负责语义相近，`ILIKE` 关键词召回兜住「只有字面匹配能命中」的
   情况（型号/术语/数字），两路结果按分数融合。
3. **MMR 多样化**：避免 Top-K 全是几乎相同的切片。新候选需同时「相关度高」且「与已入选
   内容不过度重复」。
4. **相关度阈值过滤**：把远低于基线的弱匹配直接丢掉，减少噪声干扰下游 Prompt。
5. **按课件 / 章节过滤**：支持调用方只在指定 material_ids 或 chapter 里检索，
   适合「只问这一章」「只看这份课件」的学习场景。

拼 context 时会给每段打上 `[S1]..[Sn]` 编号，Prompt 要求 LLM 在回答中引用，便于学员追溯。
"""
from __future__ import annotations

import re
from collections.abc import Sequence as SeqABC
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.course import Chunk, ChunkVisibility
from app.services.ai.provider import get_ai_provider


@dataclass
class RetrievedChunk:
    id: int
    content: str
    chapter: str | None
    score: float  # 1 - cosine_distance，越高越相关
    meta: dict


# 向量召回的候选池大小：比最终 top_k 多捞几个，留给 MMR 选择余地
_VECTOR_POOL_MULTIPLIER = 5
# 关键词召回上限（ILIKE 粗召，精度不如向量，量不用太大）
_KEYWORD_POOL_SIZE = 20
# MMR 多样化系数：1.0=只看相关度，0.0=只看多样性；0.7 是常用平衡点
_MMR_LAMBDA = 0.7
# 相关度下限：低于此值的切片基本是「凑数的」，拼进上下文只会稀释答案
_MIN_SCORE = 0.18

_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_-]{1,}|\d+(?:\.\d+)?")
_STOPWORDS = {"的", "了", "和", "是", "在", "有", "吗", "呢", "怎么", "如何", "什么", "请", "一下", "帮", "我"}


def _extract_keywords(queries: SeqABC[str], *, limit: int = 8) -> list[str]:
    """从 1~N 个查询里抽关键词用于 ILIKE。"""
    tokens: list[str] = []
    seen: set[str] = set()
    for q in queries:
        if not q:
            continue
        for m in _TOKEN_RE.finditer(q):
            t = m.group(0).strip()
            if not t or t in _STOPWORDS:
                continue
            low = t.lower()
            if low in seen:
                continue
            seen.add(low)
            tokens.append(t)
            if len(tokens) >= limit:
                return tokens
    return tokens


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


def _mmr_select(
    candidates: list[tuple[Chunk, float, list[float] | None]],
    *,
    top_k: int,
    lambda_: float = _MMR_LAMBDA,
) -> list[tuple[Chunk, float]]:
    """Maximal Marginal Relevance：在相关度与多样性之间平衡地挑 top_k。"""
    if not candidates:
        return []
    remaining = list(candidates)
    remaining.sort(key=lambda x: x[1], reverse=True)
    selected: list[tuple[Chunk, float, list[float] | None]] = [remaining.pop(0)]

    while remaining and len(selected) < top_k:
        best_idx = 0
        best_score = -1e9
        for i, (_, rel, emb) in enumerate(remaining):
            if emb is None or not any(s_emb is not None for _, _, s_emb in selected):
                diversity_penalty = 0.0
            else:
                diversity_penalty = max(
                    _cosine(emb, s_emb) if s_emb is not None else 0.0
                    for _, _, s_emb in selected
                )
            mmr = lambda_ * rel - (1 - lambda_) * diversity_penalty
            if mmr > best_score:
                best_score = mmr
                best_idx = i
        selected.append(remaining.pop(best_idx))

    return [(c, s) for c, s, _ in selected]


def retrieve_chunks(
    db: Session,
    query: str,
    *,
    course_id: int | None = None,
    top_k: int = settings.RAG_TOP_K,
    expansions: SeqABC[str] | None = None,
    material_ids: SeqABC[int] | None = None,
    chapter: str | None = None,
    knowledge_space_id: int | None = None,
) -> list[RetrievedChunk]:
    """
    检索相关 chunk。

    query: 原始问题
    expansions: 可选的语义扩展查询（来自 rewrite_query）；会和 query 一起送入向量召回
    material_ids: 限定只在这些课件内检索
    chapter: 限定只在该章节内检索（精确匹配 Chunk.chapter）
    """
    query = (query or "").strip()
    if not query:
        return []

    all_queries: list[str] = [query]
    if expansions:
        for e in expansions:
            e = (e or "").strip()
            if e and e != query and e not in all_queries:
                all_queries.append(e)

    ai = get_ai_provider()
    try:
        query_vecs = ai.embed(all_queries)
    except Exception:
        query_vecs = [ai.embed([query])[0]]
        all_queries = [query]

    pool_size = max(top_k * _VECTOR_POOL_MULTIPLIER, top_k + 5)
    scored: dict[int, tuple[Chunk, float]] = {}

    for qv in query_vecs:
        stmt = (
            select(Chunk, Chunk.embedding.cosine_distance(qv).label("distance"))
            .where(Chunk.embedding.is_not(None))
            .where(Chunk.visibility == ChunkVisibility.PUBLISHED)
            .order_by("distance")
            .limit(pool_size)
        )
        if course_id is not None:
            stmt = stmt.where(Chunk.course_id == course_id)
        if knowledge_space_id is not None:
            stmt = stmt.where(Chunk.knowledge_space_id == knowledge_space_id)
        if material_ids:
            stmt = stmt.where(Chunk.material_id.in_(list(material_ids)))
        if chapter:
            stmt = stmt.where(Chunk.chapter == chapter)

        for row in db.execute(stmt).all():
            chunk: Chunk = row[0]
            distance: float = float(row[1])
            score = max(0.0, 1.0 - distance)
            prev = scored.get(chunk.id)
            # 多查询：对同一 chunk 取最高分
            if prev is None or score > prev[1]:
                scored[chunk.id] = (chunk, score)

    keywords = _extract_keywords(all_queries)
    if keywords:
        kw_stmt = select(Chunk).where(
            Chunk.embedding.is_not(None),
            Chunk.visibility == ChunkVisibility.PUBLISHED,
        )
        if course_id is not None:
            kw_stmt = kw_stmt.where(Chunk.course_id == course_id)
        if knowledge_space_id is not None:
            kw_stmt = kw_stmt.where(Chunk.knowledge_space_id == knowledge_space_id)
        if material_ids:
            kw_stmt = kw_stmt.where(Chunk.material_id.in_(list(material_ids)))
        if chapter:
            kw_stmt = kw_stmt.where(Chunk.chapter == chapter)
        kw_stmt = kw_stmt.where(
            or_(*[Chunk.content.ilike(f"%{kw}%") for kw in keywords])
        ).limit(_KEYWORD_POOL_SIZE)
        for chunk in db.execute(kw_stmt).scalars().all():
            content_low = (chunk.content or "").lower()
            hit_n = sum(1 for kw in keywords if kw.lower() in content_low)
            if hit_n <= 0:
                continue
            kw_score = min(0.25, 0.08 * hit_n)
            if chunk.id in scored:
                c, s = scored[chunk.id]
                scored[chunk.id] = (c, min(1.0, s + kw_score * 0.6))
            else:
                scored[chunk.id] = (chunk, 0.3 + kw_score)

    if not scored:
        return []

    candidates: list[tuple[Chunk, float, list[float] | None]] = []
    for _, (chunk, s) in scored.items():
        if s < _MIN_SCORE:
            continue
        emb_attr = chunk.embedding
        emb_list: list[float] | None
        if emb_attr is None:
            emb_list = None
        else:
            try:
                emb_list = list(emb_attr)
            except TypeError:
                emb_list = None
        candidates.append((chunk, s, emb_list))

    if not candidates:
        candidates = [
            (chunk, s, list(chunk.embedding) if chunk.embedding is not None else None)
            for chunk, s in scored.values()
        ]

    picked = _mmr_select(candidates, top_k=top_k)

    results: list[RetrievedChunk] = []
    for chunk, s in picked:
        results.append(RetrievedChunk(
            id=chunk.id,
            content=chunk.content,
            chapter=chunk.chapter,
            score=round(s, 4),
            meta=chunk.meta or {},
        ))
    return results


def build_context(chunks: list[RetrievedChunk], max_chars: int = 4000) -> str:
    """把检索到的 chunk 拼成 prompt 用 context，带 [S1]..[Sn] 引用编号便于溯源。"""
    parts: list[str] = []
    total = 0
    for i, c in enumerate(chunks, 1):
        header = f"[S{i}] 《{c.chapter or '未分章'}》 相关度 {c.score}"
        body = f"{header}\n{c.content}"
        if total + len(body) > max_chars:
            break
        parts.append(body)
        total += len(body)
    return "\n\n".join(parts) if parts else "（无相关资料）"
