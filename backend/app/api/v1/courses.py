"""课程 + 课件 + 学员问答（RAG）。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from loguru import logger
from sqlalchemy import desc, or_
from sqlalchemy.exc import SQLAlchemyError

from app.core.deps import AdminUser, CurrentUser, DbSession
from app.models.course import Chunk, ChunkSourceType, Course, CourseMaterial, CourseStatus
from app.models.feedback import AnswerFeedback
from app.models.record import LearningAction, LearningRecord
from app.schemas.course import (
    AnswerFeedbackIn,
    AskRequest,
    AskResponse,
    CourseCreate,
    CourseDetail,
    CourseOut,
    CourseUpdate,
    MaterialOut,
)
from app.services.ai.prompts import RAG_ANSWER_TEMPLATE, ask_llm_config
from app.services.ai.provider import get_ai_provider
from app.services.parser.base import detect_material_type
from app.services.rag.answer_cache import (
    bump_course_version,
    get_cached_answer,
    set_cached_answer,
)
from app.services.rag.citation_verifier import verify_and_clean_citations
from app.services.rag.query_rewriter import rewrite_query
from app.services.rag.reranker import rerank_chunks
from app.services.rag.retriever import build_context, retrieve_chunks
from app.services.storage import get_storage
from app.services.material_parse import schedule_parse_material

router = APIRouter()


@router.get("", response_model=list[CourseOut])
def list_courses(
    db: DbSession,
    user: CurrentUser,
    status: CourseStatus | None = None,
    keyword: str | None = None,
):
    q = db.query(Course)
    if status:
        q = q.filter(Course.status == status)
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        q = q.filter(
            or_(
                Course.title.ilike(kw),
                Course.description.ilike(kw),
                Course.category.ilike(kw),
            )
        )
    # 学员只看已就绪
    from app.models.user import UserRole
    if user.role == UserRole.LEARNER:
        q = q.filter(Course.status == CourseStatus.READY)
    return q.order_by(desc(Course.updated_at)).limit(200).all()


@router.post("", response_model=CourseOut)
def create_course(payload: CourseCreate, db: DbSession, admin: AdminUser):
    course = Course(
        title=payload.title,
        description=payload.description,
        category=payload.category,
        tags=payload.tags,
        created_by=admin.id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


@router.get("/{course_id}", response_model=CourseDetail)
def get_course(course_id: int, db: DbSession, user: CurrentUser):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    db.add(LearningRecord(
        user_id=user.id,
        course_id=course.id,
        action=LearningAction.VIEW_COURSE,
        payload={"title": course.title},
    ))
    db.commit()
    materials = db.query(CourseMaterial).filter(CourseMaterial.course_id == course_id).all()
    detail = CourseDetail.model_validate(course)
    detail.materials = [MaterialOut.model_validate(m) for m in materials]
    return detail


@router.patch("/{course_id}", response_model=CourseOut)
def update_course(course_id: int, payload: CourseUpdate, db: DbSession, admin: AdminUser):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(course, k, v)
    db.commit()
    db.refresh(course)
    return course


@router.get("/{course_id}/chapters", response_model=list[str])
def list_course_chapters(course_id: int, db: DbSession, user: CurrentUser):
    """该课程下所有出现过的章节名（去重排序），供前端做范围下拉。"""
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    published_knowledge_exists = False
    if course.knowledge_space_id:
        published_knowledge_exists = (
            db.query(Chunk.id)
            .filter(
                Chunk.knowledge_space_id == course.knowledge_space_id,
                Chunk.source_type == ChunkSourceType.KNOWLEDGE_REVISION,
            )
            .first()
            is not None
        )
    rows = (
        db.query(Chunk.chapter)
        .filter(
            Chunk.knowledge_space_id == course.knowledge_space_id
            if published_knowledge_exists
            else Chunk.course_id == course_id
        )
        .filter(Chunk.chapter.is_not(None))
        .filter(Chunk.chapter != "")
        .distinct()
        .all()
    )
    chapters = sorted({(c or "").strip() for (c,) in rows if c and c.strip()})
    return chapters


@router.post("/{course_id}/materials", response_model=MaterialOut)
async def upload_material(
    course_id: int,
    db: DbSession,
    admin: AdminUser,
    file: UploadFile = File(...),
):
    """
    上传课件文件 → 存对象存储 → 投递异步解析任务。
    """
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")

    data = await file.read()
    if not data:
        raise HTTPException(400, "空文件")

    # 生成存储 key：course/{course_id}/{uuid}_{filename}
    safe_name = file.filename or "unnamed"
    storage_key = f"course/{course_id}/{uuid.uuid4().hex}_{safe_name}"
    get_storage().put(storage_key, data, content_type=file.content_type or "application/octet-stream")

    material = CourseMaterial(
        course_id=course_id,
        filename=safe_name,
        material_type=detect_material_type(safe_name),
        storage_key=storage_key,
        size_bytes=len(data),
        parse_status="pending",
        meta={"parse_progress": 0, "parse_stage": "排队中"},
    )
    db.add(material)
    if course.status == CourseStatus.DRAFT:
        course.status = CourseStatus.PROCESSING
    db.commit()
    db.refresh(material)

    # 课件变更 → 对应课程的答案缓存应立即失效
    bump_course_version(course_id)

    # 后台线程解析（不依赖 Celery worker 是否消费成功，避免界面长期 pending）
    schedule_parse_material(material.id)
    return material


@router.post("/{course_id}/materials/{material_id}/reparse")
def reparse_material(
    course_id: int,
    material_id: int,
    db: DbSession,
    admin: AdminUser,
):
    """管理员手动触发重新解析（pending / failed 时使用）。"""
    material = db.get(CourseMaterial, material_id)
    if not material or material.course_id != course_id:
        raise HTTPException(404, "课件不存在")
    material.parse_status = "pending"
    material.parse_error = None
    meta = dict(material.meta or {})
    meta["parse_progress"] = 0
    meta["parse_stage"] = "排队中"
    material.meta = meta
    db.commit()
    bump_course_version(course_id)
    schedule_parse_material(material_id)
    return {"message": "已开始重新解析", "material_id": material_id}


@router.delete("/{course_id}/materials/{material_id}")
def delete_material(course_id: int, material_id: int, db: DbSession, admin: AdminUser):
    material = db.get(CourseMaterial, material_id)
    if not material or material.course_id != course_id:
        raise HTTPException(404, "课件不存在")
    db.delete(material)
    db.commit()
    bump_course_version(course_id)
    return {"message": "已删除"}


@router.post("/{course_id}/ask", response_model=AskResponse)
def ask(course_id: int, payload: AskRequest, db: DbSession, user: CurrentUser):
    """
    学员在学习页向 AI 提问：RAG 检索课程知识 → 调 LLM 回答。
    """
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")

    top_k = 4 if payload.response_style == "micro" else payload.top_k

    # 校验 material_ids 都属于本课程，防止越权或写错
    material_ids = payload.material_ids or None
    if material_ids:
        valid_ids = {
            mid for (mid,) in db.query(CourseMaterial.id)
            .filter(CourseMaterial.course_id == course_id, CourseMaterial.id.in_(material_ids))
            .all()
        }
        material_ids = [mid for mid in material_ids if mid in valid_ids] or None

    published_knowledge_exists = False
    if course.knowledge_space_id:
        published_knowledge_exists = (
            db.query(Chunk.id)
            .filter(
                Chunk.knowledge_space_id == course.knowledge_space_id,
                Chunk.source_type == ChunkSourceType.KNOWLEDGE_REVISION,
            )
            .first()
            is not None
        )

    # 命中缓存则直接返回（仍会写一条轻量的学习记录，保证用户活跃度统计正确）
    cached = get_cached_answer(
        course_id=course_id,
        question=payload.question,
        persona=payload.persona,
        response_style=payload.response_style,
        top_k=top_k,
        material_ids=material_ids,
        chapter=payload.chapter,
        rewrite=payload.rewrite,
        rerank=payload.rerank,
    )
    if cached is not None:
        db.add(LearningRecord(
            user_id=user.id,
            course_id=course_id,
            action=LearningAction.ASK_QUESTION,
            payload={
                "question": payload.question[:500],
                "chunks": [s.get("chunk_id") for s in cached.get("sources", []) if isinstance(s, dict)],
                "expansions": cached.get("queries_used", [])[1:5],
                "citations_used": [
                    s.get("index") for s in cached.get("sources", [])
                    if isinstance(s, dict) and (s.get("citations") or 0) > 0
                ],
                "citations_removed": [],
                "cache_hit": True,
                "answer_id": cached.get("answer_id"),
            },
        ))
        db.commit()
        return AskResponse(**cached)

    expansions: list[str] = []
    if payload.rewrite:
        try:
            expansions = rewrite_query(payload.question)
        except Exception:
            expansions = []

    queries_used = [payload.question] + [q for q in expansions if q]

    # rerank 开启时先多捞一倍候选，再由 LLM 在更大池子里选最相关的 top_k
    retrieve_k = top_k * 2 if payload.rerank else top_k
    chunks = retrieve_chunks(
        db,
        payload.question,
        course_id=None if published_knowledge_exists else course_id,
        top_k=retrieve_k,
        expansions=expansions or None,
        material_ids=material_ids,
        chapter=(payload.chapter or None),
        knowledge_space_id=course.knowledge_space_id if published_knowledge_exists else None,
    )
    if payload.rerank and len(chunks) > top_k:
        chunks = rerank_chunks(payload.question, chunks, top_k=top_k)
    context = build_context(chunks)

    persona_raw = (payload.persona or "").strip()
    has_persona = bool(persona_raw)
    system_prompt, max_tokens = ask_llm_config(payload.response_style, has_persona=has_persona)
    user_body = RAG_ANSWER_TEMPLATE.format(
        context=context,
        persona=payload.persona or "（未指定）",
        question=payload.question,
    )
    user_body += (
        "\n\n（请严格用 Markdown 输出：用 ## / ### 分节；关键名词与记忆点多用 **粗体**；"
        "若有一段可直接照念的口语话术，请整段放在引用块中（每行以 > 开头）；"
        "文末必须有二级标题 ## 划重点 及有序列表。"
        f"回答中涉及具体结论/数据/要点，请在该句末尾用 [S1] [S2] 标注来自哪一段【参考资料】，"
        f"仅可使用 S1 至 S{max(1, len(chunks))} 之间的编号，"
        "不要引用不存在或超出范围的编号。）"
    )

    ai = get_ai_provider()
    answer = ai.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_body},
        ],
        temperature=0.35 if payload.response_style == "micro" else 0.2,
        max_tokens=max_tokens,
    )

    # 清洗非法 [Sn] 编号 & 统计每条 source 被引用次数
    answer, audit = verify_and_clean_citations(answer, source_count=len(chunks))

    answer_id = uuid.uuid4().hex[:20]

    db.add(LearningRecord(
        user_id=user.id,
        course_id=course_id,
        action=LearningAction.ASK_QUESTION,
        payload={
            "question": payload.question[:500],
            "chunks": [c.id for c in chunks],
            "expansions": expansions[:4],
            "citations_used": audit.used_indices,
            "citations_removed": audit.removed_indices,
            "answer_id": answer_id,
        },
    ))
    db.commit()

    response = AskResponse(
        answer=answer,
        answer_id=answer_id,
        sources=[
            {
                "index": i,  # 与答案中的 [S{index}] 对应，前端可以高亮跳转
                "chunk_id": c.id,
                "chapter": c.chapter,
                "wiki_path": (c.meta or {}).get("wiki_path"),
                "wiki_section": (c.meta or {}).get("wiki_section"),
                "wiki_section_anchor": (c.meta or {}).get("wiki_section_anchor"),
                "score": c.score,
                "snippet": c.content[:200],
                "citations": audit.citations_count.get(i, 0),
            }
            for i, c in enumerate(chunks, 1)
        ],
        queries_used=queries_used,
    )
    set_cached_answer(
        course_id=course_id,
        question=payload.question,
        persona=payload.persona,
        response_style=payload.response_style,
        top_k=top_k,
        material_ids=material_ids,
        chapter=payload.chapter,
        rewrite=payload.rewrite,
        rerank=payload.rerank,
        value=response.model_dump(),
    )
    return response


@router.post("/{course_id}/ask/feedback")
def submit_ask_feedback(
    course_id: int,
    payload: AnswerFeedbackIn,
    db: DbSession,
    user: CurrentUser,
):
    """
    学员对 RAG 答案的满意度反馈（好评 / 差评）。同一学员对同一 answer_id
    重复提交时，覆盖上一次（rating + comment 以最新为准）。

    从 LearningRecord 中回溯出该 answer_id 的提问上下文，存到 snapshot 里，
    便于后续管理员面板复盘 Prompt 质量。
    """
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")

    # 定位原提问记录：按 answer_id 反查最近一次 ASK_QUESTION
    rec_q = (
        db.query(LearningRecord)
        .filter(
            LearningRecord.user_id == user.id,
            LearningRecord.course_id == course_id,
            LearningRecord.action == LearningAction.ASK_QUESTION,
        )
        .order_by(desc(LearningRecord.created_at))
        .limit(50)  # 不需要全表扫，近 50 条够覆盖绝大多数场景
        .all()
    )
    origin = next(
        (r for r in rec_q if (r.payload or {}).get("answer_id") == payload.answer_id),
        None,
    )
    snapshot: dict = {}
    if origin:
        snapshot = {
            "question": (origin.payload or {}).get("question"),
            "expansions": (origin.payload or {}).get("expansions") or [],
            "chunks": (origin.payload or {}).get("chunks") or [],
            "citations_used": (origin.payload or {}).get("citations_used") or [],
            "citations_removed": (origin.payload or {}).get("citations_removed") or [],
            "cache_hit": bool((origin.payload or {}).get("cache_hit")),
        }

    try:
        existing = (
            db.query(AnswerFeedback)
            .filter(
                AnswerFeedback.answer_id == payload.answer_id,
                AnswerFeedback.user_id == user.id,
            )
            .order_by(desc(AnswerFeedback.created_at))
            .first()
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.warning("提交反馈失败，answer_feedbacks 表不存在？请执行 alembic upgrade head：{}", e)
        raise HTTPException(503, "反馈功能尚未就绪，请联系管理员完成数据库迁移") from e
    if existing:
        existing.rating = int(payload.rating)
        existing.comment = (payload.comment or None)
        existing.course_id = course_id
        # 合并 snapshot：只补不改（避免把原始上下文被二次反馈覆盖）
        merged = dict(existing.snapshot or {})
        for k, v in snapshot.items():
            merged.setdefault(k, v)
        existing.snapshot = merged
        db.commit()
        return {"message": "已更新反馈", "feedback_id": existing.id}

    fb = AnswerFeedback(
        answer_id=payload.answer_id,
        user_id=user.id,
        course_id=course_id,
        rating=int(payload.rating),
        comment=(payload.comment or None),
        snapshot=snapshot,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return {"message": "已记录反馈", "feedback_id": fb.id}


@router.get("/{course_id}/ask/feedback/mine")
def list_my_feedback(
    course_id: int,
    db: DbSession,
    user: CurrentUser,
    limit: int = 200,
):
    """
    返回当前学员在该课程下所有已打过分的答案：{answer_id: rating} 映射。
    前端刷新后用它恢复"有用 / 没解决"按钮的选中状态，避免跨会话失忆。

    answer_feedbacks 表若未建（运维没跑 alembic upgrade head），直接降级返回空对象，
    不让学员端对话页一起瘫。
    """
    try:
        rows = (
            db.query(AnswerFeedback.answer_id, AnswerFeedback.rating)
            .filter(
                AnswerFeedback.user_id == user.id,
                AnswerFeedback.course_id == course_id,
            )
            .order_by(desc(AnswerFeedback.created_at))
            .limit(max(1, min(limit, 1000)))
            .all()
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.warning("查询本人反馈失败（多半是 migration 未执行）：{}", e)
        return {}
    out: dict[str, int] = {}
    # 同一个 answer_id 取最新一条（已经按 created_at desc 了，所以先到的保留）
    for aid, rating in rows:
        if aid not in out:
            out[aid] = int(rating)
    return out
