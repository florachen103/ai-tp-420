"""
知识资产服务：
  - 课程 / 资料 与知识空间自动绑定
  - 解析后的文档生成知识页草稿
  - 草稿提交审核、审核通过/驳回
  - 发布后把知识页写入 Chunk 表，复用现有 pgvector 检索链路
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from loguru import logger
from slugify import slugify
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.course import (
    Chunk,
    ChunkSourceType,
    ChunkVisibility,
    Course,
    CourseMaterial,
    MaterialType,
)
from app.models.knowledge import (
    KnowledgeConflict,
    KnowledgeConflictStatus,
    KnowledgeConflictType,
    KnowledgeDocument,
    KnowledgeDocumentStatus,
    KnowledgeRevision,
    KnowledgeRevisionStatus,
    KnowledgeSourceLink,
    KnowledgeSpace,
    KnowledgeSpaceStatus,
)
from app.services.ai.provider import get_ai_provider
from app.services.parser.base import ParsedDocument, ParsedSection
from app.services.rag.answer_cache import bump_course_version, bump_knowledge_space_version
from app.services.rag.chunker import chunk_document

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _summarize(text: str, *, limit: int = 180) -> str:
    clean = " ".join((text or "").split())
    return clean[:limit]


def _outline_from_sections(sections: list[ParsedSection]) -> list[dict]:
    out: list[dict] = []
    for s in sections:
        out.append({
            "title": s.title,
            "order_idx": s.order_idx,
            "length": len((s.content or "").strip()),
        })
    return out


def _markdown_from_doc(doc: ParsedDocument) -> str:
    parts = [f"# {doc.filename}"]
    for section in doc.sections:
        body = (section.content or "").strip()
        if not body:
            continue
        parts.append(f"## {section.title}")
        parts.append(body)
    return "\n\n".join(parts).strip()


def _parsed_doc_from_markdown(title: str, markdown_content: str) -> ParsedDocument:
    text = (markdown_content or "").strip()
    matches = list(_HEADING_RE.finditer(text))
    sections: list[ParsedSection] = []
    if not matches:
        sections.append(ParsedSection(title=title or "正文", content=text, order_idx=0))
    else:
        for idx, m in enumerate(matches):
            heading = m.group(2).strip()
            start = m.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            if body:
                sections.append(ParsedSection(title=heading, content=body, order_idx=idx))
    return ParsedDocument(
        filename=title or "知识页",
        material_type=MaterialType.MARKDOWN,
        sections=sections,
        meta={},
    )


def _base_slug(text: str, *, fallback: str) -> str:
    return slugify(text or "", lowercase=True, separator="-") or fallback


def _section_anchor(title: str | None, *, fallback: str) -> str:
    return _base_slug((title or "").strip(), fallback=fallback)


def _unique_space_slug(db: Session, name: str, *, seed: str) -> str:
    base = _base_slug(name, fallback=seed)
    slug = base
    i = 2
    while db.query(KnowledgeSpace.id).filter(KnowledgeSpace.slug == slug).first():
        slug = f"{base}-{i}"
        i += 1
    return slug


def _unique_doc_slug(db: Session, space_id: int, title: str, *, seed: str) -> str:
    base = _base_slug(title, fallback=seed)
    slug = base
    i = 2
    while (
        db.query(KnowledgeDocument.id)
        .filter(KnowledgeDocument.space_id == space_id, KnowledgeDocument.slug == slug)
        .first()
    ):
        slug = f"{base}-{i}"
        i += 1
    return slug


def _unique_doc_path_slug(db: Session, space_id: int, title: str, *, seed: str) -> str:
    base = _base_slug(title, fallback=seed)
    slug = base
    i = 2
    while (
        db.query(KnowledgeDocument.id)
        .filter(KnowledgeDocument.space_id == space_id, KnowledgeDocument.path_slug == slug)
        .first()
    ):
        slug = f"{base}-{i}"
        i += 1
    return slug


def ensure_course_space(db: Session, *, course: Course, creator_id: int) -> KnowledgeSpace:
    if course.knowledge_space_id:
        space = db.get(KnowledgeSpace, course.knowledge_space_id)
        if space:
            return space
    name = course.title or "默认知识空间"
    space = KnowledgeSpace(
        name=name,
        slug=_unique_space_slug(db, name, seed=f"course-{course.id}"),
        description=course.description,
        category=course.category,
        tags=list(course.tags or []),
        status=KnowledgeSpaceStatus.ACTIVE,
        created_by=creator_id,
    )
    db.add(space)
    db.flush()
    course.knowledge_space_id = space.id
    return space


def _next_revision_no(db: Session, document_id: int) -> int:
    max_v = (
        db.query(func.max(KnowledgeRevision.version_no))
        .filter(KnowledgeRevision.document_id == document_id)
        .scalar()
    )
    return int(max_v or 0) + 1


def _sync_source_links_for_revision(
    db: Session,
    *,
    document: KnowledgeDocument,
    revision: KnowledgeRevision,
    material: CourseMaterial,
) -> None:
    db.query(KnowledgeSourceLink).filter(KnowledgeSourceLink.revision_id == revision.id).delete()
    db.add(KnowledgeSourceLink(
        document_id=document.id,
        revision_id=revision.id,
        source_kind="material",
        course_id=document.source_course_id,
        material_id=material.id,
        note=material.filename,
    ))
    for chunk_id, chapter in (
        db.query(Chunk.id, Chunk.chapter)
        .filter(Chunk.material_id == material.id)
        .order_by(Chunk.order_idx)
        .limit(200)
        .all()
    ):
        db.add(KnowledgeSourceLink(
            document_id=document.id,
            revision_id=revision.id,
            source_kind="chunk",
            course_id=document.source_course_id,
            material_id=material.id,
            chunk_id=chunk_id,
            note=chapter,
        ))


def _build_conflicts(
    db: Session,
    *,
    document: KnowledgeDocument,
    revision: KnowledgeRevision,
) -> None:
    db.query(KnowledgeConflict).filter(
        KnowledgeConflict.document_id == document.id,
        KnowledgeConflict.draft_revision_id == revision.id,
        KnowledgeConflict.status == KnowledgeConflictStatus.OPEN,
    ).delete()

    peers = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.space_id == document.space_id,
            KnowledgeDocument.id != document.id,
            KnowledgeDocument.status == KnowledgeDocumentStatus.PUBLISHED,
            KnowledgeDocument.published_revision_id.is_not(None),
        )
        .limit(20)
        .all()
    )
    draft_title = (revision.title or "").strip().lower()
    draft_text = (revision.markdown_content or "").strip()
    for peer in peers:
        published = db.get(KnowledgeRevision, peer.published_revision_id) if peer.published_revision_id else None
        if not published:
            continue
        same_title = draft_title and draft_title == (peer.title or "").strip().lower()
        overlap = 0.0
        if draft_text and published.markdown_content:
            draft_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_-]{3,}", draft_text.lower()))
            peer_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_-]{3,}", published.markdown_content.lower()))
            if draft_tokens and peer_tokens:
                overlap = len(draft_tokens & peer_tokens) / max(1, min(len(draft_tokens), len(peer_tokens)))
        if not same_title and overlap < 0.35:
            continue
        db.add(KnowledgeConflict(
            document_id=document.id,
            draft_revision_id=revision.id,
            published_revision_id=published.id,
            conflict_type=KnowledgeConflictType.TITLE_DUPLICATE if same_title else KnowledgeConflictType.CONTENT_CONFLICT,
            status=KnowledgeConflictStatus.OPEN,
            title=f"与《{peer.title}》存在潜在冲突",
            detail="标题相同" if same_title else f"内容相似度较高（约 {int(overlap * 100)}%）",
            existing_excerpt=(published.markdown_content or "")[:400],
            incoming_excerpt=draft_text[:400],
        ))


def create_draft_from_material(
    db: Session,
    *,
    course: Course,
    material: CourseMaterial,
    doc: ParsedDocument,
    actor_id: int,
) -> tuple[KnowledgeDocument, KnowledgeRevision]:
    space = ensure_course_space(db, course=course, creator_id=actor_id)
    document = (
        db.query(KnowledgeDocument)
        .filter(KnowledgeDocument.source_material_id == material.id)
        .first()
    )
    title = doc.sections[0].title if doc.sections else material.filename
    summary = _summarize(doc.full_text or material.filename)
    markdown = _markdown_from_doc(doc)
    if document is None:
        document = KnowledgeDocument(
            space_id=space.id,
            title=title,
            slug=_unique_doc_slug(db, space.id, title, seed=f"material-{material.id}"),
            path_slug=_unique_doc_path_slug(db, space.id, title, seed=f"material-{material.id}"),
            summary=summary,
            category=course.category,
            tags=list(course.tags or []),
            status=KnowledgeDocumentStatus.DRAFT,
            created_by=actor_id,
            assigned_editor_id=actor_id,
            assigned_reviewer_id=actor_id,
            assigned_publisher_id=actor_id,
            source_course_id=course.id,
            source_material_id=material.id,
        )
        db.add(document)
        db.flush()
    else:
        document.title = title
        document.summary = summary
        document.category = course.category
        document.tags = list(course.tags or [])
        if document.status == KnowledgeDocumentStatus.PUBLISHED:
            document.status = KnowledgeDocumentStatus.DRAFT

    revision = KnowledgeRevision(
        document_id=document.id,
        version_no=_next_revision_no(db, document.id),
        status=KnowledgeRevisionStatus.DRAFT,
        title=title,
        summary=summary,
        category=course.category,
        tags=list(course.tags or []),
        markdown_content=markdown,
        outline=_outline_from_sections(doc.sections),
        ai_meta={
            "source_filename": material.filename,
            "sections": len(doc.sections),
            "parse_doc_meta": doc.meta or {},
            "generated_from": "material_parse",
        },
        created_by=actor_id,
        change_note="系统根据最新解析结果自动生成草稿",
    )
    db.add(revision)
    db.flush()
    document.current_revision_id = revision.id
    _sync_source_links_for_revision(db, document=document, revision=revision, material=material)
    _build_conflicts(db, document=document, revision=revision)
    return document, revision


def bootstrap_course_materials_to_drafts(
    db: Session,
    *,
    course: Course,
    actor_id: int,
) -> dict:
    created = 0
    skipped = 0
    for material in (
        db.query(CourseMaterial)
        .filter(CourseMaterial.course_id == course.id)
        .order_by(CourseMaterial.id)
        .all()
    ):
        chunk_rows = (
            db.query(Chunk)
            .filter(Chunk.material_id == material.id)
            .order_by(Chunk.order_idx)
            .all()
        )
        if not chunk_rows:
            skipped += 1
            continue
        sections_by_title: dict[str, list[str]] = {}
        order_map: dict[str, int] = {}
        for row in chunk_rows:
            title = (row.chapter or "正文").strip() or "正文"
            sections_by_title.setdefault(title, []).append(row.content)
            order_map.setdefault(title, row.order_idx)
        sections = [
            ParsedSection(
                title=title,
                content="\n\n".join(parts),
                order_idx=order_map.get(title, idx),
            )
            for idx, (title, parts) in enumerate(sections_by_title.items())
        ]
        parsed = ParsedDocument(
            filename=material.filename,
            material_type=material.material_type,
            sections=sections,
            meta={"generated_from": "bootstrap_chunks"},
        )
        create_draft_from_material(
            db,
            course=course,
            material=material,
            doc=parsed,
            actor_id=actor_id,
        )
        created += 1
    return {"created": created, "skipped": skipped}


def submit_revision_for_review(db: Session, *, revision: KnowledgeRevision, actor_id: int) -> KnowledgeRevision:
    revision.status = KnowledgeRevisionStatus.IN_REVIEW
    revision.submitted_by = actor_id
    revision.submitted_at = _now()
    document = db.get(KnowledgeDocument, revision.document_id)
    if document:
        document.status = KnowledgeDocumentStatus.IN_REVIEW
        document.current_revision_id = revision.id
    return revision


def approve_revision(db: Session, *, revision: KnowledgeRevision, actor_id: int, comment: str | None = None) -> KnowledgeRevision:
    revision.status = KnowledgeRevisionStatus.APPROVED
    revision.reviewed_by = actor_id
    revision.reviewed_at = _now()
    revision.review_comment = comment or "审核通过，待发布"
    return revision


def reject_revision(db: Session, *, revision: KnowledgeRevision, actor_id: int, comment: str | None = None) -> KnowledgeRevision:
    revision.status = KnowledgeRevisionStatus.REJECTED
    revision.reviewed_by = actor_id
    revision.reviewed_at = _now()
    revision.review_comment = comment or "需修改后重新提交"
    document = db.get(KnowledgeDocument, revision.document_id)
    if document and document.current_revision_id == revision.id:
        document.status = KnowledgeDocumentStatus.DRAFT
    return revision


def _write_published_chunks(db: Session, *, document: KnowledgeDocument, revision: KnowledgeRevision) -> int:
    db.query(Chunk).filter(
        Chunk.knowledge_document_id == document.id,
        Chunk.source_type == ChunkSourceType.KNOWLEDGE_REVISION,
    ).delete()

    parsed = _parsed_doc_from_markdown(revision.title, revision.markdown_content)
    pieces = chunk_document(parsed)
    if not pieces:
        return 0

    ai = get_ai_provider()
    vectors = ai.embed([p.content for p in pieces])
    rows: list[Chunk] = []
    for piece, vec in zip(pieces, vectors):
        chapter = (piece.chapter or "").strip()
        anchor = _section_anchor(chapter, fallback=f"sec-{piece.order_idx}")
        rows.append(Chunk(
            course_id=document.source_course_id,
            material_id=document.source_material_id,
            knowledge_space_id=document.space_id,
            knowledge_document_id=document.id,
            knowledge_revision_id=revision.id,
            source_type=ChunkSourceType.KNOWLEDGE_REVISION,
            visibility=ChunkVisibility.PUBLISHED,
            chapter=chapter[:255] if chapter else None,
            order_idx=piece.order_idx,
            content=piece.content,
            token_count=len(piece.content),
            embedding=vec,
            meta={
                **piece.meta,
                "knowledge_title": revision.title,
                "wiki_path": document.path_slug,
                "wiki_section": chapter or "正文",
                "wiki_section_anchor": anchor,
                "knowledge_revision": revision.version_no,
                "source_kind": "knowledge_revision",
            },
        ))
    db.add_all(rows)
    return len(rows)


def publish_revision(
    db: Session,
    *,
    revision: KnowledgeRevision,
    actor_id: int,
    change_note: str | None = None,
) -> tuple[KnowledgeDocument, int]:
    document = db.get(KnowledgeDocument, revision.document_id)
    if not document:
        raise ValueError("知识页不存在")

    prev_published_id = document.published_revision_id
    if prev_published_id and prev_published_id != revision.id:
        prev = db.get(KnowledgeRevision, prev_published_id)
        if prev and prev.status == KnowledgeRevisionStatus.PUBLISHED:
            prev.status = KnowledgeRevisionStatus.ARCHIVED

    revision.status = KnowledgeRevisionStatus.PUBLISHED
    revision.published_by = actor_id
    revision.published_at = _now()
    revision.reviewed_by = revision.reviewed_by or actor_id
    revision.reviewed_at = revision.reviewed_at or revision.published_at
    if change_note:
        revision.change_note = change_note

    document.current_revision_id = revision.id
    document.published_revision_id = revision.id
    document.status = KnowledgeDocumentStatus.PUBLISHED

    chunk_count = _write_published_chunks(db, document=document, revision=revision)
    bump_knowledge_space_version(document.space_id)
    for (course_id,) in db.query(Course.id).filter(Course.knowledge_space_id == document.space_id).all():
        bump_course_version(course_id)
    logger.info(
        "publish_revision: document={} revision={} chunks={}",
        document.id, revision.id, chunk_count,
    )
    return document, chunk_count


def rollback_document_to_revision(
    db: Session,
    *,
    document: KnowledgeDocument,
    revision: KnowledgeRevision,
    actor_id: int,
) -> KnowledgeRevision:
    clone = KnowledgeRevision(
        document_id=document.id,
        version_no=_next_revision_no(db, document.id),
        status=KnowledgeRevisionStatus.DRAFT,
        title=revision.title,
        summary=revision.summary,
        category=revision.category,
        tags=list(revision.tags or []),
        markdown_content=revision.markdown_content,
        outline=list(revision.outline or []),
        ai_meta={**(revision.ai_meta or {}), "rolled_back_from_revision_id": revision.id},
        change_note=f"从 v{revision.version_no} 回滚生成的新草稿",
        created_by=actor_id,
    )
    db.add(clone)
    db.flush()
    document.current_revision_id = clone.id
    document.status = KnowledgeDocumentStatus.DRAFT
    return clone


def resolve_conflict(
    db: Session,
    *,
    conflict: KnowledgeConflict,
    actor_id: int,
    resolution_kind: str,
    comment: str | None = None,
) -> KnowledgeConflict:
    conflict.status = KnowledgeConflictStatus.RESOLVED if resolution_kind != "ignored" else KnowledgeConflictStatus.IGNORED
    conflict.resolution_kind = resolution_kind
    conflict.resolved_by = actor_id
    conflict.resolved_at = _now()
    if comment:
        detail = (conflict.detail or "").strip()
        conflict.detail = f"{detail}\n\n处理说明：{comment}" if detail else f"处理说明：{comment}"
    return conflict

