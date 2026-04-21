from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.knowledge import (
    KnowledgeConflictStatus,
    KnowledgeConflictType,
    KnowledgeDocumentStatus,
    KnowledgeRevisionStatus,
    KnowledgeSpaceStatus,
)


class KnowledgeSpaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)


class KnowledgeSpaceUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    status: KnowledgeSpaceStatus | None = None


class KnowledgeSpaceOut(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: KnowledgeSpaceStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeDocumentOut(BaseModel):
    id: int
    space_id: int
    title: str
    slug: str
    path_slug: str
    parent_id: int | None = None
    is_redirect: bool = False
    redirect_document_id: int | None = None
    summary: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: KnowledgeDocumentStatus
    current_revision_id: int | None = None
    published_revision_id: int | None = None
    assigned_editor_id: int | None = None
    assigned_reviewer_id: int | None = None
    assigned_publisher_id: int | None = None
    source_course_id: int | None = None
    source_material_id: int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class KnowledgeDocumentCreate(BaseModel):
    space_id: int
    title: str = Field(min_length=1, max_length=255)
    path_slug: str | None = Field(default=None, max_length=255)
    parent_id: int | None = None
    is_redirect: bool = False
    redirect_document_id: int | None = None
    summary: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    markdown_content: str = ""


class KnowledgeRevisionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    markdown_content: str | None = None
    outline: list[dict] | None = None
    change_note: str | None = None


class KnowledgeDocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    path_slug: str | None = Field(default=None, max_length=255)
    parent_id: int | None = None
    is_redirect: bool | None = None
    redirect_document_id: int | None = None
    summary: str | None = None
    category: str | None = None
    tags: list[str] | None = None


class KnowledgeReviewAction(BaseModel):
    comment: str | None = None


class KnowledgePublishAction(BaseModel):
    change_note: str | None = None


class KnowledgeConflictResolveIn(BaseModel):
    resolution_kind: Literal["keep_existing", "use_incoming", "merged", "ignored"]
    comment: str | None = None


class KnowledgeRevisionOut(BaseModel):
    id: int
    document_id: int
    version_no: int
    status: KnowledgeRevisionStatus
    title: str
    summary: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    markdown_content: str
    outline: list[dict] = Field(default_factory=list)
    ai_meta: dict = Field(default_factory=dict)
    change_note: str | None = None
    review_comment: str | None = None
    created_by: int
    submitted_by: int | None = None
    reviewed_by: int | None = None
    published_by: int | None = None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None = None
    reviewed_at: datetime | None = None
    published_at: datetime | None = None

    class Config:
        from_attributes = True


class KnowledgeSourceLinkOut(BaseModel):
    id: int
    document_id: int
    revision_id: int
    source_kind: str
    course_id: int | None = None
    material_id: int | None = None
    chunk_id: int | None = None
    similarity: float | None = None
    note: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeConflictOut(BaseModel):
    id: int
    document_id: int
    draft_revision_id: int
    published_revision_id: int | None = None
    conflict_type: KnowledgeConflictType
    status: KnowledgeConflictStatus
    title: str
    detail: str | None = None
    existing_excerpt: str | None = None
    incoming_excerpt: str | None = None
    resolution_kind: str | None = None
    resolved_by: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeDocumentDetail(KnowledgeDocumentOut):
    current_revision: KnowledgeRevisionOut | None = None
    published_revision: KnowledgeRevisionOut | None = None
    revisions: list[KnowledgeRevisionOut] = Field(default_factory=list)
    conflicts: list[KnowledgeConflictOut] = Field(default_factory=list)
    sources: list[KnowledgeSourceLinkOut] = Field(default_factory=list)


class KnowledgeAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    response_style: Literal["micro", "standard", "deep"] = "micro"
    rewrite: bool = True
    rerank: bool = False


class KnowledgeTreeNode(BaseModel):
    id: int
    title: str
    path_slug: str
    parent_id: int | None = None
    is_redirect: bool = False
    status: KnowledgeDocumentStatus

