"""add knowledge asset domain

Revision ID: 0004_knowledge_assets
Revises: 0003_answer_feedback
Create Date: 2026-04-21

知识资产中台：
  - 新增知识空间 / 知识页 / 版本 / 溯源 / 冲突表
  - 用户角色扩展 editor / reviewer / publisher
  - Chunk 增加知识来源与可见性字段，已发布知识页可直接复用现有 pgvector 检索链路
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_knowledge_assets"
down_revision: Union[str, None] = "0003_answer_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # userrole 扩容：知识中台的专业角色
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'editor'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'reviewer'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'publisher'")

    knowledge_space_status = postgresql.ENUM(
        "active", "archived", name="knowledgespacestatus", create_type=False
    )
    knowledge_document_status = postgresql.ENUM(
        "draft", "in_review", "published", "archived", name="knowledgedocumentstatus"
    )
    knowledge_document_status.create_type = False
    knowledge_revision_status = postgresql.ENUM(
        "draft", "in_review", "approved", "rejected", "published", "archived", name="knowledgerevisionstatus"
    )
    knowledge_revision_status.create_type = False
    knowledge_conflict_type = postgresql.ENUM(
        "title_duplicate", "content_conflict", "policy_conflict", "manual",
        name="knowledgeconflicttype",
    )
    knowledge_conflict_type.create_type = False
    knowledge_conflict_status = postgresql.ENUM(
        "open", "resolved", "ignored", name="knowledgeconflictstatus"
    )
    knowledge_conflict_status.create_type = False
    chunk_source_type = postgresql.ENUM(
        "course_material", "knowledge_revision", name="chunksourcetype"
    )
    chunk_source_type.create_type = False
    chunk_visibility = postgresql.ENUM("draft", "published", name="chunkvisibility", create_type=False)

    knowledge_space_status.create(op.get_bind(), checkfirst=True)
    knowledge_document_status.create(op.get_bind(), checkfirst=True)
    knowledge_revision_status.create(op.get_bind(), checkfirst=True)
    knowledge_conflict_type.create(op.get_bind(), checkfirst=True)
    knowledge_conflict_status.create(op.get_bind(), checkfirst=True)
    chunk_source_type.create(op.get_bind(), checkfirst=True)
    chunk_visibility.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "knowledge_spaces",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", knowledge_space_status, nullable=False, server_default="active"),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_spaces_name", "knowledge_spaces", ["name"])
    op.create_index("ix_knowledge_spaces_slug", "knowledge_spaces", ["slug"], unique=True)
    op.create_index("ix_knowledge_spaces_category", "knowledge_spaces", ["category"])
    op.create_index("ix_knowledge_spaces_status", "knowledge_spaces", ["status"])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("space_id", sa.Integer(), sa.ForeignKey("knowledge_spaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", knowledge_document_status, nullable=False, server_default="draft"),
        sa.Column("current_revision_id", sa.Integer(), nullable=True),
        sa.Column("published_revision_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_editor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("assigned_reviewer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("assigned_publisher_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source_course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=True),
        sa.Column("source_material_id", sa.Integer(), sa.ForeignKey("course_materials.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_documents_space_id", "knowledge_documents", ["space_id"])
    op.create_index("ix_knowledge_documents_title", "knowledge_documents", ["title"])
    op.create_index("ix_knowledge_documents_slug", "knowledge_documents", ["slug"])
    op.create_index("ix_knowledge_documents_category", "knowledge_documents", ["category"])
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])
    op.create_index(
        "ix_knowledge_documents_space_title",
        "knowledge_documents",
        ["space_id", "title"],
    )

    op.create_table(
        "knowledge_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", knowledge_revision_status, nullable=False, server_default="draft"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("markdown_content", sa.Text(), nullable=False, server_default=""),
        sa.Column("outline", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("ai_meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("published_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_revisions_document_id", "knowledge_revisions", ["document_id"])
    op.create_index("ix_knowledge_revisions_status", "knowledge_revisions", ["status"])
    op.create_index(
        "ix_knowledge_revisions_document_version",
        "knowledge_revisions",
        ["document_id", "version_no"],
        unique=True,
    )

    op.create_foreign_key(
        "fk_knowledge_documents_current_revision_id",
        "knowledge_documents",
        "knowledge_revisions",
        ["current_revision_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_knowledge_documents_published_revision_id",
        "knowledge_documents",
        "knowledge_revisions",
        ["published_revision_id"],
        ["id"],
    )

    op.create_table(
        "knowledge_source_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision_id", sa.Integer(), sa.ForeignKey("knowledge_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_kind", sa.String(length=40), nullable=False, server_default="material"),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=True),
        sa.Column("material_id", sa.Integer(), sa.ForeignKey("course_materials.id"), nullable=True),
        sa.Column("chunk_id", sa.Integer(), sa.ForeignKey("chunks.id"), nullable=True),
        sa.Column("similarity", sa.Float(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_source_links_document_id", "knowledge_source_links", ["document_id"])
    op.create_index("ix_knowledge_source_links_revision_id", "knowledge_source_links", ["revision_id"])
    op.create_index("ix_knowledge_source_links_course_id", "knowledge_source_links", ["course_id"])
    op.create_index("ix_knowledge_source_links_material_id", "knowledge_source_links", ["material_id"])
    op.create_index("ix_knowledge_source_links_chunk_id", "knowledge_source_links", ["chunk_id"])

    op.create_table(
        "knowledge_conflicts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("draft_revision_id", sa.Integer(), sa.ForeignKey("knowledge_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("published_revision_id", sa.Integer(), sa.ForeignKey("knowledge_revisions.id"), nullable=True),
        sa.Column("conflict_type", knowledge_conflict_type, nullable=False, server_default="content_conflict"),
        sa.Column("status", knowledge_conflict_status, nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("existing_excerpt", sa.Text(), nullable=True),
        sa.Column("incoming_excerpt", sa.Text(), nullable=True),
        sa.Column("resolution_kind", sa.String(length=40), nullable=True),
        sa.Column("resolved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_conflicts_document_id", "knowledge_conflicts", ["document_id"])
    op.create_index("ix_knowledge_conflicts_draft_revision_id", "knowledge_conflicts", ["draft_revision_id"])
    op.create_index("ix_knowledge_conflicts_published_revision_id", "knowledge_conflicts", ["published_revision_id"])
    op.create_index("ix_knowledge_conflicts_status", "knowledge_conflicts", ["status"])

    op.add_column("courses", sa.Column("knowledge_space_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_courses_knowledge_space_id",
        "courses",
        "knowledge_spaces",
        ["knowledge_space_id"],
        ["id"],
    )
    op.create_index("ix_courses_knowledge_space_id", "courses", ["knowledge_space_id"])

    op.alter_column("chunks", "course_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("chunks", "material_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("chunks", sa.Column("knowledge_space_id", sa.Integer(), nullable=True))
    op.add_column("chunks", sa.Column("knowledge_document_id", sa.Integer(), nullable=True))
    op.add_column("chunks", sa.Column("knowledge_revision_id", sa.Integer(), nullable=True))
    op.add_column(
        "chunks",
        sa.Column("source_type", chunk_source_type, nullable=False, server_default="course_material"),
    )
    op.add_column(
        "chunks",
        sa.Column("visibility", chunk_visibility, nullable=False, server_default="published"),
    )
    op.create_foreign_key(
        "fk_chunks_knowledge_space_id",
        "chunks",
        "knowledge_spaces",
        ["knowledge_space_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_chunks_knowledge_document_id",
        "chunks",
        "knowledge_documents",
        ["knowledge_document_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_chunks_knowledge_revision_id",
        "chunks",
        "knowledge_revisions",
        ["knowledge_revision_id"],
        ["id"],
    )
    op.create_index("ix_chunks_knowledge_space_id", "chunks", ["knowledge_space_id"])
    op.create_index("ix_chunks_knowledge_document_id", "chunks", ["knowledge_document_id"])
    op.create_index("ix_chunks_knowledge_revision_id", "chunks", ["knowledge_revision_id"])
    op.create_index("ix_chunks_source_type", "chunks", ["source_type"])
    op.create_index("ix_chunks_visibility", "chunks", ["visibility"])


def downgrade() -> None:
    op.drop_index("ix_chunks_visibility", table_name="chunks")
    op.drop_index("ix_chunks_source_type", table_name="chunks")
    op.drop_index("ix_chunks_knowledge_revision_id", table_name="chunks")
    op.drop_index("ix_chunks_knowledge_document_id", table_name="chunks")
    op.drop_index("ix_chunks_knowledge_space_id", table_name="chunks")
    op.drop_constraint("fk_chunks_knowledge_revision_id", "chunks", type_="foreignkey")
    op.drop_constraint("fk_chunks_knowledge_document_id", "chunks", type_="foreignkey")
    op.drop_constraint("fk_chunks_knowledge_space_id", "chunks", type_="foreignkey")
    op.drop_column("chunks", "visibility")
    op.drop_column("chunks", "source_type")
    op.drop_column("chunks", "knowledge_revision_id")
    op.drop_column("chunks", "knowledge_document_id")
    op.drop_column("chunks", "knowledge_space_id")

    op.drop_index("ix_courses_knowledge_space_id", table_name="courses")
    op.drop_constraint("fk_courses_knowledge_space_id", "courses", type_="foreignkey")
    op.drop_column("courses", "knowledge_space_id")

    op.drop_index("ix_knowledge_conflicts_status", table_name="knowledge_conflicts")
    op.drop_index("ix_knowledge_conflicts_published_revision_id", table_name="knowledge_conflicts")
    op.drop_index("ix_knowledge_conflicts_draft_revision_id", table_name="knowledge_conflicts")
    op.drop_index("ix_knowledge_conflicts_document_id", table_name="knowledge_conflicts")
    op.drop_table("knowledge_conflicts")

    op.drop_index("ix_knowledge_source_links_chunk_id", table_name="knowledge_source_links")
    op.drop_index("ix_knowledge_source_links_material_id", table_name="knowledge_source_links")
    op.drop_index("ix_knowledge_source_links_course_id", table_name="knowledge_source_links")
    op.drop_index("ix_knowledge_source_links_revision_id", table_name="knowledge_source_links")
    op.drop_index("ix_knowledge_source_links_document_id", table_name="knowledge_source_links")
    op.drop_table("knowledge_source_links")

    op.drop_constraint("fk_knowledge_documents_published_revision_id", "knowledge_documents", type_="foreignkey")
    op.drop_constraint("fk_knowledge_documents_current_revision_id", "knowledge_documents", type_="foreignkey")
    op.drop_index("ix_knowledge_revisions_document_version", table_name="knowledge_revisions")
    op.drop_index("ix_knowledge_revisions_status", table_name="knowledge_revisions")
    op.drop_index("ix_knowledge_revisions_document_id", table_name="knowledge_revisions")
    op.drop_table("knowledge_revisions")

    op.drop_index("ix_knowledge_documents_space_title", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_status", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_category", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_slug", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_title", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_space_id", table_name="knowledge_documents")
    op.drop_table("knowledge_documents")

    op.drop_index("ix_knowledge_spaces_status", table_name="knowledge_spaces")
    op.drop_index("ix_knowledge_spaces_category", table_name="knowledge_spaces")
    op.drop_index("ix_knowledge_spaces_slug", table_name="knowledge_spaces")
    op.drop_index("ix_knowledge_spaces_name", table_name="knowledge_spaces")
    op.drop_table("knowledge_spaces")

    for enum_name in (
        "chunkvisibility",
        "chunksourcetype",
        "knowledgeconflictstatus",
        "knowledgeconflicttype",
        "knowledgerevisionstatus",
        "knowledgedocumentstatus",
        "knowledgespacestatus",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
