"""
知识资产中台模型：

1. KnowledgeSpace
   一个长期经营的知识空间，如“医药合规库”“制度库”“产品知识库”。

2. KnowledgeDocument
   一个知识页的稳定身份（标题 / slug / 所属空间 / 当前发布版本）。

3. KnowledgeRevision
   知识页的某个具体版本。编辑、审核、发布都围绕 revision 流转。

4. KnowledgeSourceLink
   知识页版本与原始资料 / chunk / 课程的溯源关系，支撑“这页知识从哪来”。

5. KnowledgeConflict
   新草稿与已发布版本之间的冲突记录，供人工处理。
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.core.pg_enum import pg_enum


class KnowledgeSpaceStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class KnowledgeDocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class KnowledgeRevisionStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class KnowledgeConflictType(str, enum.Enum):
    TITLE_DUPLICATE = "title_duplicate"
    CONTENT_CONFLICT = "content_conflict"
    POLICY_CONFLICT = "policy_conflict"
    MANUAL = "manual"


class KnowledgeConflictStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class KnowledgeSpace(Base):
    __tablename__ = "knowledge_spaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[KnowledgeSpaceStatus] = mapped_column(
        pg_enum(KnowledgeSpaceStatus, "knowledgespacestatus"),
        default=KnowledgeSpaceStatus.ACTIVE,
        index=True,
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    documents: Mapped[list["KnowledgeDocument"]] = relationship(
        back_populates="space", cascade="all, delete-orphan"
    )


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    space_id: Mapped[int] = mapped_column(ForeignKey("knowledge_spaces.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(255), index=True)
    path_slug: Mapped[str] = mapped_column(String(255), index=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_documents.id"), nullable=True, index=True
    )
    is_redirect: Mapped[bool] = mapped_column(default=False, index=True)
    redirect_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_documents.id"), nullable=True, index=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    status: Mapped[KnowledgeDocumentStatus] = mapped_column(
        pg_enum(KnowledgeDocumentStatus, "knowledgedocumentstatus"),
        default=KnowledgeDocumentStatus.DRAFT,
        index=True,
    )
    current_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_revisions.id"), nullable=True
    )
    published_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_revisions.id"), nullable=True
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_editor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_publisher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    source_course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True, index=True)
    source_material_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_materials.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    space: Mapped["KnowledgeSpace"] = relationship(back_populates="documents")
    parent: Mapped["KnowledgeDocument | None"] = relationship(
        "KnowledgeDocument",
        remote_side=[id],
        foreign_keys=[parent_id],
        back_populates="children",
    )
    children: Mapped[list["KnowledgeDocument"]] = relationship(
        "KnowledgeDocument",
        foreign_keys=[parent_id],
        back_populates="parent",
    )
    redirect_document: Mapped["KnowledgeDocument | None"] = relationship(
        "KnowledgeDocument",
        remote_side=[id],
        foreign_keys=[redirect_document_id],
    )
    revisions: Mapped[list["KnowledgeRevision"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="KnowledgeRevision.document_id",
    )

    __table_args__ = (
        Index("ix_knowledge_documents_space_title", "space_id", "title"),
        Index("ix_knowledge_documents_space_path_slug", "space_id", "path_slug", unique=True),
    )


class KnowledgeRevision(Base):
    __tablename__ = "knowledge_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[KnowledgeRevisionStatus] = mapped_column(
        pg_enum(KnowledgeRevisionStatus, "knowledgerevisionstatus"),
        default=KnowledgeRevisionStatus.DRAFT,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    markdown_content: Mapped[str] = mapped_column(Text, default="")
    outline: Mapped[list[dict]] = mapped_column(JSON, default=list)
    ai_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    submitted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped["KnowledgeDocument"] = relationship(
        back_populates="revisions",
        foreign_keys=[document_id],
    )
    source_links: Mapped[list["KnowledgeSourceLink"]] = relationship(
        back_populates="revision", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_knowledge_revisions_document_version", "document_id", "version_no", unique=True),
    )


class KnowledgeSourceLink(Base):
    __tablename__ = "knowledge_source_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("knowledge_revisions.id"), index=True)
    source_kind: Mapped[str] = mapped_column(String(40), default="material")
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id"), nullable=True, index=True)
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_materials.id"), nullable=True, index=True
    )
    chunk_id: Mapped[int | None] = mapped_column(ForeignKey("chunks.id"), nullable=True, index=True)
    similarity: Mapped[float | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    revision: Mapped["KnowledgeRevision"] = relationship(back_populates="source_links")


class KnowledgeConflict(Base):
    __tablename__ = "knowledge_conflicts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id"), index=True)
    draft_revision_id: Mapped[int] = mapped_column(ForeignKey("knowledge_revisions.id"), index=True)
    published_revision_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_revisions.id"), nullable=True, index=True
    )
    conflict_type: Mapped[KnowledgeConflictType] = mapped_column(
        pg_enum(KnowledgeConflictType, "knowledgeconflicttype"),
        default=KnowledgeConflictType.CONTENT_CONFLICT,
    )
    status: Mapped[KnowledgeConflictStatus] = mapped_column(
        pg_enum(KnowledgeConflictStatus, "knowledgeconflictstatus"),
        default=KnowledgeConflictStatus.OPEN,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    existing_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    incoming_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_kind: Mapped[str | None] = mapped_column(String(40), nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

