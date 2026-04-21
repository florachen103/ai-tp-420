"""add answer_feedbacks table

Revision ID: 0003_answer_feedback
Revises: 0002_review_kp
Create Date: 2026-04-21

新增表 `answer_feedbacks`：承接 RAG 答案满意度回路（好评 / 差评 + 可选评语 + 快照）。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_answer_feedback"
down_revision: Union[str, None] = "0002_review_kp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "answer_feedbacks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("answer_id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=True),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_answer_feedbacks_answer_id", "answer_feedbacks", ["answer_id"])
    op.create_index("ix_answer_feedbacks_user_id", "answer_feedbacks", ["user_id"])
    op.create_index("ix_answer_feedbacks_course_id", "answer_feedbacks", ["course_id"])
    op.create_index("ix_answer_feedbacks_rating", "answer_feedbacks", ["rating"])
    op.create_index("ix_answer_feedbacks_created_at", "answer_feedbacks", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_answer_feedbacks_created_at", table_name="answer_feedbacks")
    op.drop_index("ix_answer_feedbacks_rating", table_name="answer_feedbacks")
    op.drop_index("ix_answer_feedbacks_course_id", table_name="answer_feedbacks")
    op.drop_index("ix_answer_feedbacks_user_id", table_name="answer_feedbacks")
    op.drop_index("ix_answer_feedbacks_answer_id", table_name="answer_feedbacks")
    op.drop_table("answer_feedbacks")
