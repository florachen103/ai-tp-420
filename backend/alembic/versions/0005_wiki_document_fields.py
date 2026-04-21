"""add wiki fields to knowledge documents

Revision ID: 0005_wiki_document_fields
Revises: 0004_knowledge_assets
Create Date: 2026-04-21 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_wiki_document_fields"
down_revision: str | None = "0004_knowledge_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents",
        sa.Column("path_slug", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("parent_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("is_redirect", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("redirect_document_id", sa.Integer(), nullable=True),
    )

    op.execute("UPDATE knowledge_documents SET path_slug = slug WHERE path_slug IS NULL")
    op.alter_column("knowledge_documents", "path_slug", nullable=False)

    op.create_index(
        "ix_knowledge_documents_space_path_slug",
        "knowledge_documents",
        ["space_id", "path_slug"],
        unique=True,
    )
    op.create_index("ix_knowledge_documents_parent_id", "knowledge_documents", ["parent_id"])
    op.create_index(
        "ix_knowledge_documents_redirect_document_id",
        "knowledge_documents",
        ["redirect_document_id"],
    )
    op.create_index("ix_knowledge_documents_is_redirect", "knowledge_documents", ["is_redirect"])

    op.create_foreign_key(
        "fk_knowledge_documents_parent_id",
        "knowledge_documents",
        "knowledge_documents",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_knowledge_documents_redirect_document_id",
        "knowledge_documents",
        "knowledge_documents",
        ["redirect_document_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_knowledge_documents_redirect_document_id", "knowledge_documents", type_="foreignkey")
    op.drop_constraint("fk_knowledge_documents_parent_id", "knowledge_documents", type_="foreignkey")
    op.drop_index("ix_knowledge_documents_is_redirect", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_redirect_document_id", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_parent_id", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_space_path_slug", table_name="knowledge_documents")
    op.drop_column("knowledge_documents", "redirect_document_id")
    op.drop_column("knowledge_documents", "is_redirect")
    op.drop_column("knowledge_documents", "parent_id")
    op.drop_column("knowledge_documents", "path_slug")
