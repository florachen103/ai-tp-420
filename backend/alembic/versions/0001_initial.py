"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-20 19:30:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from app.core.config import settings

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    user_role = sa.Enum("admin", "manager", "learner", name="userrole")
    course_status = sa.Enum("draft", "processing", "ready", "archived", name="coursestatus")
    material_type = sa.Enum(
        "word", "pdf", "ppt", "excel", "video", "audio", "markdown", "other",
        name="materialtype",
    )
    q_type = sa.Enum("single", "multiple", "judge", "fill", "short", name="questiontype")
    q_diff = sa.Enum("easy", "medium", "hard", name="questiondifficulty")
    exam_status = sa.Enum("in_progress", "submitted", "graded", "expired", name="examstatus")
    learning_action = sa.Enum(
        "view_course", "read_chunk", "ask_question", "complete_chapter",
        "start_exam", "submit_exam", "practice",
        name="learningaction",
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="learner"),
        sa.Column("department", sa.String(100)),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "courses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("cover_url", sa.String(500)),
        sa.Column("category", sa.String(100)),
        sa.Column("tags", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("status", course_status, nullable=False, server_default="draft"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_courses_title", "courses", ["title"])
    op.create_index("ix_courses_category", "courses", ["category"])
    op.create_index("ix_courses_status", "courses", ["status"])

    op.create_table(
        "course_materials",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("material_type", material_type, nullable=False),
        sa.Column("storage_key", sa.String(1000), nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("parse_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("parse_error", sa.Text),
        sa.Column("meta", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_course_materials_course_id", "course_materials", ["course_id"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_id", sa.Integer, sa.ForeignKey("course_materials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter", sa.String(255)),
        sa.Column("order_idx", sa.Integer, nullable=False, server_default="0"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("embedding", Vector(settings.EMBEDDING_DIM)),
        sa.Column("meta", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_chunks_course_id", "chunks", ["course_id"])
    op.create_index("ix_chunks_material_id", "chunks", ["material_id"])
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.Integer, sa.ForeignKey("chunks.id", ondelete="SET NULL")),
        sa.Column("type", q_type, nullable=False),
        sa.Column("difficulty", q_diff, nullable=False, server_default="medium"),
        sa.Column("stem", sa.Text, nullable=False),
        sa.Column("options", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("answer", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("explanation", sa.Text),
        sa.Column("knowledge_points", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("source", sa.String(30), nullable=False, server_default="ai"),
        sa.Column("reviewed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_questions_course_id", "questions", ["course_id"])
    op.create_index("ix_questions_type", "questions", ["type"])
    op.create_index("ix_questions_difficulty", "questions", ["difficulty"])

    op.create_table(
        "exams",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("duration_minutes", sa.Integer, nullable=False, server_default="30"),
        sa.Column("pass_score", sa.Float, nullable=False, server_default="60.0"),
        sa.Column("rules", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("shuffle_questions", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("shuffle_options", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_exams_course_id", "exams", ["course_id"])

    op.create_table(
        "exam_attempts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("exam_id", sa.Integer, sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("status", exam_status, nullable=False, server_default="in_progress"),
        sa.Column("score", sa.Float),
        sa.Column("max_score", sa.Float, nullable=False, server_default="100.0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("graded_at", sa.DateTime(timezone=True)),
        sa.Column("proctor_events", sa.JSON, nullable=False, server_default="[]"),
    )
    op.create_index("ix_exam_attempts_exam_id", "exam_attempts", ["exam_id"])
    op.create_index("ix_exam_attempts_user_id", "exam_attempts", ["user_id"])
    op.create_index("ix_exam_attempts_status", "exam_attempts", ["status"])

    op.create_table(
        "exam_answers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("attempt_id", sa.Integer, sa.ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer, sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("answer", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("is_correct", sa.Boolean),
        sa.Column("score", sa.Float, nullable=False, server_default="0"),
        sa.Column("ai_feedback", sa.Text),
        sa.Column("time_spent_sec", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index("ix_exam_answers_attempt_id", "exam_answers", ["attempt_id"])
    op.create_index("ix_exam_answers_question_id", "exam_answers", ["question_id"])

    op.create_table(
        "learning_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("course_id", sa.Integer, sa.ForeignKey("courses.id", ondelete="SET NULL")),
        sa.Column("action", learning_action, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("duration_sec", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_learning_records_user_id", "learning_records", ["user_id"])
    op.create_index("ix_learning_records_course_id", "learning_records", ["course_id"])
    op.create_index("ix_learning_records_action", "learning_records", ["action"])
    op.create_index("ix_learning_records_created_at", "learning_records", ["created_at"])


def downgrade() -> None:
    op.drop_table("learning_records")
    op.drop_table("exam_answers")
    op.drop_table("exam_attempts")
    op.drop_table("exams")
    op.drop_table("questions")
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.drop_table("chunks")
    op.drop_table("course_materials")
    op.drop_table("courses")
    op.drop_table("users")
    for enum_name in (
        "learningaction", "examstatus", "questiondifficulty", "questiontype",
        "materialtype", "coursestatus", "userrole",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
