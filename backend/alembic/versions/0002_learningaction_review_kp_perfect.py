"""add learningaction review_kp_perfect

Revision ID: 0002_review_kp
Revises: 0001_initial
Create Date: 2026-04-21

PostgreSQL: extend enum learningaction for 薄弱知识点自测全对记录。
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_review_kp"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE learningaction ADD VALUE IF NOT EXISTS 'review_kp_perfect'")


def downgrade() -> None:
    # PostgreSQL 不支持安全删除枚举值，降级留空
    pass
