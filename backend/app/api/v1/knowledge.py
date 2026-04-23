"""知识资产中台 API：空间、草稿、审核、发布、冲突与问答。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc

from app.core.deps import (
    CurrentUser,
    DbSession,
    EditorialUser,
    PublisherUser,
    ReviewerUser,
)
from app.models.course import Chunk, Course
from app.models.knowledge import (
    KnowledgeConflict,
    KnowledgeConflictStatus,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
    KnowledgeRevision,
    KnowledgeRevisionStatus,
    KnowledgeSourceLink,
    KnowledgeSpace,
    KnowledgeSpaceStatus,
)
from app.models.record import LearningAction, LearningRecord
from app.models.user import UserRole
from app.schemas.course import AskResponse
from app.schemas.knowledge import (
    KnowledgeAskRequest,
    KnowledgeConflictOut,
    KnowledgeConflictResolveIn,
    KnowledgeDocumentCreate,
    KnowledgeDocumentDetail,
    KnowledgeDocumentOut,
    KnowledgeDocumentUpdate,
    KnowledgePublishAction,
    KnowledgeReviewAction,
    KnowledgeRevisionOut,
    KnowledgeRevisionUpdate,
    KnowledgeSourceLinkOut,
    KnowledgeSpaceCreate,
    KnowledgeSpaceOut,
    KnowledgeSpaceUpdate,
    KnowledgeTreeNode,
)
from app.services.ai.prompts import RAG_ANSWER_TEMPLATE, ask_llm_config
from app.services.ai.provider import get_ai_provider
from app.services.knowledge_service import (
    approve_revision,
    bootstrap_course_materials_to_drafts,
    publish_revision,
    reject_revision,
    resolve_conflict,
    rollback_document_to_revision,
    submit_revision_for_review,
)
from app.services.rag.answer_cache import (
    get_cached_knowledge_answer,
    set_cached_knowledge_answer,
)
from app.services.rag.citation_verifier import verify_and_clean_citations
from app.services.rag.query_rewriter import rewrite_query
from app.services.rag.reranker import rerank_chunks
from app.services.rag.retriever import build_context, retrieve_chunks

router = APIRouter()


def _ensure_document_visible(document: KnowledgeDocument, user_role: UserRole) -> None:
    if user_role == UserRole.LEARNER and document.status != KnowledgeDocumentStatus.PUBLISHED:
        raise HTTPException(403, "该知识页尚未发布")


def _revision_out(revision: KnowledgeRevision | None) -> KnowledgeRevisionOut | None:
    return KnowledgeRevisionOut.model_validate(revision) if revision else None


def _normalize_path_slug(value: str) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    cleaned = raw.replace("/", "-").replace("\\", "-")
    return "-".join(cleaned.split()).strip("-")


def _document_detail(db: DbSession, document: KnowledgeDocument) -> KnowledgeDocumentDetail:
    detail = KnowledgeDocumentDetail.model_validate(document)
    revisions = (
        db.query(KnowledgeRevision)
        .filter(KnowledgeRevision.document_id == document.id)
        .order_by(desc(KnowledgeRevision.version_no))
        .all()
    )
    conflicts = (
        db.query(KnowledgeConflict)
        .filter(KnowledgeConflict.document_id == document.id)
        .order_by(desc(KnowledgeConflict.created_at))
        .all()
    )
    sources = (
        db.query(KnowledgeSourceLink)
        .filter(KnowledgeSourceLink.document_id == document.id)
        .order_by(desc(KnowledgeSourceLink.created_at))
        .limit(200)
        .all()
    )
    detail.current_revision = _revision_out(
        db.get(KnowledgeRevision, document.current_revision_id) if document.current_revision_id else None
    )
    detail.published_revision = _revision_out(
        db.get(KnowledgeRevision, document.published_revision_id) if document.published_revision_id else None
    )
    detail.revisions = [KnowledgeRevisionOut.model_validate(r) for r in revisions]
    detail.conflicts = [KnowledgeConflictOut.model_validate(c) for c in conflicts]
    detail.sources = [KnowledgeSourceLinkOut.model_validate(s) for s in sources]
    return detail


@router.get("/spaces", response_model=list[KnowledgeSpaceOut])
def list_spaces(
    db: DbSession,
    user: CurrentUser,
    status: KnowledgeSpaceStatus | None = None,
):
    q = db.query(KnowledgeSpace)
    if status:
        q = q.filter(KnowledgeSpace.status == status)
    if user.role == UserRole.LEARNER:
        q = q.filter(KnowledgeSpace.status == KnowledgeSpaceStatus.ACTIVE)
        q = q.filter(
            KnowledgeSpace.documents.any(
                KnowledgeDocument.status == KnowledgeDocumentStatus.PUBLISHED
            )
        )
    return q.order_by(KnowledgeSpace.name).all()


@router.post("/spaces", response_model=KnowledgeSpaceOut)
def create_space(payload: KnowledgeSpaceCreate, db: DbSession, user: EditorialUser):
    if db.query(KnowledgeSpace).filter(KnowledgeSpace.slug == payload.slug).first():
        raise HTTPException(400, "slug 已存在")
    space = KnowledgeSpace(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        category=payload.category,
        tags=payload.tags,
        created_by=user.id,
    )
    db.add(space)
    db.commit()
    db.refresh(space)
    return space


@router.patch("/spaces/{space_id}", response_model=KnowledgeSpaceOut)
def update_space(space_id: int, payload: KnowledgeSpaceUpdate, db: DbSession, user: EditorialUser):
    space = db.get(KnowledgeSpace, space_id)
    if not space:
        raise HTTPException(404, "知识空间不存在")
    if payload.slug and payload.slug != space.slug:
        if db.query(KnowledgeSpace.id).filter(KnowledgeSpace.slug == payload.slug).first():
            raise HTTPException(400, "slug 已存在")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(space, k, v)
    db.commit()
    db.refresh(space)
    return space


@router.get("/documents", response_model=list[KnowledgeDocumentOut])
def list_documents(
    db: DbSession,
    user: CurrentUser,
    space_id: int | None = None,
    status: KnowledgeDocumentStatus | None = None,
):
    q = db.query(KnowledgeDocument)
    if space_id is not None:
        q = q.filter(KnowledgeDocument.space_id == space_id)
    if status:
        q = q.filter(KnowledgeDocument.status == status)
    if user.role == UserRole.LEARNER:
        q = q.filter(KnowledgeDocument.status == KnowledgeDocumentStatus.PUBLISHED)
    return q.order_by(desc(KnowledgeDocument.updated_at)).limit(500).all()


@router.post("/documents", response_model=KnowledgeDocumentDetail)
def create_document(payload: KnowledgeDocumentCreate, db: DbSession, user: EditorialUser):
    space = db.get(KnowledgeSpace, payload.space_id)
    if not space:
        raise HTTPException(404, "知识空间不存在")
    slug_base = "-".join(payload.title.lower().split())[:60] or f"doc-{uuid.uuid4().hex[:8]}"
    slug = f"{slug_base}-{uuid.uuid4().hex[:6]}"
    raw_path = payload.path_slug or payload.title
    path_slug = _normalize_path_slug(raw_path)
    if not path_slug:
        raise HTTPException(400, "页面路径不能为空")
    if db.query(KnowledgeDocument.id).filter(
        KnowledgeDocument.space_id == payload.space_id,
        KnowledgeDocument.path_slug == path_slug,
    ).first():
        raise HTTPException(400, "页面路径已存在")

    if payload.parent_id:
        parent = db.get(KnowledgeDocument, payload.parent_id)
        if not parent or parent.space_id != payload.space_id:
            raise HTTPException(400, "父页面不存在或不在当前空间")
    else:
        parent = None

    if payload.is_redirect and payload.redirect_document_id is None:
        raise HTTPException(400, "重定向页面必须指定目标页面")
    if payload.redirect_document_id:
        target = db.get(KnowledgeDocument, payload.redirect_document_id)
        if not target or target.space_id != payload.space_id:
            raise HTTPException(400, "重定向目标不存在或不在当前空间")
    if payload.redirect_document_id and payload.redirect_document_id == payload.parent_id:
        raise HTTPException(400, "重定向目标不能与父页面相同")

    document = KnowledgeDocument(
        space_id=payload.space_id,
        title=payload.title,
        slug=slug,
        path_slug=path_slug,
        parent_id=parent.id if parent else None,
        is_redirect=payload.is_redirect,
        redirect_document_id=payload.redirect_document_id,
        summary=payload.summary,
        category=payload.category,
        tags=payload.tags,
        status=KnowledgeDocumentStatus.DRAFT,
        created_by=user.id,
        assigned_editor_id=user.id,
        assigned_reviewer_id=user.id,
        assigned_publisher_id=user.id,
    )
    db.add(document)
    db.flush()
    revision = KnowledgeRevision(
        document_id=document.id,
        version_no=1,
        status=KnowledgeRevisionStatus.DRAFT,
        title=payload.title,
        summary=payload.summary,
        category=payload.category,
        tags=payload.tags,
        markdown_content=payload.markdown_content or f"# {payload.title}\n\n",
        outline=[],
        ai_meta={"generated_from": "manual_create"},
        change_note="手工创建的首版草稿",
        created_by=user.id,
    )
    db.add(revision)
    db.flush()
    document.current_revision_id = revision.id
    db.commit()
    db.refresh(document)
    return _document_detail(db, document)


@router.get("/documents/{document_id}", response_model=KnowledgeDocumentDetail)
def get_document(document_id: int, db: DbSession, user: CurrentUser):
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        raise HTTPException(404, "知识页不存在")
    _ensure_document_visible(document, user.role)
    return _document_detail(db, document)


@router.patch("/documents/{document_id}", response_model=KnowledgeDocumentDetail)
def update_document(document_id: int, payload: KnowledgeDocumentUpdate, db: DbSession, user: EditorialUser):
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        raise HTTPException(404, "知识页不存在")

    updates = payload.model_dump(exclude_unset=True)
    if "path_slug" in updates and updates["path_slug"] is not None:
        path_slug = _normalize_path_slug(updates["path_slug"])
        if not path_slug:
            raise HTTPException(400, "页面路径不能为空")
        exists = db.query(KnowledgeDocument.id).filter(
            KnowledgeDocument.space_id == document.space_id,
            KnowledgeDocument.path_slug == path_slug,
            KnowledgeDocument.id != document.id,
        ).first()
        if exists:
            raise HTTPException(400, "页面路径已存在")
        document.path_slug = path_slug

    if "parent_id" in updates:
        parent_id = updates["parent_id"]
        if parent_id == document.id:
            raise HTTPException(400, "父页面不能是自己")
        if parent_id is None:
            document.parent_id = None
        else:
            parent = db.get(KnowledgeDocument, parent_id)
            if not parent or parent.space_id != document.space_id:
                raise HTTPException(400, "父页面不存在或不在当前空间")
            document.parent_id = parent_id

    if "redirect_document_id" in updates:
        redirect_document_id = updates["redirect_document_id"]
        if redirect_document_id is None:
            document.redirect_document_id = None
        else:
            if redirect_document_id == document.id:
                raise HTTPException(400, "重定向目标不能是自己")
            target = db.get(KnowledgeDocument, redirect_document_id)
            if not target or target.space_id != document.space_id:
                raise HTTPException(400, "重定向目标不存在或不在当前空间")
            document.redirect_document_id = redirect_document_id

    if "is_redirect" in updates:
        document.is_redirect = bool(updates["is_redirect"])
        if document.is_redirect and not document.redirect_document_id:
            raise HTTPException(400, "重定向页面必须指定目标页面")

    for field in ("title", "summary", "category", "tags"):
        if field in updates:
            setattr(document, field, updates[field])

    db.commit()
    db.refresh(document)
    return _document_detail(db, document)


@router.get("/spaces/{space_id}/tree", response_model=list[KnowledgeTreeNode])
def get_space_tree(space_id: int, db: DbSession, user: CurrentUser):
    space = db.get(KnowledgeSpace, space_id)
    if not space:
        raise HTTPException(404, "知识空间不存在")
    q = db.query(KnowledgeDocument).filter(KnowledgeDocument.space_id == space_id)
    if user.role == UserRole.LEARNER:
        q = q.filter(KnowledgeDocument.status == KnowledgeDocumentStatus.PUBLISHED)
    docs = q.order_by(KnowledgeDocument.path_slug.asc(), KnowledgeDocument.title.asc()).all()
    return [
        KnowledgeTreeNode(
            id=d.id,
            title=d.title,
            path_slug=d.path_slug,
            parent_id=d.parent_id,
            is_redirect=d.is_redirect,
            status=d.status,
        )
        for d in docs
    ]


@router.get("/revisions/{revision_id}", response_model=KnowledgeRevisionOut)
def get_revision(revision_id: int, db: DbSession, user: CurrentUser):
    revision = db.get(KnowledgeRevision, revision_id)
    if not revision:
        raise HTTPException(404, "版本不存在")
    document = db.get(KnowledgeDocument, revision.document_id)
    if not document:
        raise HTTPException(404, "知识页不存在")
    _ensure_document_visible(document, user.role)
    return revision


@router.patch("/revisions/{revision_id}", response_model=KnowledgeRevisionOut)
def update_revision(revision_id: int, payload: KnowledgeRevisionUpdate, db: DbSession, user: EditorialUser):
    revision = db.get(KnowledgeRevision, revision_id)
    if not revision:
        raise HTTPException(404, "版本不存在")
    if revision.status not in {KnowledgeRevisionStatus.DRAFT, KnowledgeRevisionStatus.REJECTED}:
        raise HTTPException(400, "只有草稿/已驳回版本允许继续编辑")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(revision, k, v)
    document = db.get(KnowledgeDocument, revision.document_id)
    if document:
        document.current_revision_id = revision.id
        document.status = KnowledgeDocumentStatus.DRAFT
    db.commit()
    db.refresh(revision)
    return revision


@router.post("/revisions/{revision_id}/submit", response_model=KnowledgeRevisionOut)
def submit_revision(revision_id: int, db: DbSession, user: EditorialUser):
    revision = db.get(KnowledgeRevision, revision_id)
    if not revision:
        raise HTTPException(404, "版本不存在")
    submit_revision_for_review(db, revision=revision, actor_id=user.id)
    db.commit()
    db.refresh(revision)
    return revision


@router.get("/review/queue", response_model=list[KnowledgeRevisionOut])
def review_queue(db: DbSession, user: ReviewerUser):
    rows = (
        db.query(KnowledgeRevision)
        .filter(KnowledgeRevision.status == KnowledgeRevisionStatus.IN_REVIEW)
        .order_by(desc(KnowledgeRevision.submitted_at))
        .all()
    )
    return rows


@router.post("/review/{revision_id}/approve", response_model=KnowledgeRevisionOut)
def review_approve(
    revision_id: int,
    payload: KnowledgeReviewAction,
    db: DbSession,
    user: ReviewerUser,
):
    revision = db.get(KnowledgeRevision, revision_id)
    if not revision:
        raise HTTPException(404, "版本不存在")
    if revision.status != KnowledgeRevisionStatus.IN_REVIEW:
        raise HTTPException(400, "该版本不在待审核状态")
    approve_revision(db, revision=revision, actor_id=user.id, comment=payload.comment)
    db.commit()
    db.refresh(revision)
    return revision


@router.post("/review/{revision_id}/reject", response_model=KnowledgeRevisionOut)
def review_reject(
    revision_id: int,
    payload: KnowledgeReviewAction,
    db: DbSession,
    user: ReviewerUser,
):
    revision = db.get(KnowledgeRevision, revision_id)
    if not revision:
        raise HTTPException(404, "版本不存在")
    if revision.status != KnowledgeRevisionStatus.IN_REVIEW:
        raise HTTPException(400, "该版本不在待审核状态")
    reject_revision(db, revision=revision, actor_id=user.id, comment=payload.comment)
    db.commit()
    db.refresh(revision)
    return revision


@router.post("/revisions/{revision_id}/publish")
def publish_revision_api(
    revision_id: int,
    payload: KnowledgePublishAction,
    db: DbSession,
    user: PublisherUser,
):
    revision = db.get(KnowledgeRevision, revision_id)
    if not revision:
        raise HTTPException(404, "版本不存在")
    if revision.status not in {KnowledgeRevisionStatus.APPROVED, KnowledgeRevisionStatus.PUBLISHED}:
        raise HTTPException(400, "只有审核通过版本允许发布")
    document, chunk_count = publish_revision(
        db,
        revision=revision,
        actor_id=user.id,
        change_note=payload.change_note,
    )
    db.commit()
    db.refresh(document)
    return {
        "message": "已发布",
        "document_id": document.id,
        "revision_id": revision.id,
        "chunk_count": chunk_count,
    }


@router.post("/documents/{document_id}/rollback")
def rollback_document(
    document_id: int,
    db: DbSession,
    user: PublisherUser,
    revision_id: int = Query(...),
):
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        raise HTTPException(404, "知识页不存在")
    revision = db.get(KnowledgeRevision, revision_id)
    if not revision or revision.document_id != document.id:
        raise HTTPException(404, "目标版本不存在")
    clone = rollback_document_to_revision(db, document=document, revision=revision, actor_id=user.id)
    db.commit()
    db.refresh(clone)
    return {"message": "已创建回滚草稿", "revision_id": clone.id}


@router.get("/conflicts", response_model=list[KnowledgeConflictOut])
def list_conflicts(
    db: DbSession,
    user: EditorialUser,
    status: KnowledgeConflictStatus | None = None,
    document_id: int | None = None,
):
    q = db.query(KnowledgeConflict)
    if status:
        q = q.filter(KnowledgeConflict.status == status)
    if document_id is not None:
        q = q.filter(KnowledgeConflict.document_id == document_id)
    return q.order_by(desc(KnowledgeConflict.created_at)).all()


@router.get("/conflicts/{conflict_id}", response_model=KnowledgeConflictOut)
def get_conflict(conflict_id: int, db: DbSession, user: EditorialUser):
    conflict = db.get(KnowledgeConflict, conflict_id)
    if not conflict:
        raise HTTPException(404, "冲突不存在")
    return conflict


@router.post("/conflicts/{conflict_id}/resolve", response_model=KnowledgeConflictOut)
def resolve_conflict_api(
    conflict_id: int,
    payload: KnowledgeConflictResolveIn,
    db: DbSession,
    user: EditorialUser,
):
    conflict = db.get(KnowledgeConflict, conflict_id)
    if not conflict:
        raise HTTPException(404, "冲突不存在")
    resolve_conflict(
        db,
        conflict=conflict,
        actor_id=user.id,
        resolution_kind=payload.resolution_kind,
        comment=payload.comment,
    )
    db.commit()
    db.refresh(conflict)
    return conflict


@router.post("/spaces/{space_id}/ask", response_model=AskResponse)
def ask_knowledge(
    space_id: int,
    payload: KnowledgeAskRequest,
    db: DbSession,
    user: CurrentUser,
):
    space = db.get(KnowledgeSpace, space_id)
    if not space or space.status != KnowledgeSpaceStatus.ACTIVE:
        raise HTTPException(404, "知识空间不存在")

    top_k = payload.top_k
    cached = get_cached_knowledge_answer(
        space_id=space_id,
        question=payload.question,
        response_style=payload.response_style,
        top_k=top_k,
        rewrite=payload.rewrite,
        rerank=payload.rerank,
    )
    if cached is not None:
        return AskResponse(**cached)

    expansions = rewrite_query(payload.question) if payload.rewrite else []
    retrieve_k = top_k * 2 if payload.rerank else top_k
    chunks = retrieve_chunks(
        db,
        payload.question,
        top_k=retrieve_k,
        expansions=expansions or None,
        knowledge_space_id=space_id,
    )
    if payload.rerank and len(chunks) > top_k:
        chunks = rerank_chunks(payload.question, chunks, top_k=top_k)
    context = build_context(chunks)
    queries_used = [payload.question, *expansions]

    ai = get_ai_provider()
    cfg = ask_llm_config(payload.response_style)
    system, max_tokens = ask_llm_config(payload.response_style, has_persona=False)
    user_prompt = RAG_ANSWER_TEMPLATE.format(
        question=payload.question,
        context=context,
        persona="（知识空间问答未指定学员画像）",
    )
    answer = ai.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}],
        temperature=0.2,
        max_tokens=max_tokens,
    )
    answer, audit = verify_and_clean_citations(answer, source_count=len(chunks))
    answer_id = uuid.uuid4().hex[:20]

    db.add(LearningRecord(
        user_id=user.id,
        course_id=None,
        action=LearningAction.ASK_QUESTION,
        payload={
            "question": payload.question[:500],
            "knowledge_space_id": space_id,
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
                "index": i,
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
    set_cached_knowledge_answer(
        space_id=space_id,
        question=payload.question,
        response_style=payload.response_style,
        top_k=top_k,
        rewrite=payload.rewrite,
        rerank=payload.rerank,
        value=response.model_dump(),
    )
    return response


@router.post("/bootstrap/courses/{course_id}")
def bootstrap_course_to_knowledge(course_id: int, db: DbSession, user: EditorialUser):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "课程不存在")
    result = bootstrap_course_materials_to_drafts(db, course=course, actor_id=user.id)
    db.commit()
    return {"message": "已完成历史资料回填", **result}
