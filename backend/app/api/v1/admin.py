"""管理端专用接口：目前挂 RAG 效果监控 + 答案反馈 + 缓存管控。"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from sqlalchemy import desc, func
from sqlalchemy.exc import SQLAlchemyError

from app.core.deps import AdminUser, DbSession
from app.models.course import Chunk, ChunkSourceType, Course, CourseMaterial
from app.models.feedback import AnswerFeedback
from app.models.knowledge import (
    KnowledgeDocument,
    KnowledgeDocumentStatus,
    KnowledgeSpace,
)
from app.models.record import LearningAction, LearningRecord
from app.services.rag.answer_cache import bump_course_version
from app.services.rag.prompt_auditor import generate_prompt_audit

router = APIRouter()


@router.get("/rag/metrics")
def rag_metrics(db: DbSession, admin: AdminUser, days: int = 30):
    """
    RAG 效果看板：基于 LearningRecord.payload + AnswerFeedback 聚合。
    """
    days = max(1, min(days, 180))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    records = (
        db.query(LearningRecord)
        .filter(LearningRecord.action == LearningAction.ASK_QUESTION)
        .filter(LearningRecord.created_at >= since)
        .all()
    )

    ask_count = len(records)

    # 逐日聚合
    daily: dict[str, dict[str, int]] = defaultdict(
        lambda: {"asks": 0, "cache_hits": 0, "with_citation": 0, "citation_removed": 0}
    )

    cache_hit = 0
    with_citation = 0
    total_citations_used = 0
    removed_any = 0
    per_course_counter: dict[int, int] = {}

    for r in records:
        payload = r.payload or {}
        day_key = r.created_at.date().isoformat() if r.created_at else "unknown"
        bucket = daily[day_key]
        bucket["asks"] += 1

        if payload.get("cache_hit"):
            cache_hit += 1
            bucket["cache_hits"] += 1
        used = payload.get("citations_used") or []
        removed = payload.get("citations_removed") or []
        if isinstance(used, list) and len(used) > 0:
            with_citation += 1
            total_citations_used += len(used)
            bucket["with_citation"] += 1
        if isinstance(removed, list) and len(removed) > 0:
            removed_any += 1
            bucket["citation_removed"] += 1
        if r.course_id:
            per_course_counter[r.course_id] = per_course_counter.get(r.course_id, 0) + 1

    # 填充缺失日（哪怕当日 0 条，也要出现在折线图上）
    daily_series: list[dict] = []
    today = datetime.now(timezone.utc).date()
    for offset in range(days):
        d = today - timedelta(days=days - 1 - offset)
        key = d.isoformat()
        b = daily.get(key, {"asks": 0, "cache_hits": 0, "with_citation": 0, "citation_removed": 0})
        daily_series.append({"date": key, **b})

    # Top 提问课程
    top_course_ids = sorted(per_course_counter.items(), key=lambda x: -x[1])[:10]
    title_map: dict[int, str] = {}
    if top_course_ids:
        rows = (
            db.query(Course.id, Course.title)
            .filter(Course.id.in_([cid for cid, _ in top_course_ids]))
            .all()
        )
        title_map = {cid: title for cid, title in rows}
    top_courses = [
        {"course_id": cid, "title": title_map.get(cid) or f"课程 #{cid}", "ask_count": cnt}
        for cid, cnt in top_course_ids
    ]

    # 最近提问样本（抽检用）
    recent_records = (
        db.query(LearningRecord)
        .filter(LearningRecord.action == LearningAction.ASK_QUESTION)
        .filter(LearningRecord.created_at >= since)
        .order_by(desc(LearningRecord.created_at))
        .limit(20)
        .all()
    )
    recent_samples = []
    for r in recent_records:
        p = r.payload or {}
        recent_samples.append({
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "course_id": r.course_id,
            "question": p.get("question", ""),
            "expansions": (p.get("expansions") or [])[:4],
            "citations_used": p.get("citations_used") or [],
            "citations_removed": p.get("citations_removed") or [],
            "cache_hit": bool(p.get("cache_hit")),
        })

    # 答案满意度：如果运维还没跑 alembic upgrade head，answer_feedbacks 表是不存在的，
    # 此时 SQLAlchemy 会抛 ProgrammingError/UndefinedTable，我们降级为 "零反馈"，
    # 不能因为一个新表没建好就把整个监控面板拖崩。
    n_good = 0
    n_bad = 0
    fb_total = 0
    recent_bad_out: list[dict] = []
    feedback_table_missing = False
    try:
        fb_rows = (
            db.query(AnswerFeedback)
            .filter(AnswerFeedback.created_at >= since)
            .all()
        )
        n_good = sum(1 for f in fb_rows if f.rating == 1)
        n_bad = sum(1 for f in fb_rows if f.rating == -1)
        fb_total = n_good + n_bad
        recent_bad = (
            db.query(AnswerFeedback)
            .filter(AnswerFeedback.created_at >= since, AnswerFeedback.rating == -1)
            .order_by(desc(AnswerFeedback.created_at))
            .limit(10)
            .all()
        )
        for f in recent_bad:
            snap = f.snapshot or {}
            recent_bad_out.append({
                "id": f.id,
                "created_at": f.created_at.isoformat() if f.created_at else None,
                "course_id": f.course_id,
                "question": snap.get("question") or "",
                "comment": f.comment or "",
                "citations_used": snap.get("citations_used") or [],
                "cache_hit": bool(snap.get("cache_hit")),
            })
    except SQLAlchemyError as e:
        # 关键：一次失败后整个 session 会被 PostgreSQL 标记为 aborted，后续任何 query 都会失败，
        # 所以必须 rollback 把状态清干净，后面的 _index_health 才能继续查。
        db.rollback()
        feedback_table_missing = True
        logger.warning(
            "answer_feedbacks 查询失败（多半是 migration 未执行）："
            "请在 backend 目录运行 `alembic upgrade head`。原始错误：{}",
            e,
        )

    safe_ask = ask_count or 1  # 防 /0
    return {
        "window_days": days,
        "ask_count": ask_count,
        "cache_hit_rate": round(cache_hit / safe_ask, 4) if ask_count else 0.0,
        "answers_with_citation_rate": round(with_citation / safe_ask, 4) if ask_count else 0.0,
        "avg_citations_per_answer": round(total_citations_used / safe_ask, 2) if ask_count else 0.0,
        "citation_removed_rate": round(removed_any / safe_ask, 4) if ask_count else 0.0,
        "top_courses": top_courses,
        "recent_questions": recent_samples,
        "daily_series": daily_series,
        "feedback": {
            "total": fb_total,
            "good": n_good,
            "bad": n_bad,
            "satisfaction_rate": round(n_good / fb_total, 4) if fb_total else 0.0,
            "coverage_rate": round(fb_total / safe_ask, 4) if ask_count else 0.0,
            "recent_bad": recent_bad_out,
            "table_missing": feedback_table_missing,
        },
        "index_health": _index_health(db),
    }


def _index_health(db: DbSession) -> dict:
    """索引体检：当前有多少课程 / 课件 / 切片，用于判断知识库是否就绪。"""
    n_courses = db.query(func.count(Course.id)).scalar() or 0
    n_materials = db.query(func.count(CourseMaterial.id)).scalar() or 0
    n_chunks = db.query(func.count(Chunk.id)).scalar() or 0
    n_spaces = db.query(func.count(KnowledgeSpace.id)).scalar() or 0
    n_docs = db.query(func.count(KnowledgeDocument.id)).scalar() or 0
    n_published_docs = (
        db.query(func.count(KnowledgeDocument.id))
        .filter(KnowledgeDocument.status == KnowledgeDocumentStatus.PUBLISHED)
        .scalar()
        or 0
    )
    n_knowledge_chunks = (
        db.query(func.count(Chunk.id))
        .filter(Chunk.source_type == ChunkSourceType.KNOWLEDGE_REVISION)
        .scalar()
        or 0
    )
    n_embedded = (
        db.query(func.count(Chunk.id))
        .filter(Chunk.embedding.is_not(None))
        .scalar()
        or 0
    )
    return {
        "courses": int(n_courses),
        "materials": int(n_materials),
        "chunks": int(n_chunks),
        "chunks_with_embedding": int(n_embedded),
        "knowledge_spaces": int(n_spaces),
        "knowledge_documents": int(n_docs),
        "published_documents": int(n_published_docs),
        "knowledge_chunks": int(n_knowledge_chunks),
    }


@router.post("/rag/cache/clear")
def clear_course_cache(
    db: DbSession,
    admin: AdminUser,
    course_id: int = Query(..., description="要清空答案缓存的课程 id"),
):
    """管理员强制让该课程的所有答案缓存失效（课件没动但 Prompt 调优时很有用）。"""
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    bump_course_version(course_id)
    return {"message": "已清空缓存", "course_id": course_id}


@router.post("/rag/prompt_audit")
def prompt_audit(
    db: DbSession,
    admin: AdminUser,
    days: int = Query(30, ge=1, le=180, description="分析近多少天的差评"),
    course_id: int | None = Query(None, description="只分析某个课程；不传=全课程"),
):
    """
    差评驱动的 Prompt 自检报告：取近 N 天的差评 → 让 LLM 归纳共性 + 给出调整建议。
    这是 POST 是因为它会触发 LLM 调用，有实际成本，按钮式触发更合适（避免被爬虫 / 意外访问刷）。
    """
    result = generate_prompt_audit(db, days=days, course_id=course_id)
    return {
        "days": days,
        "course_id": course_id,
        "sample_size": result.sample_size,
        "patterns": result.patterns,
        "recommendations": result.recommendations,
        "examples": result.examples,
        "cases": result.cases,
        "error": result.error,
    }
