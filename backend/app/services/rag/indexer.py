"""
索引构建：把 ParsedDocument → 切块 → 批量 embedding → 入库 Chunk 表。

**三层去重**：
  1) chunker 阶段（同文档内）：归一化后字面相同 → 直接不产出
  2) indexer 字面层（跨文档同课程）：与该课程其他课件已有切片做归一化比对，命中则跳过
  3) indexer 语义层（跨文档同课程）：用 pgvector 查每个新切片的最近邻；距离 < 阈值
     （≈ 余弦相似度 > 0.97）判定为「换了个说法的同一段内容」，也跳过

多层目的：
- 字面层几乎零成本，先干掉"一字不差重复"
- 语义层稍贵（每个新切片一次索引查询），但能过滤掉"改写过、排版不同但语义一致"的重复

**顺序**：字面去重 → embedding → 语义去重 → 写库。
语义去重放 embedding 之后，因为它需要向量；但之前先字面筛一遍能显著减少 embedding 调用量。
"""
from __future__ import annotations

import re
from collections.abc import Callable

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Chunk, CourseMaterial
from app.services.ai.provider import get_ai_provider
from app.services.parser.base import ParsedDocument
from app.services.rag.chunker import chunk_document

_WHITESPACE_RE = re.compile(r"\s+")
# 用切片前 240 个归一化字符作为去重 key：完全一样或近乎一样的页面会命中同一 key
_DEDUP_KEY_LEN = 240

# 语义去重阈值：pgvector cosine_distance < 0.03 → 余弦相似度 > 0.97
# 这个阈值比较保守，只干掉「几乎一模一样意思」的切片，不会误杀真正互补的段落。
_SEMANTIC_DEDUP_DISTANCE = 0.03


def _normalize(text: str) -> str:
    return _WHITESPACE_RE.sub("", (text or "").strip().lower())[:_DEDUP_KEY_LEN]


def _load_existing_keys(db: Session, *, course_id: int, exclude_material_id: int) -> set[str]:
    """加载该课程下、排除当前课件的全部已入库切片，用归一化 key 做去重集合。"""
    rows = (
        db.query(Chunk.content)
        .filter(Chunk.course_id == course_id)
        .filter(Chunk.material_id != exclude_material_id)
        .all()
    )
    keys: set[str] = set()
    for (content,) in rows:
        k = _normalize(content or "")
        if k:
            keys.add(k)
    return keys


def _find_semantic_duplicate(
    db: Session,
    *,
    course_id: int,
    exclude_material_id: int,
    embedding: list[float],
) -> tuple[int, float] | None:
    """返回 (最近邻 chunk_id, 距离) 或 None。距离小于阈值视作语义重复。

    使用 pgvector `<=>` 余弦距离 + HNSW 索引，单次查询 O(log N)。
    """
    stmt = (
        select(Chunk.id, Chunk.embedding.cosine_distance(embedding).label("distance"))
        .where(Chunk.course_id == course_id)
        .where(Chunk.material_id != exclude_material_id)
        .where(Chunk.embedding.is_not(None))
        .order_by("distance")
        .limit(1)
    )
    row = db.execute(stmt).first()
    if not row:
        return None
    chunk_id, distance = row[0], float(row[1])
    if distance < _SEMANTIC_DEDUP_DISTANCE:
        return chunk_id, distance
    return None


def index_document(
    db: Session,
    *,
    course_id: int,
    material: CourseMaterial,
    doc: ParsedDocument,
    batch_size: int = 16,
    progress_hook: Callable[[int, str], None] | None = None,
) -> int:
    """解析好的文档 → Chunk 记录 + 向量。返回生成的 chunk 数量。

    progress_hook: 可选 (0–100 的进度, 阶段说明)，用于写入课件 meta 供前端轮询展示。
    """
    pieces = chunk_document(doc)
    if not pieces:
        if progress_hook:
            progress_hook(90, "未分出有效文本块")
        return 0

    # 先清空该 material 以前的 chunks，支持重新解析
    db.query(Chunk).filter(Chunk.material_id == material.id).delete()
    db.flush()
    if progress_hook:
        progress_hook(32, "跨文档去重")

    existing_keys = _load_existing_keys(
        db, course_id=course_id, exclude_material_id=material.id
    )

    deduped_pieces = []
    skipped = 0
    for p in pieces:
        key = _normalize(p.content)
        if not key:
            continue
        if key in existing_keys:
            skipped += 1
            continue
        existing_keys.add(key)
        deduped_pieces.append(p)

    if skipped:
        logger.info(
            "index_document: course={} material={} skipped {} duplicate chunks (cross-material dedup)",
            course_id, material.id, skipped,
        )

    if not deduped_pieces:
        if progress_hook:
            progress_hook(92, f"全部切片与课程内已有内容重复（跳过 {skipped} 段）")
        # 仍然把跳过情况记到 material meta，前端可见
        existing_meta = dict(material.meta or {})
        existing_meta["indexed_chunks"] = 0
        existing_meta["dedup_skipped"] = skipped
        material.meta = existing_meta
        db.commit()
        return 0

    if progress_hook:
        progress_hook(38, f"准备向量化（去重后 {len(deduped_pieces)} 段，跳过 {skipped}）")

    ai = get_ai_provider()

    all_chunks: list[Chunk] = []
    semantic_skipped = 0
    n_batches = max(1, (len(deduped_pieces) + batch_size - 1) // batch_size)
    for bi, i in enumerate(range(0, len(deduped_pieces), batch_size)):
        batch = deduped_pieces[i : i + batch_size]
        texts = [b.content for b in batch]
        vectors = ai.embed(texts)
        for piece, vec in zip(batch, vectors):
            # 语义去重：查同课程其他课件的最近邻
            dup = _find_semantic_duplicate(
                db,
                course_id=course_id,
                exclude_material_id=material.id,
                embedding=list(vec),
            )
            if dup is not None:
                dup_id, distance = dup
                semantic_skipped += 1
                logger.debug(
                    "index_document: semantic-dup skip (course={} material={} vs chunk={} distance={:.4f})",
                    course_id, material.id, dup_id, distance,
                )
                continue
            all_chunks.append(Chunk(
                course_id=course_id,
                material_id=material.id,
                chapter=(piece.chapter or "")[:250],
                order_idx=piece.order_idx,
                content=piece.content,
                token_count=len(piece.content),
                embedding=vec,
                meta={**piece.meta, "filename": material.filename},
            ))
        if progress_hook:
            pct = 40 + int(52 * (bi + 1) / n_batches)
            progress_hook(min(92, pct), f"向量化 {bi + 1}/{n_batches}")

    if semantic_skipped:
        logger.info(
            "index_document: course={} material={} semantic-dedup skipped {} chunks",
            course_id, material.id, semantic_skipped,
        )

    if progress_hook:
        progress_hook(96, "正在写入索引")
    db.add_all(all_chunks)

    existing_meta = dict(material.meta or {})
    existing_meta["indexed_chunks"] = len(all_chunks)
    existing_meta["dedup_skipped"] = skipped
    existing_meta["semantic_dedup_skipped"] = semantic_skipped
    material.meta = existing_meta

    db.commit()
    if progress_hook:
        progress_hook(99, "索引写入完成")
    return len(all_chunks)
